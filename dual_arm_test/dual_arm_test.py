import json
import time
from typing import Dict, Tuple, Optional

import serial


# =========================
# Dual Arm Serial Settings
# =========================
LEFT_PORT = "/dev/ttyACM0"
RIGHT_PORT = "/dev/ttyACM1"
BAUDRATE = 1000000
LEFT_HOME_POSE_PATH = "left_home_pose.json"
RIGHT_HOME_POSE_PATH = "right_home_pose.json"

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

# 기존 arm_test.py 기준 테스트 자세 delta
# 왼팔/오른팔은 각자 HOME 기준으로 같은 delta만큼 움직임.
TEST_DELTA = {
    "base_yaw": 80,
    "shoulder_pitch": -420,
    "elbow_pitch": 480,
    "wrist_pitch": -300,
    "wrist_roll": 0,
    "gripper": 0,
}

# Motion parameters
HOME_SPEED = 250
HOME_ACC = 15
TEST_SPEED = 300
TEST_ACC = 25

MOVE_INTERVAL = 0.035
JOINT_INTERVAL = 0.05


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


class FeetechServoBus:
    def __init__(self, name: str, port: str, baudrate: int = BAUDRATE, timeout: float = 0.2):
        self.name = name
        self.port = port
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(0.1)

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def write_packet(self, servo_id: int, instruction: int, params: list[int]):
        packet = make_packet(servo_id, instruction, params)
        self.ser.write(packet)
        self.ser.flush()
        time.sleep(MOVE_INTERVAL)

    def write_byte(self, servo_id: int, address: int, value: int):
        self.write_packet(servo_id, INST_WRITE, [address, value & 0xFF])

    def torque_enable(self, servo_id: int, enable: bool = True):
        self.write_byte(servo_id, ADDR_TORQUE_ENABLE, 1 if enable else 0)

    def read_position(self, servo_id: int, strict_error: bool = False) -> Optional[int]:
        """
        Returns raw position.
        If the servo returns a non-zero status error but still includes position data,
        this function prints a warning and returns the position by default.
        Set strict_error=True to raise an exception on non-zero status error.
        """
        packet = make_packet(servo_id, INST_READ, [ADDR_PRESENT_POSITION, 2])

        self.ser.reset_input_buffer()
        self.ser.write(packet)
        self.ser.flush()

        response = self.ser.read(64)

        if len(response) < 7:
            print(f"[WARN] {self.name} {self.port} ID {servo_id}: no response, RX={response.hex(' ')}")
            return None

        if response[0] != 0xFF or response[1] != 0xFF:
            print(f"[WARN] {self.name} {self.port} ID {servo_id}: invalid header, RX={response.hex(' ')}")
            return None

        resp_id = response[2]
        length = response[3]
        error = response[4]
        data = response[5:-1]
        checksum = response[-1]

        calc = ~(resp_id + length + error + sum(data)) & 0xFF
        if checksum != calc:
            print(
                f"[WARN] {self.name} {self.port} ID {servo_id}: checksum mismatch, "
                f"got={checksum:02x}, expected={calc:02x}, RX={response.hex(' ')}"
            )
            return None

        if error != 0:
            msg = decode_error(error)
            print(f"[WARN] {self.name} {self.port} ID {servo_id}: servo status error {error} ({msg})")
            if strict_error:
                raise RuntimeError(f"[{self.port}] ID {servo_id}: servo error {error} ({msg})")

        if len(data) < 2:
            print(f"[WARN] {self.name} {self.port} ID {servo_id}: response has no position data")
            return None

        return data[0] | (data[1] << 8)

    def move_raw(self, servo_id: int, position: int, speed: int = 300, acc: int = 25):
        position = clamp_raw(position)
        speed = clamp_raw(speed)
        acc = max(0, min(255, int(acc)))

        # STS3215 / STS/SCS serial bus servo goal command
        # 41: acceleration
        # 42~43: goal position
        # 44~45: goal time
        # 46~47: goal speed
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


def validate_pose(pose: Dict[str, int], label: str):
    missing = [joint for joint in JOINTS if joint not in pose]
    if missing:
        raise ValueError(f"{label} pose is missing joints: {missing}")


def load_pose(path: str, label: str) -> Dict[str, int]:
    with open(path, "r") as f:
        pose = json.load(f)

    validate_pose(pose, label)
    return {joint: clamp_raw(pose[joint]) for joint in JOINTS}


def load_home_poses(
    left_path: str = LEFT_HOME_POSE_PATH,
    right_path: str = RIGHT_HOME_POSE_PATH,
) -> Tuple[Dict[str, int], Dict[str, int]]:
    left_home = load_pose(left_path, "left_home")
    right_home = load_pose(right_path, "right_home")
    return left_home, right_home


def add_delta(base_pose: Dict[str, int], delta: Dict[str, int]) -> Dict[str, int]:
    return {
        joint: clamp_raw(base_pose[joint] + delta.get(joint, 0))
        for joint in JOINTS
    }


