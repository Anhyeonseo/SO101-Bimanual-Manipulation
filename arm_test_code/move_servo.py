import serial
import time


PORT = "/dev/ttyACM0"
BAUDRATE = 1000000
SERVO_ID = 1

INST_WRITE = 0x03

# STS3215 계열 기준
ADDR_ACC = 41
ADDR_GOAL_POSITION = 42


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


def write_goal_position(ser, servo_id, position, speed=300, acc=20):
    """
    position: 0~4095
    speed: 처음에는 100~300 정도 추천
    acc: 처음에는 10~30 정도 추천
    """

    position = max(0, min(4095, position))
    speed = max(0, min(4095, speed))
    acc = max(0, min(255, acc))

    # 주소 41부터 연속 write:
    # 41: acc 1 byte
    # 42~43: goal position 2 byte
    # 44~45: goal time 2 byte
    # 46~47: goal speed 2 byte
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

    print("TX:", packet.hex(" "))

    ser.write(packet)
    ser.flush()


def main():
    ser = serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        timeout=0.2
    )

    time.sleep(0.1)

    # 방금 읽은 현재 위치 3672 기준으로 아주 조금만 이동
    target_position = 3500

    print(f"move ID {SERVO_ID} to {target_position}")
    write_goal_position(
        ser,
        servo_id=SERVO_ID,
        position=target_position,
        speed=200,
        acc=20
    )

    time.sleep(1.0)

    ser.close()


if __name__ == "__main__":
    main()
