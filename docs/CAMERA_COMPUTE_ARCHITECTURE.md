# Raspberry Pi Camera and Compute Architecture

상태: `PROPOSED`. 실제 UVC 포맷과 Pi benchmark 후 수치를 확정한다.

## 1. 설계 목표

Raspberry Pi 5 4GB에서 다음 작업을 동시에 수행하되 control과 safety가 vision 부하에 밀리지 않게 한다.

- USB RGB 카메라 3대 연결
- 필요한 view만 decode/inference
- MoveIt은 task transition에서만 planning
- structured-state policy는 작은 모델로 제한
- STM32 heartbeat와 ROS safety 상태는 vision과 독립
- 원본 이미지는 vision process 밖으로 상시 publish하지 않음

핵심 원칙은 `3 cameras connected ≠ 3 cameras inferred`다.

## 2. 카메라별 역할

### Top camera — 전역 상태 관측

주요 역할:

- 작업대와 전체 작업 영역 관측
- 검은색 마커펜 탐색과 후보 선택
- 펜의 평면 `x, y, yaw` 추정
- 펜꽂이 위치와 입구 영역 추정
- active arm 선택에 필요한 전역 좌표 제공
- grasp 이후 물체가 원래 위치에서 사라졌는지 확인
- place 이후 펜이 목표 영역에 들어갔는지 확인
- 양팔 private/shared zone의 전역 작업 상태 관측

적용 기술:

- intrinsic calibration
- 고정 camera-to-base extrinsic
- 작업대 homography를 이용한 pixel→table 좌표 변환
- 초기에는 검은 물체 threshold/contour/PCA 기반 yaw
- 이후 Nano급 YOLO 또는 작은 keypoint detector
- source timestamp, frame age, confidence 기반 freshness 검사

Top RGB 한 대로 일반적인 3D pose를 복원한다고 가정하지 않는다. 초기 Z는 작업대와 물체 모델의 알려진 높이로 제한한다.

### Right wrist camera — 오른팔 근접 정렬

주요 역할:

- pre-grasp 이후 그리퍼와 펜의 상대 오차 계산
- 마지막 수 cm의 center/yaw correction
- gripper close 직전 물체 존재 확인
- lift 후 물체가 그리퍼와 함께 움직이는지 확인
- 펜꽂이 접근 시 입구 중심과 삽입 방향 미세 보정

적용 기술:

- intrinsic calibration
- eye-in-hand calibration으로 `right_tool0 → right_wrist_camera` 고정 transform 추정
- ROI crop과 작은 feature/keypoint detector
- image-based visual servo 또는 bounded Cartesian correction
- stale frame/low confidence/timeout 시 즉시 abort

카메라는 세계 좌표에서 움직이지만 end-effector에 대한 extrinsic은 고정이다. TF가 매 순간 camera pose를 계산한다.

### Left wrist camera — 왼팔 근접 정렬

오른팔과 같은 역할을 갖지만 초기 오른팔 MVP에서는 inference를 수행하지 않는다.

- 초기: 장치 연결과 freshness만 저주기로 확인
- 왼팔 단독 기준 통과 후: 왼팔 visual alignment
- 양팔 private 작업: active phase에 따라 좌우 wrist를 교대로 추론
- 수건 작업: 양쪽 grasp point와 cloth edge 확인

## 3. Calibration 전략

체크보드 또는 ChArUco는 개발 중 calibration에만 사용하고 시연 작업대에서는 제거한다.

| 카메라 | Intrinsic | Extrinsic |
|---|---|---|
| Top | 개별 calibration | eye-to-hand, base 기준 고정 |
| Left wrist | 개별 calibration | eye-in-hand, left tool 기준 고정 |
| Right wrist | 개별 calibration | eye-in-hand, right tool 기준 고정 |

Calibration 결과는 `camera_info` YAML과 transform YAML로 버전 관리한다. 해상도, focus, camera mount가 바뀌면 기존 calibration을 재사용하지 않는다.

## 4. Vision process 구조

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
- V4L2 mmap 또는 측정 후 GStreamer fallback
- UVC MJPEG 우선, `640×480 @ 15FPS` 시작
- compressed latest frame 한 장만 camera별 유지
- active view만 libjpeg-turbo/OpenCV decode
- inference input `320×320`부터 시작
- queue depth 1, 오래된 frame 폐기
- debug image는 요청 시 또는 1FPS 이하
- raw image의 process 간 DDS 전송과 상시 rosbag 금지

카메라가 MJPEG를 지원하지 않거나 decode 비용이 더 큰 경우 실제 `v4l2-ctl` 결과와 benchmark에 따라 YUYV를 선택한다.

## 5. 추론 구조

### Vision inference

- 동시 heavy inference lane: 1개
- ONNX Runtime execution mode: sequential부터 시작
- `intra_op_num_threads`: 2부터 측정
- `inter_op_num_threads`: 1
- 같은 detector를 Top/Wrist에 사용할 수 있으면 session 1개 공유
- 서로 다른 모델이 필요해도 동시에 실행하지 않고 scheduler가 직렬화
- INT8은 FP32 baseline의 정확도와 latency를 측정한 뒤 적용

### Policy inference

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

출력은 bounded Cartesian delta, arm selection, grasp decision 또는 residual correction으로 제한한다.

