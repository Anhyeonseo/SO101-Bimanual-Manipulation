# ADR-0001: Raspberry Pi와 STM32 역할 분리

- 상태: 채택
- 날짜: 2026-07-12

## 결정

Raspberry Pi는 인식(perception), TF, MoveIt, 작업 상태 머신, policy 추론과 시스템 운영을 담당한다. STM32는 상위 제어기 packet 검증, 크기가 제한된 setpoint buffer, 공통 제어 주기(tick), 서보 bus 입출력, 동작 범위 제한, heartbeat와 fault 처리를 담당한다.

## 이유

Linux와 USB serial의 시간 흔들림(jitter)이 실제 서보 bus timing과 안전 정지를 좌우하지 않게 하기 위해서다. 동시에 STM32에는 IK나 작업 logic을 넣지 않아 두 장치의 책임이 섞이지 않게 한다.
