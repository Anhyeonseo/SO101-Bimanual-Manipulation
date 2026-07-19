# STM32 모듈 구조와 시뮬레이션 확장 경계

## 목적

STM32 펌웨어는 실제 STS3215 서보의 시간 결정적 실행과 안전 감시만 담당한다. 작업 계획, 역기구학, MoveIt, Isaac Sim/Isaac Lab은 상위 컴퓨터에서 수행한다. 실물과 시뮬레이션은 같은 관절 단위 계약을 사용하고 실행 백엔드만 교체한다.

## STM32 파일 구조

| 모듈 | 책임 | 확장 시 변경 이유 |
|---|---|---|
| `main.c` | HAL, clock, GPIO, UART 초기화와 앱 호출 | CubeMX 재생성 시에만 변경 |
| `single_arm_config.h` | 축 수, 펌웨어 버전, 기능 플래그, heartbeat 제한 | 제품 설정 또는 프로토콜 기능 변경 |
| `servo_bus.c/.h` | STS3215 패킷, telemetry, trajectory 설정, sync write | 다른 물리 액추에이터 사용 |
| `binary_control.c/.h` | COBS/CRC, ARM/ENABLE, heartbeat, SAFE_STOP, µrad setpoint 실행 | wire protocol 또는 실시간 실행 정책 변경 |
| `single_arm_app.c/.h` | 앱 생명주기와 bring-up용 ASCII 진단 명령 | 보드 진단 기능 변경 |
| `stm32_actuator` | 플랫폼 독립 calibration, protocol, safety core | STM32와 host가 공유하는 제어 계약 변경 |

`main.c`는 애플리케이션 내부 상태를 소유하지 않는다. UART handle은 초기화 시 모듈에 주입되므로 CubeMX 전역 변수 이름이 서보 드라이버나 프로토콜 구현으로 퍼지지 않는다.

## 실물과 Isaac Sim의 공통 계약

상위 제어기는 다음 표현만 사용한다.

- 관절 순서가 고정된 joint vector
- 위치 단위: signed micro-radian (`int32`, µrad)
- 단조 증가하는 적용 시각
- arm mask와 protocol version
- 상태, heartbeat, HOLD, SAFE_STOP 의미

실물 경로에서는 STM32가 µrad를 각 서보의 home/sign/raw range로 변환한다. Isaac Sim 경로에서는 같은 µrad 값을 URDF/USD articulation joint position으로 변환한다. 따라서 상위 task나 trajectory 코드는 모터 raw 값과 STM32 UART 세부사항을 알지 않는다.

```text
MoveIt / Task State Machine / Policy
                 |
        joint command in µrad
                 |
        backend interface
          /             \
 STM32 serial backend   Isaac Sim backend
          |                    |
 binary protocol        articulation joints
          |
 STS3215 servo bus
```

## 양팔 확장 규칙

현재 펌웨어는 `SINGLE_ARM_JOINT_COUNT=6`과 left-arm mask만 실행한다. 양팔 확장에서는 아래 순서를 지킨다.

1. 상위 모델에서 좌·우 joint name과 순서를 확정한다.
2. protocol의 기존 12-joint payload와 arm mask를 유지한다.
3. STM32 하드웨어가 한 보드인지 두 보드인지 결정한 뒤 servo backend instance를 늘린다.
4. 안전 상태는 팔별 상태와 전체 시스템 정지 상태를 분리한다.
5. 동일 trajectory를 mock, Isaac Sim, 저토크 실물 순서로 검증한다.

축 수를 늘리기 위해 `servo_bus.c`에 Isaac Sim 조건문을 넣지 않는다. 시뮬레이터 선택은 Raspberry Pi/ROS 2의 backend 계층에서 수행한다.

## 변경 후 검증 기준

- STM32 Debug 전체 빌드: 오류와 경고 0
- Python/C protocol 및 calibration 테스트 통과
- binary smoke test에서 firmware version과 calibration hash 일치
- 저각도 OUT/HOME, 이동 중 SAFE_STOP, 홈 복구 재확인

