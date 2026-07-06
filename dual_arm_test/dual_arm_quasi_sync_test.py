import json
import time
from typing import Dict, Optional

import serial

LEFT_PORT = "/dev/ttyACM0"
RIGHT_PORT = "/dev/ttyACM1"
BAUDRATE = 1000000

LEFT_HOME_PATH = "left_home_pose_5dof.json"
RIGHT_HOME_PATH = "right_home_pose.json"

INST_PING = 0x01
INST_READ = 0x02
INST_WRITE = 0x03

ADDR_TORQUE_ENABLE = 40
ADDR_PRESENT_POSITION = 56
ADDR_ACC = 41

# LEFT ID 5 is disabled in this test.
LEFT_JOINTS = {
    "base_yaw": 1,
    "shoulder_pitch": 2,
    "elbow_pitch": 3,
    "wrist_pitch": 4,
    "gripper": 6,
}

RIGHT_JOINTS = {
    "base_yaw": 1,
    "shoulder_pitch": 2,
    "elbow_pitch": 3,
    "wrist_pitch": 4,
    "wrist_roll": 5,
    "gripper": 6,
}

# Common order used for quasi-simultaneous dual write.
# If a joint does not exist on one side, that side is skipped.
DUAL_JOINT_ORDER = [
    "base_yaw",
    "shoulder_pitch",
    "elbow_pitch",
    "wrist_pitch",
    "wrist_roll",
    "gripper",
]

# Safe small deltas. Increase only after this passes repeatedly.
LEFT_TEST_DELTA = {
    "base_yaw": 30,
    "shoulder_pitch": -40,
    "elbow_pitch": 60,
    "wrist_pitch": -30,
    "gripper": 0,
}

RIGHT_TEST_DELTA = {
    "base_yaw": 50,
    "shoulder_pitch": -250,
    "elbow_pitch": 270,
    "wrist_pitch": -180,
    "wrist_roll": 0,
    "gripper": 0,
}

HOME_SPEED = 120
HOME_ACC = 5
TEST_SPEED = 140
TEST_ACC = 6

# Gap between left/right serial writes for the same joint.
# 0.003~0.010 is a practical range for this USB-serial setup.
DUAL_WRITE_GAP = 0.001

# Gap after each joint pair.
JOINT_PAIR_INTERVAL = 0.02

POSE_WAIT = 2.5
READ_INTERVAL = 0.08

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


def move_params(position: int, speed: int, acc: int) -> list[int]:
    position = clamp_raw(position)
    speed = clamp_raw(speed)
    acc = max(0, min(255, int(acc)))
    return [
        ADDR_ACC,
        acc & 0xFF,
        position & 0xFF,
        (position >> 8) & 0xFF,
        0x00,
        0x00,
        speed & 0xFF,
        (speed >> 8) & 0xFF,
    ]


