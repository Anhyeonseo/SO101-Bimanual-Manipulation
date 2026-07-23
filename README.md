# 화면 없이 운영하는(Headless) 양팔 로봇 조작 시스템

Raspberry Pi 5, ROS 2 Jazzy, STM32G474, 두 대의 SO-ARM101과 세 대의 USB 카메라를 통합하는 멀티카메라 듀얼암 로봇 프로젝트다.

첫 기능 목표는 현재 정상인 왼팔로 마커펜을 옮기는 Pick and Place다. 이후 손목 카메라를 이용한 Visual Servo, Raspberry Pi Headless 운영, 양팔 병렬 작업, Isaac Sim/Isaac Lab policy, 수건 접기 순으로 확장한다.

## 핵심 원칙

- Raspberry Pi는 인식, TF, 계획, 상태 머신과 운영을 담당한다.
- STM32는 서보 버스 타이밍, 짧은 setpoint 보간, 제한, watchdog과 fault 처리를 담당한다.
- 부팅과 재연결만으로 로봇이 움직이지 않는다. 기본 상태는 `STANDBY`다.
- 모든 기능은 검증 게이트를 통과한 뒤 다음 단계로 이동한다.
- 성능과 안정성은 추측하지 않고 측정 결과를 남긴다.
- 실제 하드웨어 상수는 측정 전 코드 기본값으로 사용하지 않는다.

## 현재 상태

- 완료 범위: NUCLEO-G474RE 기반 단일 팔 STS3215 6축 제어
- 펌웨어: binary protocol v1, COBS/CRC-32C, 500ms heartbeat, SAFE_STOP, 6축 절대 위치 명령과 홈 복귀
- 보정(calibration): 홈 raw 2048, µrad 관절 좌표 변환, hash `0x3DB42B48`
- 검증 펌웨어: `0x00020700`, SAFE_STOP, 홈 복귀, 축별 torque·load/current 보호, 실제 위치 feedback 실기 통과
- ROS 2: Pi host bridge의 `/joint_states`, READ_ONLY 차단, `/clear_fault`, 단일 `JointTrajectory` 이동·복귀 실기 통과
- 카메라: 3대 MJPEG 640x480/30FPS 동시 capture, hot-plug 자동 복구, 작업 phase별 선택적 JPEG decode 실기 통과
- 성능: RGB 3개 topic과 STM32 bridge 동시 부하에서 CPU 평균 6.38%, `/joint_states` 5.008Hz, heartbeat 위반 0
- 현재 simulation: 정상인 왼팔 1대의 URDF/Xacro, MoveIt mock, Isaac Sim 6.0.1 backend와 대표 arm/gripper trajectory 검증 완료
- 다음 단계: 단계 4 결과를 기준으로 실제 STM32 backend의 안전 선행조건 검토
- 확장 방향: 동일한 µrad 관절 규격을 사용해 왼팔 실물, 향후 양팔 실물, Isaac Sim backend를 교체할 수 있게 구성

## 새 개발 환경 준비

필수 도구:

- STM32CubeIDE 2.2.0 이상과 STM32CubeG4 package
- Python 3.12 이상
- host-side C core를 빌드할 경우 CMake와 C11 compiler

Windows PowerShell에서 Python 환경과 자동 테스트를 준비한다.

```powershell
py -3.12 -m venv .venv-host
.\.venv-host\Scripts\Activate.ps1
python -m pip install -r requirements-host.txt
python -m unittest discover -s tests -p "test_*.py"
python tools\validate_protocol_manifest.py
```

STM32CubeIDE에서는 `firmware/stm32_g474_single_arm`을 Existing Project로 import한다. 상위의 `firmware/stm32_actuator`가 linked resource로 연결되므로 두 디렉터리의 상대 위치를 바꾸지 않는다. `Debug/` 산출물과 개인별 `.launch` 설정은 저장소에 포함하지 않으며 각 PC에서 다시 생성한다.

실제 모터를 사용하는 기본 점검(smoke) 및 동작 시험 도구는 `tools/stm32_*_test.py`에 있다. 전원 차단 수단과 작업 공간을 확보한 뒤 실행한다.

## 장치별 로컬 설정

공개 저장소에는 개인 NUCLEO의 ST-LINK serial을 넣지 않는다. `single_arm_bridge`의 공개 기본값 `serial_device: auto`는 다음 순서로 장치를 찾는다.

