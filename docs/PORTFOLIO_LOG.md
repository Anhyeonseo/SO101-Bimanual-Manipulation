# 포트폴리오 작업 기록

이 파일은 결과만 나열하지 않고 문제, 판단, 검증과 개선 과정을 기록한다.

날짜가 지난 항목은 당시의 판단을 남긴 기록이다. 현재 구현 상태는 [바이너리 제어 경로 검증 결과](test-results/2026-07-20-stm32-binary-control-plane.md)와 [검증 매트릭스](VERIFICATION_MATRIX.md)를 우선해서 확인한다.

## 기록 템플릿

### YYYY-MM-DD — 작업 제목

**목표**

- 이번 작업에서 확인하려는 내용

**구현/시험**

- 변경한 파일, 하드웨어 구성, 실행한 명령

**측정 결과**

| 지표 | 결과 | 조건 |
|---|---|---|
| 예시 |  |  |

**문제와 원인**

- 관찰된 증상
- 확인한 원인

**설계 판단**

- 채택한 방식
- 대안과 채택하지 않은 이유

**증거**

- 로그, 그래프, 사진, 영상, 성능 측정 결과 경로

**완료 판정**

- 통과/실패/차단
- 다음 단계 진입 가능 여부

---

## 2026-07-12 — 프로젝트 착수 및 단계 0 정의

**목표**

- 전체 프로젝트를 검증 게이트 방식으로 관리한다.
- 하드웨어, 안전, ROS, 펌웨어, 카메라, 시뮬레이션과 정책 학습의 선행 관계를 명확히 한다.

**구현/시험**

- 프로젝트 헌장 작성
- 하드웨어 인벤토리 작성
- 전체 로드맵 및 검증 매트릭스 작성
- 핵심 아키텍처 ADR 작성

**설계 판단**

- 오른팔의 재현 가능한 Pick and Place를 첫 통합 목표로 선택했다.
- Policy 학습 전에 측정할 수 있는 기준 동작(baseline)을 만든다.
- Raspberry Pi 카메라 성능 검증은 인식 기능 구현보다 먼저 수행한다.
- STM32는 실시간 actuator 제어와 안전 처리만 담당하게 제한한다.

**완료 판정**

- 문서 생성 후 검토 예정
- 다음 작업: 서보 12축의 하드웨어 기준선 기록

---

## 2026-07-12 — 단계 0 측정 데이터 자동 검증

**목표**

- 서보 기준선 측정의 누락과 안전 상태 모순을 자동으로 검출한다.
- 오른팔 우선 측정과 양팔 최종 게이트를 같은 데이터 형식으로 관리한다.

**구현/시험**

- `hardware/phase0_baseline.json` 측정 템플릿 추가
- `tools/validate_phase0.py`에 문제가 있으면 반드시 실패하도록 만든(fail-closed) 검증기 추가
- 정상 데이터, 오른팔 단독, 중복 관절, 비명령 동작, safe range 이탈 테스트 추가

**측정 결과**

| 지표 | 결과 | 조건 |
|---|---|---|
| 단위 테스트 | 5/5 통과 | Python unittest |
| 실제 오른팔 기준선 | 실패, 미입력 70개 | 측정 전 템플릿 |
| 공백 문자 검사 | 통과 | `git diff --check` |

**설계 판단**

- 측정 전 검증 실패를 정상 상태로 취급한다.
- 누락값을 임의 기본값으로 대체하지 않는다.
- 오른팔만 먼저 검증할 수 있지만 전체 Phase 0 완료는 양팔 데이터가 필요하다.

**증거**

- `tests/test_validate_phase0.py`
- `hardware/phase0_baseline.json`
- `tools/validate_phase0.py`

**완료 판정**

- 도구 구현 PASS
- 하드웨어 게이트는 실제 측정 전이므로 미실행 유지

---

## 2026-07-12 — Pi–STM32 통신 규격 초안

**목표**

- 펌웨어와 ROS hardware interface를 작성하기 전에 유선 통신 규격의 책임, frame 구성, 단위, 상태와 메시지 ID를 고정한다.

**구현/시험**

- COBS + CRC-32C 기반 frame 구조 제안
- little-endian 고정 크기 정수와 micro-radian 단위 정의
- 공통 `apply_tick`을 이용해 좌우 setpoint를 한 번에 적용하는 방식 정의
- session/state/motion/feedback 메시지 ID manifest 작성
- 중복 ID, 예약 범위, 필수 메시지, 잘못된 `ESTOP` software 메시지 검출 시험

