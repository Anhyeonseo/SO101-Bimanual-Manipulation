import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


PACKAGE_ROOT = Path("ros2_ws/src/single_arm_bridge")
sys.path.insert(0, str(PACKAGE_ROOT))

from single_arm_bridge.backend_lease import (  # noqa: E402
    BackendLeaseError,
    LOCK_FILENAME,
    acquire_backend_lease,
)
from single_arm_bridge.serial_port import open_exclusive_serial  # noqa: E402


class FakeSerialModule:
    def __init__(self) -> None:
        self.args = None
        self.kwargs = None
        self.port = object()

    def Serial(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return self.port


class BackendExclusivityTests(unittest.TestCase):
    def test_second_backend_is_rejected_without_overwriting_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_directory = Path(directory)
            first = acquire_backend_lease("stm32", 30, runtime_directory)
            owner_before = first.path.read_text(encoding="utf-8")

            with self.assertRaisesRegex(
                BackendLeaseError,
                '"backend": "stm32"',
            ):
                acquire_backend_lease("isaac", 30, runtime_directory)

            self.assertEqual(
                first.path.read_text(encoding="utf-8"),
                owner_before,
            )
            first.release()

    def test_release_allows_a_new_backend_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_directory = Path(directory)
            first = acquire_backend_lease("mock", 30, runtime_directory)
            first.release()
            self.assertFalse(first.acquired)

            second = acquire_backend_lease("isaac", 30, runtime_directory)
            self.assertTrue(second.acquired)
            owner = json.loads(second.path.read_text(encoding="utf-8"))
            self.assertEqual(owner["backend"], "isaac")
            self.assertEqual(owner["pid"], os.getpid())
            self.assertEqual(owner["ros_domain_id"], 30)
            second.release()

    def test_invalid_backend_does_not_create_a_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_directory = Path(directory)
            with self.assertRaisesRegex(BackendLeaseError, "unsupported backend"):
                acquire_backend_lease("", 30, runtime_directory)
            self.assertFalse((runtime_directory / LOCK_FILENAME).exists())

    def test_invalid_ros_domain_does_not_create_a_lock(self) -> None:
        for domain_id in (-1, 233, True, "30"):
            with self.subTest(domain_id=domain_id):
                with tempfile.TemporaryDirectory() as directory:
                    runtime_directory = Path(directory)
                    with self.assertRaisesRegex(
                        BackendLeaseError,
                        "ROS domain ID",
                    ):
                        acquire_backend_lease(
                            "stm32",
                            domain_id,
                            runtime_directory,
                        )
                    self.assertFalse(
                        (runtime_directory / LOCK_FILENAME).exists()
                    )

    def test_lock_file_is_private_to_the_user(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lease = acquire_backend_lease("stm32", 30, Path(directory))
            mode = stat.S_IMODE(lease.path.stat().st_mode)
            self.assertEqual(mode, 0o600)
            lease.release()

    def test_process_exit_automatically_releases_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child_code = (
                "import sys; "
                f"sys.path.insert(0, {str(PACKAGE_ROOT.resolve())!r}); "
                "from pathlib import Path; "
                "from single_arm_bridge.backend_lease import "
                "acquire_backend_lease; "
                "lease = acquire_backend_lease('stm32', 30, Path(sys.argv[1]))"
            )
            subprocess.run(
                [sys.executable, "-c", child_code, directory],
                check=True,
            )

            replacement = acquire_backend_lease("mock", 30, Path(directory))
            self.assertTrue(replacement.acquired)
            replacement.release()

    def test_serial_open_requests_posix_exclusivity(self) -> None:
        serial_module = FakeSerialModule()
        port = open_exclusive_serial(
            serial_module,
            "/dev/ttyACM0",
            115200,
            0.12,
        )

        self.assertIs(port, serial_module.port)
        self.assertEqual(serial_module.args, ("/dev/ttyACM0", 115200))
        self.assertEqual(
            serial_module.kwargs,
            {
                "timeout": 0.12,
                "write_timeout": 0.12,
                "exclusive": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
