from pathlib import Path
import unittest

from tools.joint_calibration import (
    CalibrationError,
    calibration_hash,
    load_calibration,
    raw_to_urad,
    urad_to_raw,
)


class JointCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.calibration = load_calibration(
            Path("config/single_arm_calibration.json")
        )

    def test_hash_matches_verified_firmware(self) -> None:
        self.assertEqual(calibration_hash(self.calibration), 0x3DB42B48)

    def test_every_joint_zero_maps_to_raw_2048(self) -> None:
        for joint_index in range(6):
            self.assertEqual(urad_to_raw(self.calibration, joint_index, 0), 2048)

    def test_verified_positive_directions_map_to_34_raw_steps(self) -> None:
        expected_raw = [2082, 2082, 2014, 2014, 2082, 2014]
        position_urad = raw_to_urad(self.calibration, 0, 2082)
        for joint_index, raw in enumerate(expected_raw):
            self.assertEqual(
                urad_to_raw(self.calibration, joint_index, position_urad),
                raw,
            )

    def test_raw_round_trip_covers_every_safe_endpoint(self) -> None:
        for joint_index, joint in enumerate(self.calibration["joints"]):
            for raw in (joint["minimum_raw"], joint["zero_raw"], joint["maximum_raw"]):
                urad = raw_to_urad(self.calibration, joint_index, raw)
                self.assertEqual(urad_to_raw(self.calibration, joint_index, urad), raw)

    def test_out_of_range_joint_target_is_rejected(self) -> None:
        with self.assertRaises(CalibrationError):
            urad_to_raw(self.calibration, 2, 1_000_000)


if __name__ == "__main__":
    unittest.main()
