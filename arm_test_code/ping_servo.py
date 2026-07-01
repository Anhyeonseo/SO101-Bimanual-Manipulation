import serial
import time


PORT = "/dev/ttyACM0"
BAUDRATE = 1000000
SERVO_ID = 2


def make_packet(servo_id, instruction, params):
    length = len(params) + 2
    checksum = ~(servo_id + length + instruction + sum(params)) & 0xFF

    packet = bytes([
        0xFF, 0xFF,
        servo_id,
        length,
        instruction,
        *params,
        checksum
    ])

    return packet


def main():
    ser = serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        timeout=0.2
    )

    time.sleep(0.1)

    # Feetech/SCS/STS 계열 PING instruction = 0x01
    packet = make_packet(
        servo_id=SERVO_ID,
        instruction=0x01,
        params=[]
    )

    print("TX:", packet.hex(" "))

    ser.reset_input_buffer()
    ser.write(packet)
    ser.flush()

    response = ser.read(64)

    print("RX:", response.hex(" "))

    ser.close()


if __name__ == "__main__":
    main()