**측정 결과**

| 지표 | 결과 | 조건 |
|---|---|---|
| 저장소 전체 단위 테스트 | 10/10 통과 | 단계 0 + 통신 규격 검증기 |
| 통신 규격 manifest | 통과 | 서로 다른 메시지 18개 |
| 문법/공백 문자 | 통과 | compileall, git diff --check |

**설계 판단**

- 소프트웨어 정지는 `SAFE_STOP`, 물리 정지는 E-stop으로 명확히 구분했다.
- Raspberry Pi는 서보 raw 위치가 아닌 관절 micro-radian 값을 전송한다.
- STM32가 보정 정보(calibration)와 최종 raw 제한을 적용한다.
- timeout, queue 크기와 제어 속도는 실제로 측정하기 전에 확정하지 않는다.

**증거**

- `protocol/README.md`
- `protocol/message_ids.json`
- `tools/validate_protocol_manifest.py`
- `tests/test_validate_protocol_manifest.py`

**완료 판정**

- 통신 규격 구조 검증 통과
- ADR-0006은 하드웨어 측정과 사용자 검토 전까지 제안 상태

---

## 2026-07-12 — Raspberry Pi 카메라 역할과 연산 자원 한도

**목표**

- 카메라 3대, 검출기, MoveIt과 향후 policy가 Raspberry Pi 5 4GB 자원을 무제한으로 경쟁하지 않도록 작업 단계별 연산 한도를 정의한다.

**구현/시험**

- 상단/왼쪽 손목/오른쪽 손목 카메라 역할과 보정 범위 정의
- 압축된 최신 frame, 선택적 decode, 단일 추론 실행 경로 정의
- 작업 상태 8개의 decode, 추론, policy 실행 속도 작성
- 전체 영상 추론 속도, queue 크기, thread 수, 원본 영상 policy 금지를 자동 검증

**측정 결과**

| 지표 | 결과 | 조건 |
|---|---|---|
| 저장소 단위 테스트 | 15/15 통과 | 기준선·통신 규격·카메라 검증기 |
| 카메라 실행 일정 | 통과 | 작업 상태 8개 |
| 최대 영상 추론 속도 | 12Hz | DUAL_PRIVATE |
| Policy 입력 | 구조화 상태 | 원본 영상 사용 안 함 |

**설계 판단**

- 상단 카메라는 전역 평면 자세와 결과 확인, 손목 카메라는 마지막 상대 정렬을 담당한다.
- 카메라 연결·영상 수집 속도와 decode·추론 속도를 분리한다.
- 영상 처리 thread 2개와 policy thread 1개를 초기 상한으로 두고 실제 CPU core 고정은 성능 측정 후 결정한다.
- 제어와 안전 처리는 부하를 줄이는 대상에서 제외한다.

**증거**

- `docs/CAMERA_COMPUTE_ARCHITECTURE.md`
- `config/camera_schedule.json`
- `tools/validate_camera_schedule.py`
- `tests/test_validate_camera_schedule.py`

**완료 판정**

- 아키텍처와 정적 연산 한도 검증 통과
- 실제 UVC/Raspberry Pi 성능 측정 전까지 ADR-0007은 제안 상태

---

## 2026-07-21 — 카메라 선택적 decode와 STM32 제어 격리

**목표**

- 카메라 세 대의 RGB decode와 DDS 전달 부하가 Raspberry Pi 자원과 STM32 heartbeat·feedback을 방해하지 않는지 실기로 확인한다.

**구현/시험**

- 작업 phase에 따라 필요한 카메라만 JPEG decode하는 scheduler 구현
- phase별 frame age와 decode 시간 p50/p95/max 진단 추가
- `DUAL_PRIVATE`에서 top 6Hz, wrist A/B 각 5Hz RGB topic 동시 소비
- STM32 bridge를 READ_ONLY, heartbeat 10Hz, joint feedback 5Hz로 동시 실행
- CPU, memory, 온도, swap과 joint feedback 간격을 120초간 측정

**측정 결과**

| 지표 | 결과 |
|---|---:|
| package 시험 | 14 tests, 실패 0 |
| phase별 목표 decode rate | 전부 일치 |
| JPEG decode 실패 | 0회 |
| frame age 전체 최댓값 | 35.98ms |
| JPEG decode 전체 최댓값 | 6.31ms |
| 부하 중 `/joint_states` | 5.008Hz |
| joint feedback 최대 간격 | 201.30ms |
| CPU 평균/1초 최대 | 6.38% / 8.73% |
| memory 사용 최대 | 465.3MB |
| 온도 최대 | 33.6°C |
| swap in/out | 0/0 |
| 시험 후 STM32 stop latch | 0 |