class ServoBus:
    def __init__(self, name: str, port: str, joints: Dict[str, int], timeout: float = 0.2):
        self.name = name
        self.port = port
        self.joints = joints
        print(f"Open {name}: {port}")
        self.ser = serial.Serial(port, BAUDRATE, timeout=timeout)
        time.sleep(0.1)

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def write_packet(self, servo_id: int, instruction: int, params: list[int], post_delay: float = 0.0):
        packet = make_packet(servo_id, instruction, params)
        self.ser.write(packet)
        self.ser.flush()
        if post_delay > 0:
            time.sleep(post_delay)

    def ping(self, servo_id: int) -> bool:
        packet = make_packet(servo_id, INST_PING, [])
        self.ser.reset_input_buffer()
        self.ser.write(packet)
        self.ser.flush()
        resp = self.ser.read(6)
        ok = len(resp) >= 6 and resp[0] == 0xFF and resp[1] == 0xFF
        print(f"[{self.name}] ID {servo_id} ping: {'OK' if ok else 'FAIL'} RX={resp.hex(' ')}")
        return ok

    def write_byte(self, servo_id: int, address: int, value: int):
        self.write_packet(servo_id, INST_WRITE, [address, value & 0xFF], post_delay=0.03)

    def torque_enable(self, servo_id: int, enable: bool = True):
        self.write_byte(servo_id, ADDR_TORQUE_ENABLE, 1 if enable else 0)

    def move_raw(self, servo_id: int, position: int, speed: int, acc: int, post_delay: float = 0.03):
        self.write_packet(servo_id, INST_WRITE, move_params(position, speed, acc), post_delay=post_delay)

    def read_position(self, servo_id: int) -> Optional[int]:
        packet = make_packet(servo_id, INST_READ, [ADDR_PRESENT_POSITION, 2])
        self.ser.reset_input_buffer()
        self.ser.write(packet)
        self.ser.flush()
        resp = self.ser.read(64)

        if len(resp) < 7:
            print(f"[WARN] {self.name} ID {servo_id}: no response RX={resp.hex(' ')}")
            return None
        if resp[0] != 0xFF or resp[1] != 0xFF:
            print(f"[WARN] {self.name} ID {servo_id}: bad header RX={resp.hex(' ')}")
            return None

        resp_id = resp[2]
        length = resp[3]
        error = resp[4]
        data = resp[5:-1]
        checksum = resp[-1]
        calc = ~(resp_id + length + error + sum(data)) & 0xFF

        if checksum != calc:
            print(f"[WARN] {self.name} ID {servo_id}: checksum mismatch RX={resp.hex(' ')}")
            return None
        if error != 0:
            print(f"[WARN] {self.name} ID {servo_id}: status error {error} ({decode_error(error)}) RX={resp.hex(' ')}")
        if len(data) < 2:
            return None
        return data[0] | (data[1] << 8)


def load_pose(path: str, joints: Dict[str, int]) -> Dict[str, int]:
    with open(path, "r") as f:
        data = json.load(f)
    missing = [j for j in joints if j not in data]
    if missing:
        raise ValueError(f"{path} missing joints: {missing}")
    return {j: clamp_raw(data[j]) for j in joints}


def add_delta(home: Dict[str, int], delta: Dict[str, int], joints: Dict[str, int]) -> Dict[str, int]:
    return {j: clamp_raw(home[j] + delta.get(j, 0)) for j in joints}


def print_pose(title: str, pose: Dict[str, Optional[int]], joints: Dict[str, int]):
    print(f"\n{title}")
    for j in joints:
        print(f"  {j}: {pose.get(j)}")
    print()


def read_all(bus: ServoBus) -> Dict[str, Optional[int]]:
    out = {}
    for j, sid in bus.joints.items():
        out[j] = bus.read_position(sid)
        time.sleep(READ_INTERVAL)
    return out


def print_error(label: str, final: Dict[str, Optional[int]], target: Dict[str, int], joints: Dict[str, int]):
    print(f"\n=== {label} ERROR FROM TARGET ===")
    for j in joints:
        if final.get(j) is None:
            print(f"{j}: read failed")
        else:
            print(f"{j}: {final[j] - target[j]}")


def scan(bus: ServoBus):
    print(f"\n=== SCAN {bus.name} ===")
    found = []
    for sid in range(1, 7):
        if bus.name == "LEFT" and sid == 5:
            print("[LEFT] ID 5 scan: SKIP (disabled / disconnected)")
            continue
        if bus.ping(sid):
            found.append(sid)
        time.sleep(0.06)
    print(f"[{bus.name}] found IDs: {found}")


def torque_all(bus: ServoBus, enable: bool = True):
    for j, sid in bus.joints.items():
        print(f"[{bus.name}] torque {'ON' if enable else 'OFF'} {j} / ID {sid}")
        bus.torque_enable(sid, enable)
        time.sleep(0.08)


