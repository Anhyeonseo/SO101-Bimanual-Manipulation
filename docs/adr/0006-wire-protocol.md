# ADR-0006: Pi–STM32 wire protocol

- 상태: Proposed
- 날짜: 2026-07-12

## 제안

- ST-LINK VCP 위에 COBS framing과 CRC-32C를 사용한다.
- wire 값은 little-endian fixed-width integer와 명시적 단위를 사용한다.
- Pi는 joint micro-radians를 전송하고 STM32가 calibration과 raw safe range를 적용한다.
- 좌우 6 actuator setpoint를 공통 `apply_tick`에 원자 적용한다.
- protocol version과 calibration hash가 다르면 ARMING을 거부한다.
- Pi의 감속 정지 요청은 `SAFE_STOP`으로 명명하고 물리 E-stop과 구분한다.

## 미확정

heartbeat timeout, control frequency, lead ticks, queue capacity와 stop profile은 하드웨어 latency 및 정지 시험 후 확정한다.

## 승인 조건

- Phase 0 servo bus와 VCP 기준선 측정 완료
- message manifest 자동 검증 통과
- 사용자 검토

