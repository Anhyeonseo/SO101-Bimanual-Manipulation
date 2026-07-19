# 화면 없이 운영하는(Headless) 양팔 로봇 조작 시스템

Raspberry Pi 5, ROS 2 Jazzy, STM32G474, 두 대의 SO-ARM101과 세 대의 USB 카메라를 통합하는 멀티카메라 듀얼암 로봇 프로젝트다.

첫 기능 목표는 오른팔로 마커펜을 옮기는 Pick and Place다. 이후 손목 카메라를 이용한 Visual Servo, Raspberry Pi Headless 운영, 양팔 병렬 작업, Isaac Sim/Isaac Lab policy, 수건 접기 순으로 확장한다.

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
- 검증 펌웨어: `0x00020500`, 이동 중 SAFE_STOP과 정지 후 홈 복귀 실기 통과
- 다음 단계: Raspberry Pi host bridge와 ROS 2 joint backend 구현
- 확장 방향: 동일한 µrad 관절 규격을 사용해 오른팔 실물, 양팔 실물, Isaac Sim backend를 교체할 수 있게 구성

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

## 저장소 구조

```text
Manipulation/
├── docs/
├── protocol/
├── firmware/stm32_actuator/          # 플랫폼 독립 C core
├── firmware/stm32_g474_single_arm/   # CubeIDE board project
├── config/
├── hardware/
├── tests/
├── tools/
└── requirements-host.txt
```

ROS 2 workspace와 Isaac Sim/Isaac Lab 디렉터리는 해당 검증 단계에 진입할 때 추가한다.

## 자동 판정

```bash
python3 -m unittest discover -s tests -v
python3 tools/validate_protocol_manifest.py
python3 tools/validate_camera_schedule.py
```
