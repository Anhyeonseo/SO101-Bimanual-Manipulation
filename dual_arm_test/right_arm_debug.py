import serial
import time

PORT = "/dev/ttyACM1"
BAUDRATE = 1000000

INST_PING = 0x01
INST_READ = 0x02
INST_WRITE = 0x03

ADDR_TORQUE_ENABLE = 40
ADDR_ACC = 41
ADDR_PRESENT_POSITION = 56

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
    return bytes([0xFF, 0xFF, servo_id, length, instruction, *params, checksum])


def clamp_raw(pos):
    return max(0, min(4095, int(pos)))


class Bus:
    def __init__(self, port=PORT, baudrate=BAUDRATE, timeout=0.25):
        self.port = port
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(0.1)

    def close(self):
        self.ser.close()

    def ping(self, servo_id):
        pkt = make_packet(servo_id, INST_PING, [])
        self.ser.reset_input_buffer()
        self.ser.write(pkt)
        self.ser.flush()
        resp = self.ser.read(6)
        return resp

    def write_byte(self, servo_id, address, value):
        pkt = make_packet(servo_id, INST_WRITE, [address, value & 0xFF])
        self.ser.write(pkt)
        self.ser.flush()
        time.sleep(0.04)

    def torque(self, servo_id, enable=True):
        self.write_byte(servo_id, ADDR_TORQUE_ENABLE, 1 if enable else 0)

    def read_position(self, servo_id):
        pkt = make_packet(servo_id, INST_READ, [ADDR_PRESENT_POSITION, 2])
        self.ser.reset_input_buffer()
        self.ser.write(pkt)
        self.ser.flush()
        resp = self.ser.read(64)

        if len(resp) < 7:
            return None, f"no response RX={resp.hex(' ')}"
        if resp[0] != 0xFF or resp[1] != 0xFF:
            return None, f"bad header RX={resp.hex(' ')}"

        rid = resp[2]
        length = resp[3]
        error = resp[4]
        data = resp[5:-1]
        chk = resp[-1]
        calc = ~(rid + length + error + sum(data)) & 0xFF

        if chk != calc:
            return None, f"checksum mismatch RX={resp.hex(' ')}"
        if len(data) < 2:
            return None, f"short data RX={resp.hex(' ')}"

        pos = data[0] | (data[1] << 8)
        if error != 0:
            return pos, f"servo status error={error} RX={resp.hex(' ')}"
        return pos, None

    def move_raw(self, servo_id, position, speed=180, acc=10):
        position = clamp_raw(position)
        speed = clamp_raw(speed)
        acc = max(0, min(255, int(acc)))

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
        pkt = make_packet(servo_id, INST_WRITE, params)
        self.ser.write(pkt)
        self.ser.flush()
        time.sleep(0.04)


def scan(bus):
    print("\n=== RIGHT ARM SCAN ===")
    found = []
    for sid in range(1, 7):
        resp = bus.ping(sid)
        if len(resp) >= 6 and resp[0] == 0xFF and resp[1] == 0xFF:
            print(f"ID {sid} / {JOINTS[sid]}: OK RX={resp.hex(' ')}")
            found.append(sid)
        else:
            print(f"ID {sid} / {JOINTS[sid]}: FAIL RX={resp.hex(' ')}")
        time.sleep(0.08)
    return found


def read_all(bus, title):
    print(f"\n=== {title} ===")
    result = {}
    for sid, name in JOINTS.items():
        pos, err = bus.read_position(sid)
        result[sid] = pos
        if err:
            print(f"ID {sid} / {name}: pos={pos}, WARN={err}")
        else:
            print(f"ID {sid} / {name}: pos={pos}")
        time.sleep(0.08)
    return result


def test_joint(bus, sid, delta=120):
    name = JOINTS[sid]
    print(f"\n=== TEST ID {sid} / {name} ===")
    bus.torque(sid, True)
    time.sleep(0.2)

    home, err = bus.read_position(sid)
    print(f"home={home}, err={err}")
    if home is None:
        return

    for label, target in [("PLUS", home + delta), ("BACK", home), ("MINUS", home - delta), ("BACK", home)]:
        target = clamp_raw(target)
        print(f"{label}: move to {target}")
        bus.move_raw(sid, target, speed=160, acc=8)
        time.sleep(1.5)
        pos, err = bus.read_position(sid)
        print(f"  after: pos={pos}, err={err}")


def main():
    print(f"Open {PORT}")
    bus = Bus(PORT, BAUDRATE)
    try:
        scan(bus)
        read_all(bus, "CURRENT POSITIONS BEFORE TEST")

        print("\n=== TORQUE ON ALL ===")
        for sid in JOINTS:
            print(f"Torque ON ID {sid} / {JOINTS[sid]}")
            bus.torque(sid, True)
            time.sleep(0.08)

        # Focus on the joints that looked suspicious in the dual-arm log.
        test_joint(bus, 2, delta=120)
        test_joint(bus, 5, delta=120)
        test_joint(bus, 1, delta=120)

        read_all(bus, "CURRENT POSITIONS AFTER TEST")
    finally:
        print("\nClose serial")
        bus.close()


if __name__ == "__main__":
    main()
