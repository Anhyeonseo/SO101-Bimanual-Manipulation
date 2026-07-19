# Pi–STM32 통신 규격 v1 초안

상태: `채택`. 단일 팔용 protocol v1은 실기에 적용했으며, 여러 sample queue와 양팔 payload 실행은 이후 단계에서 추가 검증한다.

## 1. 범위

이 규격은 Raspberry Pi의 ROS 2 제어 bridge와 NUCLEO-G474RE 사이에서 사용한다. STM32와 STS3215 사이에서는 Feetech STS bus protocol을 별도로 사용한다.

~~~text
ROS 2 / Pi
    ↓ ST-LINK VCP, 이 문서에서 정의한 protocol
STM32G474
    ├─ UART → Left Waveshare adapter → STS3215 ID 1~6
    └─ UART → Right Waveshare adapter → STS3215 ID 1~6
~~~

`START`, `SEARCH`, `PLACE`처럼 작업 의미를 나타내는 상태는 ROS 계층에 둔다. MCU protocol은 actuator 활성화, setpoint, 상태와 fault만 다룬다.

## 2. 전송 방식과 frame 구분

- 전송 경로(transport): ST-LINK Virtual COM Port
- Byte 순서: little-endian
- Frame 구분: COBS로 encoding한 frame 뒤에 구분값(delimiter) `0x00` 추가
- 오류 검출: CRC-32C
- Decode 후 payload 최대 크기: 512 byte
- 구조체를 `memcpy`로 바로 보내지 않는다. 메모리 정렬용 여백(padding)과 compiler ABI에 의존하지 않도록 byte 단위로 encode/decode한다.

Decode한 frame 구조:

| 시작 위치 | 자료형 | 필드 | 설명 |
|---:|---|---|---|
| 0 | `uint16` | magic | 고정값 `0xA55A` |
| 2 | `uint8` | version | protocol의 주 version, 초기값 1 |
| 3 | `uint8` | message_type | `message_ids.json` 참조 |
| 4 | `uint16` | flags | ACK 요청, 응답, 오류 등의 표시 |
| 6 | `uint16` | payload_length | payload 크기, 최대 512 byte |
| 8 | `uint32` | sequence | 전송 방향마다 따로 증가하는 번호 |
| 12 | `uint32` | sender_time_ms | 송신 장치에서 계속 증가하는 시간, 최댓값 이후 0으로 돌아감 허용 |
| 16 | bytes | payload | message마다 정의한 실제 데이터 |
| 16+N | `uint32` | crc32c | header와 payload 전체 검사값 |

CRC가 맞더라도 magic, version, type, length 또는 현재 MCU 상태가 올바르지 않으면 packet을 거부한다.

## 3. Sequence와 재전송

- Pi→MCU와 MCU→Pi의 sequence는 서로 독립적으로 증가한다.
- `uint32`가 최댓값을 넘어 0으로 돌아가는 현상은 modular comparison으로 처리한다.
- 상태를 바꾸는 명령이 중복되면 이전과 같은 결과를 반환하되 동작을 다시 실행하지 않는다.
- 이미 지난 setpoint sequence는 거부한다.
- ACK가 필요한 명령만 정해진 횟수와 간격으로 재전송한다. 정확한 값은 VCP 지연 시간을 측정한 뒤 확정한다.

## 4. 시간 기준

Header의 `sender_time_ms`는 데이터가 오래됐는지 확인하고 문제를 진단하는 용도다. Raspberry Pi와 STM32의 절대 시간이 같다고 가정하지 않는다.

Setpoint는 MCU가 알려 준 `control_tick`을 기준으로 `apply_tick`을 지정한다.

~~~text
HELLO/TIME_SYNC
→ MCU의 현재 control_tick 확인
→ Pi가 충분한 여유 시간(lead time)을 둔 apply_tick 생성
→ STM32의 크기가 제한된 queue에 저장
→ 같은 apply_tick에 좌우 setpoint를 한 번에 적용
~~~

다음 값은 양팔 및 장시간 실기 시험 후 최종 확정한다.

- control loop 주기
- 최소 apply lead tick
- heartbeat 제한 시간
- setpoint queue 크기
- queue low-watermark
- 감속 정지 시간

## 5. 관절 단위와 보정(calibration)

- 전송 위치: 부호 있는 micro-radian(`int32`, µrad)
- 전송 속도: 부호 있는 micro-radian/second(`int32`)
- 전송 가속도: 부호 있는 micro-radian/second²(`int32`)
- 전압: millivolt(`uint16`)
- 부하: STS raw feedback와 정규화 값의 관계는 이후 단계에서 확정

Raspberry Pi는 STS3215 raw 위치를 보내지 않는다. STM32가 보정 정보에 기록된 방향 부호, 원점과 안전 raw 범위를 사용해 관절 단위를 서보 raw 단위로 바꾸고 마지막 안전 제한을 적용한다.

Pi와 STM32는 `HELLO` 단계에서 `calibration_hash`를 비교한다. 값이 다르면 `ARMING`을 거부한다.

## 6. Setpoint를 한 번에 적용하는 규칙

`SETPOINT_BATCH` frame 하나에는 좌우 각 6개 actuator의 목표가 들어간다. 한 팔만 움직일 때도 반대쪽 목표를 현재 Hold 목표로 채운다.

