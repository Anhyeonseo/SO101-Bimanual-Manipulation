# Pi–STM32 Wire Protocol v1 Draft

상태: `PROPOSED`. Phase 0 벤치 측정과 사용자 검토 후 `ACCEPTED`로 변경한다.

## 1. 범위

이 프로토콜은 Raspberry Pi의 ROS 2 control bridge와 NUCLEO-G474RE 사이에서만 사용한다. STM32와 STS3215 사이에는 Feetech STS bus protocol을 별도로 사용한다.

```text
ROS 2 / Pi
    ↓ ST-LINK VCP, 이 문서의 protocol
STM32G474
    ├─ UART → Left Waveshare adapter → STS3215 IDs 1..6
    └─ UART → Right Waveshare adapter → STS3215 IDs 1..6
```

Task의 `START`, `SEARCH`, `PLACE` 같은 의미는 ROS 계층에 남긴다. MCU protocol은 actuator 활성화, setpoint, 상태와 fault만 다룬다.

## 2. 전송 및 프레이밍

- Transport: ST-LINK Virtual COM Port
- Byte order: little-endian
- Framing: COBS encoded frame + `0x00` delimiter
- Integrity: CRC-32C
- Maximum decoded payload: 512 bytes
- 구조체 `memcpy` 직렬화 금지: padding과 compiler ABI에 의존하지 않고 바이트 단위로 encode/decode한다.

Decoded frame:

| Offset | Type | Field | 설명 |
|---:|---|---|---|
| 0 | `uint16` | magic | `0xA55A` |
| 2 | `uint8` | version | protocol major version, 초기값 1 |
| 3 | `uint8` | message_type | `message_ids.json` 참조 |
| 4 | `uint16` | flags | ACK 요구, response, error 등 |
| 6 | `uint16` | payload_length | payload bytes, 최대 512 |
| 8 | `uint32` | sequence | 방향별 독립 sequence |
| 12 | `uint32` | sender_time_ms | 송신자의 monotonic time, wrap 허용 |
| 16 | bytes | payload | message별 정의 |
| 16+N | `uint32` | crc32c | header와 payload 전체 검사 |

CRC가 맞더라도 magic, version, type, length와 현재 MCU 상태가 유효하지 않으면 패킷을 거부한다.

## 3. Sequence와 재전송

- Pi→MCU와 MCU→Pi sequence는 독립적으로 증가한다.
- `uint32` wrap은 modular comparison으로 처리한다.
- 중복된 state-changing command는 같은 결과를 반환하되 다시 실행하지 않는다.
- 오래된 setpoint sequence는 거부한다.
- ACK가 필요한 명령은 제한된 횟수와 간격으로만 재전송한다. 구체적인 값은 VCP latency 측정 후 확정한다.

## 4. 시간 모델

Header의 `sender_time_ms`는 freshness와 diagnostics용이며 두 장치의 절대 시간이 같다고 가정하지 않는다.

Setpoint는 MCU가 보고한 `control_tick` 기준의 `apply_tick`을 사용한다.

```text
HELLO/TIME_SYNC
→ MCU current control_tick 확인
→ Pi가 충분한 lead time을 둔 apply_tick 생성
→ STM32 bounded queue에 적재
→ 같은 apply_tick에 좌우 setpoint 원자 적용
```

다음 값은 벤치 측정 전 `TBD`다.

- control loop frequency
- minimum apply lead ticks
- heartbeat timeout
- setpoint queue capacity
- queue low-watermark
- 감속 정지 시간

## 5. 관절 단위와 보정

- wire position: signed micro-radians (`int32`, µrad)
- wire velocity: signed micro-radians/second (`int32`)
- wire acceleration: signed micro-radians/second² (`int32`)
- voltage: millivolts (`uint16`)
- load: STS raw feedback와 정규화 값의 매핑을 Phase 2에서 확정

Pi는 STS3215 raw position을 보내지 않는다. STM32가 Phase 0 calibration의 sign, zero와 safe raw range를 이용해 joint unit을 raw unit으로 변환하고 마지막 제한을 적용한다.

Pi와 STM32는 `calibration_hash`를 HELLO 단계에서 비교한다. 불일치 시 ARMING을 거부한다.

## 6. Setpoint 원자성

`SETPOINT_BATCH`의 한 frame에는 좌우 각 6 actuator의 목표를 포함한다. 한 팔만 움직일 때도 반대쪽 목표는 현재 Hold 목표로 채운다.

v1 payload 형식:

