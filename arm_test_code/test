# Feetech / Waveshare STS/SCS Serial Bus Servo 로봇팔 제어

## 1. 프로젝트 개요

이 프로젝트는 Feetech / Waveshare STS/SCS 계열 Serial Bus Servo를 사용한 6축 로봇팔의 하위 제어 테스트 프로젝트이다.

이번 단계의 목표는 카메라 기반 인식이나 AI 정책 제어를 구현하는 것이 아니라, Ubuntu 환경에서 Python Serial 통신을 이용해 로봇팔 하드웨어를 직접 제어할 수 있는지 검증하는 것이다.

현재까지 구현 및 확인한 내용은 다음과 같다.

* STS/SCS 계열 서보와 Serial 통신 확인
* 각 서보에 ID 1~6 부여
* 서보 현재 위치 읽기 구현
* 목표 위치 명령 전송 구현
* 6개 서보 통합 제어 테스트
* HOME 자세 저장 및 복귀 동작 구현

---

## 2. 개발 환경

### 하드웨어

* Ubuntu PC / Laptop
* Waveshare / Feetech Serial Bus Servo Adapter
* Feetech / Waveshare STS/SCS Serial Bus Servo
* 서보용 외부 전원

### 소프트웨어

* Ubuntu
* Python 3
* pyserial
* Serial device: `/dev/ttyACM0`
* Baudrate: `1000000`

---

## 3. 시스템 구조

```text
Ubuntu PC
   |
   | USB
   |
Serial Bus Servo Adapter
   |
   | TTL Serial Bus
   |
Servo ID 1 - Servo ID 2 - Servo ID 3 - Servo ID 4 - Servo ID 5 - Servo ID 6
```

Python 코드에서 Serial 패킷을 직접 생성하여 각 서보 ID에 명령을 전송하는 방식으로 제어한다.

각 서보는 고유한 ID를 가지고 있으며, 패킷에 포함된 ID를 기준으로 해당 서보만 명령에 반응한다.

---

## 4. 관절 ID 매핑

| Servo ID | Joint Name       |
| -------: | ---------------- |
|        1 | `base_yaw`       |
|        2 | `shoulder_pitch` |
|        3 | `elbow_pitch`    |
|        4 | `wrist_pitch`    |
|        5 | `wrist_roll`     |
|        6 | `gripper`        |

---

## 5. 구현 내용

### 5.1 Serial 포트 인식

Ubuntu에서 Serial Bus Servo Adapter가 다음 포트로 인식되는 것을 확인했다.

```bash
/dev/ttyACM0
```

권한 문제는 다음 명령어로 해결했다.

```bash
sudo chmod 666 /dev/ttyACM0
```

---

### 5.2 단일 서보 Ping 테스트

서보 ID 1번에 Ping 패킷을 전송하여 통신이 정상적으로 되는지 확인했다.

예시 결과:

```text
TX: ff ff 01 02 01 fb
RX: ff ff 01 02 00 fc
```

이를 통해 Python 코드에서 직접 패킷을 생성하고, 서보로부터 정상 응답을 받을 수 있음을 확인했다.

---

### 5.3 현재 위치 읽기

서보의 현재 위치 값을 읽는 기능을 구현했다.

현재 위치는 raw position 값으로 읽히며, STS/SCS 계열 서보의 위치 범위는 일반적으로 `0~4095`이다.

이를 통해 각 관절의 현재 엔코더 위치를 확인할 수 있다.

---

### 5.4 목표 위치 이동

서보에 목표 위치, 속도, 가속도 값을 포함한 패킷을 전송하여 실제 이동을 확인했다.

처음에는 단일 서보를 대상으로 이동 테스트를 진행했고, 이후 6개 서보 전체 제어로 확장했다.

---

### 5.5 서보 ID 변경

처음에는 모든 서보가 기본 ID를 가지고 있을 가능성이 있기 때문에, 서보를 하나씩 연결하여 ID를 변경했다.

ID 변경 과정에서 EEPROM lock 문제를 확인했고, 다음 순서로 해결했다.

```text
EEPROM Unlock
→ ID Write
→ EEPROM Lock
→ 전원 재인가
→ ID Scan으로 확인
```

최종적으로 ID 1~6을 각각 다른 관절에 할당했다.

---

### 5.6 전체 ID 스캔

모든 서보에 ID를 부여한 후, 전체 서보를 하나의 TTL Serial Bus에 연결하고 ID 스캔을 진행했다.

목표 상태:

```text
Found IDs: [1, 2, 3, 4, 5, 6]
```

이를 통해 하나의 버스에 연결된 6개 서보를 ID 기반으로 개별 제어할 수 있음을 확인했다.

---

### 5.7 6축 로봇팔 통합 제어

6개 서보를 모두 연결한 뒤, 각 관절에 목표 위치를 전송하여 로봇팔 전체가 움직이는 것을 확인했다.

구현한 기본 동작은 다음과 같다.

```text
HOME 자세
→ TEST 자세
→ HOME 자세 복귀
```

이 과정에서 일부 관절이 예상보다 작게 움직이거나, 동작 방향이 반대인 문제가 있었지만, raw position delta를 조정하면서 전체 제어 흐름을 확인했다.

---

## 6. HOME 자세 저장 방식

초기에는 코드 실행 시점의 현재 자세를 임시 HOME으로 사용하는 방식으로 테스트했다.

