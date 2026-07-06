# Dual Arm Feetech STS3215 디버깅 정리

## 1. 현재 프로젝트 상태

양팔 로봇팔을 Ubuntu 노트북에서 Python serial packet으로 제어 중이다. 아직 ROS2로 넘어가기 전이며, 하위 제어는 직접 Feetech STS/SCS serial bus protocol packet을 만들어 `/dev/ttyACM0`, `/dev/ttyACM1`로 전송하는 구조다.

현재 목표는 다음과 같다.

- 왼팔/오른팔을 각각 안정적으로 구동
- 양팔을 같은 시간축에서 준동시 제어
- 이후 ROS2 node로 시스템화
- 최종적으로 `/joint_states`, raw command, e-stop, trajectory command 구조로 확장

---

## 2. 하드웨어 구성

### 포트

```text
LEFT_PORT  = /dev/ttyACM0
RIGHT_PORT = /dev/ttyACM1
BAUDRATE   = 1000000
```

### 서보

- Feetech STS3215 계열 serial bus servo
- baudrate: `1000000`
- protocol: STS/SCS 계열 packet
- packet header: `FF FF`

### 기본 ID 매핑

```python
JOINTS = {
    "base_yaw": 1,
    "shoulder_pitch": 2,
    "elbow_pitch": 3,
    "wrist_pitch": 4,
    "wrist_roll": 5,
    "gripper": 6,
}
```

### 현재 임시 구성

왼팔 5번 모터가 고장 의심으로 분리되어 있어, 현재 안정 테스트 기준은 다음과 같다.

```python
LEFT_JOINTS = {
    "base_yaw": 1,
    "shoulder_pitch": 2,
    "elbow_pitch": 3,
    "wrist_pitch": 4,
    "gripper": 6,
}

RIGHT_JOINTS = {
    "base_yaw": 1,
    "shoulder_pitch": 2,
    "elbow_pitch": 3,
    "wrist_pitch": 4,
    "wrist_roll": 5,
    "gripper": 6,
}
```

즉 현재 테스트 기준은:

```text
왼팔: 5DOF, ID 5 wrist_roll 제외
오른팔: 6DOF
```

---

## 3. 사용 중인 주요 제어 주소

```python
INST_PING  = 0x01
INST_READ  = 0x02
INST_WRITE = 0x03

ADDR_TORQUE_ENABLE    = 40
ADDR_ACC              = 41
ADDR_PRESENT_POSITION = 56
```

move command는 `ADDR_ACC = 41`부터 acceleration, goal position, time, speed를 연속 write하는 방식으로 구성했다.

---

## 4. 문제 발생 흐름

### 초기 증상

처음에는 양팔을 같은 HOME pose 또는 같은 delta로 움직이게 했을 때 다음 문제가 있었다.

- 한 팔씩은 비교적 정상
- 두 팔을 같이 제어하면 오른팔 또는 왼팔이 이상하게 움직임
- 왼팔이 “뒤집히는” 현상 발생
- 일부 관절에서 overload error 발생
- 왼팔 특정 모터에서 연기 발생

### 중요한 관찰

처음에는 USB 허브, 전원, 동시 제어 문제가 의심됐지만, 이후 테스트를 통해 핵심 원인은 다음으로 좁혀졌다.

```text
1. 왼팔 기존 HOME 값이 실제 안전 자세와 맞지 않았음
2. 오른팔 기준 delta를 왼팔에 그대로 적용해서 왼팔이 반대 방향으로 말림
3. 왼팔 ID 5 wrist_roll 모터가 고장 또는 버스 방해 의심
4. 기존 left_home_pose.json이 위험한 pose였음
```

---

## 5. 왼팔 ID 5 문제

왼팔에서 연기가 발생한 뒤 전체 왼팔 bus response가 불안정해졌다. 이후 모터를 분리해가며 확인했다.

확인 결과:

```text
왼팔 ID 1: 정상
왼팔 ID 2: 정상 응답
왼팔 ID 3: 정상 응답
왼팔 ID 4: 정상 응답
왼팔 ID 5: 문제 의심, 분리
왼팔 ID 6: 정상 응답
```

