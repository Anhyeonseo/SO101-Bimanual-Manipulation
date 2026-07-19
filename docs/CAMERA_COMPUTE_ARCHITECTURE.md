# Raspberry Pi 카메라·연산 아키텍처

상태: `제안`. 실제 UVC 영상 형식과 Raspberry Pi 성능을 측정한 뒤 수치를 확정한다.

## 1. 설계 목표

Raspberry Pi 5 4GB에서 다음 작업을 동시에 수행하되 제어와 안전 처리가 영상 연산 부하에 밀리지 않게 한다.

- USB RGB 카메라 3대 연결
- 필요한 카메라 영상만 압축 해제(decode)하고 추론(inference) 수행
- MoveIt은 작업 상태가 바뀔 때만 경로 계획 수행
- 구조화 상태(structured-state) policy는 작은 모델로 제한
- STM32 heartbeat와 ROS 안전 상태는 영상 처리와 독립
- 원본 이미지는 영상 처리 process 밖으로 계속 publish하지 않음

핵심 원칙은 "카메라 3대를 연결했다고 해서 3대 영상을 항상 모두 추론하지 않는다"는 것이다.

## 2. 카메라별 역할

### Top 카메라 — 전체 상태 관측

주요 역할:

- 작업대와 전체 작업 영역 관측
- 검은색 마커펜 탐색과 후보 선택
- 펜의 평면 `x, y, yaw` 추정
- 펜꽂이 위치와 입구 영역 추정
- 사용할 팔(active arm)을 고르는 데 필요한 전역 좌표 제공
- grasp 후 물체가 원래 위치에서 사라졌는지 확인
- place 후 펜이 목표 영역에 들어갔는지 확인
- 양팔의 개별·공유 작업 영역을 전체적으로 관측

적용 기술:

- 카메라 내부 보정(intrinsic calibration)
- 카메라와 base 사이의 고정된 외부 보정값(extrinsic)
- 작업대 homography를 이용한 pixel→작업대 좌표 변환
- 초기에는 검은 물체의 밝기 기준 분리, 윤곽선과 PCA를 이용해 yaw 계산
- 이후 Nano급 YOLO 또는 작은 특징점 검출기(keypoint detector) 사용
- 촬영 시각, frame이 지난 시간과 검출 신뢰도를 이용해 데이터 최신성 검사

상단 RGB 카메라 한 대만으로 일반적인 3차원 자세를 복원할 수 있다고 가정하지 않는다. 초기 Z 좌표는 작업대와 물체 모델에서 이미 알고 있는 높이로 제한한다.

### Right wrist 카메라 — 오른팔 근접 정렬

주요 역할:

- pre-grasp 이후 그리퍼와 펜의 상대 오차 계산
- 마지막 수 cm 구간에서 중심과 yaw 오차 보정
- gripper를 닫기 직전에 물체가 있는지 확인
- 들어 올린 뒤 물체가 gripper와 함께 움직이는지 확인
- 펜꽂이 접근 시 입구 중심과 삽입 방향 미세 보정

적용 기술:

- 카메라 내부 보정(intrinsic calibration)
- eye-in-hand calibration으로 `right_tool0 → right_wrist_camera` 고정 transform 추정
- 필요한 영역만 자른 영상(ROI)과 작은 특징 검출기 사용
- 영상 기반 Visual Servo 또는 크기가 제한된 Cartesian 좌표 보정
- frame이 오래됐거나 신뢰도가 낮거나 timeout이 발생하면 즉시 중단

카메라는 세계 좌표에서 움직이지만 로봇팔 말단 장치(end-effector)와 카메라 사이의 보정값은 고정이다. TF가 매 순간 카메라 자세를 계산한다.

### Left wrist 카메라 — 왼팔 근접 정렬

오른팔 카메라와 같은 역할을 하지만 초기 오른팔 최소 기능 제품(MVP)에서는 추론을 수행하지 않는다.

- 초기: 장치 연결과 데이터 최신성만 낮은 주기로 확인
- 왼팔 단독 기준 통과 후: 왼팔 영상 정렬
- 양팔 개별 작업: 현재 작업 단계에 따라 좌우 손목 영상을 교대로 추론
- 수건 작업: 양쪽 grasp 지점과 수건 가장자리 확인

## 3. 카메라 보정(Calibration) 방법

체크보드 또는 ChArUco는 개발 중 카메라 보정에만 사용하고 시연 작업대에서는 제거한다.

