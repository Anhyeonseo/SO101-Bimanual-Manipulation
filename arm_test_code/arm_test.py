import serial
import time
import json


PORT = "/dev/ttyACM0"
BAUDRATE = 1000000

INST_READ = 0x02
INST_WRITE = 0x03

ADDR_TORQUE_ENABLE = 40
ADDR_PRESENT_POSITION = 56

JOINTS = {
    "base_yaw": 1,
    "shoulder_pitch": 2,
    "elbow_pitch": 3,
    "wrist_pitch": 4,
    "wrist_roll": 5,
    "gripper": 6,
}


def make_packet(servo_id, instruction, params):
    length = len(params) + 2
    checksum = ~(servo_id + length + instruction + sum(params)) & 0xFF
    return bytes([0xFF, 0xFF, servo_id, length, instruction, *params, checksum])


def clamp_raw(pos):
    return max(0, min(4095, int(pos)))


class FeetechServo:
    def __init__(self, port=PORT, baudrate=BAUDRATE, timeout=0.2):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(0.1)

    def close(self):
        self.ser.close()

    def write_byte(self, servo_id, address, value):
        packet = make_packet(
            servo_id,
            INST_WRITE,
            [address, value & 0xFF]
        )
        self.ser.write(packet)
        self.ser.flush()
        time.sleep(0.03)

    def torque_enable(self, servo_id, enable=True):
        self.write_byte(servo_id, ADDR_TORQUE_ENABLE, 1 if enable else 0)

    def read_position(self, servo_id):
        packet = make_packet(
            servo_id,
            INST_READ,
            [ADDR_PRESENT_POSITION, 2]
        )

        self.ser.reset_input_buffer()
        self.ser.write(packet)
        self.ser.flush()

        response = self.ser.read(64)

        if len(response) < 7:
            raise TimeoutError(f"ID {servo_id}: no response, RX={response.hex(' ')}")

        if response[0] != 0xFF or response[1] != 0xFF:
            raise ValueError(f"ID {servo_id}: invalid header, RX={response.hex(' ')}")

        resp_id = response[2]
        length = response[3]
        error = response[4]
        data = response[5:-1]
        checksum = response[-1]

        calc = ~(resp_id + length + error + sum(data)) & 0xFF

        if checksum != calc:
            raise ValueError(
                f"ID {servo_id}: checksum mismatch, "
                f"got={checksum:02x}, expected={calc:02x}, RX={response.hex(' ')}"
            )

        if error != 0:
            raise RuntimeError(f"ID {servo_id}: servo error {error}")

        return data[0] | (data[1] << 8)

    def move_raw(self, servo_id, position, speed=300, acc=25):
        position = clamp_raw(position)
        speed = clamp_raw(speed)
        acc = max(0, min(255, int(acc)))

        params = [
            41,
            acc & 0xFF,

            position & 0xFF,
            (position >> 8) & 0xFF,

            0x00,
            0x00,

            speed & 0xFF,
            (speed >> 8) & 0xFF,
        ]

        packet = make_packet(servo_id, INST_WRITE, params)

        self.ser.write(packet)
        self.ser.flush()
        time.sleep(0.03)


def load_home_pose(path="home_pose.json"):
    with open(path, "r") as f:
        return json.load(f)


def read_all_positions(bus):
    positions = {}

    for joint_name, servo_id in JOINTS.items():
        pos = bus.read_position(servo_id)
        positions[joint_name] = pos
        time.sleep(0.05)

    return positions


def move_arm(bus, pose, speed=300, acc=25):
    for joint_name, target in pose.items():
        servo_id = JOINTS[joint_name]
        safe_target = clamp_raw(target)

        print(f"{joint_name} / ID {servo_id}: {target} -> {safe_target}")

        bus.move_raw(
            servo_id=servo_id,
            position=safe_target,
            speed=speed,
            acc=acc
        )

        time.sleep(0.05)


def add_delta(base_pose, delta):
    new_pose = {}

    for joint_name, base_pos in base_pose.items():
        d = delta.get(joint_name, 0)
        new_pose[joint_name] = clamp_raw(base_pos + d)

    return new_pose


def print_pose(title, pose):
    print("\n" + title)
    for joint_name, pos in pose.items():
        print(f"  {joint_name}: {pos}")
    print()


def torque_all(bus, enable=True):
    for joint_name, servo_id in JOINTS.items():
        print(f"Torque {'ON' if enable else 'OFF'}: {joint_name} / ID {servo_id}")
        bus.torque_enable(servo_id, enable)
        time.sleep(0.05)


def main():
    home = load_home_pose()
    print_pose("LOADED HOME", home)

    bus = FeetechServo(PORT, BAUDRATE)

    try:
        print("=== Torque ON ===")
        torque_all(bus, True)

        print("=== Move to HOME ===")
        move_arm(bus, home, speed=250, acc=15)
        time.sleep(3.0)

        # HOME 기준 테스트 자세
        # 들었다가 내리는 느낌. 방향이 반대면 부호를 바꾸면 됨.
        test_delta = {
            "base_yaw": 80,
            "shoulder_pitch": -420,
            "elbow_pitch": 480,
            "wrist_pitch": -300,
            "wrist_roll": 0,
            "gripper": 0,
        }

        test_pose = add_delta(home, test_delta)
        print_pose("TEST POSE", test_pose)

        print("=== Move to TEST POSE ===")
        move_arm(bus, test_pose, speed=300, acc=25)
        time.sleep(3.0)

        print("=== Back to HOME ===")
        move_arm(bus, home, speed=300, acc=25)
        time.sleep(3.0)

        print("=== Final position check ===")
        final_pose = read_all_positions(bus)
        print_pose("FINAL", final_pose)

        print("=== Error from HOME ===")
        for joint_name in JOINTS.keys():
            err = final_pose[joint_name] - home[joint_name]
            print(f"{joint_name}: {err}")

    finally:
        print("=== Close serial ===")
        bus.close()


if __name__ == "__main__":
    main()
