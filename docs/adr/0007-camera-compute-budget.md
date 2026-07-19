# ADR-0007: Raspberry Pi camera and compute budget

- 상태: Proposed
- 날짜: 2026-07-12

## 제안

- 세 카메라는 연결하되 상태 머신이 decode와 inference를 선택한다.
- camera별 compressed latest frame 한 장만 유지한다.
- vision heavy inference는 한 lane으로 직렬화하고 합계 12Hz를 초기 상한으로 둔다.
- Top은 전역 `x, y, yaw`와 task verification, Wrist는 마지막 상대 정렬을 담당한다.
- policy는 raw image가 아닌 structured state를 10Hz 이하로 입력받는다.
- vision ONNX는 최대 2 intra-op threads, policy는 1 thread로 시작한다.
- raw image DDS 상시 전송과 연속 raw rosbag을 금지한다.

## 이유

Raspberry Pi 5 4GB에서 MoveIt, DDS, camera decode, detector와 policy가 CPU·메모리를 경쟁하므로 모든 view를 동일한 속도로 추론하면 control/safety 여유를 보장하기 어렵다.

## 승인 조건

- 실제 UVC format과 USB topology 확인
- capture/decode/dummy inference benchmark
- camera+policy 부하에서 STM32 heartbeat 위반 0회
- CPU, memory, temperature와 frame age 합격 기준 충족

