import serial
import time


PORT = "/dev/ttyACM0"
BAUDRATE = 1000000

INST_WRITE = 0x03

ADDR_ID = 5

# STS/SMS/STS3215 계열에서 EEPROM lock 주소로 자주 쓰이는 값
ADDR_LOCK = 55


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


def write_byte(ser, servo_id, address, value):
    params = [address, value & 0xFF]
    packet = make_packet(servo_id, INST_WRITE, params)

    print("TX:", packet.hex(" "))

    ser.write(packet)
    ser.flush()
    time.sleep(0.1)


def unlock_eeprom(ser, servo_id):
    print(f"Unlock EEPROM: ID {servo_id}")
    write_byte(ser, servo_id, ADDR_LOCK, 0)


def lock_eeprom(ser, servo_id):
    print(f"Lock EEPROM: ID {servo_id}")
    write_byte(ser, servo_id, ADDR_LOCK, 1)


def main():
    old_id = int(input("현재 ID 입력: "))
    new_id = int(input("새 ID 입력: "))

    if not (1 <= new_id <= 253):
        raise ValueError("ID는 1~253 범위 권장")

    ser = serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        timeout=0.2
    )

    time.sleep(0.1)

    print(f"Change ID: {old_id} -> {new_id}")

    # 1. EEPROM unlock
    unlock_eeprom(ser, old_id)
    time.sleep(0.2)

    # 2. ID write
    write_byte(ser, old_id, ADDR_ID, new_id)
    time.sleep(0.2)

    # 3. 새 ID 기준으로 EEPROM lock
    lock_eeprom(ser, new_id)

    ser.close()

    print("완료. 서보 전원을 껐다 켠 다음 scan_id.py로 확인해라.")


if __name__ == "__main__":
    main()
