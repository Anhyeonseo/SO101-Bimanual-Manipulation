# ADR-0001: Raspberry Pi와 STM32 역할 분리

- 상태: Accepted
- 날짜: 2026-07-12

## 결정

Raspberry Pi는 perception, TF, MoveIt, task state machine, policy inference와 운영을 담당한다. STM32는 host packet 검증, bounded setpoint buffer, 공통 제어 tick, 서보 bus I/O, 제한, heartbeat와 fault 처리를 담당한다.

## 이유

Linux와 USB serial의 jitter가 실제 servo bus 타이밍과 안전 정지를 결정하지 않도록 하기 위함이다. 동시에 STM32에 IK나 task logic을 넣어 책임을 혼합하지 않는다.