```text
uint32 apply_tick_ms
uint8  sample_count       # 1..9 (512-byte frame 제한)
uint8  arm_mask           # bit0=left, bit1=right
uint16 reserved           # 반드시 0
for each sample:
    uint32 tick_offset_ms
    int32  left_position_urad[6]
    int32  right_position_urad[6]
```

단일 팔 bring-up 펌웨어는 `arm_mask=1`만 허용하며 존재하지 않는 오른팔
목표 여섯 개가 모두 0인지 검사한다. 이 조건은 양팔 통합 시 두 팔의 현재
hold 목표를 모두 포함하는 규칙으로 확장한다.

초기 검증 단계의 `SETPOINT_STATUS.status` 값은 다음과 같다.

- `0`: queue accepted
- `1`: payload/tick 형식 오류
- `2`: ACTIVE 상태가 아니거나 stop latch 상태
- `3`: 관절각 변환 또는 raw limit 위반
- `4`: 지원하지 않는 arm slot 값
- `5`: 전체 검증 통과, 실행은 compile-time으로 비활성화된 상태
- `6`: 실행 완료 (`detail`은 최대 raw 위치 오차, 최대 255)
- `7`: servo bus 설정·쓰기·최종 읽기 실패
- `8`: Heartbeat/HOLD/SAFE_STOP으로 실행 중단

`flags.bit0=1`이면 패킷 전체를 검증만 하고 실행하지 않는다. 초기 단일 팔
실행기는 `flags.bit0=0`, `sample_count=1`만 실행하며, 여러 sample의 queue
보간은 후속 실시간 제어 단계에서 활성화한다.

- packet 전체가 유효할 때만 queue에 반영한다.
- 일부 joint만 반영하지 않는다.
- NaN은 integer wire format에 존재하지 않는다.
- unit conversion overflow, limit 위반, 불연속 setpoint는 packet 전체를 거부한다.

## 7. MCU 상태 머신

```text
BOOT
  → SAFE_DISABLED
  → ARMED
  → ACTIVE
  → HOLD

어느 상태에서든 조건에 따라:
  → FAULT
  → ESTOPPED
```

- `SAFE_DISABLED`: 통신과 feedback은 가능하지만 actuator command 금지
- `ARMED`: health와 configuration 검사를 통과했으나 아직 setpoint 실행 금지
- `ACTIVE`: bounded setpoint 실행 허용
- `HOLD`: 감속 정지 후 유지
- `FAULT`: 원인이 제거되고 명시적 CLEAR_FAULT 전까지 latch
- `ESTOPPED`: 물리 E-stop 입력이 해제되고 명시적 복구 절차 전까지 latch

전원 인가, VCP 재연결, Pi process restart만으로 `ACTIVE`가 되지 않는다.

## 8. 정지 명령 구분

- `HOLD`: 계획된 일시 정지 또는 짧은 통신 이상
- `SAFE_STOP`: Pi가 요청하는 감속 정지. 물리 E-stop이 아니다.
- `DISABLE`: torque command 비활성화 요청
- Physical E-stop: 독립 입력과 전원 계통으로 처리하고 `FAULT_REPORT`로만 보고

Serial message 이름으로 `ESTOP`을 사용하지 않는다. 소프트웨어 패킷이 물리 E-stop과 같은 보장을 제공한다는 오해를 피하기 위함이다.

## 9. Fault code 범위

| 범위 | 분류 |
|---|---|
| `0x0000` | no fault |
| `0x0100–0x01FF` | host link / heartbeat |
| `0x0200–0x02FF` | framing / CRC / protocol |
| `0x0300–0x03FF` | setpoint queue / timing |
| `0x0400–0x04FF` | joint position/speed/acceleration limit |
| `0x0500–0x05FF` | STS servo response / overload / temperature |
| `0x0600–0x06FF` | power / voltage |
| `0x0700–0x07FF` | watchdog / physical E-stop |
| `0xFF00–0xFFFF` | internal firmware fault |

세부 fault 번호는 firmware 구현 전에 별도 machine-readable manifest로 고정한다.

## 10. 검증 게이트

구현 전:

```bash
python3 tools/validate_protocol_manifest.py
```

펌웨어 단계:

- 임의 byte stream에서 delimiter 재동기화
- truncated/oversized/unknown-version frame 거부
- CRC bit flip 검출
- duplicate command idempotence
- stale/out-of-order setpoint 거부
- queue overflow/underflow fault
- heartbeat loss 정지
- config hash 불일치 시 ARMING 거부
- 한 팔 servo fault 시 양팔 coordinated stop
