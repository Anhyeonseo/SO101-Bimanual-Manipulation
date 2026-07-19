# Architecture Decision Records

| ADR | 결정 | 상태 |
|---|---|---|
| [0001](0001-system-partition.md) | Pi와 STM32 역할 분리 | Accepted |
| [0002](0002-motion-time-ownership.md) | trajectory 시간축 소유권 | Accepted |
| [0003](0003-five-dof-task-scope.md) | 5DOF 초기 작업 제약 | Accepted |
| [0004](0004-safety-and-arming.md) | STANDBY/ARMING/fault 원칙 | Accepted |
| [0005](0005-camera-and-policy-staging.md) | 카메라와 정책 구현 순서 | Accepted |
| [0006](0006-wire-protocol.md) | Pi–STM32 wire protocol | Proposed |
| [0007](0007-camera-compute-budget.md) | Pi camera and compute budget | Proposed |

ADR을 변경해야 하면 기존 문서를 삭제하지 않고 `Superseded`로 표시한 뒤 새 ADR을 추가한다.
