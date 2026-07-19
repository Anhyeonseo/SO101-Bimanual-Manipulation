# ADR-0003: 5DOF 초기 작업 제약

- 상태: Accepted
- 날짜: 2026-07-12

## 상황

SO-ARM101은 자세 관절 5개와 gripper 1개로 구성된다. 임의의 6D end-effector pose를 항상 만족할 수 없다.

## 결정

1차 Pick and Place는 평면 작업대의 top-down 접근으로 제한한다.

- 위치 `x, y`와 접근 높이를 우선한다.
- 허용되는 범위에서 펜의 평면 yaw를 맞춘다.
- 펜꽂이는 초기에는 입구가 넓은 것을 사용한다.
- 도달 불가능한 pose는 IK fallback으로 강행하지 않고 task failure로 처리한다.

