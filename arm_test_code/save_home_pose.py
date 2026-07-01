import serial
import time
import json


PORT = "/dev/ttyACM0"
BAUDRATE = 1000000

INST_READ = 0x02
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


def read_position(ser, servo_id):
    packet = make_packet(
        servo_id,
        INST_READ,
        [ADDR_PRESENT_POSITION, 2]
    )

    ser.reset_input_buffer()
    ser.write(packet)
    ser.flush()

    response = ser.read(64)

    if len(response) < 7:
        raise TimeoutError(f"ID {servo_id}: no response, RX={response.hex(' ')}")

    if response[0] != 0xFF or response[1] != 0xFF:
        raise ValueError(f"ID {servo_id}: invalid header, RX={response.hex(' ')}")

    data = response[5:-1]
    return data[0] | (data[1] << 8)


def main():
    ser = serial.Serial(PORT, BAUDRATE, timeout=0.2)
    time.sleep(0.1)

    home_pose = {}

    print("=== Read current servo positions as HOME ===")

    for joint_name, servo_id in JOINTS.items():
        pos = read_position(ser, servo_id)
        home_pose[joint_name] = pos
        print(f"{joint_name} / ID {servo_id}: {pos}")
        time.sleep(0.05)

    ser.close()

    with open("home_pose.json", "w") as f:
        json.dump(home_pose, f, indent=4)

    print("\nSaved to home_pose.json")


if __name__ == "__main__":
    main()
