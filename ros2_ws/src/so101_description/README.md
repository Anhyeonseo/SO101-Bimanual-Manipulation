# so101_description

Parameterized SO-101 description for the left-arm-first MoveIt and Isaac Sim integration.
The validated entrypoint is `urdf/so101_left.urdf.xacro`; its default prefix is `left_` and its fixed root is `workcell_base_link`.

The geometry and inertial data are derived from `TheRobotStudio/SO-ARM100`, file `Simulation/SO101/so101_new_calib.urdf`, pinned at commit `fda892cba81032c46c40976a48c9ceadbf40a9ca` under Apache-2.0.
This project changes link/joint names, arm joint signs, wrist-roll limits, and the gripper zero convention. The `meshes/` STL files are unmodified copies from that pinned revision.

Only the left-arm configuration has been validated. The macro and prefix prepare later right-arm/bimanual composition but do not claim that a mirrored right-arm mount has been calibrated.
