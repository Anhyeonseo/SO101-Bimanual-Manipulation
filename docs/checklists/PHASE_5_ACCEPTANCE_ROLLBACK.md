# 단계 5 — Acceptance와 rollback 기준

- 상태: **APPROVED — 기준 승인, motion 미승인**
- 작성일: 2026-07-24
- 승인일: 2026-07-24
- 대상: 왼팔 MoveIt → STM32 B안 backend
- 실제 motion 허용: **아니오**

이 문서는 단계 5의 PASS/FAIL과 실패 후 복구 방식을 고정한다. 문서 승인은
실제 servo motion 승인이 아니다. 모든 hardware motion은 READ_ONLY gate와
사용자의 별도 명시 승인을 요구한다.

## 판정 원칙

- 필수 안전 항목은 한 번이라도 실패하면 단계 5를 PASS로 처리하지 않는다.
- firmware가 명령을 접수한 상태와 실제 실행 완료를 구분한다.
- `SETPOINT_STATUS=0`은 접수일 뿐 성공이 아니다.
- 초기 hardware 성공은 `SETPOINT_STATUS=6`과 최종 위치 오차를 함께 본다.
- 실패 후 자동 retry, 자동 fault clear와 stale goal 재전송을 금지한다.
- 실제 측정값, 실행 환경과 repository commit이 없는 구두 판정은 PASS 근거로
  사용하지 않는다.

## A — Static/unit acceptance

hardware를 연결하지 않고 다음 항목이 모두 PASS해야 한다.

| 항목 | PASS 기준 |
|---|---|
| joint contract | 왼팔 arm 5개와 gripper 1개 이름·순서 일치 |
| invalid number | NaN/Inf goal 100% reject, serial write 0회 |
| joint set | unknown, duplicate, missing joint 100% reject |
| trajectory shape | 최초 milestone은 정확히 1 point만 허용 |
| time | 지원 범위 밖 duration과 잘못된 timestamp 100% reject |
| safe range | host/firmware 범위 밖 goal 100% reject, clamp 0회 |
| calibration | hash mismatch에서 ARM/ENABLE과 motion 0회 |
| cancel state | accepted goal만 cancel 가능, terminal state 정확 |
| reconnect | stale goal 재전송·재개 0회 |
| backend value | `mock`, `isaac`, `stm32` 외 값은 provider 시작 전 실패 |
| duplicate backend | 두 번째 guard는 provider와 serial open 전에 실패 |

package unit test와 launch test가 모두 통과하고 test result에 failure가 없어야
한다.

## B — Backend exclusivity acceptance

| 선택 | Action owner | `/joint_states` owner | serial open |
|---|---:|---:|---:|
| `mock` | 정확히 1 | 정확히 1 | 0 |
| `isaac` | 정확히 1 | 정확히 1 | 0 |
| `stm32` | 정확히 1 | 정확히 1 | 정확히 1 |

- 두 개의 통합 bringup을 동시에 시작하면 두 번째 실행은 실패해야 한다.
- STM32 device를 다른 process가 열고 있으면 POSIX exclusive open이 실패해야
  한다.
- backend 변경은 기존 process가 완전히 종료되고 lock이 반환된 뒤에만
  가능하다.
- backend 변경 후 이전 Action goal의 feedback, result 또는 command가 새
  backend에서 발생하면 FAIL이다.

## C — Hardware READ_ONLY acceptance

Raspberry Pi 5에서 `allow_motion=false`로 다음을 확인한다.

| 항목 | PASS 기준 |
|---|---|
| serial 후보 | 정확히 1개 |
| firmware | `0x00020700` |
| protocol | version 1, joint count 6 |
| calibration | `0x3DB42B48` |
| state | 6개 joint position이 모두 존재 |
| name/order | project 왼팔 6개 contract와 정확히 일치 |
| position | 모든 raw가 각 firmware safe range 안 |
| feedback rate | 60초 측정에서 `4.5..5.5 Hz` |
| heartbeat | 측정 중 count 증가, timeout 0회 |
| rejected frame | 측정 구간 delta 0 |
| motion | servo motion command 0회 |

