import json
import time
from typing import Optional

import serial

PORT = "/dev/ttyACM0"
BAUDRATE = 1000000
OUTPUT_PATH = "left_home_pose_5dof.json"

INST_READ = 0x02
ADDR_PRESENT_POSITION = 56

# LEFT ARM 5DOF: ID 5 / wrist_roll is disabled and must stay physically disconnected.
JOINTS_5DOF = {
    "base_yaw": 1,
    "shoulder_pitch": 2,
    "elbow_pitch": 3,
    "wrist_pitch": 4,
    "gripper": 6,
}


def make_packet(servo_id: int, instruction: int, params: list[int]) -> bytes:
    length = len(params) + 2
    checksum = ~(servo_id + length + instruction + sum(params)) & 0xFF
    return bytes([0xFF, 0xFF, servo_id, length, instruction, *params, checksum])


def decode_error(error: int) -> str:
    error_bits = {
        1: "Input voltage error",
        2: "Angle limit error",
        4: "Over temperature error",
        8: "Range error",
        16: "Checksum error",
        32: "Overload error",
        64: "Instruction error",
    }
    if error == 0:
        return "OK"
    names = [name for bit, name in error_bits.items() if error & bit]
    return ", ".join(names) if names else f"Unknown error {error}"


def read_position(ser: serial.Serial, servo_id: int, retries: int = 3) -> Optional[int]:
    packet = make_packet(servo_id, INST_READ, [ADDR_PRESENT_POSITION, 2])

    for attempt in range(1, retries + 1):
        ser.reset_input_buffer()
        ser.write(packet)
        ser.flush()
        resp = ser.read(64)

        if len(resp) < 7:
            print(f"[WARN] ID {servo_id}: no response attempt {attempt}/{retries} RX={resp.hex(' ')}")
            time.sleep(0.08)
            continue

        if resp[0] != 0xFF or resp[1] != 0xFF:
            print(f"[WARN] ID {servo_id}: bad header attempt {attempt}/{retries} RX={resp.hex(' ')}")
            time.sleep(0.08)
            continue

        resp_id = resp[2]
        length = resp[3]
        error = resp[4]
        data = resp[5:-1]
        checksum = resp[-1]
        calc = ~(resp_id + length + error + sum(data)) & 0xFF

        if checksum != calc:
            print(f"[WARN] ID {servo_id}: checksum mismatch attempt {attempt}/{retries} RX={resp.hex(' ')}")
            time.sleep(0.08)
            continue

        if error != 0:
            print(f"[WARN] ID {servo_id}: status error {error} ({decode_error(error)}) RX={resp.hex(' ')}")

        if len(data) < 2:
            print(f"[WARN] ID {servo_id}: short data attempt {attempt}/{retries} RX={resp.hex(' ')}")
            time.sleep(0.08)
            continue

        return data[0] | (data[1] << 8)

    return None


def main():
    print("[SAFETY] This script only reads positions.")
    print("[SAFETY] LEFT ID 5 / wrist_roll is disabled. Keep it physically disconnected.")
    print(f"Open LEFT: {PORT}")

    ser = serial.Serial(PORT, BAUDRATE, timeout=0.2)
    time.sleep(0.2)

    pose = {}
    failed = []

    print("\n=== READ LEFT 5DOF CURRENT POSE ===")
    for joint, servo_id in JOINTS_5DOF.items():
        pos = read_position(ser, servo_id)
        if pos is None:
            print(f"{joint} / ID {servo_id}: READ FAILED")
            failed.append(joint)
        else:
            print(f"{joint} / ID {servo_id}: {pos}")
            pose[joint] = int(pos)
        time.sleep(0.08)

    ser.close()

    if failed:
        print("\n[ABORT] Some joints failed to read. Home pose was NOT saved.")
        print("Failed joints:", failed)
        return

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(pose, f, indent=2)
        f.write("\n")

    print(f"\nSaved LEFT 5DOF home pose to: {OUTPUT_PATH}")
    print(json.dumps(pose, indent=2))


if __name__ == "__main__":
    main()
