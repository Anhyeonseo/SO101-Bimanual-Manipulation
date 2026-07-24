#!/usr/bin/env python3
"""Send one fixed single-point trajectory through MoveIt's execution Action."""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from typing import Any

from action_msgs.msg import GoalStatus

from builtin_interfaces.msg import Duration

from moveit_msgs.action import ExecuteTrajectory
from moveit_msgs.msg import MoveItErrorCodes, RobotTrajectory

import rclpy
from rclpy.action import ActionClient

from trajectory_msgs.msg import JointTrajectoryPoint


ACTION_NAME = "/execute_trajectory"
ARM_CONTROLLER = "left_arm_controller"
GRIPPER_CONTROLLER = "left_gripper_controller"
ARM_JOINTS = (
    "left_base_joint",
    "left_shoulder_joint",
    "left_elbow_joint",
    "left_wrist_flex_joint",
    "left_wrist_roll_joint",
)
GRIPPER_JOINT = "left_gripper_joint"


@dataclass(frozen=True, slots=True)
class Preset:
    controller: str
    joint_names: tuple[str, ...]
    positions: tuple[float, ...]
    duration_s: int


PRESETS = {
    "home": Preset(ARM_CONTROLLER, ARM_JOINTS, (0.0,) * 5, 2),
    "representative": Preset(
        ARM_CONTROLLER,
        ARM_JOINTS,
        (0.05,) * 5,
        2,
    ),
    "visible": Preset(
        ARM_CONTROLLER,
        ARM_JOINTS,
        (0.10,) * 5,
        2,
    ),
    "gripper-safe": Preset(
        GRIPPER_CONTROLLER,
        (GRIPPER_JOINT,),
        (0.08,),
        1,
    ),
}


def wait_future(node: Any, future: Any, timeout_s: float) -> Any:
    deadline = time.monotonic() + timeout_s
    while rclpy.ok() and not future.done() and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    if not future.done():
        raise TimeoutError("ROS Action response timeout")
    result = future.result()
    if result is None:
        raise RuntimeError("ROS Action future returned no result")
    return result


def build_goal(preset: Preset) -> ExecuteTrajectory.Goal:
    trajectory = RobotTrajectory()
    trajectory.joint_trajectory.joint_names = list(preset.joint_names)
    point = JointTrajectoryPoint()
    point.positions = list(preset.positions)
    point.time_from_start = Duration(sec=preset.duration_s)
    trajectory.joint_trajectory.points = [point]

    goal = ExecuteTrajectory.Goal()
    goal.trajectory = trajectory
    goal.controller_names = [preset.controller]
    return goal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute one fixed, verified-safe, single-point goal through MoveIt. "
            "This tool never retries a physical command."
        )
    )
    parser.add_argument("--target", required=True, choices=tuple(PRESETS))
    parser.add_argument(
        "--execute-once",
        action="store_true",
        help="required acknowledgement that exactly one physical goal will be sent",
    )
    args = parser.parse_args()
    if not args.execute_once:
        parser.error("--execute-once is required; no goal was sent")
    return args


def main() -> int:
    args = parse_args()
    preset = PRESETS[args.target]
    rclpy.init()
    node = rclpy.create_node("so101_moveit_execute_once")
    client = ActionClient(node, ExecuteTrajectory, ACTION_NAME)

    try:
        if not client.wait_for_server(timeout_sec=5.0):
            raise TimeoutError(f"Action server unavailable: {ACTION_NAME}")

        print(
            "MOVEIT_EXECUTE_REQUEST "
            f"target={args.target} controller={preset.controller} "
            f"positions={','.join(f'{value:.2f}' for value in preset.positions)} "
            f"duration_ms={preset.duration_s * 1000}"
        )
        goal_handle = wait_future(
            node,
            client.send_goal_async(build_goal(preset)),
            timeout_s=5.0,
        )
        if not goal_handle.accepted:
            raise RuntimeError("MOVEIT_EXECUTE_GOAL_REJECTED")
        print("MOVEIT_EXECUTE_GOAL_ACCEPTED")

        wrapped_result = wait_future(
            node,
            goal_handle.get_result_async(),
            timeout_s=preset.duration_s + 8.0,
        )
        error_value = int(wrapped_result.result.error_code.val)
        print(
            "MOVEIT_EXECUTE_RESULT "
            f"status={wrapped_result.status} error_code={error_value}"
        )
        if wrapped_result.status != GoalStatus.STATUS_SUCCEEDED:
            raise RuntimeError("MOVEIT_EXECUTE_ACTION_NOT_SUCCEEDED")
        if error_value != MoveItErrorCodes.SUCCESS:
            raise RuntimeError(f"MOVEIT_EXECUTE_ERROR_CODE_{error_value}")
        print(f"MOVEIT_EXECUTE_PASS target={args.target}")
        return 0
    except Exception as error:
        print(f"MOVEIT_EXECUTE_FAIL {error}")
        return 1
    finally:
        client.destroy()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
