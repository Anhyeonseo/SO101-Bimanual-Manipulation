# 검증 게이트 기반 전체 로드맵

## 진행 규칙

- 각 단계의 검증 결과를 `docs/PORTFOLIO_LOG.md`에 기록한다.
- 수치 결과는 `benchmark/results/`에 원본과 요약을 분리해 보관한다.
- 실제 하드웨어 활성화는 이전 단계의 완료 조건을 충족한 뒤 진행한다.

## 단계 0 — 하드웨어 기준선과 요구사항 동결

- 서보 12축의 ID, 방향, raw 범위와 상태값(feedback) 확인
- 전원, 배선, adapter, MCU, 카메라 인벤토리 완성
- 시스템 역할과 안전 상태 확정
- 완료 조건: 미확정 하드웨어 상수 목록과 측정 계획이 모두 존재

## 단계 1 — 저장소·인터페이스·모의 장치(Mock) 골격

- `dual_arm_interfaces`, `dual_arm_description`, `dual_arm_control`
- `dual_arm_safety`, `dual_arm_bringup`, `dual_arm_benchmark`
- SO-101 Xacro, SRDF, ros2_control 모의 하드웨어
- STANDBY/ARMING 최소 상태 머신
- 완료 조건: 새로 내려받은 저장소에서 build, test, 모의 장치 실행 성공

## 단계 2 — STM32 제어 기반

- ST-LINK VCP 바이너리 통신 규격
- CRC, 전송 순서 번호, heartbeat, fault latch
- 단일 팔 UART와 6축 동시 쓰기/읽기
- 공통 제어 주기(tick)와 크기가 제한된 trajectory buffer
- 완료 조건: 단일 팔 통신·동작·SAFE_STOP 실기 시험과 protocol 자동 시험 통과
- 양팔용 독립 UART와 8시간 반복 시험은 단계 10에서 추가

## 단계 3 — Pi 카메라 관리와 성능 기준선

- 카메라 3대의 영상 수집 thread
- 최신 frame 하나만 보관하는 buffer와 queue
- 상태 기반 scheduler와 임시 영상 소비기(dummy consumer)
- USB, FPS, frame age, 재연결, CPU, memory, 온도 측정
- 완료 조건: 카메라와 STM32를 동시에 사용해도 제어 heartbeat 위반이 없음

## 단계 4 — MoveIt/Isaac Sim 기구학 검증

- 정상인 왼팔 단일 planning group을 먼저 검증
- 충돌 모델, 작업 가능 공간(workspace) 계산, 공유·개별 작업 영역
- Isaac Sim에 URDF를 불러오고 카메라 mount 검증
- 완료 조건: 모의 하드웨어와 Isaac 환경에서 대표 trajectory 검증
- 2026-07-24 판정: 왼팔 arm/gripper 대표 trajectory까지 통과. 반대편 팔,
  양팔 planning group, 공유 workspace와 simulated camera mount는 해당
  하드웨어 복구 및 측정 후 후속 gate로 유지

## 단계 5 — 실제 왼팔 제어

- JTC → ros2_control → STM32 → 현재 정상인 왼팔
- 단일 관절, 전체 팔, home, 취소, fault 복구
- 완료 조건: 반복 trajectory와 통신 단절 시험 통과

## 단계 6 — Top 카메라 인식(Perception)

- 카메라 내부 보정(intrinsic calibration)과 작업대 homography
- 임시 입력 → 녹화 영상 → 전통 영상 검출기 → YOLO 순서로 검증
- 펜의 `x, y, yaw`, 검출 신뢰도와 데이터 최신성 출력
- 완료 조건: 위치 오차가 grasp 허용 오차 이내

## 단계 7 — 재현 가능한 Pick and Place

- 왼팔 상태 머신
- grasp/place 검증
- 50회 반복 시험
- 완료 조건: Pick/Place 각각 90% 이상, 비명령 동작·충돌 0회

## 단계 8 — 손목(Wrist) 카메라 Visual Servo

- 손목 카메라 위치 보정(eye-in-hand calibration)
- 현재 사용하는 손목 카메라만 처리하도록 일정 관리
- 크기가 제한된 Cartesian 좌표 보정
- 완료 조건: 오래됐거나 신뢰도가 낮은 입력을 차단하고 최종 정렬 오차 목표 충족

## 단계 9 — Raspberry Pi Headless 통합

- ARM64 Release build와 ONNX Runtime, systemd, udev, journald 설정
- watchdog, 재연결, 원격 제어, 안전 종료
- 완료 조건: 반복해서 부팅해도 `STANDBY` 유지, fault 강제 발생 시험, 8시간/24시간 장시간 시험 통과

## 단계 10 — 양팔 병렬·공유 영역

- 왼팔 단독 기준 통과
- 공통 MCU 제어 주기, 실제 시작 시각 차이 측정
- 개별 작업 영역에서 병렬 실행하고 공유 영역은 하나의 계획으로 실행
- 완료 조건: 충돌 0회, 한 팔 fault 발생 시 양팔 동시 정지

## 단계 11 — Isaac Lab policy와 Edge 추론

- 구조화 상태(structured-state) policy
- 시뮬레이션 → 저장 데이터 평가 → 실제 명령 없는 비교(shadow) → 제한된 보정값 적용 순서로 진행
- ONNX로 내보낸 뒤 Raspberry Pi 추론 지연 시간 검증
- 완료 조건: 재현 가능한 기준 동작과 비교해 수치상 개선

## 단계 12 — 수건 접기와 최종 포트폴리오

- 영역 분할(segmentation), 특징점(keypoint), 수건 상태, 양팔 grasp
- 단계별 fold와 재인식
- 최종 benchmark, 영상, 아키텍처·장애복구 보고서