absolute rejected-frame 누적값이 아니라 시험 시작과 종료 사이의 delta를
사용한다. READ_ONLY가 PASS하기 전에는 motion command를 제시하지 않는다.

## D — 제한 motion acceptance

physical E-stop이 없으므로 저속·무부하 벤치 시험만 허용한다. 작업 공간,
전원 차단 수단, physical q0와 backend 단독 실행을 사용자가 확인한 뒤 별도
motion 승인을 받아 한 항목씩 실행한다.

### 정상 완료

초기 단일 point goal은 다음을 모두 만족해야 PASS다.

- target이 firmware verified safe range 안
- duration이 protocol 실행 범위 `300..2000 ms` 안
- 최초 응답 `SETPOINT_STATUS=0`
- 최종 응답 `SETPOINT_STATUS=6`
- `detail` 최대 최종 오차 `20 raw` 이하
- Action terminal state `SUCCEEDED`
- 완료 후 feedback이 target 근처에서 안정
- fault, stop latch와 load/current protection event 0회
- 명령하지 않은 joint의 체계적인 이동 0회

`20 raw`는 기존 무부하 실기 최대 `17~19 raw`와 약 `0.03 rad` goal
tolerance를 근거로 한 초기 기준이다. firmware status `6`은 오차 크기와
무관하게 완료를 보고하므로 `detail > 20`이면 Action adapter는 성공으로
처리하지 않고 goal을 실패시켜야 한다.

### Cancel

- cancel 요청을 받은 Action은 `CANCELED`로 종료
- STM32는 실행 중단 status `8` 또는 확인 가능한 stop-latched 상태 보고
- cancel 뒤 추가 setpoint 0회
- cancel goal의 늦은 `SUCCEEDED` result 0회
- 명시적 recovery 전 새 goal 수락 0회

### SAFE_STOP과 통신 단절

- SAFE_STOP 요청 후 stop latch 확인
- Action은 `ABORTED`로 종료하고 원인을 기록
- status `7`, `8`, `9`, heartbeat timeout 또는 serial failure를 성공으로
  변환하지 않음
- reconnect 후 이전 goal 재개·재전송 0회
- 사용자 확인과 명시적 recovery 전 ARM/ENABLE 0회

### Gripper

- 승인된 mapping plan의 sample과 verified safe range만 사용
- `backend:=stm32`에서 MoveIt planning limit,
  Action adapter range reject와 firmware raw limit 모두 활성
- 기존 MoveIt `open=1.91986 rad` hardware 실행 0회
- `hardware_safe_open`은 실측 mapping이 확정된 뒤에만 PASS 대상에 추가

## E — MoveIt end-to-end acceptance

다음 결과를 한 실행 기록 안에서 확인한다.

- MoveIt controller 이름과 Action type이 mock/Isaac/STM32에서 동일
- named `home`과 representative arm goal이 verified safe range 안에서 성공
- hardware-safe gripper goal 성공
- invalid/out-of-range goal은 planning 또는 Action 단계에서 실패
- cancel, SAFE_STOP와 communication loss가 올바른 Action result로 전파
- 실제 goal duration, result latency, final error raw와 feedback rate 기록

초기 B안의 단계 5는 single-point hardware goal만 PASS 대상으로 한다.
multi-point MoveIt trajectory는 firmware queue/streaming 계약을 별도로
구현하기 전 완료 조건에 포함하지 않는다.

## F — Regression과 기록 acceptance

- controller/MoveIt 공통 source가 바뀌면 mock regression PASS
- Isaac 관련 source가 바뀌면 Isaac vertical slice regression PASS
- 기존 firmware/calibration source가 바뀌면 protocol, calibration hash와
  host test를 다시 수행
- 실행 환경, commit, 명령, 기대값, 실제값과 판정을
  `docs/test-results`에 기록
- source가 바뀌지 않은 기존 PASS 시험은 이유 없이 반복하지 않음

