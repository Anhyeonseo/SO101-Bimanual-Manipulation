import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PACKAGE_ROOT = Path("ros2_ws/src/single_arm_bridge")
sys.path.insert(0, str(PACKAGE_ROOT))

from single_arm_bridge.backend_lease import (  # noqa: E402
    BackendLeaseError,
    EXTERNAL_OWNER_PID_ENV,
    acquire_backend_lease,
)


class BackendLeaseHandoffTests(unittest.TestCase):
    def test_child_accepts_matching_held_launch_lease(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_directory = Path(directory)
            owner = acquire_backend_lease(
                "stm32",
                30,
                runtime_directory,
            )
            with patch.dict(
                os.environ,
                {EXTERNAL_OWNER_PID_ENV: str(os.getpid())},
            ):
                child_view = acquire_backend_lease(
                    "stm32",
                    30,
                    runtime_directory,
                )

            self.assertFalse(child_view.acquired)
            self.assertEqual(child_view.path, owner.path)
            owner.release()

    def test_child_rejects_mismatched_owner_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_directory = Path(directory)
            owner = acquire_backend_lease(
                "stm32",
                30,
                runtime_directory,
            )
            with patch.dict(
                os.environ,
                {EXTERNAL_OWNER_PID_ENV: str(os.getpid() + 1)},
            ):
                with self.assertRaisesRegex(
                    BackendLeaseError,
                    "owner mismatch",
                ):
                    acquire_backend_lease(
                        "stm32",
                        30,
                        runtime_directory,
                    )
            owner.release()

    def test_child_rejects_unheld_lock_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_directory = Path(directory)
            owner = acquire_backend_lease(
                "stm32",
                30,
                runtime_directory,
            )
            owner.release()
            with patch.dict(
                os.environ,
                {EXTERNAL_OWNER_PID_ENV: str(os.getpid())},
            ):
                with self.assertRaisesRegex(
                    BackendLeaseError,
                    "not currently held",
                ):
                    acquire_backend_lease(
                        "stm32",
                        30,
                        runtime_directory,
                    )


if __name__ == "__main__":
    unittest.main()
