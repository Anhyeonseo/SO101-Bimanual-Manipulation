# ADR-0004: 안전 상태와 ARMING

- 상태: Accepted
- 날짜: 2026-07-12

## 결정

- 부팅·재연결·process restart 후 기본 상태는 `STANDBY`다.
- 명시적 Start 후 `ARMING` 검사를 통과해야 actuator command를 허용한다.
- 통신 단절은 감속 정지 후 제한 시간 Hold로 처리한다.
- 심각한 servo fault, 반복 과부하와 E-stop은 Torque Disable 및 latched fault로 처리한다.
- 장애 복구 후 `CLEAR_FAULT → ARMING → ENABLE`을 다시 수행한다.
- 한 팔의 심각한 fault는 양팔 coordinated stop을 발생시킨다.

물리 E-stop이 설치되기 전에는 저속 벤치 시험만 허용한다.

