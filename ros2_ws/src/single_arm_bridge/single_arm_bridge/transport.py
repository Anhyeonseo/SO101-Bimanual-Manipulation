"""Synchronous serial session used by the ROS node and unit tests."""

from __future__ import annotations

import struct
import time
from collections import deque
from typing import Any

from .protocol import (
    ARM_RESPONSE,
    SETPOINT_STATUS,
    Frame,
    Hello,
    MessageType,
    ProtocolError,
    State,
    decode_frame,
    encode_frame,
    parse_hello,
    parse_setpoint_status,
    parse_state,
)


class TransportError(RuntimeError):
    pass


class ActuatorTransport:
    def __init__(self, port: Any, response_timeout_s: float = 0.4) -> None:
        self._port = port
        self._timeout_s = response_timeout_s
        self._sequence = 1
        self.hello_info: Hello | None = None
        self._motion_results: deque[Any] = deque(maxlen=16)

    def _next_sequence(self) -> int:
        result = self._sequence
        self._sequence = (self._sequence + 1) & 0xFFFFFFFF
        return result

    @staticmethod
    def _now_ms() -> int:
        return int(time.monotonic() * 1000.0) & 0xFFFFFFFF

    def _send(self, message_type: MessageType, payload: bytes = b"", flags: int = 0) -> int:
        sequence = self._next_sequence()
        self._port.write(
            encode_frame(
                Frame(message_type, flags, sequence, self._now_ms(), payload)
            )
        )
        self._port.flush()
        return sequence

    def _receive_matching(
        self,
        sequence: int,
        message_type: MessageType,
        timeout_s: float | None = None,
    ) -> Frame:
        response_timeout = self._timeout_s if timeout_s is None else timeout_s
        deadline = time.monotonic() + response_timeout
        while time.monotonic() < deadline:
            packet = self._port.read_until(b"\x00")
            if not packet.endswith(b"\x00"):
                continue
            try:
                frame = decode_frame(packet)
            except ProtocolError:
                continue
            if frame.sequence == sequence and frame.message_type is message_type:
                return frame
            if frame.message_type is MessageType.SETPOINT_STATUS:
                result = parse_setpoint_status(frame.payload)
                if result.status_code != 0:
                    self._motion_results.append(result)
        raise TransportError(f"timeout waiting for {message_type.name}")

    def drain_motion_results(self) -> list[Any]:
        results = list(self._motion_results)
        self._motion_results.clear()
        return results

    def enter_binary_mode(self) -> Hello:
        self._port.reset_input_buffer()
        self._port.write(b"P")
        self._port.flush()

        acknowledgement = ""
        acknowledgement_deadline = time.monotonic() + self._timeout_s
        while time.monotonic() < acknowledgement_deadline:
            line = self._port.readline().decode("ascii", errors="replace").strip()
            if line == "BINARY_PROTOCOL_READY_RESET_TO_EXIT":
                acknowledgement = line
                break
            if not line:
                break

        if not acknowledgement:
            # A previous host may already have switched the MCU to binary mode.
            # Terminate any partial ASCII byte buffered by the COBS parser, then
            # prove the mode with HELLO instead of requiring a physical reset.
            self._port.write(b"\x00")
            self._port.flush()
            self._port.reset_input_buffer()

        sequence = self._send(MessageType.HELLO_REQUEST)
        try:
            hello = parse_hello(
                self._receive_matching(sequence, MessageType.HELLO_RESPONSE).payload
            )
        except Exception as error:
            raise TransportError(
                "binary mode entry/reconnect failed; press RESET and retry"
            ) from error
        if hello.protocol_version != 1 or hello.joint_count != 6:
            raise TransportError("protocol version or joint count mismatch")
        if (hello.capabilities & 0x00000008) == 0:
            raise TransportError("firmware does not provide position feedback")
        self.hello_info = hello
        return hello

    def heartbeat(self) -> None:
        self._send(MessageType.HEARTBEAT)

    def get_state(self, include_positions: bool = True) -> State:
        payload = b"\x01" if include_positions else b""
        sequence = self._send(MessageType.GET_STATE, payload)
        state = parse_state(
            self._receive_matching(sequence, MessageType.STATE_FEEDBACK).payload
        )
        if state.status_code != 0:
            raise TransportError(f"GET_STATE status={state.status_code}")
        if include_positions and state.raw_positions is None:
            raise TransportError("position feedback missing")
        return state

    def arm_and_enable(self, calibration_hash: int) -> None:
        sequence = self._send(
            MessageType.ARM_REQUEST,
            struct.pack("<I", calibration_hash),
        )
        result, state, returned_hash = ARM_RESPONSE.unpack(
            self._receive_matching(
                sequence,
                MessageType.ARM_RESPONSE,
                timeout_s=1.5,
            ).payload
        )
        if result != 0 or state != 2 or returned_hash != calibration_hash:
            raise TransportError("ARM_REQUEST rejected")
        self.heartbeat()
        sequence = self._send(MessageType.ENABLE)
        enabled = parse_state(
            self._receive_matching(sequence, MessageType.STATE_FEEDBACK).payload
        )
        if enabled.status_code != 0 or enabled.stop_latched:
            raise TransportError("ENABLE rejected")

    def send_setpoint(self, positions_urad: list[int], duration_ms: int) -> None:
        if len(positions_urad) != 6 or not 300 <= duration_ms <= 2000:
            raise ValueError("six positions and duration 300..2000ms are required")
        self.heartbeat()
        state = self.get_state(include_positions=False)
        apply_tick = (state.last_heartbeat_ms + duration_ms) & 0xFFFFFFFF
        payload = struct.pack(
            "<IBBH" + "I" + "i" * 12,
            apply_tick,
            1,
            1,
            0,
            0,
            *positions_urad,
            *([0] * 6),
        )
        sequence = self._send(MessageType.SETPOINT_BATCH, payload)
        status = SETPOINT_STATUS.unpack(
            self._receive_matching(sequence, MessageType.SETPOINT_STATUS).payload
        )
        if status[0] != 0:
            raise TransportError(f"SETPOINT_BATCH rejected: status={status[0]}")

    def safe_stop(self) -> None:
        sequence = self._send(MessageType.SAFE_STOP)
        state = parse_state(
            self._receive_matching(
                sequence,
                MessageType.STATE_FEEDBACK,
                timeout_s=0.5,
            ).payload
        )
        if not state.stop_latched:
            raise TransportError("SAFE_STOP was not latched")

    def disable(self) -> None:
        sequence = self._send(MessageType.DISABLE)
        state = parse_state(
            self._receive_matching(
                sequence,
                MessageType.STATE_FEEDBACK,
                timeout_s=0.2,
            ).payload
        )
        if state.status_code != 0:
            raise TransportError(f"DISABLE rejected: status={state.status_code}")

    def clear_fault(self) -> State:
        sequence = self._send(MessageType.CLEAR_FAULT)
        state = parse_state(
            self._receive_matching(
                sequence,
                MessageType.STATE_FEEDBACK,
                timeout_s=0.5,
            ).payload
        )
        if state.status_code != 0 or state.stop_latched:
            raise TransportError(
                f"CLEAR_FAULT rejected: status={state.status_code} "
                f"latched={int(state.stop_latched)}"
            )
        return state
