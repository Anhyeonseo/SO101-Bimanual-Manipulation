# ADR-0010: 하나의 bringup 진입점에서 backend를 독점 선택

- 상태: 채택
- 날짜: 2026-07-24

## 상황

현재 MoveIt bringup은 mock과 Isaac용 launch가 분리되어 있고 STM32 bridge도
독립 launch로 실행된다. 세 backend는 최종적으로 같은 `/joint_states`와
왼팔 arm/gripper Action 이름을 사용하므로 둘 이상을 동시에 실행하면
상태와 명령 소유권이 불명확해진다.

ROS 2 graph는 같은 topic publisher를 여러 개 허용하며, 잘못 실행된 두
backend를 launch condition만으로 완전히 막을 수 없다. STM32 serial도 현재
일반 `serial.Serial` open만 사용하므로 별도의 host process에 대한 명시적인
독점 보장이 없다.

## 결정

공식 MoveIt 실행 진입점을 다음 하나로 통합한다.

```text
ros2 launch so101_bringup so101_moveit.launch.py backend:=mock
ros2 launch so101_bringup so101_moveit.launch.py backend:=isaac
ros2 launch so101_bringup so101_moveit.launch.py backend:=stm32
```

- `backend` 허용값은 `mock`, `isaac`, `stm32` 세 개뿐이다.
- 값을 생략하면 실제 장치를 열지 않는 `mock`을 기본값으로 사용한다.
- 알 수 없는 값, 빈 값 또는 여러 backend 지정은 node를 시작하기 전에
  launch error로 종료한다.
- 통합 launch는 backend provider를 정확히 하나만 포함하고 MoveIt, RViz,
  robot state publisher와 static TF의 공통 구성을 한 번만 실행한다.
- 기존 `mock_moveit.launch.py`와 `isaac_moveit.launch.py`는 통합 launch에
  고정 backend 값을 넘기는 호환 wrapper로 바꾼다.
- STM32 MoveIt backend는 통합 bringup을 공식 경로로 사용한다. 독립
  `single_arm_bridge` launch는 READ_ONLY 진단 용도로만 남기고 MoveIt Action을
  동시에 제공하는 경로로 사용하지 않는다.

## 실행 중 독점 보장

통합 launch가 시작하는 backend guard는 현재 ROS domain에서 SO-101
backend lease를 하나만 보유한다.

- runtime lock은 사용자 runtime directory 아래 고정 파일에 non-blocking
  exclusive lock으로 구현한다.
- lock에는 backend 이름, process ID와 ROS domain을 진단 정보로 기록한다.
- 다른 통합 bringup이 이미 lock을 보유하면 두 번째 실행은 backend node와
  MoveIt을 시작하지 않고 실패한다.
- 정상 종료와 오류 종료에서 운영체제가 lock을 자동 회수할 수 있도록 file
  descriptor lifetime으로 소유한다.
- backend 변경은 기존 bringup을 완전히 종료한 뒤 새 process로 시작한다.
- 종료된 backend의 goal은 새 backend로 복원하거나 재전송하지 않는다.

STM32 backend는 추가로 serial port를 POSIX exclusive mode로 열어 같은
device를 다른 host process가 동시에 열지 못하게 한다. backend guard는 ROS
interface 충돌을 막고 serial exclusive open은 실제 장치 소유권을 보호한다.

## Backend별 구성

| backend | command/action owner | `/joint_states` owner | serial open |
|---|---|---|---|
| `mock` | `ros2_control` mock controllers | joint state broadcaster | 금지 |
| `isaac` | `so101_isaac_bridge` | `so101_isaac_bridge` | 금지 |
| `stm32` | `single_arm_bridge` Action adapter | `single_arm_bridge` | 허용 |

STM32에서는 `allow_motion=false`가 기본값이다. 이 값은 `backend:=stm32`를
선택했다는 이유만으로 자동으로 true가 되지 않는다.

## 구현 순서

1. backend 값 validator와 launch 단위 test
2. backend guard와 lock contention test
3. mock/Isaac 호환 wrapper 및 regression
4. STM32 Action adapter 구현 후 `stm32` branch 연결
5. POSIX serial exclusive open test
6. READ_ONLY에서 실제 STM32 통합 bringup 검증

`stm32` Action adapter가 구현되기 전에는 통합 MoveIt launch의
`backend:=stm32` 선택을 명시적인 미구현 오류로 거부한다. custom topic만
있는 기존 bridge를 완성된 MoveIt backend처럼 노출하지 않는다.

## 검증 기준

- 각 backend 선택에서 action owner와 `/joint_states` owner가 각각 하나
- 두 번째 bringup 실행은 provider node를 만들기 전에 실패
- 잘못된 backend 값에서 serial open 0회
- `mock`과 `isaac` 선택에서 serial open 0회
- `stm32`, `allow_motion=false`에서 motion command 0회
- backend 종료 후 stale goal 재개 0회
- 기존 mock과 Isaac vertical slice regression PASS

## 영향

사용자는 backend마다 다른 전체 launch 명령을 외울 필요가 없다. 호환
wrapper는 기존 작업 기록을 재현하기 위해 유지하지만 새 문서와 시험은
통합 진입점을 기준으로 한다. runtime lock만으로 모든 임의 ROS node를 막을
수는 없으므로 public action server를 구현하는 project backend는 guard를
통과한 공식 bringup에서만 실행한다.
