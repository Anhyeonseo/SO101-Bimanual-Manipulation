import serial
import time


PORT = "/dev/ttyACM0"
BAUDRATE = 1000000
SERVO_ID = 1

INST_READ = 0x02

# STS3215 기준 현재 위치 주소
ADDR_PRESENT_POSITION = 56
READ_LEN = 2


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


def parse_response(response):
    if len(response) < 6:
        raise TimeoutError("response too short or empty")

    if response[0] != 0xFF or response[1] != 0xFF:
        raise ValueError(f"invalid header: {response.hex(' ')}")

    servo_id = response[2]
    length = response[3]
    error = response[4]
    data = response[5:-1]
    checksum = response[-1]

    calc_checksum = ~(servo_id + length + error + sum(data)) & 0xFF

    if checksum != calc_checksum:
        raise ValueError(
            f"checksum mismatch: got {checksum:02x}, expected {calc_checksum:02x}"
        )

    if error != 0:
        raise RuntimeError(f"servo error: {error}")

    return servo_id, data


def main():
    ser = serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        timeout=0.2
    )

    time.sleep(0.1)

    # READ packet: address, read length
    packet = make_packet(
        servo_id=SERVO_ID,
        instruction=INST_READ,
        params=[ADDR_PRESENT_POSITION, READ_LEN]
    )

    print("TX:", packet.hex(" "))

    ser.reset_input_buffer()
    ser.write(packet)
    ser.flush()

    response = ser.read(64)
    print("RX:", response.hex(" "))

    servo_id, data = parse_response(response)

    position = data[0] | (data[1] << 8)

    print(f"servo id: {servo_id}")
    print(f"present position raw: {position}")

    ser.close()


if __name__ == "__main__":
    main()