1. `/dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_*-if02`와 일치하는 장치가 정확히 하나면 사용
2. by-id 장치가 없고 `/dev/ttyACM0`가 있으면 fallback으로 사용
3. ST-LINK가 여러 개면 임의로 선택하지 않고 실행을 거부

여러 보드를 연결하거나 장치를 명시적으로 고정하려면 아래 example을 복사한다.

```bash
cd ~/Manipulation/ros2_ws/src/single_arm_bridge/config
cp bridge.local.yaml.example bridge.local.yaml
```

`bridge.local.yaml`에 실제 by-id 경로를 넣고 package를 다시 build하면 기존 `ros2 launch single_arm_bridge bridge.launch.py` 명령이 local 설정을 자동으로 우선 적용한다. `*.local.yaml`은 Git에서 제외되므로 공개 저장소에 장치 식별자가 올라가지 않는다. 자세한 내용은 [로컬 하드웨어 설정](docs/LOCAL_HARDWARE_CONFIG.md)에 기록했다.

## 문서 안내

- [프로젝트 헌장](docs/PROJECT_CHARTER.md)
- [전체 로드맵](docs/ROADMAP.md)
- [하드웨어 인벤토리](docs/HARDWARE_INVENTORY.md)
- [단계 0 하드웨어 검사](docs/checklists/PHASE_0_HARDWARE_BASELINE.md)
- [단계 0 측정 데이터](hardware/phase0_baseline.json)
- [검증 매트릭스](docs/VERIFICATION_MATRIX.md)
- [포트폴리오 작업 기록](docs/PORTFOLIO_LOG.md)
- [아키텍처 결정 기록](docs/adr/README.md)
- [Pi–STM32 통신 규격 초안](protocol/README.md)
- [Pi 카메라·연산 아키텍처](docs/CAMERA_COMPUTE_ARCHITECTURE.md)
- [STM32 모듈 구조와 Isaac Sim 확장 경계](docs/STM32_MODULAR_ARCHITECTURE.md)
- [STM32 단일 팔 실기 체크리스트](docs/checklists/STM32_SINGLE_ARM_BRINGUP.md)
- [단계 4 왼팔 Isaac Sim·MoveIt 체크리스트](docs/checklists/PHASE_4_ISAAC_MOVEIT_INTEGRATION.md)
- [단계 4 시험 결과](docs/test-results/2026-07-24-isaac-moveit-left-arm-integration.md)
- [Windows 재개용 단계 4 인계 프롬프트](docs/handoff/PHASE_4_WINDOWS_HANDOFF_PROMPT.md)
- [로컬 하드웨어 설정](docs/LOCAL_HARDWARE_CONFIG.md)
- [제3자 license 고지](THIRD_PARTY_NOTICES.md)

## 저장소 구조

```text
Manipulation/
├── docs/
├── protocol/
├── firmware/stm32_actuator/          # 플랫폼 독립 C core
├── firmware/stm32_g474_single_arm/   # CubeIDE board project
├── ros2_ws/src/single_arm_bridge/    # Pi binary transport와 ROS 2 bridge
├── ros2_ws/src/so101_description/    # 왼팔 URDF/Xacro와 mesh
├── ros2_ws/src/so101_moveit_config/  # SRDF, planning, controller contract
├── ros2_ws/src/so101_bringup/        # mock/Isaac launch
├── ros2_ws/src/so101_isaac_bridge/   # MoveIt ↔ Isaac adapter
├── ros2_ws/src/manipulation_camera_manager/ # V4L2 capture와 phase scheduler
├── isaac_sim/assets/                 # 검증된 Isaac Sim 6.0.1 stage
├── config/
├── hardware/
├── tests/
├── tools/
└── requirements-host.txt
```

Isaac Lab policy는 단계 11에서 추가한다. 현재 `isaac_sim/`은 단계 4에서
검증한 왼팔 simulation asset만 포함한다.

## 자동 판정

```bash
python3 -m unittest discover -s tests -v
python3 tools/validate_protocol_manifest.py
python3 tools/validate_camera_schedule.py
```

Pi에서 ROS package까지 확인할 때는 다음을 추가로 실행한다.

```bash
cd ~/Manipulation/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
colcon test
colcon test-result --verbose
```

## License

자체 작성 코드는 [Apache License 2.0](LICENSE)으로 공개한다. STM32 HAL, CMSIS와 BSP는 각 원본 파일 및 [제3자 license 고지](THIRD_PARTY_NOTICES.md)에 적힌 조건을 따른다.