def move_both_quasi_sync(
    left: ServoBus,
    right: ServoBus,
    left_pose: Dict[str, int],
    right_pose: Dict[str, int],
    speed: int,
    acc: int,
    label: str,
):
    print(f"\n=== QUASI-SYNC DUAL WRITE: {label} ===")
    print(f"[INFO] DUAL_WRITE_GAP={DUAL_WRITE_GAP}s, JOINT_PAIR_INTERVAL={JOINT_PAIR_INTERVAL}s")

    for joint_name in DUAL_JOINT_ORDER:
        left_has = joint_name in left.joints
        right_has = joint_name in right.joints

        if not left_has and not right_has:
            continue

        if left_has:
            l_sid = left.joints[joint_name]
            l_target = clamp_raw(left_pose[joint_name])
            print(f"[DUAL] LEFT  {joint_name:14s} ID {l_sid} -> {l_target}")
            left.move_raw(l_sid, l_target, speed=speed, acc=acc, post_delay=0.0)

        time.sleep(DUAL_WRITE_GAP)

        if right_has:
            r_sid = right.joints[joint_name]
            r_target = clamp_raw(right_pose[joint_name])
            print(f"[DUAL] RIGHT {joint_name:14s} ID {r_sid} -> {r_target}")
            right.move_raw(r_sid, r_target, speed=speed, acc=acc, post_delay=0.0)

        time.sleep(JOINT_PAIR_INTERVAL)


def main():
    left_home = load_pose(LEFT_HOME_PATH, LEFT_JOINTS)
    right_home = load_pose(RIGHT_HOME_PATH, RIGHT_JOINTS)
    left_test = add_delta(left_home, LEFT_TEST_DELTA, LEFT_JOINTS)
    right_test = add_delta(right_home, RIGHT_TEST_DELTA, RIGHT_JOINTS)

    print("[SAFETY] LEFT ID 5 is disabled. Keep it physically disconnected.")
    print("[SAFETY] This file tests quasi-simultaneous dual write. Cut power immediately if the arm binds, smells, or heats.")
    print(f"[INFO] LEFT_HOME_PATH={LEFT_HOME_PATH}")
    print(f"[INFO] RIGHT_HOME_PATH={RIGHT_HOME_PATH}")

    print_pose("LEFT HOME 5DOF", left_home, LEFT_JOINTS)
    print_pose("RIGHT HOME 6DOF", right_home, RIGHT_JOINTS)
    print_pose("LEFT TEST 5DOF", left_test, LEFT_JOINTS)
    print_pose("RIGHT TEST 6DOF", right_test, RIGHT_JOINTS)

    left = ServoBus("LEFT", LEFT_PORT, LEFT_JOINTS)
    right = ServoBus("RIGHT", RIGHT_PORT, RIGHT_JOINTS)

    try:
        scan(left)
        scan(right)

        print("\n=== CURRENT POSITION CHECK ===")
        left_cur = read_all(left)
        right_cur = read_all(right)
        print_pose("LEFT CURRENT 5DOF", left_cur, LEFT_JOINTS)
        print_pose("RIGHT CURRENT 6DOF", right_cur, RIGHT_JOINTS)

        input("\nPress ENTER to torque ON enabled joints only, or Ctrl+C to stop.")
        print("\n=== TORQUE ON ENABLED JOINTS ONLY ===")
        torque_all(left, True)
        torque_all(right, True)

        input("\nPress ENTER to start QUASI-SYNC HOME -> TEST -> HOME, or Ctrl+C to stop.")

        move_both_quasi_sync(left, right, left_home, right_home, HOME_SPEED, HOME_ACC, "HOME")
        time.sleep(POSE_WAIT)

        move_both_quasi_sync(left, right, left_test, right_test, TEST_SPEED, TEST_ACC, "TEST")
        time.sleep(POSE_WAIT)

        move_both_quasi_sync(left, right, left_home, right_home, TEST_SPEED, TEST_ACC, "HOME BACK")
        time.sleep(POSE_WAIT)

        print("\n=== FINAL POSITION CHECK ===")
        left_after = read_all(left)
        right_after = read_all(right)
        print_pose("LEFT AFTER QUASI-SYNC", left_after, LEFT_JOINTS)
        print_pose("RIGHT AFTER QUASI-SYNC", right_after, RIGHT_JOINTS)
        print_error("LEFT QUASI-SYNC", left_after, left_home, LEFT_JOINTS)
        print_error("RIGHT QUASI-SYNC", right_after, right_home, RIGHT_JOINTS)

    finally:
        print("\nClose serial")
        left.close()
        right.close()


if __name__ == "__main__":
    main()
