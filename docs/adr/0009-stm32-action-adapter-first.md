# ADR-0009: STM32 백엔드는 기존 bridge의 표준 Action 확장부터 구현

- 상태: 채택
- 날짜: 2026-07-24

## 상황

단계 4에서 MoveIt의 왼팔 표준 controller contract를 mock과 Isaac에서
검증했다. 단계 5에서는 같은 contract를 실제 STM32 backend에 연결해야
한다.

현재 `single_arm_bridge`는 Python으로 구현되어 있으며 다음과 같이 실제
장치에서 검증한 기능을 소유한다.

- serial device 단독 소유
- protocol v1, COBS와 CRC-32C
- heartbeat와 feedback
- calibration hash 검사
- firmware safe range 적용
- fault latch와 `SAFE_STOP`

현재 STM32 executor는 `sample_count=1`인 setpoint만 실행하고 약 20 ms
주기로 내부 보간한다. 따라서 PC가 고주기 position command를 계속 쓰는
일반적인 `ros2_control` `SystemInterface`를 바로 연결하려면 firmware와
transport의 실행 주기 및 시간축 계약을 먼저 다시 설계해야 한다.

## 결정

단계 5의 첫 실제 STM32 backend는 기존 `single_arm_bridge`의 검증된
transport를 재사용하는 **B안**으로 구현한다.

```text
MoveIt
→ FollowJointTrajectory / ParallelGripperCommand
→ single_arm_bridge의 STM32 Action adapter
→ 기존 serial transport
→ STM32
```

- arm public interface는
  `/left_arm_controller/follow_joint_trajectory`를 사용한다.
- gripper public interface는
  `/left_gripper_controller/gripper_cmd`를 사용한다.
- MoveIt과 상위 task는 `/joint_command`, raw servo position과 binary
  protocol을 알지 못한다.
- Action adapter와 기존 transport는 하나의 STM32 backend 경계 안에 두고
  serial owner를 하나로 유지한다.
- 최초 hardware milestone은 verified safe range 안의 single-point arm
  goal로 제한한다.
- cancel, timeout, 통신 단절과 action failure는 `SAFE_STOP` 및 명시적인
  Action result로 연결한다.
- gripper mapping이 확정되기 전에는 MoveIt의 `open=1.91986 rad` 값을
  STM32에 전달하지 않는다.
- `allow_motion=false`를 기본값으로 유지하며 READ_ONLY gate가 PASS하기
  전에는 motion goal을 거부한다.

이 결정은 장기적으로 `ros2_control`을 배제하지 않는다. 다음 조건을
충족하면 기존 bridge를 C++ `ros2_control SystemInterface`로 대체하는
**A안**을 별도 ADR에서 재검토한다.

1. STM32가 다중 sample queue 또는 명시적인 streaming contract를 지원
2. controller update rate와 STM32 apply/interpolation rate 계약 확정
3. non-blocking serial read/write와 cancel/timeout 동작 검증
4. position/velocity state의 단위, timestamp와 freshness 계약 확정
5. protocol, calibration과 safety 로직을 중복 구현하지 않는 공유 방법 확정
6. 단일 팔 B안의 지연, jitter와 trajectory error 측정 결과가 C++ 전환
   필요성을 뒷받침

## 이유

- 이미 실제 장치에서 확인한 통신과 safety path를 그대로 사용할 수 있다.
- 단계 5에서 새 C++ transport와 hardware plugin을 동시에 검증하는 위험을
  피한다.
- 현재 병목은 Python 계산보다 serial protocol과 STM32의 single-point
  executor 계약에 가깝다.
- MoveIt에는 처음부터 표준 Action만 노출하므로 향후 A안으로 교체해도
  상위 interface를 유지할 수 있다.

## 영향

- Python bridge는 고주기 servo loop가 아니라 STM32에 goal을 전달하고
  상태를 감시하는 역할로 한정한다.
- multi-point trajectory를 임의로 빠르게 분할해 전송하지 않는다. 실행
  시간축, queue와 cancel semantics가 검증된 뒤 확장한다.
- B안과 향후 A안을 동시에 실행하지 않는다.
- 실제 성능은 언어만으로 추정하지 않고 지연, jitter, feedback rate와
  final error를 측정해 판단한다.
- ADR-0002의 장기 trajectory 시간축 원칙은 유지한다. 현재 B안은 그
  원칙을 완전 구현하기 전의 단일 팔 검증 단계다.

## 종료 및 전환 조건

B안은 다음을 만족할 때 단계 5의 첫 backend로 완료 처리할 수 있다.

- standard arm action의 success, cancel과 failure 결과 검증
- firmware safe range 밖 명령 100% 거부
- backend exclusivity와 serial single-owner 검증
- reconnect 후 stale goal 자동 재개 0회
- hardware-safe gripper mapping 검증
- 측정 결과와 실행 환경을 `docs/test-results`에 기록

A안 전환은 위 완료 조건과 결정 절의 여섯 재검토 조건을 근거로 별도
작업에서 수행한다. 단순히 C++이 더 빠를 것이라는 추정만으로 실제
hardware backend를 교체하지 않는다.