| 카메라 | 내부 보정 | 외부 보정 |
|---|---|---|
| 상단 | 카메라별 보정 | eye-to-hand, base 기준 고정 |
| 왼쪽 손목 | 카메라별 보정 | eye-in-hand, 왼팔 tool 기준 고정 |
| 오른쪽 손목 | 카메라별 보정 | eye-in-hand, 오른팔 tool 기준 고정 |

보정 결과는 `camera_info` YAML과 transform YAML로 버전 관리한다. 해상도, 초점 또는 카메라 mount가 바뀌면 기존 보정값을 재사용하지 않는다.

## 4. 영상 처리 process 구조

```text
Top V4L2 Capture Thread ─────────┐
Left Wrist V4L2 Capture Thread ─┼→ compressed latest-frame slots
Right Wrist V4L2 Capture Thread ┘            ↓
                                      Phase Scheduler
                                             ↓
                              decode/resize only selected frame
                                             ↓
                               single vision inference lane
                                             ↓
                         detection/pose/confidence/timestamp only
                                             ↓
                                      ROS structured output
```

권장 구현:

- C++17
- V4L2 mmap을 우선 사용하고, 측정 결과에 따라 GStreamer로 대체
- UVC MJPEG 우선, `640×480 @ 15FPS` 시작
- 카메라별로 압축된 최신 frame 한 장만 유지
- 현재 사용하는 카메라 영상만 libjpeg-turbo/OpenCV로 decode
- inference input `320×320`부터 시작
- queue 크기는 1로 두고 오래된 frame 폐기
- debug image는 요청이 있을 때만 보내거나 1FPS 이하로 제한
- 원본 영상을 process 사이에서 DDS로 보내거나 rosbag으로 계속 기록하지 않음

카메라가 MJPEG를 지원하지 않거나 decode 비용이 더 큰 경우 `v4l2-ctl` 결과와 성능 측정값을 보고 YUYV를 선택한다.

## 5. 추론 구조

### 영상 추론(inference)

- 동시에 실행하는 고부하 추론 작업: 1개
- ONNX Runtime 실행 방식: 순차 실행(sequential)부터 시작
- `intra_op_num_threads`: 2부터 측정
- `inter_op_num_threads`: 1
- 상단/손목 영상에 같은 검출기를 사용할 수 있으면 ONNX session 1개 공유
- 서로 다른 모델이 필요해도 동시에 실행하지 않고 scheduler가 차례로 실행
- INT8은 FP32 기준 모델의 정확도와 지연 시간을 측정한 뒤 적용

### Policy 추론

정책은 원본 카메라 3장을 입력받지 않는다.

입력 예:

```text
object x/y/yaw
target x/y
left/right end-effector pose
joint positions/velocities
gripper state
task phase
detection confidence
active arm
```

출력은 크기가 제한된 Cartesian 좌표 변화량, 사용할 팔 선택, grasp 판단 또는 보정값으로 제한한다.

- 별도 `policy_runtime` process
- 작은 구조화 상태 ONNX session
- 초기 rate 10Hz
- `intra_op_num_threads = 1`
- 입력 queue depth 1
- 구조화 상태 정보가 오래됐으면 결과 폐기
- 서보 raw 위치를 직접 출력하지 않음
- 재현 가능한 기준 동작을 완성한 뒤에만 실제 명령 경로 활성화

Policy와 영상 추론을 동시에 실행할 수는 있지만, 영상 처리 thread 2개와 policy thread 1개를 초기 상한으로 둔다. 이렇게 해서 제어와 운영체제에 최소 한 코어 정도의 여유를 남긴다. 실제 CPU core 고정(affinity)은 성능 측정 전에 적용하지 않는다.

## 6. 작업 상태별 연산 일정

아래 수치는 초기 연산 자원 한도이며 `config/camera_schedule.json`이 전체 영상 추론 속도를 12Hz 이하로 검증한다.

| 작업 상태 | 상단 추론 | 왼쪽 손목 | 오른쪽 손목 | Policy | 목적 |
|---|---:|---:|---:|---:|---|
| STANDBY | 1Hz | 0 | 0 | OFF | 장치·작업대 저주기 감시 |
| SEARCH | 8Hz | 0 | 0 | OFF | 펜 탐색 |
| APPROACH_RIGHT | 4Hz | 0 | 6Hz | OFF | 전역+근접 전환 |
| VISUAL_ALIGN_RIGHT | 1Hz | 0 | 10Hz | OFF | 오른팔 마지막 정렬 |
| TRANSFER_RIGHT | 2Hz | 0 | 1Hz | OFF | 운반 상태 확인 |
| VERIFY_RIGHT | 4Hz | 0 | 4Hz | OFF | grasp/place 결과 확인 |
| DUAL_PRIVATE | 4Hz | 4Hz | 4Hz | OFF | 양팔 영상을 번갈아 처리 |
| POLICY_ASSIST | 4Hz | 0 | 6Hz | 10Hz | 구조화 상태 보정값 평가 |

