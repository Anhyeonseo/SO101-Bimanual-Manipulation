import time
from typing import Optional

import serial

PORT = "/dev/ttyACM0"
BAUDRATE = 1000000

INST_PING = 0x01
INST_READ = 0x02
INST_WRITE = 0x03

ADDR_TORQUE_ENABLE = 40
ADDR_PRESENT_POSITION = 56
ADDR_ACC = 41

# LEFT ID 5 wrist_roll is intentionally excluded.
JOINTS = {
    "base_yaw": 1,
    "shoulder_pitch": 2,
    "elbow_pitch": 3,
    "wrist_pitch": 4,
    "gripper": 6,
}

# Very small step. Increase only after direction and mechanism are confirmed.
STEP = 10
SPEED = 40
ACC = 2
WAIT = 1.0

ERROR_BITS = {
    1: "Input voltage error",
    2: "Angle limit error",
    4: "Over temperature error",
    8: "Range error",
    16: "Checksum error",
    32: "Overload error",
    64: "Instruction error",
}


def decode_error(error: int) -> str:
    if error == 0:
        return "OK"
    names = [name for bit, name in ERROR_BITS.items() if error & bit]
    return ", ".join(names) if names else f"Unknown error {error}"


def make_packet(servo_id: int, instruction: int, params: list[int]) -> bytes:
    length = len(params) + 2
    checksum = ~(servo_id + length + instruction + sum(params)) & 0xFF
    return bytes([0xFF, 0xFF, servo_id, length, instruction, *params, checksum])


def clamp_raw(pos: int) -> int:
    return max(0, min(4095, int(pos)))


class ServoBus:
    def __init__(self, port: str):
        print(f"Open LEFT: {port}")
        self.ser = serial.Serial(port, BAUDRATE, timeout=0.2)
        time.sleep(0.2)

    def close(self):
        self.ser.close()

    def ping(self, servo_id: int) -> bool:
        self.ser.reset_input_buffer()
        self.ser.write(make_packet(servo_id, INST_PING, []))
        self.ser.flush()
        resp = self.ser.read(16)
        ok = len(resp) >= 6 and resp[0] == 0xFF and resp[1] == 0xFF
        print(f"ID {servo_id} ping: {'OK' if ok else 'FAIL'} RX={resp.hex(' ')}")
        return ok

    def write_packet(self, servo_id: int, instruction: int, params: list[int]):
        self.ser.write(make_packet(servo_id, instruction, params))
        self.ser.flush()
        time.sleep(0.04)

    def torque_enable(self, servo_id: int, enable: bool):
        self.write_packet(servo_id, INST_WRITE, [ADDR_TORQUE_ENABLE, 1 if enable else 0])

    def move_raw(self, servo_id: int, position: int):
        position = clamp_raw(position)
        speed = clamp_raw(SPEED)
        params = [
            ADDR_ACC,
            ACC & 0xFF,
            position & 0xFF,
            (position >> 8) & 0xFF,
            0x00,
            0x00,
            speed & 0xFF,
            (speed >> 8) & 0xFF,
        ]
        self.write_packet(servo_id, INST_WRITE, params)

    def read_position(self, servo_id: int) -> Optional[int]:
        self.ser.reset_input_buffer()
        self.ser.write(make_packet(servo_id, INST_READ, [ADDR_PRESENT_POSITION, 2]))
        self.ser.flush()
        resp = self.ser.read(64)
        if len(resp) < 7:
            print(f"ID {servo_id} read: NO RESPONSE RX={resp.hex(' ')}")
            return None
        if resp[0] != 0xFF or resp[1] != 0xFF:
            print(f"ID {servo_id} read: BAD HEADER RX={resp.hex(' ')}")
            return None
        resp_id = resp[2]
        length = resp[3]
        error = resp[4]
        data = resp[5:-1]
        checksum = resp[-1]
        calc = ~(resp_id + length + error + sum(data)) & 0xFF
        if checksum != calc:
            print(f"ID {servo_id} read: CHECKSUM MISMATCH RX={resp.hex(' ')}")
            return None
        if error:
            print(f"[WARN] ID {servo_id}: status error {error} ({decode_error(error)}) RX={resp.hex(' ')}")
        if len(data) < 2:
            return None
        return data[0] | (data[1] << 8)


def scan(bus: ServoBus):
    print("\n=== LEFT 5DOF SCAN, ID 5 SKIPPED ===")
    for name, sid in JOINTS.items():
        bus.ping(sid)
        time.sleep(0.1)


def read_all(bus: ServoBus):
    print("\n=== CURRENT LEFT 5DOF POSITIONS ===")
    current = {}
    for name, sid in JOINTS.items():
        pos = bus.read_position(sid)
        current[name] = pos
        print(f"{name} / ID {sid}: {pos}")
        time.sleep(0.1)
    return current


def test_one_joint(bus: ServoBus, joint_name: str, sid: int):
    print(f"\n--- {joint_name} / ID {sid} MICRO DIRECTION TEST ---")
    start = bus.read_position(sid)
    if start is None:
        print("skip: cannot read start position")
        return

    print(f"start = {start}")
    input("Press ENTER to torque ON this joint and move +STEP. Type Ctrl+C to stop.")

    bus.torque_enable(sid, True)
    time.sleep(0.2)

    plus = clamp_raw(start + STEP)
    print(f"move +{STEP}: {start} -> {plus}")
    bus.move_raw(sid, plus)
    time.sleep(WAIT)
    after_plus = bus.read_position(sid)
    print(f"after +STEP read = {after_plus}")

    input("Observe direction. Press ENTER to return to start.")
    bus.move_raw(sid, start)
    time.sleep(WAIT)
    back1 = bus.read_position(sid)
    print(f"back read = {back1}")

    input("Press ENTER to move -STEP. Type Ctrl+C to stop.")
    minus = clamp_raw(start - STEP)
    print(f"move -{STEP}: {start} -> {minus}")
    bus.move_raw(sid, minus)
    time.sleep(WAIT)
    after_minus = bus.read_position(sid)
    print(f"after -STEP read = {after_minus}")

    input("Observe direction. Press ENTER to return to start and torque OFF.")
    bus.move_raw(sid, start)
    time.sleep(WAIT)
    back2 = bus.read_position(sid)
    print(f"final back read = {back2}")
    bus.torque_enable(sid, False)
    print(f"ID {sid} torque OFF")


def main():
    print("[SAFETY] LEFT ID 5 is disabled. Keep it physically disconnected.")
    print("[SAFETY] This script only moves one joint at a time by ±10 raw.")
    print("[SAFETY] If a joint binds, heats, smells, or moves the wrong way dangerously, press Ctrl+C and cut power.")

    bus = ServoBus(PORT)
    try:
        scan(bus)
        read_all(bus)
        print("\nJoint order:")
        for name, sid in JOINTS.items():
            print(f"  {name}: ID {sid}")

        print("\nStart per-joint direction calibration.")
        for name, sid in JOINTS.items():
            ans = input(f"\nTest {name} / ID {sid}? [y/N]: ").strip().lower()
            if ans == "y":
                test_one_joint(bus, name, sid)
            else:
                print(f"skip {name}")

        print("\nDone. Use the observed +STEP/-STEP directions to build LEFT_DELTA signs.")
    finally:
        print("Close serial")
        bus.close()


if __name__ == "__main__":
    main()