v1 payload 구조:

~~~text
uint32 apply_tick_ms
uint8  sample_count       # 1~9, 512-byte frame 제한
uint8  arm_mask           # bit0=left, bit1=right
uint16 reserved           # 반드시 0
for each sample:
    uint32 tick_offset_ms
    int32  left_position_urad[6]
    int32  right_position_urad[6]
~~~

현재 단일 팔 초기 구동 펌웨어는 `arm_mask=1`만 허용하고, 존재하지 않는 오른팔 목표 6개가 모두 0인지 검사한다. 양팔 통합 시에는 두 팔의 현재 Hold 목표를 모두 포함하는 규칙으로 확장한다.

초기 검증 단계의 `SETPOINT_STATUS.status` 값:

- `0`: queue가 명령을 정상 접수
- `1`: payload 또는 적용 시각 형식 오류
- `2`: `ACTIVE` 상태가 아니거나 stop latch 상태
- `3`: 관절각 변환 실패 또는 raw limit 위반
- `4`: 지원하지 않는 팔 위치(slot)
- `5`: 전체 검증은 통과했지만 실행하지 않는 validation-only 상태
- `6`: 실행 완료. `detail`은 최대 raw 위치 오차이며 최댓값은 255
- `7`: servo bus 설정, 쓰기 또는 최종 읽기 실패
- `8`: Heartbeat, `HOLD` 또는 `SAFE_STOP`으로 실행 중단

`flags.bit0=1`이면 packet 전체를 검사만 하고 실행하지 않는다. 현재 단일 팔 실행기는 `flags.bit0=0`과 `sample_count=1`만 실행한다. 여러 sample을 queue에 넣고 보간하는 기능은 이후 실시간 제어 단계에서 활성화한다.

- Packet 전체가 유효할 때만 queue에 반영한다.
- 일부 관절만 따로 반영하지 않는다.
- Integer 전송 형식에는 NaN이 존재하지 않는다.
- 단위 변환 overflow, limit 위반 또는 불연속 setpoint가 있으면 packet 전체를 거부한다.

## 7. MCU 상태 머신

~~~text
BOOT
  → SAFE_DISABLED
  → ARMED
  → ACTIVE
  → HOLD

어느 상태에서든 조건에 따라:
  → FAULT
  → ESTOPPED
~~~

- `SAFE_DISABLED`: 통신과 상태값 읽기는 가능하지만 actuator 명령은 금지
- `ARMED`: 장치 상태와 설정 검사를 통과했지만 setpoint 실행은 아직 금지
- `ACTIVE`: 제한된 setpoint 실행 허용
- `HOLD`: 감속 정지한 뒤 현재 위치 유지
- `FAULT`: 원인을 제거하고 명시적으로 `CLEAR_FAULT`를 보내기 전까지 잠금 유지
- `ESTOPPED`: 물리 E-stop 입력을 해제하고 정해진 복구 절차를 수행할 때까지 잠금 유지

전원 인가, VCP 재연결 또는 Pi process 재시작만으로 `ACTIVE` 상태가 되지 않는다.

## 8. 정지 명령 구분

- `HOLD`: 계획된 일시 정지 또는 짧은 통신 이상
- `SAFE_STOP`: Pi가 요청하는 감속 정지이며 물리 E-stop이 아님
- `DISABLE`: torque 명령 비활성화 요청
- 물리 E-stop: 독립 입력과 전원 계통으로 처리하고 `FAULT_REPORT`로만 상태 보고

Serial message 이름으로 `ESTOP`을 사용하지 않는다. Software packet이 물리 E-stop과 같은 수준의 안전을 보장한다는 오해를 막기 위해서다.

## 9. Fault code 범위

| 범위 | 분류 |
|---|---|
| `0x0000` | fault 없음 |
| `0x0100–0x01FF` | 상위 제어기 연결 또는 heartbeat |
| `0x0200–0x02FF` | framing, CRC 또는 protocol |
| `0x0300–0x03FF` | setpoint queue 또는 적용 시각 |
| `0x0400–0x04FF` | 관절 위치, 속도 또는 가속도 제한 |
| `0x0500–0x05FF` | STS 서보 응답, 과부하 또는 온도 |
| `0x0600–0x06FF` | 전원 또는 전압 |
| `0x0700–0x07FF` | watchdog 또는 물리 E-stop |
| `0xFF00–0xFFFF` | 펌웨어 내부 fault |

세부 fault 번호는 펌웨어에 넣기 전에 기계가 읽을 수 있는 별도 manifest로 고정한다.

## 10. 검증 항목

구현 전 확인:

~~~bash
python3 tools/validate_protocol_manifest.py
~~~

펌웨어 단계 확인:

- 임의 byte stream에서 구분값을 찾아 frame 경계를 다시 맞춤
- 잘린 frame, 제한보다 큰 frame, 알 수 없는 version 거부
- CRC bit가 바뀐 오류 검출
- 중복 명령을 한 번만 실행
- 오래됐거나 순서가 뒤바뀐 setpoint 거부
- queue overflow/underflow fault 처리
- heartbeat가 끊기면 정지
- config hash가 다르면 `ARMING` 거부
- 한 팔에서 서보 fault가 발생하면 양팔 동시 정지