처음에는 4번이 탄 것처럼 보였지만, 실제 bus 테스트 기준으로는 5번이 문제였고, 5번을 제외하면 1,2,3,4,6은 통신 가능했다.

현재 결론:

```text
왼팔 ID 5는 일단 물리적으로 분리하고, command/read/torque 대상에서도 제외한다.
```

---

## 6. 기존 왼팔 HOME 문제

기존 왼팔 HOME 값은 다음과 같았다.

```json
{
  "base_yaw": 113,
  "shoulder_pitch": 3544,
  "elbow_pitch": 3584,
  "wrist_pitch": 514,
  "wrist_roll": 1281,
  "gripper": 3650
}
```

하지만 실제 안전 자세에서 읽은 왼팔 현재 pose는 완전히 달랐다.

```json
{
  "base_yaw": 284,
  "shoulder_pitch": 3875,
  "elbow_pitch": 122,
  "wrist_pitch": 463,
  "gripper": 2967
}
```

특히 elbow 값이 심각하게 달랐다.

```text
기존 elbow_pitch HOME: 3584
현재 안전 pose elbow_pitch: 122
```

이 상태에서 기존 HOME으로 이동시키면 팔이 정상 pose로 가는 것이 아니라, 큰 raw 이동으로 인해 뒤집히거나 기구 한계에 걸릴 수 있다.

따라서 기존 `left_home_pose.json`은 폐기하고, 5DOF 기준 `left_home_pose_5dof.json`을 새 기준으로 사용한다.

---

## 7. 현재 사용 중인 HOME 파일

### left_home_pose_5dof.json

```json
{
  "base_yaw": 284,
  "shoulder_pitch": 3875,
  "elbow_pitch": 122,
  "wrist_pitch": 463,
  "gripper": 2967
}
```

### right_home_pose.json

```json
{
  "base_yaw": 110,
  "shoulder_pitch": 3465,
  "elbow_pitch": 3825,
  "wrist_pitch": 362,
  "wrist_roll": 1299,
  "gripper": 3553
}
```

---

## 8. 안정화된 delta

오른팔과 왼팔은 기구 방향과 raw 방향이 다르므로 같은 delta를 쓰면 안 된다. 현재 안정 테스트 기준 delta는 분리되어 있다.

### 왼팔 5DOF 테스트 delta

```python
LEFT_TEST_DELTA = {
    "base_yaw": 30,
    "shoulder_pitch": -40,
    "elbow_pitch": 60,
    "wrist_pitch": -30,
    "gripper": 0,
}
```

### 오른팔 6DOF 테스트 delta

```python
RIGHT_TEST_DELTA = {
    "base_yaw": 50,
    "shoulder_pitch": -250,
    "elbow_pitch": 270,
    "wrist_pitch": -180,
    "wrist_roll": 0,
    "gripper": 0,
}
```

---

## 9. 안정화된 속도/가속 설정

현재 안전 테스트 기준:

```python
HOME_SPEED = 120
HOME_ACC = 5
TEST_SPEED = 140
TEST_ACC = 6
```

이전보다 속도와 가속도를 낮췄고, STS3215의 하중/정밀도 한계를 고려해 무리한 명령을 피한다.

---

## 10. 테스트 결과

### 순차 dual control 결과

v2 기준으로 왼팔 5DOF + 오른팔 6DOF 순차 dual test를 수행했다.

최종 오차:

```text
=== LEFT TEST C ERROR FROM TARGET ===
base_yaw: 0
shoulder_pitch: -4
elbow_pitch: 13
wrist_pitch: -1
gripper: 0

=== RIGHT TEST C ERROR FROM TARGET ===
base_yaw: 1
shoulder_pitch: -4
elbow_pitch: 15
wrist_pitch: -2
wrist_roll: 0
gripper: 0
```

판정:

```text
순차 양팔 제어 정상
왼팔 새 HOME 기준 정상
오른팔 정상
오차는 STS3215 기준 양호
```

---

## 11. 준동시 dual write 테스트

ROS2로 넘어가기 전, Python에서 ROS2식 동시 제어를 흉내 내는 quasi-sync test를 수행했다.

기존 순차 방식:

