# ADR-0002: Trajectory 시간축 소유권

- 상태: Accepted
- 날짜: 2026-07-12

## 결정

초기 버전은 ROS 2 `joint_trajectory_controller`가 전체 trajectory 시간축을 소유한다. STM32는 20~50Hz의 timestamp setpoint를 짧게 버퍼링하고 100~250Hz에서 보간한다.

## 제약

- STM32는 trajectory를 임의로 재시간화하지 않는다.
- 좌우 목표는 공통 `apply_tick`으로 원자적으로 적용한다.
- MoveIt trajectory와 Visual Servo는 command arbiter를 통해 상호 배타적으로 실행한다.

## 대안

전체 trajectory를 STM32에 업로드하는 구조는 초기 범위에서 제외한다. 필요 시 표준 `FollowJointTrajectory` 호환성과 실행 감시 방식을 별도 ADR로 정의한다.

