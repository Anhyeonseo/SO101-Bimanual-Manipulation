import json
import time
from typing import Dict, Optional

import serial

LEFT_PORT = "/dev/ttyACM0"
RIGHT_PORT = "/dev/ttyACM1"
BAUDRATE = 1000000

LEFT_HOME_PATH = "left_home_pose.json"
RIGHT_HOME_PATH = "right_home_pose.json"

INST_PING = 0x01
INST_READ = 0x02
INST_WRITE = 0x03

ADDR_TORQUE_ENABLE = 40
ADDR_PRESENT_POSITION = 56
ADDR_ACC = 41

JOINTS = {
    "base_yaw": 1,
    "shoulder_pitch": 2,
    "elbow_pitch": 3,
    "wrist_pitch": 4,
    "wrist_roll": 5,
    "gripper": 6,
}

# 원래 arm_test.py 기준 delta. 불안정하면 아래 SAFE_TEST_DELTA로 바꿔도 됨.
TEST_DELTA = {
    "base_yaw": 80,
    "shoulder_pitch": -420,
    "elbow_pitch": 480,
    "wrist_pitch": -300,
    "wrist_roll": 0,
    "gripper": 0,
}

SAFE_TEST_DELTA = {
    "base_yaw": 50,
    "shoulder_pitch": -250,
    "elbow_pitch": 300,
    "wrist_pitch": -180,
    "wrist_roll": 0,
    "gripper": 0,
}

USE_SAFE_DELTA = False

HOME_SPEED = 180
HOME_ACC = 10
TEST_SPEED = 220
TEST_ACC = 15

JOINT_INTERVAL = 0.06
ARM_INTERVAL = 0.25
POSE_WAIT = 3.0

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
    def __init__(self, name: str, port: str, timeout: float = 0.2):
        self.name = name
        self.port = port
        print(f"Open {name}: {port}")
        self.ser = serial.Serial(port, BAUDRATE, timeout=timeout)
        time.sleep(0.1)

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def write_packet(self, servo_id: int, instruction: int, params: list[int]):
        packet = make_packet(servo_id, instruction, params)
        self.ser.write(packet)
        self.ser.flush()
        time.sleep(0.03)

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
        self.write_packet(servo_id, INST_WRITE, [address, value & 0xFF])

    def torque_enable(self, servo_id: int, enable: bool = True):
        self.write_byte(servo_id, ADDR_TORQUE_ENABLE, 1 if enable else 0)

    def move_raw(self, servo_id: int, position: int, speed: int, acc: int):
        position = clamp_raw(position)
        speed = clamp_raw(speed)
        acc = max(0, min(255, int(acc)))
        params = [
            ADDR_ACC,
            acc & 0xFF,
            position & 0xFF,
            (position >> 8) & 0xFF,
            0x00,
            0x00,
            speed & 0xFF,
            (speed >> 8) & 0xFF,
        ]
        self.write_packet(servo_id, INST_WRITE, params)

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


def load_pose(path: str) -> Dict[str, int]:
    with open(path, "r") as f:
        data = json.load(f)
    missing = [j for j in JOINTS if j not in data]
    if missing:
        raise ValueError(f"{path} missing joints: {missing}")
    return {j: clamp_raw(data[j]) for j in JOINTS}


def add_delta(home: Dict[str, int], delta: Dict[str, int]) -> Dict[str, int]:
    return {j: clamp_raw(home[j] + delta.get(j, 0)) for j in JOINTS}


def print_pose(title: str, pose: Dict[str, Optional[int]]):
    print(f"\n{title}")
    for j in JOINTS:
        print(f"  {j}: {pose.get(j)}")
    print()


def read_all(bus: ServoBus) -> Dict[str, Optional[int]]:
    out = {}
    for j, sid in JOINTS.items():
        out[j] = bus.read_position(sid)
        time.sleep(JOINT_INTERVAL)
    return out


def print_error(label: str, final: Dict[str, Optional[int]], target: Dict[str, int]):
    print(f"\n=== {label} ERROR FROM TARGET ===")
    for j in JOINTS:
        if final.get(j) is None:
            print(f"{j}: read failed")
        else:
            print(f"{j}: {final[j] - target[j]}")


def torque_all(bus: ServoBus, enable: bool = True):
    for j, sid in JOINTS.items():
        print(f"[{bus.name}] torque {'ON' if enable else 'OFF'} {j} / ID {sid}")
        bus.torque_enable(sid, enable)
        time.sleep(JOINT_INTERVAL)


def move_pose(bus: ServoBus, pose: Dict[str, int], speed: int, acc: int, label: str):
    print(f"\n=== {bus.name} MOVE {label} ===")
    for j, sid in JOINTS.items():
        target = clamp_raw(pose[j])
        print(f"[{bus.name}] {j} / ID {sid} -> {target}")
        bus.move_raw(sid, target, speed=speed, acc=acc)
        time.sleep(JOINT_INTERVAL)


def move_both_stable(left: ServoBus, right: ServoBus, left_pose: Dict[str, int], right_pose: Dict[str, int], speed: int, acc: int, label: str):
    print(f"\n=== STABLE SEQUENTIAL BOTH: {label} ===")
    move_pose(left, left_pose, speed, acc, label)
    time.sleep(ARM_INTERVAL)
    move_pose(right, right_pose, speed, acc, label)