```text
왼팔 전체 move_pose()
대기
오른팔 전체 move_pose()
```

quasi-sync 방식:

```text
base_yaw:       LEFT write -> RIGHT write
shoulder_pitch: LEFT write -> RIGHT write
elbow_pitch:    LEFT write -> RIGHT write
wrist_pitch:    LEFT write -> RIGHT write
wrist_roll:     RIGHT only
gripper:        LEFT write -> RIGHT write
```

초기 설정:

```python
DUAL_WRITE_GAP = 0.005
JOINT_PAIR_INTERVAL = 0.03
```

준동시 test 결과:

```text
=== LEFT QUASI-SYNC ERROR FROM TARGET ===
base_yaw: 0
shoulder_pitch: -4
elbow_pitch: 14
wrist_pitch: -1
gripper: 0

=== RIGHT QUASI-SYNC ERROR FROM TARGET ===
base_yaw: 0
shoulder_pitch: -6
elbow_pitch: 17
wrist_pitch: -2
wrist_roll: 0
gripper: 0
```

판정:

```text
준동시 dual write 정상
하드웨어/전원/통신은 양팔 준동시 제어를 버틸 수 있음
```

다만 왼쪽을 먼저 write하는 구조라 사람 눈에는 왼팔이 약간 먼저 출발하는 느낌이 있었다.

---

## 12. 미세 출발 차이 개선 방향

기존 quasi-sync 함수는 항상 left write 후 right write를 수행한다.

```python
left.move_raw(...)
time.sleep(DUAL_WRITE_GAP)
right.move_raw(...)
```

따라서 왼팔이 먼저 출발하는 것이 정상이다.

개선 방향:

```python
DUAL_WRITE_GAP = 0.001
JOINT_PAIR_INTERVAL = 0.02
WRITE_ORDER_MODE = "alternate"
```

alternate 방식:

```text
base_yaw:        LEFT -> RIGHT
shoulder_pitch:  RIGHT -> LEFT
elbow_pitch:     LEFT -> RIGHT
wrist_pitch:     RIGHT -> LEFT
wrist_roll:      RIGHT only
gripper:         RIGHT -> LEFT
```

이렇게 하면 한쪽이 항상 먼저 움직이는 느낌을 줄일 수 있다.

더 정교하게 하려면 추후 ROS2에서 left writer thread와 right writer thread를 분리한다.

---

## 13. ROS2 전환 판단

현재 기준으로 ROS2로 넘어갈 수 있는 수준까지 하위 제어는 검증됐다.

확인 완료:

```text
한 팔 단독 제어: 정상
순차 양팔 제어: 정상
준동시 양팔 제어: 정상
왼팔 5번 제외 시 왼팔 5DOF 정상
오른팔 6DOF 정상
```

아직 남은 조건:

```text
왼팔 ID 5를 교체하거나 정상화하면 왼팔도 6DOF로 복귀 가능
ROS2에서도 왼팔/오른팔 HOME과 direction sign은 반드시 분리해야 함
joint limit을 raw 기준으로 먼저 좁게 잡아야 함
```

---

## 14. ROS2 시스템 설계 권장 구조

처음부터 MoveIt2로 가지 말고, raw driver ROS2 node부터 만든다.

추천 단계:

```text
1단계: Python ROS2 raw driver node
2단계: /joint_states publish
3단계: /dual_arm/command_raw subscribe
4단계: e-stop 추가
5단계: raw <-> radian 변환 추가
6단계: URDF/RViz 연결
7단계: ros2_control 또는 MoveIt2 연결
```

### 초기 ROS2 node 구조

```text
dual_arm_driver_node
├── left serial bus: /dev/ttyACM0
├── right serial bus: /dev/ttyACM1
├── command timer: 10~20Hz
├── read timer: 5~10Hz
├── /dual_arm/command_raw subscriber
├── /joint_states publisher
└── /dual_arm/estop subscriber
```

### 권장 topic

```text
/dual_arm/command_raw
/joint_states
/dual_arm/estop
```

초기에는 관절별 topic을 만들지 말고, 양팔 목표를 하나의 message로 묶는 것이 좋다.

---

