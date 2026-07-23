# Isaac Sim assets

검증 기준은 Isaac Sim 6.0.1이다.

## SO-101 왼팔 stage

```text
assets/so101_new_calib/so101_new_calib.usda
```

이 stage에는 `/so101_new_calib/Geometry` articulation과
`/Graph/ROS_JointStates` OmniGraph가 저장돼 있다.

- publish: `/isaac/joint_states`
- subscribe: `/isaac/joint_command`
- drive stiffness/damping/maxForce: `1000` / `100` / `10`
- arm target: `0 deg`
- gripper target: `-10 deg`

ROS 2 Bridge가 필요한 경우 Isaac Sim을 ROS 2 Jazzy 환경을 source한
terminal에서 실행한다. 전체 실행 순서와 joint mapping은
`../docs/checklists/PHASE_4_ISAAC_MOVEIT_INTEGRATION.md`를 따른다.

`assets/so101_new_calib`의 geometry는 TheRobotStudio SO-101 asset의
commit `fda892cba81032c46c40976a48c9ceadbf40a9ca`에서 가져왔다.
license는 root `THIRD_PARTY_NOTICES.md`와 `LICENSE`를 확인한다.