def move_both_interleaved(left: ServoBus, right: ServoBus, left_pose: Dict[str, int], right_pose: Dict[str, int], speed: int, acc: int, label: str):
    print(f"\n=== INTERLEAVED BOTH: {label} ===")
    for j, sid in JOINTS.items():
        lt = clamp_raw(left_pose[j])
        rt = clamp_raw(right_pose[j])
        print(f"[DUAL] {j} / ID {sid} | L {lt}, R {rt}")
        left.move_raw(sid, lt, speed=speed, acc=acc)
        time.sleep(0.04)
        right.move_raw(sid, rt, speed=speed, acc=acc)
        time.sleep(JOINT_INTERVAL)


def scan(bus: ServoBus):
    print(f"\n=== SCAN {bus.name} ===")
    found = []
    for sid in range(1, 7):
        if bus.ping(sid):
            found.append(sid)
        time.sleep(0.04)
    print(f"[{bus.name}] found IDs: {found}")


def main():
    delta = SAFE_TEST_DELTA if USE_SAFE_DELTA else TEST_DELTA

    left_home = load_pose(LEFT_HOME_PATH)
    right_home = load_pose(RIGHT_HOME_PATH)
    left_test = add_delta(left_home, delta)
    right_test = add_delta(right_home, delta)

    print_pose("LEFT HOME", left_home)
    print_pose("RIGHT HOME", right_home)
    print_pose("LEFT TEST", left_test)
    print_pose("RIGHT TEST", right_test)

    left = ServoBus("LEFT", LEFT_PORT)
    right = ServoBus("RIGHT", RIGHT_PORT)

    try:
        scan(left)
        scan(right)

        print("\n=== CURRENT POSITION CHECK ===")
        left_cur = read_all(left)
        right_cur = read_all(right)
        print_pose("LEFT CURRENT", left_cur)
        print_pose("RIGHT CURRENT", right_cur)

        print("\n=== TORQUE ON ===")
        torque_all(left, True)
        torque_all(right, True)

        # Test A: each arm alone. This verifies both arms work with their own HOME.
        print("\n\n######## TEST A: LEFT ONLY ########")
        move_pose(left, left_home, HOME_SPEED, HOME_ACC, "HOME")
        time.sleep(POSE_WAIT)
        move_pose(left, left_test, TEST_SPEED, TEST_ACC, "TEST")
        time.sleep(POSE_WAIT)
        move_pose(left, left_home, TEST_SPEED, TEST_ACC, "HOME BACK")
        time.sleep(POSE_WAIT)
        left_after_a = read_all(left)
        print_pose("LEFT AFTER TEST A", left_after_a)
        print_error("LEFT TEST A", left_after_a, left_home)

        print("\n\n######## TEST B: RIGHT ONLY ########")
        move_pose(right, right_home, HOME_SPEED, HOME_ACC, "HOME")
        time.sleep(POSE_WAIT)
        move_pose(right, right_test, TEST_SPEED, TEST_ACC, "TEST")
        time.sleep(POSE_WAIT)
        move_pose(right, right_home, TEST_SPEED, TEST_ACC, "HOME BACK")
        time.sleep(POSE_WAIT)
        right_after_b = read_all(right)
        print_pose("RIGHT AFTER TEST B", right_after_b)
        print_error("RIGHT TEST B", right_after_b, right_home)

        # Test C: stable sequential dual-arm. Prefer this if interleaved is unstable.
        print("\n\n######## TEST C: STABLE SEQUENTIAL DUAL ########")
        move_both_stable(left, right, left_home, right_home, HOME_SPEED, HOME_ACC, "HOME")
        time.sleep(POSE_WAIT)
        move_both_stable(left, right, left_test, right_test, TEST_SPEED, TEST_ACC, "TEST")
        time.sleep(POSE_WAIT)
        move_both_stable(left, right, left_home, right_home, TEST_SPEED, TEST_ACC, "HOME BACK")
        time.sleep(POSE_WAIT)
        left_after_c = read_all(left)
        right_after_c = read_all(right)
        print_pose("LEFT AFTER TEST C", left_after_c)
        print_pose("RIGHT AFTER TEST C", right_after_c)
        print_error("LEFT TEST C", left_after_c, left_home)
        print_error("RIGHT TEST C", right_after_c, right_home)

        # Test D: interleaved dual-arm. This is closer to the previous dual-arm motion.
        print("\n\n######## TEST D: INTERLEAVED DUAL ########")
        move_both_interleaved(left, right, left_home, right_home, HOME_SPEED, HOME_ACC, "HOME")
        time.sleep(POSE_WAIT)
        move_both_interleaved(left, right, left_test, right_test, TEST_SPEED, TEST_ACC, "TEST")
        time.sleep(POSE_WAIT)
        move_both_interleaved(left, right, left_home, right_home, TEST_SPEED, TEST_ACC, "HOME BACK")
        time.sleep(POSE_WAIT)
        left_after_d = read_all(left)
        right_after_d = read_all(right)
        print_pose("LEFT AFTER TEST D", left_after_d)
        print_pose("RIGHT AFTER TEST D", right_after_d)
        print_error("LEFT TEST D", left_after_d, left_home)
        print_error("RIGHT TEST D", right_after_d, right_home)

    finally:
        print("\nClose serial")
        left.close()
        right.close()


if __name__ == "__main__":
    main()