Policy 학습 단계 전까지 policy는 끈다. Visual Servo 중에는 정해진 보정 계산을 우선하며 policy를 동시에 명령 입력으로 사용하지 않는다.

## 7. 실행 우선순위

부하가 높을 때 기능을 줄이는 순서:

1. debug image 전송과 영상 기록 중단
2. 사용하지 않는 손목 영상의 decode와 추론 중단
3. 상단 또는 현재 사용하는 손목 영상의 추론 속도 감소
4. policy를 10Hz에서 5Hz로 낮추거나 일시 중단
5. 검출기 입력 크기 또는 모델 축소

절대로 자동으로 줄이지 않는 항목:

- STM32 heartbeat
- serial RX/TX와 관절 상태값
- 안전 및 fault 처리
- 명령 유효성 검사
- 카메라와 인식 결과의 최신성 검사

Policy 또는 인식 결과가 정해진 처리 시간을 넘기면 오래된 결과로 계속 움직이지 않고 Hold하거나 다시 탐색한다.

## 8. Pi 자원 사용 목표

초기 합격 기준:

| 지표 | 목표 |
|---|---|
| 전체 CPU 지속 평균 | 70% 이하 목표, 최대 75% 상한 검토 |
| 10초 평균 최댓값 | 90% 미만 |
| 메모리 사용 | 3.0GB 이하 |
| 사용 가능한 memory | 700MB 이상 목표 |
| swap-in/swap-out | 0 |
| 온도로 인한 성능 제한 | 0회 |
| 온도 | 80°C 미만 목표 |
| 카메라 queue | 카메라별 최신 frame 1장 |
| vision 부하 중 heartbeat 위반 | 0회 |
| memory 또는 queue가 계속 증가하는 현상 | 0 |

수치는 30분 부하 시험 후 조정하고 8시간 장시간 시험에서 다시 검증한다.

## 9. USB 배치 원칙

- STM32 ST-LINK VCP는 카메라 hub와 가능한 한 다른 Raspberry Pi 물리 포트에 연결
- 세 카메라는 전원 공급형 hub를 우선 사용하되 `lsusb -t`로 실제 USB 연결 구조 기록
- 1080p를 사용하지 않고 640×480부터 시작
- 세 카메라의 하드웨어 동기화를 가정하지 않음
- frame을 꺼낸 시각을 촬영 시각으로 기록하고 여러 카메라 결과의 최대 시각 차이 검사
- 장치 serial이 없으면 USB 물리 경로와 카메라 식별 자체 시험을 함께 사용

## 10. Process 분리

| Process | 역할 | 영상 처리 장애의 영향 |
|---|---|---|
| `vision_pipeline` | 영상 수집, decode, 검출, 자세 계산 | 재시작 가능 |
| `policy_runtime` | 구조화 상태 policy | 실패 시 정해진 기준 동작 사용 |
| `move_group` | 경로 계획과 충돌 검사 | 작업 상태 전환이 늦어질 수 있음 |
| `robot_core` | 상태, 작업, 명령 중재 | 오래된 입력 거부 |
| `control_bridge` | ros2_control, STM32 VCP | 영상 처리와 독립 유지 |
| `safety_supervisor` | 최신성, fault, process 상태 확인 | 영상 처리 실패 시 Hold 요청 |

영상 처리 process가 종료되거나 CPU를 많이 사용해도 STM32 heartbeat와 안전 정지가 같은 process 또는 thread에 묶이지 않게 한다.

## 11. 단계별 확인 방법

1. 카메라 3대의 영상 수집만 실행
2. decode 없이 압축된 최신 frame buffer 검증
3. 카메라별 decode 지연 시간 측정
4. 임시 추론 부하 추가
5. 실제 검출기 추가
6. 구조화 상태 policy의 임시 연산 부하 추가
7. MoveIt 경로 계획을 짧은 시간에 반복하며 동시 부하 확인
8. STM32 heartbeat와 serial 왕복 시간 확인
9. 30분 부하 시험
10. 8시간 장시간 시험

각 단계에서 frame이 지난 시간, decode 및 추론 시간의 p50/p95/최댓값, CPU, memory, 온도, USB reset 횟수와 heartbeat 최대 간격을 기록한다.
