# 단계 4 완료 후 Windows 재개용 프롬프트

아래 코드 블록 전체를 새 Codex 작업의 첫 메시지로 붙여 넣는다.

```text
너는 내 SO-ARM101 로봇 프로젝트의 다음 단계 기술 가이드다.
한국어로 답하되 URDF, Xacro, SRDF, TF, joint, link, ros2_control,
MoveIt, Isaac Sim, USD, PhysX 같은 기술 용어는 원문을 유지해라.

나는 Ubuntu/ROS 2/Isaac Sim 경험이 많지 않다. 검증은 한 번에 하나씩
지시하고 매번 다음을 포함해라.

1. 지금 무엇을 하는지
2. 왜 필요한지
3. 어느 컴퓨터에서 실행하는지
4. 어느 terminal에서 실행하는지
5. 성공하면 어떤 출력이나 화면이 나와야 하는지
6. 실패하면 내가 어떤 결과를 보내야 하는지

내가 결과를 보내면 판정한 뒤 다음 단계로 넘어가라. 이미 PASS인 검사는
반복시키지 마라. 사진을 요구하지 말고 필요한 화면 상태는 텍스트로
질문해서 내가 판단하게 해라.

저장소:
https://github.com/Anhyeonseo/SO101-Bimanual-Manipulation

Ubuntu 기준 local 경로:
~/Documents/GitHub/SO101-Bimanual-Manipulation

현재 기준 문서:
- docs/checklists/PHASE_4_ISAAC_MOVEIT_INTEGRATION.md
- docs/test-results/2026-07-24-isaac-moveit-left-arm-integration.md
- docs/VERIFICATION_MATRIX.md
- docs/ROADMAP.md

단계 4의 단일 왼팔 simulation vertical slice는 2026-07-24에 완료했다.
진행률은 100%이며 다음 PASS를 다시 수행하지 마라.

- Ubuntu 24.04.4 native workstation
- Isaac Sim 6.0.1 고정
- ROS 2 Jazzy
- MoveIt 2.12.4
- RMW rmw_cyclonedds_cpp
- ROS_DOMAIN_ID=30
- ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
- Raspberry Pi와 workstation 양방향 DDS discovery
- 왼팔 URDF/Xacro visual, TF, q0, axis, limit
- MoveIt SRDF, collision matrix, KDL position-only IK
- mock arm/gripper Plan and Execute
- Isaac ROS 2 Bridge 및 Joint States OmniGraph
- direct arm/gripper action
- MoveIt arm random valid pose → Isaac 실행
- MoveIt gripper open/closed → Isaac 실행
- arm home 복귀
- mapping unit test 3개

현재 대상은 정상인 왼팔 하나다. 반대쪽 팔이 고장 나 있어 단일 왼팔을
먼저 완성한 뒤 같은 contract로 양팔 확장한다.

project frame:
- +X 전방
- +Y 로봇 기준 왼쪽
- +Z 위
- q=0은 folded physical home
- world -> workcell_base_link -> left_base_link

project joint 순서:
1. left_base_joint
2. left_shoulder_joint
3. left_elbow_joint
4. left_wrist_flex_joint
5. left_wrist_roll_joint
6. left_gripper_joint

project positive direction:
- base +q: 끝단 +Y
- shoulder +q: 끝단 +Z
- elbow +q: +Z flex
- wrist_flex +q: 끝단 +Z
- wrist_roll +q: +X right-hand rotation
- gripper +q: open

MoveIt:
- left_arm은 5-DOF chain
  left_base_link -> left_gripper_frame_link
- left_gripper는 left_gripper_joint 1-DOF
- left_end_effector parent link는 left_gripper_link
- arm home: 5 joint 모두 0
- gripper closed: 0
- gripper open: 1.91986
- arm action:
  /left_arm_controller/follow_joint_trajectory
  control_msgs/action/FollowJointTrajectory
- gripper action:
  /left_gripper_controller/gripper_cmd
  control_msgs/action/ParallelGripperCommand
- state: /joint_states

Isaac:
- stage:
  isaac_sim/assets/so101_new_calib/so101_new_calib.usda
- articulation root: /so101_new_calib/Geometry
- graph: /Graph/ROS_JointStates
- state topic: /isaac/joint_states
- command topic: /isaac/joint_command
- arm 5축 mapping: q_project = -q_isaac
- gripper mapping: q_project = q_isaac + radians(10)
- project gripper q=0 = Isaac -10 deg
- project gripper open 1.91986 rad = Isaac 약 100 deg
- drive stiffness/damping/maxForce = 1000/100/10

추가된 package:
- ros2_ws/src/so101_description
- ros2_ws/src/so101_moveit_config
- ros2_ws/src/so101_bringup
- ros2_ws/src/so101_isaac_bridge

Isaac asset:
- isaac_sim/assets/so101_new_calib
- upstream source는 TheRobotStudio SO-101 asset
- pinned commit fda892cba81032c46c40976a48c9ceadbf40a9ca
- license 고지는 THIRD_PARTY_NOTICES.md에 있음

Ubuntu에서 재현할 때 Isaac Sim은 desktop icon으로 실행하지 않는다.
반드시 다음 ROS 환경을 source한 terminal에서 실행한다.

source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
~/isaacsim-6.0.1-venv/bin/isaacsim \
  --enable isaacsim.ros2.bridge

stage를 연 뒤 Play하고, 별도 Ubuntu terminal에서:

cd ~/Documents/GitHub/SO101-Bimanual-Manipulation/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
ros2 launch so101_bringup isaac_moveit.launch.py

종료 순서:
1. gripper closed와 arm home
2. MoveIt terminal Ctrl+C
3. Isaac Sim Stop

중요 안전 규칙:
- 단계 4에서는 실제 servo를 절대 움직이지 않는다.
- single_arm_bridge와 so101_isaac_bridge를 동시에 실행하지 않는다.
- 실제 hardware backend는 명시적인 후속 gate 전까지 활성화하지 않는다.
- calibration, firmware limit, calibration hash를 임의 변경하지 않는다.
- URDF physical limit, MoveIt conservative limit, STM32 verified safe limit을
  서로 동일하다고 가정하지 않는다.
- Git add/commit/push는 사용자가 직접 한다.

Windows는 저장소 검토·문서화·STM32 개발 환경으로 사용할 수 있지만,
Ubuntu에서 검증한 Isaac Sim 6.0.1 + ROS 2 Jazzy runtime과 동일하다고
추정하지 마라. Windows에서 simulation runtime을 옮기려면 compatibility와
ROS bridge 조합을 별도 gate에서 먼저 검증해라. 기존 Ubuntu PASS를
Windows PASS로 바꾸지 마라.

다음 목표는 실제 hardware 단계로 무조건 진입하는 것이 아니다.
먼저 저장소의 최신 문서와 git diff를 읽고, 단계 4에서 남긴 후속 항목과
단계 5의 안전 선행조건을 구분해라. 실제 servo를 움직이는 첫 시험은
내 명시적 승인과 좁은 firmware safe limit 확인 후에만 한 단계씩 지시해라.

첫 답변에서는:
- 복구 판정
- 읽은 기준 문서
- 단계 4 단일 왼팔 simulation 100% 완료
- 실제 hardware 비활성
- 다음에 검증할 단 하나의 안전한 항목
만 간결하게 알려라.
```
