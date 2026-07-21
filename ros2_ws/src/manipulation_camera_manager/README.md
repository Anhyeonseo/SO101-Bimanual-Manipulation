# manipulation_camera_manager

세 대의 UVC 카메라에서 MJPEG를 계속 수집하면서, 현재 작업 단계에 필요한 영상만 JPEG로 디코딩하는 ROS 2 패키지다.

## 동작 원리

- 카메라마다 독립된 V4L2 mmap capture thread를 사용한다.
- 카메라마다 압축된 최신 frame 한 장만 보관한다. 오래된 frame queue는 만들지 않는다.
- USB가 분리되면 500 ms 간격으로 자동 재연결한다.
- `camera_phase`에 따라 선택된 카메라만 지정된 `decode_hz`로 RGB 변환한다.
- 디코딩된 영상은 `camera/<name>/image_raw`에 `sensor_msgs/Image`로 발행한다.
- phase가 바뀌면 지연시간 통계를 초기화하여 작업 단계별 p50/p95/max를 따로 측정한다.
- `inference_hz`는 다음 perception node가 사용할 계산 예산이다. 이 패키지는 아직 inference를 실행하지 않는다.

## 장치와 topic

| 이름 | 장치 경로 | 디코딩 영상 topic |
|---|---|---|
| `top` | USB 1.1 고정 경로 | `/camera/top/image_raw` |
| `wrist_a` | USB 1.2 고정 경로 | `/camera/wrist_a/image_raw` |
| `wrist_b` | USB 1.3 고정 경로 | `/camera/wrist_b/image_raw` |

작업 단계 명령은 `/camera_phase`의 `std_msgs/msg/String`으로 받는다. 지원 phase는 다음과 같다.

- `STANDBY`
- `SEARCH`
- `APPROACH_RIGHT`
- `VISUAL_ALIGN_RIGHT`
- `TRANSFER_RIGHT`
- `VERIFY_RIGHT`
- `DUAL_PRIVATE`
- `POLICY_ASSIST`

실행에 사용하는 규칙은 `config/cameras.yaml`에 있다. 프로젝트 최상위의 `config/camera_schedule.json`은 vision/policy 전체 설계를 위한 같은 값의 기준 문서다.

## Raspberry Pi 빌드

JPEG 개발 library가 없으면 먼저 설치한다.

```bash
sudo apt update
sudo apt install -y libjpeg-dev
```

그 다음 패키지를 빌드하고 테스트한다.

```bash
cd ~/Manipulation/ros2_ws
source /opt/ros/jazzy/setup.bash

colcon build \
  --symlink-install \
  --packages-select manipulation_camera_manager \
  --cmake-clean-cache

colcon test --packages-select manipulation_camera_manager
colcon test-result --verbose
source install/setup.bash
```

## 실행과 phase 변경

터미널 1:

```bash
cd ~/Manipulation/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch manipulation_camera_manager camera_manager.launch.py
```

터미널 2에서 phase를 변경한다.

```bash
cd ~/Manipulation/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash

ros2 topic pub --once /camera_phase std_msgs/msg/String \
  "{data: SEARCH}"
```

예를 들어 `VISUAL_ALIGN_RIGHT`는 top을 2 Hz, wrist_b를 12 Hz로 디코딩하고 wrist_a는 디코딩하지 않는다.

```bash
ros2 topic pub --once /camera_phase std_msgs/msg/String \
  "{data: VISUAL_ALIGN_RIGHT}"

timeout 15 ros2 topic hz /camera/top/image_raw
timeout 15 ros2 topic hz /camera/wrist_b/image_raw
```

## 진단값

```bash
ros2 topic echo --once /camera_diagnostics
```

카메라별 주요 값:

- `phase`: 현재 작업 단계
- `configured_decode_hz`: 현재 phase의 목표 디코딩 속도
- `configured_inference_hz`: 다음 perception node에 허용할 추론 속도
- `decoded_frames`, `decode_failures`: 현재 phase에서의 디코딩 결과
- `decode_frame_age_p50_ms`, `decode_frame_age_p95_ms`, `decode_frame_age_max_ms`: capture부터 디코딩 선택까지의 frame age
- `decode_time_p50_ms`, `decode_time_p95_ms`, `decode_time_max_ms`: JPEG 디코딩 시간
- `reconnect_count`, `driver_frames_dropped`: USB 복구와 driver frame 손실 횟수

기본 경고 기준은 frame age p95 200 ms, JPEG decode p95 50 ms다. 현재 phase에서 디코딩하지 않는 카메라의 지연 통계는 `-1`이 정상이다.
