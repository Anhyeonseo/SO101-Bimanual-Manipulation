"""Binary actuator protocol codec. This module has no ROS dependency."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import struct


MAGIC = 0xA55A
VERSION = 1
MAX_PAYLOAD = 512
HEADER = struct.Struct("<HBBHHII")
CRC = struct.Struct("<I")
HELLO_PAYLOAD = struct.Struct("<BBBBIIII")
STATE_BASE = struct.Struct("<BBBBIIII")
STATE_POSITIONS = struct.Struct("<6H")
ARM_RESPONSE = struct.Struct("<BB2xI")
SETPOINT_STATUS = struct.Struct("<BBBBIII")


class MessageType(IntEnum):
    HELLO_REQUEST = 1
    HELLO_RESPONSE = 2
    HEARTBEAT = 3
    ARM_REQUEST = 16
    ARM_RESPONSE = 17
    ENABLE = 18
    HOLD = 19
    SAFE_STOP = 20
    DISABLE = 21
    CLEAR_FAULT = 22
    SETPOINT_BATCH = 32
    SETPOINT_STATUS = 33
    GET_STATE = 48
    STATE_FEEDBACK = 49


KNOWN_TYPES = {int(value) for value in MessageType}


class ProtocolError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Frame:
    message_type: MessageType
    flags: int = 0
    sequence: int = 0
    sender_time_ms: int = 0
    payload: bytes = b""


@dataclass(frozen=True, slots=True)
class Hello:
    protocol_version: int
    joint_count: int
    stop_latched: bool
    firmware_version: int
    calibration_hash: int
    capabilities: int
    rejected_frame_count: int


@dataclass(frozen=True, slots=True)
class State:
    stop_latched: bool
    status_code: int
    joint_count: int
    protocol_version: int
    heartbeat_count: int
    rejected_frame_count: int
    calibration_hash: int
    last_heartbeat_ms: int
    raw_positions: tuple[int, ...] | None


@dataclass(frozen=True, slots=True)
class MotionResult:
    status_code: int
    sample_count: int
    safety_state: int
    detail: int
    request_sequence: int
    apply_tick_ms: int
    calibration_hash: int


def crc32c(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            mask = -(crc & 1) & 0xFFFFFFFF
            crc = ((crc >> 1) ^ (0x82F63B78 & mask)) & 0xFFFFFFFF
    return (~crc) & 0xFFFFFFFF


def cobs_encode(data: bytes) -> bytes:
    output = bytearray(b"\x00")
    code_index = 0
    code = 1
    for byte in data:
        if byte == 0:
            output[code_index] = code
            code_index = len(output)
            output.append(0)
            code = 1
        else:
            output.append(byte)
            code += 1
            if code == 0xFF:
                output[code_index] = code
                code_index = len(output)
                output.append(0)
                code = 1
    output[code_index] = code
    return bytes(output)


def cobs_decode(encoded: bytes) -> bytes:
    if not encoded:
        raise ProtocolError("empty COBS frame")
    output = bytearray()
    index = 0
    while index < len(encoded):
        code = encoded[index]
        if code == 0:
            raise ProtocolError("zero inside COBS frame")
        index += 1
        block_end = index + code - 1
        if block_end > len(encoded):
            raise ProtocolError("truncated COBS frame")
        output.extend(encoded[index:block_end])
        index = block_end
        if code != 0xFF and index < len(encoded):
            output.append(0)
    return bytes(output)


def encode_frame(frame: Frame) -> bytes:
    if int(frame.message_type) not in KNOWN_TYPES:
        raise ProtocolError("unknown message type")
    if len(frame.payload) > MAX_PAYLOAD:
        raise ProtocolError("payload too large")
    header = HEADER.pack(
        MAGIC,
        VERSION,
        int(frame.message_type),
        frame.flags,
        len(frame.payload),
        frame.sequence,
        frame.sender_time_ms,
    )
    decoded = header + frame.payload
    return cobs_encode(decoded + CRC.pack(crc32c(decoded))) + b"\x00"


def decode_frame(packet: bytes) -> Frame:
    encoded = packet[:-1] if packet.endswith(b"\x00") else packet
    decoded = cobs_decode(encoded)
    if len(decoded) < HEADER.size + CRC.size:
        raise ProtocolError("short frame")
    magic, version, raw_type, flags, length, sequence, sender_ms = (
        HEADER.unpack_from(decoded)
    )
    if magic != MAGIC or version != VERSION or raw_type not in KNOWN_TYPES:
        raise ProtocolError("invalid header")
    expected_length = HEADER.size + length + CRC.size
    if len(decoded) != expected_length:
        raise ProtocolError("invalid payload length")
    expected_crc = CRC.unpack_from(decoded, HEADER.size + length)[0]
    if crc32c(decoded[: HEADER.size + length]) != expected_crc:
        raise ProtocolError("bad CRC-32C")
    return Frame(
        message_type=MessageType(raw_type),
        flags=flags,
        sequence=sequence,
        sender_time_ms=sender_ms,
        payload=decoded[HEADER.size : HEADER.size + length],
    )


def parse_hello(payload: bytes) -> Hello:
    if len(payload) != HELLO_PAYLOAD.size:
        raise ProtocolError("invalid HELLO_RESPONSE length")
    version, count, stop, _, firmware, cal_hash, capabilities, rejected = (
        HELLO_PAYLOAD.unpack(payload)
    )
    return Hello(version, count, stop != 0, firmware, cal_hash, capabilities, rejected)


def parse_state(payload: bytes) -> State:
    if len(payload) not in (STATE_BASE.size, STATE_BASE.size + STATE_POSITIONS.size):
        raise ProtocolError("invalid STATE_FEEDBACK length")
    values = STATE_BASE.unpack_from(payload)
    positions = None
    if len(payload) > STATE_BASE.size:
        positions = STATE_POSITIONS.unpack_from(payload, STATE_BASE.size)
    return State(
        stop_latched=values[0] != 0,
        status_code=values[1],
        joint_count=values[2],
        protocol_version=values[3],
        heartbeat_count=values[4],
        rejected_frame_count=values[5],
        calibration_hash=values[6],
        last_heartbeat_ms=values[7],
        raw_positions=positions,
    )


def parse_setpoint_status(payload: bytes) -> MotionResult:
    if len(payload) != SETPOINT_STATUS.size:
        raise ProtocolError("invalid SETPOINT_STATUS length")
    return MotionResult(*SETPOINT_STATUS.unpack(payload))