- 별도 `policy_runtime` process
- 작은 structured-state ONNX session
- 초기 rate 10Hz
- `intra_op_num_threads = 1`
- 입력 queue depth 1
- stale structured state면 결과 폐기
- raw servo position 직접 출력 금지
- deterministic baseline 이후에만 command path 활성화

정책과 vision이 동시에 실행될 수는 있지만 vision 2 threads + policy 1 thread를 초기 상한으로 두어 최소 한 코어 상당의 여유를 control/OS에 남긴다. 실제 CPU affinity는 benchmark 전 적용하지 않는다.

## 6. 상태별 compute schedule

아래 수치는 초기 budget이며 `config/camera_schedule.json`이 총 vision inference를 12Hz 이하로 검증한다.

| Task phase | Top inference | Left wrist | Right wrist | Policy | 목적 |
|---|---:|---:|---:|---:|---|
| STANDBY | 1Hz | 0 | 0 | OFF | 장치·작업대 저주기 감시 |
| SEARCH | 8Hz | 0 | 0 | OFF | 펜 탐색 |
| APPROACH_RIGHT | 4Hz | 0 | 6Hz | OFF | 전역+근접 전환 |
| VISUAL_ALIGN_RIGHT | 1Hz | 0 | 10Hz | OFF | 오른팔 마지막 정렬 |
| TRANSFER_RIGHT | 2Hz | 0 | 1Hz | OFF | 운반 상태 확인 |
| VERIFY_RIGHT | 4Hz | 0 | 4Hz | OFF | grasp/place 확인 |
| DUAL_PRIVATE | 4Hz | 4Hz | 4Hz | OFF | 양팔 view 시분할 |
| POLICY_ASSIST | 4Hz | 0 | 6Hz | 10Hz | structured residual 평가 |

정책 학습 단계 전까지 policy는 OFF다. Visual Servo 중에는 deterministic correction을 우선하며 policy를 동시에 command source로 사용하지 않는다.

## 7. 실행 우선순위

부하가 높을 때 기능을 줄이는 순서:

1. debug image와 영상 기록 중단
2. inactive wrist decode/inference 중단
3. Top 또는 active wrist inference rate 감소
4. policy 10Hz → 5Hz 감소 또는 일시 중단
5. detector 입력 크기/모델 축소

절대로 자동으로 줄이지 않는 항목:

- STM32 heartbeat
- serial RX/TX와 joint feedback
- safety/fault 처리
- command validation
- 카메라·perception freshness 검사

policy 또는 perception deadline을 만족하지 못하면 오래된 결과로 계속 움직이지 않고 Hold 또는 재탐색한다.

## 8. Pi 자원 목표

초기 합격 기준:

| 지표 | 목표 |
|---|---|
| 전체 CPU 지속 평균 | 70% 이하 목표, 최대 75% 상한 검토 |
| 10초 평균 peak | 90% 미만 |
| 메모리 사용 | 3.0GB 이하 |
| available memory | 700MB 이상 목표 |
| swap-in/swap-out | 0 |
| thermal throttling | 0회 |
| 온도 | 80°C 미만 목표 |
| camera queue | camera별 latest 1장 |
| vision 부하 중 heartbeat 위반 | 0회 |
| 지속적인 memory/queue 증가 | 0 |

수치는 30분 stress test 후 조정하고 8시간 soak에서 다시 검증한다.

## 9. USB 배치 원칙

- STM32 ST-LINK VCP는 카메라 hub와 가능한 한 다른 Pi 물리 포트에 연결
- 세 카메라는 powered hub를 우선 사용하되 `lsusb -t`로 실제 topology 기록
- 1080p를 사용하지 않고 640×480부터 시작
- 세 카메라의 hardware synchronization을 가정하지 않음
- dequeue 시각을 source timestamp로 기록하고 multi-view 결과의 최대 skew 검사
- 장치 serial이 없으면 USB physical path와 camera identity self-test를 함께 사용

## 10. Process 격리

| Process | 역할 | Vision 장애 영향 |
|---|---|---|
| `vision_pipeline` | capture, decode, detector, pose | 재시작 가능 |
| `policy_runtime` | structured policy | 실패 시 deterministic fallback |
| `move_group` | planning/collision | task transition 지연 가능 |
| `robot_core` | state/task/command arbitration | stale input 거부 |
| `control_bridge` | ros2_control, STM32 VCP | vision과 독립 유지 |
| `safety_supervisor` | freshness/fault/process health | vision 실패 시 Hold 요청 |

Vision process가 죽거나 CPU를 소모해도 STM32 heartbeat와 안전 정지가 같은 process/thread에 묶이지 않게 한다.

## 11. 단계별 검증

1. 세 카메라 capture만 실행
2. decode 없이 compressed latest buffer 검증
3. camera별 decode latency 측정
4. dummy inference workload 추가
5. 실제 detector 추가
6. structured policy dummy workload 추가
7. MoveIt planning burst 동시 부하
8. STM32 heartbeat와 serial RTT 확인
9. 30분 stress
10. 8시간 soak

각 단계에서 frame age, decode/inference p50/p95/max, CPU, memory, temperature, USB reset, heartbeat gap을 기록한다.