def print_pose(title: str, pose: Dict[str, Optional[int]]):
    print(f"\n{title}")
    for joint in JOINTS:
        print(f"  {joint}: {pose.get(joint)}")
    print()


def read_all_positions(bus: FeetechServoBus) -> Dict[str, Optional[int]]:
    positions: Dict[str, Optional[int]] = {}
    for joint_name, servo_id in JOINTS.items():
        positions[joint_name] = bus.read_position(servo_id, strict_error=False)
        time.sleep(JOINT_INTERVAL)
    return positions


def torque_all(bus: FeetechServoBus, enable: bool = True):
    for joint_name, servo_id in JOINTS.items():
        print(f"[{bus.name}] Torque {'ON' if enable else 'OFF'}: {joint_name} / ID {servo_id}")
        try:
            bus.torque_enable(servo_id, enable)
        except Exception as e:
            print(f"[WARN] {bus.name} torque command failed: {joint_name} / ID {servo_id}: {e}")
        time.sleep(JOINT_INTERVAL)


def move_both_arms(
    left_bus: FeetechServoBus,
    right_bus: FeetechServoBus,
    left_pose: Dict[str, int],
    right_pose: Dict[str, int],
    speed: int = 300,
    acc: int = 25,
):
    """
    Sends each joint command to LEFT and RIGHT in sequence.
    This keeps both arms moving almost together while avoiding packet collisions
    because they are on separate serial ports.
    """
    for joint_name in JOINTS:
        servo_id = JOINTS[joint_name]
        left_target = clamp_raw(left_pose[joint_name])
        right_target = clamp_raw(right_pose[joint_name])

        print(
            f"[DUAL] {joint_name} / ID {servo_id} | "
            f"L: {left_target}, R: {right_target}"
        )

        try:
            left_bus.move_raw(servo_id, left_target, speed=speed, acc=acc)
        except Exception as e:
            print(f"[WARN] LEFT move failed: {joint_name} / ID {servo_id}: {e}")

        try:
            right_bus.move_raw(servo_id, right_target, speed=speed, acc=acc)
        except Exception as e:
            print(f"[WARN] RIGHT move failed: {joint_name} / ID {servo_id}: {e}")

        time.sleep(JOINT_INTERVAL)


def print_error_from_home(label: str, final_pose: Dict[str, Optional[int]], home_pose: Dict[str, int]):
    print(f"\n=== {label} Error from HOME ===")
    for joint_name in JOINTS:
        final = final_pose.get(joint_name)
        home = home_pose[joint_name]
        if final is None:
            print(f"{joint_name}: read failed")
        else:
            print(f"{joint_name}: {final - home}")


def main():
    left_home, right_home = load_home_poses()

    print(f"Using LEFT home:  {LEFT_HOME_POSE_PATH}")
    print(f"Using RIGHT home: {RIGHT_HOME_POSE_PATH}")

    print_pose("LOADED LEFT HOME", left_home)
    print_pose("LOADED RIGHT HOME", right_home)

    # Both arms use the same delta, but each delta is applied to its own HOME pose.
    left_test_pose = add_delta(left_home, TEST_DELTA)
    right_test_pose = add_delta(right_home, TEST_DELTA)

    left_bus = FeetechServoBus("LEFT", LEFT_PORT, BAUDRATE)
    right_bus = FeetechServoBus("RIGHT", RIGHT_PORT, BAUDRATE)

    try:
        print("=== Current position check ===")
        left_current = read_all_positions(left_bus)
        right_current = read_all_positions(right_bus)
        print_pose("LEFT CURRENT", left_current)
        print_pose("RIGHT CURRENT", right_current)

        print("=== Torque ON ===")
        torque_all(left_bus, True)
        torque_all(right_bus, True)

        print("=== Move both arms to HOME ===")
        move_both_arms(
            left_bus,
            right_bus,
            left_home,
            right_home,
            speed=HOME_SPEED,
            acc=HOME_ACC,
        )
        time.sleep(3.0)

        print_pose("LEFT TEST POSE", left_test_pose)
        print_pose("RIGHT TEST POSE", right_test_pose)

        print("=== Move both arms to TEST POSE ===")
        move_both_arms(
            left_bus,
            right_bus,
            left_test_pose,
            right_test_pose,
            speed=TEST_SPEED,
            acc=TEST_ACC,
        )
        time.sleep(3.0)

        print("=== Back both arms to HOME ===")
        move_both_arms(
            left_bus,
            right_bus,
            left_home,
            right_home,
            speed=TEST_SPEED,
            acc=TEST_ACC,
        )
        time.sleep(3.0)

        print("=== Final position check ===")
        left_final = read_all_positions(left_bus)
        right_final = read_all_positions(right_bus)
        print_pose("LEFT FINAL", left_final)
        print_pose("RIGHT FINAL", right_final)

        print_error_from_home("LEFT", left_final, left_home)
        print_error_from_home("RIGHT", right_final, right_home)

    finally:
        print("=== Close serial ===")
        left_bus.close()
        right_bus.close()


if __name__ == "__main__":
    main()
