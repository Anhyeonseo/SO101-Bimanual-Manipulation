import importlib.util
import sys
import unittest
from pathlib import Path


BRINGUP_LAUNCH = Path(
    "ros2_ws/src/so101_bringup/launch/external_stm32_moveit.launch.py"
)
MOVE_GROUP_LAUNCH = Path(
    "ros2_ws/src/so101_moveit_config/launch/external_move_group.launch.py"
)
TOOLS_ROOT = Path("tools")
sys.path.insert(0, str(TOOLS_ROOT))

launch_spec = importlib.util.spec_from_file_location(
    "external_stm32_moveit_launch",
    BRINGUP_LAUNCH,
)
launch_module = importlib.util.module_from_spec(launch_spec)
assert launch_spec.loader is not None
launch_spec.loader.exec_module(launch_module)

move_group_spec = importlib.util.spec_from_file_location(
    "external_move_group_launch",
    MOVE_GROUP_LAUNCH,
)
move_group_module = importlib.util.module_from_spec(move_group_spec)
assert move_group_spec.loader is not None
move_group_spec.loader.exec_module(move_group_module)

tool_spec = importlib.util.spec_from_file_location(
    "ros_moveit_execute_once",
    TOOLS_ROOT / "ros_moveit_execute_once.py",
)
tool_module = importlib.util.module_from_spec(tool_spec)
assert tool_spec.loader is not None
sys.modules[tool_spec.name] = tool_module
tool_spec.loader.exec_module(tool_module)


class ExternalMoveItLaunchTests(unittest.TestCase):
    def test_external_launch_starts_only_four_moveit_includes(self) -> None:
        actions = launch_module._moveit_actions()
        self.assertEqual(len(actions), 4)
        self.assertTrue(
            all(
                action.__class__.__name__ == "IncludeLaunchDescription"
                for action in actions
            )
        )

    def test_external_launch_has_no_backend_or_motion_argument(self) -> None:
        description = launch_module.generate_launch_description()
        names = {
            entity.name
            for entity in description.entities
            if hasattr(entity, "name") and entity.name
        }
        self.assertNotIn("backend", names)
        self.assertNotIn("allow_motion", names)

    def test_external_move_group_uses_bounded_single_point_tolerance(self) -> None:
        config = move_group_module._moveit_config()
        tolerance = config.trajectory_execution[
            "trajectory_execution"
        ]["allowed_start_tolerance"]
        self.assertEqual(tolerance, 0.20)


class MoveItExecuteOnceTests(unittest.TestCase):
    def test_presets_are_fixed_single_point_safe_contracts(self) -> None:
        self.assertEqual(
            tuple(tool_module.PRESETS),
            ("home", "representative", "visible", "gripper-safe"),
        )
        representative = tool_module.PRESETS["representative"]
        self.assertEqual(representative.positions, (0.05,) * 5)
        visible = tool_module.PRESETS["visible"]
        self.assertEqual(visible.positions, (0.10,) * 5)
        gripper = tool_module.PRESETS["gripper-safe"]
        self.assertEqual(gripper.positions, (0.08,))

    def test_goal_contains_exactly_one_point_and_one_controller(self) -> None:
        preset = tool_module.PRESETS["representative"]
        goal = tool_module.build_goal(preset)
        self.assertEqual(goal.controller_names, [preset.controller])
        trajectory = goal.trajectory.joint_trajectory
        self.assertEqual(trajectory.joint_names, list(preset.joint_names))
        self.assertEqual(len(trajectory.points), 1)
        self.assertEqual(
            tuple(trajectory.points[0].positions),
            preset.positions,
        )
        self.assertEqual(
            trajectory.points[0].time_from_start.sec,
            preset.duration_s,
        )


if __name__ == "__main__":
    unittest.main()
