import serial
import time


PORT = "/dev/ttyACM0"
BAUDRATE = 1000000

INST_WRITE = 0x03
ADDR_ACC = 41

JOINTS = {
    1: "base_yaw",
    2: "shoulder_pitch",
    3: "elbow_pitch",
    4: "wrist_pitch",
    5: "wrist_roll",
    6: "gripper",
}

# 방금 읽은 현재 위치 기준으로 작은 이동만 테스트
POSE_SMALL = {
    1: 480,
    2: 3227,
    3: 3954,
    4: 335,
    5: 1366,
    6: 3537,
}

POSE_BACK = {
    1: 380,
    2: 3327,
    3: 4054,
    4: 235,
    5: 1266,
    6: 3637,
}


def make_packet(servo_id, instruction, params):
    length = len(params) + 2
    checksum = ~(servo_id + length + instruction + sum(params)) & 0xFF

    return bytes([
        0xFF, 0xFF,
        servo_id,
        length,
        instruction,
        *params,
        checksum
    ])


def write_goal_position(ser, servo_id, position, speed=150, acc=10):
    position = max(0, min(4095, position))
    speed = max(0, min(4095, speed))
    acc = max(0, min(255, acc))

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

    packet = make_packet(servo_id, INST_WRITE, params)

    print(f"ID {servo_id} -> {position} | TX: {packet.hex(' ')}")

    ser.write(packet)
    ser.flush()
    time.sleep(0.05)


def move_pose(ser, pose, speed=150, acc=10):
    for servo_id, position in pose.items():
        name = JOINTS[servo_id]
        print(f"Move {name}")
        write_goal_position(ser, servo_id, position, speed=speed, acc=acc)


def main():
    ser = serial.Serial(PORT, BAUDRATE, timeout=0.2)
    time.sleep(0.1)

    print("Move small pose")
    move_pose(ser, POSE_SMALL, speed=150, acc=10)

    time.sleep(2)

    print("Move back")
    move_pose(ser, POSE_BACK, speed=150, acc=10)

    time.sleep(2)

    ser.close()


if __name__ == "__main__":
    main()
