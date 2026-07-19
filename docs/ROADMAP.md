# 검증 게이트 기반 전체 로드맵

## 진행 규칙

- 각 Phase의 검증 결과를 `docs/PORTFOLIO_LOG.md`에 기록한다.
- 수치 결과는 `benchmark/results/`에 원본과 요약을 분리해 보관한다.
- 실제 하드웨어 활성화는 이전 Phase의 완료 조건을 충족한 뒤 진행한다.

## Phase 0 — 하드웨어 기준선과 요구사항 동결

- 서보 12축 ID, 방향, raw range, feedback 확인
- 전원, 배선, adapter, MCU, 카메라 인벤토리 완성
- 시스템 역할과 안전 상태 확정
- 완료 조건: 미확정 하드웨어 상수 목록과 측정 계획이 모두 존재

## Phase 1 — 저장소·인터페이스·Mock 골격

- `dual_arm_interfaces`, `dual_arm_description`, `dual_arm_control`
- `dual_arm_safety`, `dual_arm_bringup`, `dual_arm_benchmark`
- SO-101 Xacro, SRDF, ros2_control Mock Hardware
- STANDBY/ARMING 최소 상태 머신
- 완료 조건: fresh checkout에서 build/test/mock launch 성공

## Phase 2 — STM32 FreeRTOS 제어 기반

- ST-LINK VCP binary protocol
- CRC, sequence, heartbeat, fault latch
- 좌우 독립 UART와 sync write/read
- 공통 tick과 bounded trajectory buffer
- 완료 조건: protocol fault injection 및 8시간 loop 시험 통과

## Phase 3 — Pi 카메라 관리와 성능 기준선

- 카메라 3대 capture thread
- latest-frame buffer, queue depth 1
- 상태 기반 scheduler, dummy consumer
- USB, FPS, frame age, reconnect, CPU, memory, thermal 측정
- 완료 조건: 카메라+STM32 동시 부하에서 control heartbeat 위반 없음

## Phase 4 — MoveIt/Isaac Sim 기구학 검증

- right/left/both planning groups
- 충돌 모델, workspace 계산, shared/private zone
- Isaac Sim URDF import와 카메라 mount 검증
- 완료 조건: Mock 및 Isaac 환경에서 대표 trajectory 검증

## Phase 5 — 실제 오른팔 제어

- JTC → ros2_control → STM32 → 오른팔
- 단일 관절, 전체 팔, home, cancel, fault recovery
- 완료 조건: 반복 trajectory와 통신 단절 시험 통과

## Phase 6 — Top 카메라 Perception

- intrinsic calibration, 작업대 homography
- dummy → recorded → classical detector → YOLO
- 펜 `x, y, yaw`, confidence, freshness 출력
- 완료 조건: 위치 오차가 grasp 허용 오차 이내

## Phase 7 — Deterministic Pick and Place

- 오른팔 상태 머신
- grasp/place 검증
- 50회 반복 시험
- 완료 조건: Pick/Place 각각 90% 이상, 비명령 동작·충돌 0회

## Phase 8 — Wrist Visual Servo

- eye-in-hand calibration
- active wrist scheduling
- bounded Cartesian correction
- 완료 조건: stale/low-confidence 입력 차단과 최종 정렬 오차 목표 충족

## Phase 9 — Raspberry Pi Headless 통합

- ARM64 Release build, ONNX Runtime, systemd, udev, journald
- watchdog, reconnect, remote control, safe shutdown
- 완료 조건: 반복 부팅 STANDBY, fault injection, 8/24시간 soak 통과

## Phase 10 — 양팔 병렬·공유 영역

- 왼팔 단독 기준 통과
- 공통 MCU tick, physical skew 측정
- private zone 병렬 작업, shared zone 통합 계획
- 완료 조건: 충돌 0회, 한 팔 fault 시 coordinated stop

## Phase 11 — Isaac Lab 정책과 Edge 추론

- structured-state policy
- simulation → offline → shadow → bounded residual
- ONNX export와 Pi latency 검증
- 완료 조건: deterministic baseline 대비 정량적 개선

## Phase 12 — 수건 접기와 최종 포트폴리오

- segmentation, keypoint, cloth state, dual-arm grasp
- 단계별 fold와 재인식
- 최종 benchmark, 영상, 아키텍처·장애복구 보고서