**설계 판단**

- 세 카메라는 capture를 유지하되 작업에 필요하지 않은 JPEG는 decode하지 않는다.
- RGB 원본은 queue에 쌓지 않고 sensor-data QoS depth 1로 전달한다.
- phase 전환 시 rolling 통계를 초기화해 서로 다른 작업 단계의 지연값이 섞이지 않게 한다.
- 제어와 영상 처리는 서로 다른 process에서 실행하고 영상 부하 때문에 heartbeat rate를 낮추지 않는다.

**증거**

- `docs/test-results/2026-07-21-camera-phase-decode-latency.md`
- `docs/test-results/2026-07-21-camera-decode-control-load.md`
- `tools/camera_control_load_test.py`
- `ros2_ws/src/manipulation_camera_manager`

**완료 판정**

- `CAM-003`, `CAM-005` 통과
- `RES-001`의 capture + decode + DDS 하위 gate 통과
- 실제 perception inference, MoveIt과 장시간 부하는 후속 단계에서 검증

---

## 2026-07-24 — 왼팔 MoveIt·Isaac Sim 6.0.1 통합

**목표**

- 고장 난 반대편 팔을 제외하고 정상인 왼팔 하나의 simulation vertical
  slice를 먼저 완성한다.
- URDF/Xacro, MoveIt, controller action과 Isaac articulation이 동일한
  joint 이름, radian, q0와 positive direction을 사용하게 한다.
- 실제 STM32/servo를 활성화하지 않고 대표 trajectory를 검증한다.

**구현/시험**

- TheRobotStudio SO-101 geometry를 pinned commit 기준으로 가져와 왼팔
  URDF/Xacro와 `ros2_control` mock interface 구성
- `left_arm` 5-DOF, `left_gripper` 1-DOF SRDF와 KDL position-only IK 구성
- mock controller에서 arm/gripper Plan/Execute 검증
- Isaac Sim 6.0.1 stage에 articulation drive와 ROS 2 Joint States
  OmniGraph 저장
- project joint와 Isaac joint 사이의 sign/offset adapter 구현
- MoveIt action을 Isaac `/isaac/joint_command`로 전달하고
  `/isaac/joint_states`를 project `/joint_states`로 변환

**측정 결과**

| 지표 | 결과 |
|---|---:|
| mapping unit test | 3/3 통과 |
| mock arm/gripper | 모두 Plan/Execute 성공 |
| direct Isaac arm/gripper action | 모두 `SUCCEEDED` |
| MoveIt → Isaac arm | random valid pose와 home 성공 |
| MoveIt → Isaac gripper | open/closed 성공 |
| home 후 최대 project joint 오차 | 약 `0.0097 rad` |
| goal tolerance | `0.03 rad` |
| 실제 servo 동작 | 0회 |

**문제와 원인**

- desktop에서 실행한 Isaac은 ROS library path가 없어 ROS 2 Bridge가
  시작되지 않았다.
- Isaac 6.0.1의 USD Python API와 Jazzy
  `ParallelGripperCommand` feedback schema가 초기 가정과 달랐다.
- bridge 종료 시 ROS context 이중 shutdown 예외가 있었다.

**설계 판단**

- Isaac Sim은 ROS 2 Jazzy 환경을 source한 terminal에서 시작한다.
- 다섯 arm joint는 sign을 반전하고 gripper는 sign 유지와 `+10 deg`
  project offset을 적용한다.
- Isaac topic과 USD path는 `so101_isaac_bridge` 안에 격리하고 MoveIt
  controller contract는 backend와 무관하게 유지한다.
- 단일 왼팔 단계 4를 완료하되 양팔·camera mount는 검증 없이 PASS로
  올리지 않는다.

**증거**

- `docs/checklists/PHASE_4_ISAAC_MOVEIT_INTEGRATION.md`
- `docs/test-results/2026-07-24-isaac-moveit-left-arm-integration.md`
- `ros2_ws/src/so101_isaac_bridge/test/test_mapping.py`
- `isaac_sim/assets/so101_new_calib/so101_new_calib.usda`

**완료 판정**

- 단계 4 단일 왼팔 simulation vertical slice 통과
- 실제 hardware는 비활성
- 단계 5 실제 hardware 진입 전 safe limit과 backend 단일 선택 조건 검토
