# ADR-0004: 안전 상태와 ARMING

- 상태: 채택
- 날짜: 2026-07-12

## 결정

- 부팅·재연결·process 재시작 후 기본 상태는 `STANDBY`다.
- 사용자가 명시적으로 시작한 뒤 `ARMING` 검사를 통과해야 actuator 명령을 허용한다.
- 통신 단절은 감속 정지 후 제한 시간 Hold로 처리한다.
- 심각한 서보 fault, 반복 과부하와 E-stop은 Torque Disable 및 해제 전까지 유지되는 fault(latched fault)로 처리한다.
- 장애 복구 후 `CLEAR_FAULT → ARMING → ENABLE`을 다시 수행한다.
- 한 팔에서 심각한 fault가 발생하면 양팔을 함께 정지(coordinated stop)시킨다.

물리 E-stop이 설치되기 전에는 저속 벤치 시험만 허용한다.
