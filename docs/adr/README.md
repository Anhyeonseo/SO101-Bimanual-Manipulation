# 아키텍처 결정 기록(ADR)

| ADR | 결정 | 상태 |
|---|---|---|
| [0001](0001-system-partition.md) | Pi와 STM32 역할 분리 | 채택 |
| [0002](0002-motion-time-ownership.md) | trajectory 시간축 소유권 | 채택 |
| [0003](0003-five-dof-task-scope.md) | 5DOF 초기 작업 제약 | 채택 |
| [0004](0004-safety-and-arming.md) | `STANDBY`, `ARMING`, fault 원칙 | 채택 |
| [0005](0005-camera-and-policy-staging.md) | 카메라와 policy 구현 순서 | 채택 |
| [0006](0006-wire-protocol.md) | Pi–STM32 통신 규격 | 채택 |
| [0007](0007-camera-compute-budget.md) | Pi 카메라와 연산 자원 한도 | 제안 |

기존 결정을 바꿔야 할 때는 문서를 삭제하지 않는다. 기존 문서를 `대체됨(Superseded)`으로 표시하고 새 ADR을 추가해 변경 이유를 남긴다.
