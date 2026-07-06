import serial
import time


PORT = "/dev/ttyACM0"
BAUDRATE = 1000000


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


def ping(ser, servo_id):
    packet = make_packet(servo_id, 0x01, [])

    ser.reset_input_buffer()
    ser.write(packet)
    ser.flush()

    response = ser.read(6)

    if len(response) >= 6 and response[0] == 0xFF and response[1] == 0xFF:
        return response

    return None


def main():
    ser = serial.Serial(PORT, BAUDRATE, timeout=0.05)
    time.sleep(0.1)

    found = []

    for servo_id in range(1, 21):
        response = ping(ser, servo_id)

        if response:
            print(f"Found ID {servo_id}: {response.hex(' ')}")
            found.append(servo_id)

        time.sleep(0.03)

    ser.close()

    if not found:
        print("No servo found")
    else:
        print("Found IDs:", found)


if __name__ == "__main__":
    main()