이후에는 사용자가 직접 로봇팔을 원하는 초기 자세로 맞춘 뒤, 해당 자세의 각 관절 raw position 값을 읽어서 `home_pose.json` 파일로 저장하는 방식으로 정리했다.

HOME 저장 흐름은 다음과 같다.

```text
사용자가 로봇팔을 원하는 HOME 자세로 맞춤
→ 현재 1~6번 관절 위치 읽기
→ home_pose.json에 저장
→ 이후 실행 시 home_pose.json을 HOME 자세로 사용
```

이 방식은 매번 코드 내부의 숫자를 직접 수정하지 않아도 되며, HOME 자세를 바꾸고 싶을 때 다시 저장하면 된다는 장점이 있다.

---

## 7. 현재 파일 구조

```text
feetech_driver/
├── ping_servo.py
├── read_position.py
├── move_servo.py
├── scan_id.py
├── change_id.py
├── read_all_positions.py
├── save_home_pose.py
├── home_pose.json
├── move_all_small.py
└── arm_test.py
```

---

## 8. 파일별 역할

| 파일                      | 역할                              |
| ----------------------- | ------------------------------- |
| `ping_servo.py`         | 단일 서보 Ping 테스트                  |
| `read_position.py`      | 단일 서보 현재 위치 읽기                  |
| `move_servo.py`         | 단일 서보 목표 위치 이동                  |
| `scan_id.py`            | 연결된 서보 ID 탐색                    |
| `change_id.py`          | EEPROM unlock을 포함한 서보 ID 변경     |
| `read_all_positions.py` | 1~6번 전체 관절 위치 읽기                |
| `save_home_pose.py`     | 현재 자세를 HOME 자세로 저장              |
| `home_pose.json`        | 저장된 HOME 자세 raw position 값      |
| `move_all_small.py`     | 전체 모터 작은 이동 테스트                 |
| `arm_test.py`           | HOME → TEST 자세 → HOME 복귀 통합 테스트 |

---

## 9. 실행 순서

### 9.1 포트 권한 설정

```bash
sudo chmod 666 /dev/ttyACM0
```

### 9.2 연결된 서보 ID 확인

```bash
python3 scan_id.py
```

### 9.3 전체 관절 현재 위치 확인

```bash
python3 read_all_positions.py
```

### 9.4 HOME 자세 저장

로봇팔을 원하는 HOME 자세로 맞춘 뒤 실행한다.

```bash
python3 save_home_pose.py
```

실행 후 `home_pose.json` 파일이 생성된다.

### 9.5 HOME → TEST 자세 → HOME 복귀 테스트

```bash
python3 arm_test.py
```

---

## 10. 현재까지의 결과

현재까지 다음 기능을 확인했다.

```text
1. Ubuntu에서 Serial Bus Servo Adapter 인식
2. Python Serial 통신으로 서보 Ping 성공
3. 서보 현재 위치 읽기 성공
4. 단일 서보 목표 위치 이동 성공
5. 서보 ID 1~6 부여 완료
6. 전체 ID 스캔 성공
7. 6개 서보 통합 제어 성공
8. HOME 자세 저장 및 복귀 테스트 구현
```

따라서 현재 단계는 다음과 같이 정리할 수 있다.

```text
Python 기반 Feetech/Waveshare STS/SCS 6축 로봇팔 하위 제어 MVP 구현
```

---

## 11. 현재 한계

현재 제어는 아직 raw position 기반이다.

즉, 각 관절을 각도 단위나 ROS joint command로 제어하는 단계는 아니다.

현재 한계는 다음과 같다.

* 관절별 실제 안전 범위가 아직 완전히 측정되지 않음
* 각 관절의 +방향 / -방향이 아직 정리되지 않음
* raw position 기반 제어이므로 직관적인 각도 제어가 아님
* ROS2 joint interface는 아직 구현되지 않음
* 카메라 기반 인식은 아직 적용되지 않음
* AI policy / imitation learning / reinforcement learning은 아직 적용되지 않음

---

## 12. 다음 단계

다음 단계에서는 하위 제어 코드를 정리하고, 로봇팔 제어를 더 구조화할 예정이다.

우선순위는 다음과 같다.

```text
1. HOME 자세 안정화
2. 각 관절의 실제 min/max raw position 측정
3. 각 관절의 +방향 / -방향 정리
4. raw position → degree/radian 변환 함수 구현
5. joint name 기반 제어 API 정리
6. ROS2 joint_states publish 구현
7. ROS2 joint command subscribe 구현
8. URDF / MoveIt2 연동 준비
```

카메라와 AI 정책은 로봇팔의 하위 제어가 안정화된 이후에 추가할 예정이다.

---

## 13. 최종 정리

이번 작업을 통해 Feetech / Waveshare STS/SCS Serial Bus Servo 기반 로봇팔의 기본 하드웨어 제어가 가능함을 확인했다.

특히 Python에서 직접 패킷을 생성하여 서보와 통신했고, ID 설정, 위치 읽기, 목표 위치 이동, 전체 관절 통합 제어까지 구현했다.

현재 프로젝트는 카메라나 AI가 붙기 전 단계의 하위 제어 MVP이며, 이후 ROS2 기반 로봇팔 제어 구조로 확장할 예정이다.
