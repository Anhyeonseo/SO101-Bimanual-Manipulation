# ADR-0002: Trajectory 실행 시간의 소유권

- 상태: 채택
- 날짜: 2026-07-12

## 결정

초기 버전에서는 ROS 2 `joint_trajectory_controller`가 전체 trajectory의 실행 시간을 관리한다. STM32는 20~50Hz로 들어오는 시간 정보가 포함된 setpoint를 짧게 저장하고, 100~250Hz 주기로 그 사이 값을 보간한다.

## 제약

- STM32는 trajectory의 시간을 임의로 다시 계산하지 않는다.
- 좌우 팔의 목표는 공통 `apply_tick`에서 한 번에 적용한다.
- MoveIt trajectory와 Visual Servo는 명령 중재기(command arbiter)를 거쳐 둘 중 하나만 실행한다.

## 대안

전체 trajectory를 STM32에 한 번에 올리는 구조는 초기 범위에서 제외한다. 필요해지면 표준 `FollowJointTrajectory` 호환 방식과 실행 감시 방법을 별도 ADR로 정의한다.
