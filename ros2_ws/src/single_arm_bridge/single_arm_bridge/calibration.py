"""Calibration loading and ROS-radian conversion."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path

from .protocol import crc32c


@dataclass(frozen=True, slots=True)
class JointCalibration:
    servo_id: int
    name: str
    zero_raw: int
    minimum_raw: int
    maximum_raw: int
    direction: int
    p_gain: int


@dataclass(frozen=True, slots=True)
class ArmCalibration:
    arm_slot: str
    joints: tuple[JointCalibration, ...]
    calibration_hash: int

    @property
    def ros_joint_names(self) -> list[str]:
        return [f"{self.arm_slot}_{joint.name.lower()}_joint" for joint in self.joints]

    def raw_feedback_to_radians(self, raw_positions: tuple[int, ...]) -> list[float]:
        if len(raw_positions) != len(self.joints):
            raise ValueError("feedback joint count mismatch")
        return [
            (raw - joint.zero_raw) * joint.direction * (2.0 * math.pi / 4096.0)
            for joint, raw in zip(self.joints, raw_positions, strict=True)
        ]

    def radians_to_urad(self, positions: list[float]) -> list[int]:
        if len(positions) != len(self.joints):
            raise ValueError("command joint count mismatch")
        result: list[int] = []
        for joint, position in zip(self.joints, positions, strict=True):
            if not math.isfinite(position):
                raise ValueError(f"{joint.name}: non-finite position")
            raw = round(
                joint.zero_raw
                + joint.direction * position * 4096.0 / (2.0 * math.pi)
            )
            if not joint.minimum_raw <= raw <= joint.maximum_raw:
                raise ValueError(
                    f"{joint.name}: target raw {raw} outside "
                    f"{joint.minimum_raw}..{joint.maximum_raw}"
                )
            result.append(round(position * 1_000_000.0))
        return result


def load_calibration(path: str | Path) -> ArmCalibration:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    joints = tuple(
        JointCalibration(
            servo_id=item["id"],
            name=item["name"],
            zero_raw=item["zero_raw"],
            minimum_raw=item["minimum_raw"],
            maximum_raw=item["maximum_raw"],
            direction=item["positive_raw_direction"],
            p_gain=item["p_gain"],
        )
        for item in document["joints"]
    )
    if len(joints) != 6 or [joint.servo_id for joint in joints] != list(range(1, 7)):
        raise ValueError("calibration must contain ordered servo IDs 1..6")

    serialized = bytearray()
    for joint in joints:
        serialized.extend(
            bytes((joint.servo_id,))
            + joint.zero_raw.to_bytes(2, "little")
            + joint.minimum_raw.to_bytes(2, "little")
            + joint.maximum_raw.to_bytes(2, "little")
            + (joint.direction & 0xFF).to_bytes(1, "little")
            + joint.p_gain.to_bytes(1, "little")
        )
    return ArmCalibration(document["arm_slot"], joints, crc32c(bytes(serialized)))
