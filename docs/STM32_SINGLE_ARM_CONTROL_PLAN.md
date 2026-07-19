# STM32 단일 팔 제어 계획

## 범위

이 계획의 진행률은 전체 로봇 프로젝트가 아니라 다음 목표만 추적한다.

> NUCLEO-G474RE 한 대가 정상 SO-ARM101 한 팔의 STS3215 여섯 개를 안전하게 조회하고, 제한된 setpoint를 실행하며, 호스트 통신 이상 시 정해진 안전 상태로 전환한다.

카메라, MoveIt, Pick and Place, 왼팔과 양팔 동기화는 이 진행률에 포함하지 않는다. 단, 이후 양팔 확장을 막지 않도록 팔별 설정과 공통 코어의 경계는 유지한다.

## 진행 현황

| ID | 단계 | 상태 | 완료 기준 |
|---|---|---|---|
| SA-00 | 필수 인터페이스·안전 선행조건 | PARTIAL | 실제 보드 revision, UART 신호 전압, 배선, 오른팔 ID/range 확인 |
| SA-01 | 하드웨어 독립 actuator core | PASS | host build, protocol/safety/queue test 통과 |
| SA-02 | NUCLEO-G474RE HAL/FreeRTOS 프로젝트 | NOT STARTED | boot 후 무동작 `SAFE_DISABLED`, VCP diagnostics |
| SA-03 | STS3215 read-only bus | NOT RUN | ID 1~6 ping 및 feedback 반복 read, torque command 없음 |
| SA-04 | calibration·limit 적용 | NOT RUN | joint sign/zero/raw safe range 적용, hash 일치 확인 |
| SA-05 | 단일 관절 저속 동작 | NOT RUN | 각 관절 개별 제한 이동, cancel/timeout/limit 시험 |
| SA-06 | 6축 setpoint 실행 | NOT RUN | bounded queue, 공통 tick, feedback와 반복 trajectory |
| SA-07 | 호스트 링크·fault 시험 | NOT RUN | heartbeat loss, CRC 오류, stale setpoint, 재연결 시험 |

## 생략할 수 없는 선행조건

### 1. 보드·배선 확인

- NUCLEO 보드의 MB1367 revision을 실제 PCB 표기에서 확인한다.
- STLINK-V3E VCP의 기본 `LPUART1 PA2/PA3` 경로를 호스트 링크로 사용한다.
- 별도 `USART1 PC4/PC5` 경로를 단일 servo bus로 사용한다.
- Waveshare Bus Servo Adapter (A)는 UART 모드 점퍼 `A`로 설정한다.
- 제조사 문서의 표기대로 adapter `RX↔MCU RX`, `TX↔MCU TX`, `GND↔GND`를 연결한다.
- adapter UART 핀의 실제 idle voltage를 멀티미터 또는 logic analyzer로 확인한 뒤 NUCLEO에 연결한다.
- NUCLEO와 servo adapter는 공통 신호 GND만 연결하고, servo 12 V를 NUCLEO 전원 핀에 연결하지 않는다.

UART의 `RX↔RX`, `TX↔TX` 표기는 일반적인 교차 연결과 반대이므로 임의로 바꾸지 않고 adapter 실크와 공식 회로를 기준으로 확인한다.

### 2. 오른팔 기준선

실제 이동 전에 최소한 다음 값이 필요하다.

- servo ID 1~6 응답
- ID와 관절 이름 매핑
- 각 관절에서 raw 값이 증가하는 물리 방향
- 현재 raw 위치
- 충돌과 케이블 장력을 고려한 보수적 raw min/max
- position/speed/load/voltage feedback 안정성
- 전원 인가 시 비명령 동작 없음

측정 전에는 joint unit을 raw servo position으로 변환하지 않는다.

### 3. 개발 도구

Windows에서는 ST의 `STM32CubeIDE` 설치를 권장한다. 이 한 패키지로 STM32용 GNU Arm compiler, Cube 기반 설정, ST-LINK build/debug/flash 경로를 확보한다. 설치 후 다음을 확인한다.

1. NUCLEO를 CN1 ST-LINK USB로 연결한다.
2. Windows 장치 관리자에 ST-LINK와 Virtual COM Port가 나타나는지 확인한다.
3. CubeIDE에서 `NUCLEO-G474RE` 보드를 선택할 수 있는지 확인한다.
4. 빈 프로젝트를 build하고 ST-LINK로 flash/debug할 수 있는지 확인한다.
5. 필요한 경우 CubeIDE의 firmware package manager에서 STM32CubeG4 패키지를 설치한다.

별도 `STM32CubeProgrammer`는 flash 자동화나 보드 연결 진단이 필요할 때 추가한다. 초기 개발에는 CubeIDE에 포함된 programmer 경로로 충분하다.

## 구현 순서

### SA-01 — Portable core

- COBS + CRC-32C frame
- protocol version/message/length 검증
- delimiter 기반 stream 재동기화
- 명시적 `ARM → ENABLE`
- heartbeat timeout 시 `HOLD`
- latched `FAULT`와 physical `ESTOPPED`
- 6축 setpoint batch 전체 검증 후 원자적 queue 반영

### SA-02 — Board integration

- CubeMX generated startup/HAL 경계
- LPUART1 VCP RX DMA와 TX
- USART1 servo bus RX/TX와 timeout
- FreeRTOS task: `host_rx`, `control`, `servo_bus`, `diagnostics`
- hardware timer 기반 control tick
- ISR에서는 byte 이동과 event 기록만 수행하고 frame parsing과 servo transaction은 task에서 수행

### SA-03 — Read-only servo discovery

첫 실기 펌웨어는 위치 명령을 구현하지 않는다.

- torque enable/write API 비활성
- ID 1~6 ping
- model/firmware 정보가 가능하면 기록
- position, speed, load, voltage 반복 read
- packet error, timeout, bus turnaround 측정
- 잘못된 ID가 silent인지 확인

### SA-04~SA-05 — Calibration and limited motion

- 측정한 sign/zero/raw limit을 별도 configuration으로 생성
- firmware에 calibration hash 포함
- 처음에는 servo 한 개만 연결하거나 팔을 안전 자세로 지지
- 현재 위치 주변의 아주 작은 저속 목표만 허용
- 각 관절을 독립 검증한 뒤에만 sync write 활성화

### SA-06~SA-07 — Full single-arm control

- 6축 sync write/read
- timestamped setpoint buffer
- underflow/overflow/stale setpoint fault
- VCP heartbeat loss와 reconnect
- 반복 trajectory와 장시간 bus 시험

## 초기 안전 규칙

- reset, flash, VCP reconnect 후 항상 `SAFE_DISABLED`
- servo 발견만으로 torque를 활성화하지 않음
- calibration이 없거나 hash가 다르면 ARMING 거부
- host heartbeat 없이 `ACTIVE` 진입 금지
- queue 전체가 유효하지 않으면 joint 하나도 반영하지 않음
- fault 이후 자동 재활성화 금지
- 물리 E-stop 설치 전에는 저속 벤치 시험만 수행

heartbeat timeout, control rate, queue size와 stop profile의 최종 수치는 read-only bus 및 저속 정지 측정 후 확정한다.
