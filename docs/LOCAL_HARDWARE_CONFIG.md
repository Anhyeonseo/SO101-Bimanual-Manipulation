# 로컬 하드웨어 설정

이 문서는 공개 저장소에 개인 장치 식별자를 넣지 않으면서 개발 PC와 Raspberry Pi의 실행 설정을 유지하는 방법을 설명한다.

## 기본 원칙

- 공개 가능한 공통 설정은 tracked YAML에 둔다.
- 장치 serial, 실험실별 port와 개인 경로는 `*.local.yaml`에 둔다.
- `*.local.yaml`은 `.gitignore`로 제외한다.
- launch는 공통 YAML을 먼저 읽고 local YAML이 있으면 나중에 읽어 같은 parameter를 덮어쓴다.
- calibration과 안전 limit은 개인 편의 설정이 아니므로 검증된 공통 파일에서 관리한다.

## STM32 serial 설정

공통 파일:

```text
ros2_ws/src/single_arm_bridge/config/bridge.yaml
```

기본 `serial_device` 값은 `auto`다. node가 단일 ST-LINK by-id를 탐색하고, 발견하지 못하면 `/dev/ttyACM0`를 사용한다. 둘 이상의 ST-LINK가 발견되면 잘못된 팔을 제어하지 않도록 실행을 거부한다.

장치를 명시적으로 고정하려면:

```bash
cd ~/Manipulation/ros2_ws/src/single_arm_bridge/config
cp bridge.local.yaml.example bridge.local.yaml
```

그 후 `bridge.local.yaml`의 `<SERIAL>`을 다음 명령에서 확인한 실제 값으로 바꾼다.

```bash
ls -l /dev/serial/by-id/
```

다시 build한다.

```bash
cd ~/Manipulation/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select single_arm_bridge
source install/setup.bash
```

실행 명령은 기존과 같다.

```bash
ros2 launch single_arm_bridge bridge.launch.py
```

## 새 PC 또는 새 Pi로 이동할 때

Git clone에는 local YAML이 포함되지 않는다. 다음 순서로 복구한다.

1. tracked example을 local YAML로 복사
2. 새 장치의 by-id를 측정해 입력
3. package 다시 build
4. `allow_motion:=false`로 먼저 `/joint_states` 확인
5. protocol smoke를 통과한 뒤에만 motion 허용

local YAML을 별도로 백업할 수는 있지만 공개 GitHub나 issue 본문에는 올리지 않는다.

## 카메라 경로

현재 카메라는 `manipulation_camera_manager/config/cameras.yaml`의 USB 물리 port 기반 경로를 사용한다. 카메라나 hub port를 바꾸면 아래 명령으로 경로를 다시 확인한 뒤 YAML을 수정한다.

```bash
ls -l /dev/v4l/by-path/
```

카메라 경로에는 인증정보가 없지만 port 역할이 바뀌면 `top`, `wrist_a`, `wrist_b` 영상이 뒤바뀔 수 있으므로 변경 후 `/camera_diagnostics`와 실제 영상을 함께 확인한다.
