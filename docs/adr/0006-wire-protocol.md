# ADR-0006: Pi–STM32 통신 규격

- 상태: 채택
- 날짜: 2026-07-12

## 결정

- ST-LINK VCP에서 COBS frame 구성과 CRC-32C를 사용한다.
- 전송 값은 little-endian 고정 크기 정수와 명시적인 단위를 사용한다.
- Raspberry Pi는 관절 micro-radian 값을 전송하고 STM32가 보정 정보와 raw 안전 범위를 적용한다.
- 좌우 각 6개 actuator의 setpoint를 공통 `apply_tick`에 한 번에 적용한다.
- Protocol version과 보정 정보 hash가 다르면 `ARMING`을 거부한다.
- Pi가 요청하는 감속 정지는 `SAFE_STOP`으로 부르고 물리 E-stop과 구분한다.

## 아직 확정하지 않은 값

Heartbeat timeout, 제어 주기, 명령을 미리 보내는 시간, queue 크기와 정지 방식은 실제 하드웨어의 지연 시간과 정지 거리를 측정한 뒤 확정한다.

## 채택 근거

- 단일 팔 서보 bus와 VCP 기준선 측정 완료
- 메시지 manifest 자동 검증 통과
- 사용자 검토 완료
