import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest


PACKAGE_ROOT = Path("ros2_ws/src/single_arm_bridge")
sys.path.insert(0, str(PACKAGE_ROOT))

from single_arm_bridge.calibration import load_calibration  # noqa: E402
from single_arm_bridge.device_discovery import resolve_serial_device  # noqa: E402
from single_arm_bridge.protocol import (  # noqa: E402
    Frame,
    MessageType,
    decode_frame,
    encode_frame,
)
from single_arm_bridge.transport import ActuatorTransport  # noqa: E402


CALIBRATION_PATH = PACKAGE_ROOT / "config" / "single_arm_calibration.json"


class FakeSerial:
    def __init__(
        self,
        already_binary: bool = False,
        include_async_result: bool = False,
    ) -> None:
        self._responses: list[bytes] = []
        self._ascii_response = b""
        self._already_binary = already_binary
        self._include_async_result = include_async_result

    def reset_input_buffer(self) -> None:
        self._responses.clear()

    def flush(self) -> None:
        pass

    def write(self, data: bytes) -> int:
        if data == b"P":
            if not self._already_binary:
                self._ascii_response = b"BINARY_PROTOCOL_READY_RESET_TO_EXIT\r\n"
            return 1
        if data == b"\x00":
            return 1

        request = decode_frame(data)
        if request.message_type is MessageType.HELLO_REQUEST:
            payload = struct.pack(
                "<BBBBIIII",
                1,
                6,
                0,
                0,
                0x00020700,
                0x3DB42B48,
                0x0000000F,
                0,
            )
            response_type = MessageType.HELLO_RESPONSE
        elif request.message_type is MessageType.GET_STATE:
            if self._include_async_result:
                self._responses.append(
                    encode_frame(
                        Frame(
                            message_type=MessageType.SETPOINT_STATUS,
                            sequence=77,
                            sender_time_ms=1200,
                            payload=struct.pack(
                                "<BBBBIII",
                                6,
                                1,
                                3,
                                4,
                                77,
                                1200,
                                0x3DB42B48,
                            ),
                        )
                    )
                )
            payload = struct.pack(
                "<BBBBIIII6H",
                0,
                0,
                6,
                1,
                3,
                0,
                0x3DB42B48,
                1200,
                2048,
                2050,
                2046,
                2047,
                2051,
                2045,
            )
            response_type = MessageType.STATE_FEEDBACK
        elif request.message_type is MessageType.CLEAR_FAULT:
            payload = struct.pack(
                "<BBBBIIII",
                0,
                0,
                6,
                1,
                4,
                0,
                0x3DB42B48,
                1200,
            )
            response_type = MessageType.STATE_FEEDBACK
        else:
            return len(data)

        self._responses.append(
            encode_frame(
                Frame(
                    message_type=response_type,
                    sequence=request.sequence,
                    sender_time_ms=1201,
                    payload=payload,
                )
            )
        )
        return len(data)

    def readline(self) -> bytes:
        response = self._ascii_response
        self._ascii_response = b""
        return response

    def read_until(self, delimiter: bytes) -> bytes:
        del delimiter
        return self._responses.pop(0) if self._responses else b""


class SingleArmBridgeCoreTests(unittest.TestCase):
    def test_explicit_serial_device_is_preserved(self) -> None:
        self.assertEqual(resolve_serial_device("COM3"), "COM3")

    def test_auto_serial_device_uses_unique_stlink_by_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            by_id = Path(directory)
            device = by_id / "usb-STMicroelectronics_STLINK-V3_TEST-if02"
            device.touch()
            self.assertEqual(
                resolve_serial_device(
                    "auto",
                    by_id_directory=by_id,
                    fallback_device=by_id / "missing",
                ),
                str(device),
            )

    def test_auto_serial_device_rejects_ambiguous_stlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            by_id = Path(directory)
            for serial in ("A", "B"):
                (by_id / f"usb-STMicroelectronics_STLINK-V3_{serial}-if02").touch()
            with self.assertRaisesRegex(RuntimeError, "multiple ST-LINK"):
                resolve_serial_device(
                    "auto",
                    by_id_directory=by_id,
                    fallback_device=by_id / "missing",
                )

    def test_auto_serial_device_falls_back_to_ttyacm0(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fallback = root / "ttyACM0"
            fallback.touch()
            self.assertEqual(
                resolve_serial_device(
                    "auto",
                    by_id_directory=root / "missing",
                    fallback_device=fallback,
                ),
                str(fallback),
            )

    def test_packaged_calibration_matches_repository_source(self) -> None:
        source = json.loads(
            Path("config/single_arm_calibration.json").read_text(encoding="utf-8")
        )
        packaged = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
        self.assertEqual(packaged["joints"], source["joints"])
        self.assertEqual(packaged["arm_slot"], source["arm_slot"])

    def test_calibration_hash_and_feedback_conversion(self) -> None:
        calibration = load_calibration(CALIBRATION_PATH)
        self.assertEqual(calibration.calibration_hash, 0x3DB42B48)
        radians = calibration.raw_feedback_to_radians(
            (2048, 2048, 2048, 2048, 2048, 2048)
        )
        self.assertEqual(radians, [0.0] * 6)

    def test_transport_enters_binary_mode_and_reads_positions(self) -> None:
        transport = ActuatorTransport(FakeSerial(), response_timeout_s=0.01)
        hello = transport.enter_binary_mode()
        self.assertEqual(hello.firmware_version, 0x00020700)
        state = transport.get_state(include_positions=True)
        self.assertEqual(
            state.raw_positions,
            (2048, 2050, 2046, 2047, 2051, 2045),
        )

    def test_transport_reconnects_when_mcu_is_already_binary(self) -> None:
        transport = ActuatorTransport(
            FakeSerial(already_binary=True),
            response_timeout_s=0.01,
        )
        hello = transport.enter_binary_mode()
        self.assertEqual(hello.capabilities, 0x0000000F)

    def test_transport_preserves_async_motion_completion(self) -> None:
        transport = ActuatorTransport(
            FakeSerial(include_async_result=True),
            response_timeout_s=0.01,
        )
        transport.enter_binary_mode()
        transport.get_state(include_positions=True)
        results = transport.drain_motion_results()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status_code, 6)
        self.assertEqual(results[0].detail, 4)

    def test_transport_clear_fault_requires_unlatched_success(self) -> None:
        transport = ActuatorTransport(FakeSerial(), response_timeout_s=0.01)
        transport.enter_binary_mode()
        state = transport.clear_fault()
        self.assertFalse(state.stop_latched)
        self.assertEqual(state.status_code, 0)


if __name__ == "__main__":
    unittest.main()