## 즉시 FAIL 조건

다음 중 하나는 해당 시험을 즉시 중단하고 단계 5를 PARTIAL로 유지한다.

- 예상하지 않은 joint 또는 방향으로 움직임
- safe range 밖 target 전송 또는 raw feedback
- backend/action owner 중복
- calibration/version mismatch 상태에서 ARM 또는 motion 발생
- status `7` 또는 `9`, 의도하지 않은 status `8`, fault, stop latch 또는
  heartbeat timeout
- final error `20 raw` 초과
- cancel/SAFE_STOP 후 motion 지속 또는 stale goal 재개
- 비정상 소음, 진동, 걸림, 충돌 또는 사용자 위험 판단

## Rollback 단계

### R0 — Goal validation 실패, motion 0

1. 해당 goal을 거부하고 입력과 이유를 기록한다.
2. 자동 수정, clamp 또는 retry를 하지 않는다.
3. static/unit 원인을 수정하기 전 hardware gate로 진행하지 않는다.

### R1 — Action/trajectory 실패, 통신 유지

1. 새 command 전송을 중지한다.
2. `SAFE_STOP`을 요청하고 stop latch를 확인한다.
3. Action을 `ABORTED` 또는 cancel이면 `CANCELED`로 종료한다.
4. 현재 feedback, firmware status, request sequence와 log를 보존한다.
5. `/clear_fault`, ARM/ENABLE과 goal 재전송을 하지 않는다.

### R2 — 통신 단절, servo fault 또는 보호 event

1. 새 command 전송을 중지한다.
2. 통신이 남아 있으면 `SAFE_STOP`을 한 번 요청한다.
3. acknowledgement가 없으면 software 정지를 신뢰하지 않는다.
4. 사용자가 준비한 물리 전원 차단 수단으로 servo power를 분리한다.
5. process를 종료하고 자동 reconnect/recovery를 금지한다.

### R3 — 충돌 또는 사람·장비 위험

1. software response를 기다리지 않고 즉시 servo power를 차단한다.
2. 로봇을 손으로 억지로 복구하거나 다시 energize하지 않는다.
3. 작업 공간과 기구 상태를 사용자가 확인할 때까지 시험을 중단한다.

`SAFE_STOP`은 software 감속 정지이며 물리 E-stop이 아니다.

## Software 복귀 기준

- 통합 STM32 MoveIt bringup을 종료한다.
- 기존 `single_arm_bridge`를 `allow_motion=false` READ_ONLY로만 실행한다.
- calibration, firmware safe limit과 verified firmware를 변경하지 않는다.
- mock/Isaac backend는 실제 serial을 열지 않는 독립 검증 경로로 유지한다.
- Git 복구는 사용자가 검토한 commit 단위로 수행하며 `git reset --hard`,
  `git clean`과 파일 강제 삭제를 사용하지 않는다.

## Recovery 승인 gate

rollback 뒤 재시도는 다음을 모두 만족해야 한다.

1. 원인과 영향 범위 기록
2. hardware 상태와 작업 공간 사용자 확인
3. 수정 source의 static/unit test PASS
4. `allow_motion=false` READ_ONLY 전체 재확인
5. 이전 goal과 pending command가 없음을 확인
6. 사용자의 새로운 motion 승인

fault clear 성공만으로 자동 재시작하지 않는다.

## 단계 5 최종 PASS

A~F의 해당 항목이 모두 PASS하고 즉시 FAIL 항목이 0회여야 한다. rollback을
실제로 유발한 시험은 원인 수정, READ_ONLY 재확인과 사용자의 새 승인 뒤
처음부터 다시 검증한다. 단계 5 PASS는 actual mechanical full range, 양팔,
payload Pick and Place 또는 multi-point streaming까지 보장하지 않는다.

이 기준은 2026-07-24 사용자가 승인했다. Gate 5A의
`acceptance criteria와 rollback 승인`은 PASS다. 이 승인만으로 실제
motion은 허용되지 않는다.
