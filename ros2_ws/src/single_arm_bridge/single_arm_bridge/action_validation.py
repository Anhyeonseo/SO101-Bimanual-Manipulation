"""Pure validation for the STM32 arm and gripper Action adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math


MIN_DURATION_NS = 300_000_000
MAX_DURATION_NS = 2_000_000_000


class GoalValidationError(ValueError):
    """Raised before an invalid goal can reach the serial transport."""


@dataclass(frozen=True, slots=True)
class TrajectoryPointData:
    positions: tuple[float, ...]
    time_from_start_ns: int
    velocities: tuple[float, ...] = ()
    accelerations: tuple[float, ...] = ()
    effort: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidatedTrajectory:
    ordered_positions: tuple[float, ...]
    duration_ms: int


@dataclass(frozen=True, slots=True)
class GripperCommandData:
    positions: tuple[float, ...]
    joint_names: tuple[str, ...] = ()
    velocities: tuple[float, ...] = ()
    efforts: tuple[float, ...] = ()


def _validate_expected_contract(
    expected_joint_names: Sequence[str],
    limits: Mapping[str, tuple[float, float]],
) -> tuple[str, ...]:
    expected = tuple(expected_joint_names)
    if not expected:
        raise GoalValidationError("expected joint contract is empty")
    if len(set(expected)) != len(expected):
        raise GoalValidationError("expected joint contract contains duplicates")
    if set(limits) != set(expected):
        raise GoalValidationError("safe limits do not match expected joints")
    for name in expected:
        lower, upper = limits[name]
        if (
            not math.isfinite(lower)
            or not math.isfinite(upper)
            or lower > upper
        ):
            raise GoalValidationError(f"{name} has invalid safe limits")
    return expected


def _validate_goal_joint_names(
    joint_names: Sequence[str],
    expected: tuple[str, ...],
) -> tuple[str, ...]:
    names = tuple(joint_names)
    if len(set(names)) != len(names):
        raise GoalValidationError("goal contains duplicate joint names")
    if len(names) != len(expected) or set(names) != set(expected):
        raise GoalValidationError("goal joint names do not match expected joints")
    return names


def _validate_strictly_increasing_times(
    points: Sequence[TrajectoryPointData],
) -> None:
    previous = -1
    for point in points:
        value = point.time_from_start_ns
        if isinstance(value, bool) or not isinstance(value, int):
            raise GoalValidationError("time_from_start must be integer nanoseconds")
        if value <= previous:
            raise GoalValidationError("trajectory times must be strictly increasing")
        previous = value


def _validate_position(name: str, value: float, lower: float, upper: float) -> float:
    position = float(value)
    if not math.isfinite(position):
        raise GoalValidationError(f"{name} position is not finite")
    if not lower <= position <= upper:
        raise GoalValidationError(
            f"{name} position {position} is outside safe range {lower}..{upper}"
        )
    return position


def validate_single_point_trajectory(
    joint_names: Sequence[str],
    points: Sequence[TrajectoryPointData],
    expected_joint_names: Sequence[str],
    limits: Mapping[str, tuple[float, float]],
) -> ValidatedTrajectory:
    """Validate and reorder a single arm point without touching hardware."""

    expected = _validate_expected_contract(expected_joint_names, limits)
    names = _validate_goal_joint_names(joint_names, expected)
    if not points:
        raise GoalValidationError("trajectory has no points")
    _validate_strictly_increasing_times(points)
    if len(points) != 1:
        raise GoalValidationError("STM32 milestone requires exactly one point")

    point = points[0]
    if len(point.positions) != len(names):
        raise GoalValidationError("trajectory point position count is invalid")
    if point.velocities or point.accelerations or point.effort:
        raise GoalValidationError(
            "velocity, acceleration, and effort fields are not supported"
        )
    if not MIN_DURATION_NS <= point.time_from_start_ns <= MAX_DURATION_NS:
        raise GoalValidationError("duration must be within 300..2000 ms")

    by_name = dict(zip(names, point.positions, strict=True))
    ordered = tuple(
        _validate_position(name, by_name[name], *limits[name])
        for name in expected
    )
    duration_ms = (point.time_from_start_ns + 999_999) // 1_000_000
    return ValidatedTrajectory(ordered, duration_ms)


def validate_gripper_command(
    command: GripperCommandData,
    expected_joint_name: str,
    safe_limit: tuple[float, float],
) -> float:
    """Validate a hardware gripper command and return its project-radian target."""

    lower, upper = safe_limit
    if (
        not math.isfinite(lower)
        or not math.isfinite(upper)
        or lower > upper
    ):
        raise GoalValidationError("gripper has invalid safe limits")
    if command.velocities or command.efforts:
        raise GoalValidationError("gripper velocity and effort are not supported")

    names = tuple(command.joint_names)
    if names:
        if len(set(names)) != len(names):
            raise GoalValidationError("gripper command contains duplicate joint names")
        if names != (expected_joint_name,):
            raise GoalValidationError("gripper command joint name is invalid")
    if len(command.positions) != 1:
        raise GoalValidationError("gripper command requires exactly one position")
    return _validate_position(
        expected_joint_name,
        command.positions[0],
        lower,
        upper,
    )