## 15. ROS2에서 동시 제어의 의미

ROS2로 간다고 물리적으로 완전히 같은 마이크로초에 명령이 나가는 것은 아니다. USB serial 포트가 2개이므로 실제 write는 순서가 있다.

그러나 제어 관점에서는 다음이 중요하다.

```text
하나의 dual-arm command 생성
같은 timestamp 기준으로 left/right target 계산
같은 control loop에서 양쪽 write
같은 duration으로 trajectory 실행
```

즉, ROS2에서 말하는 동시 제어는:

```text
두 팔이 같은 시간축의 trajectory를 따라가게 하는 것
```

이다.

---

## 16. ROS2 전환 시 가장 주의할 점

### 1. 왼팔/오른팔 sign 분리

오른팔 raw delta를 왼팔에 그대로 쓰면 다시 뒤집힐 수 있다.

```python
LEFT_SIGN = {
    "base_yaw": ..., 
    "shoulder_pitch": ..., 
    "elbow_pitch": ..., 
    "wrist_pitch": ..., 
    "wrist_roll": ..., 
    "gripper": ...,
}

RIGHT_SIGN = {
    "base_yaw": ..., 
    "shoulder_pitch": ..., 
    "elbow_pitch": ..., 
    "wrist_pitch": ..., 
    "wrist_roll": ..., 
    "gripper": ...,
}
```

### 2. raw <-> radian 변환

ROS는 joint 단위를 radian으로 쓰는 것이 일반적이다. 현재는 raw 0~4095를 사용 중이므로 변환 계층이 필요하다.

```python
raw = home_raw + sign * rad * raw_per_rad
```

### 3. joint limit

잘못된 command 하나로 다시 기구 한계까지 갈 수 있으므로, 초기에는 아주 좁은 raw limit을 둔다.

예:

```python
LEFT_LIMITS_RAW = {
    "base_yaw": (240, 330),
    "shoulder_pitch": (3800, 3950),
    "elbow_pitch": (80, 220),
    "wrist_pitch": (420, 510),
    "gripper": (2900, 3050),
}
```

실제 limit은 테스트하면서 확장한다.

### 4. read/write 주기 제한

STS3215 + Python serial + USB hub 환경에서는 무리한 주기를 피한다.

```text
command write: 10~20Hz
position read: 5~10Hz
joint_states publish: 5~10Hz
```

### 5. e-stop

개발 중 반드시 필요하다.

```text
/dual_arm/estop
```

기능:

```text
새 command 중단
현재 target 유지 또는 torque off
driver loop safe state 진입
```

갑자기 torque off하면 팔이 떨어질 수 있으므로, 상황에 따라 current hold가 더 안전할 수 있다.

---

## 17. 현재 최종 판단

현재까지 확인한 바로는:

```text
USB/전원 문제가 핵심 원인은 아니었음
왼팔 기존 HOME과 delta 방향 문제가 핵심이었음
왼팔 5번은 고장/격리 필요
왼팔 5DOF + 오른팔 6DOF 기준으로는 안정적
준동시 dual write도 통과
```

따라서 다음 단계는:

```text
1. 왼팔 5번 교체 또는 복구
2. 왼팔 6DOF HOME 재저장
3. 왼팔/오른팔 direction sign map 작성
4. ROS2 raw driver node 작성
5. e-stop과 joint limit 추가
6. 이후 URDF/RViz/MoveIt2로 확장
```

---

## 18. 현재 기준으로 가장 중요한 금지 사항

```text
기존 left_home_pose.json으로 전체 pose 이동 금지
오른팔 delta를 왼팔에 그대로 적용 금지
왼팔 ID 5 연결 상태에서 전체 bus 테스트 금지
큰 TEST_DELTA 바로 적용 금지
MoveIt2부터 바로 진입 금지
```

---

## 19. 현재 기준 핵심 파일

```text
left_home_pose_5dof.json
right_home_pose.json
dual_arm_stability_test_left5dof_v2.py
dual_arm_quasi_sync_test_left5dof.py
dual_arm_quasi_sync_test_left5dof_v2.py
save_left_home_pose_5dof.py
left_direction_calibration_5dof.py
```

