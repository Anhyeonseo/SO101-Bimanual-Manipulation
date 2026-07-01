import serial
import time


PORT = "/dev/ttyACM0"
BAUDRATE = 1000000

INST_READ = 0x02
ADDR_PRESENT_POSITION = 56
READ_LEN = 2

JOINTS = {
    1: "base_yaw",
    2: "shoulder_pitch",
    3: "elbow_pitch",
    4: "wrist_pitch",
    5: "wrist_roll",
    6: "gripper",
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


def read_position(ser, servo_id):
    packet = make_packet(
        servo_id,
        INST_READ,
        [ADDR_PRESENT_POSITION, READ_LEN]
    )

    ser.reset_input_buffer()
    ser.write(packet)
    ser.flush()

    response = ser.read(64)

    if len(response) < 7:
        raise TimeoutError(f"ID {servo_id}: no response")

    if response[0] != 0xFF or response[1] != 0xFF:
        raise ValueError(f"ID {servo_id}: invalid header {response.hex(' ')}")

    resp_id = response[2]
    length = response[3]
    error = response[4]
    data = response[5:-1]
    checksum = response[-1]

    calc = ~(resp_id + length + error + sum(data)) & 0xFF

    if checksum != calc:
        raise ValueError(f"ID {servo_id}: checksum mismatch")

    if error != 0:
        raise RuntimeError(f"ID {servo_id}: servo error {error}")

    position = data[0] | (data[1] << 8)
    return position


def main():
    ser = serial.Serial(PORT, BAUDRATE, timeout=0.2)
    time.sleep(0.1)

    for servo_id, name in JOINTS.items():
        try:
            pos = read_position(ser, servo_id)
            print(f"ID {servo_id} / {name}: {pos}")
        except Exception as e:
            print(f"ID {servo_id} / {name}: ERROR - {e}")

        time.sleep(0.05)

    ser.close()


if __name__ == "__main__":
    main()
