# ADR-0008: 정상인 왼팔 단일 팔 우선

- 상태: 채택
- 날짜: 2026-07-24

## 상황

현재 한쪽 SO-ARM101이 고장 나 정상인 한 팔로 simulation과 실제 backend를
먼저 완성해야 한다. 기존 ROS 2 bridge, calibration과 joint 이름은 모두
`left_*` contract를 사용한다. 과거 일부 계획 문서에는 첫 작업 팔이
오른팔로 기록돼 있어 현재 구현과 불일치했다.

## 결정

- 첫 완성 대상은 왼팔로 확정한다.
- 단일 팔 public ROS contract는 `left_*` joint/link 이름을 유지한다.
- URDF/Xacro, SRDF, MoveIt group, controller action, Isaac adapter는 왼팔
  contract를 source of truth로 사용한다.
- 고장 난 반대편 팔의 이름, mirror transform, calibration과 limit은 실제
  측정 없이 추정하지 않는다.
- 양팔 확장 시 왼팔 macro와 prefix 구조를 재사용하되 두 backend가 동시에
  같은 command를 받지 않도록 launch에서 하나만 선택한다.

## 이유

이미 실기로 검증한 calibration과 ROS interface를 유지하는 것이 joint
rename/migration보다 위험이 낮다. 먼저 단일 팔 vertical slice를 완성하면
향후 반대편 팔 복구 시 새로 측정해야 할 값과 재사용할 software contract를
분리할 수 있다.

## 영향

- 초기 Pick and Place와 실제 hardware 단계는 왼팔 기준으로 진행한다.
- 과거 문서의 오른팔 우선 기록은 당시 기록으로 남기되 현재 계획과 헌장은
  왼팔 우선으로 갱신한다.
- 양팔 완료 기준은 변경하지 않는다.
