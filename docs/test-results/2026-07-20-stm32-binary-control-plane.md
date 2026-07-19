# STM32 binary control-plane verification

- Date: 2026-07-20
- Board: NUCLEO-G474RE
- Firmware: `0x00020500`
- Protocol: v1, COBS framing, CRC-32C
- Servo bus: six STS3215 actuators, IDs 1 through 6
- Calibration hash: `0x3DB42B48`

## Host codec tests

- Python protocol unit tests: 6/6 PASS
- COBS round trip: PASS
- CRC-32C known vector: PASS
- Corrupted frame rejection: PASS
- Stream resynchronization: PASS
- Message manifest parity: PASS

## Hardware-in-the-loop results

```text
BINARY_SMOKE_OK
PROTOCOL_VERSION=1
JOINT_COUNT=6
FIRMWARE_VERSION=0x00020000
CALIBRATION_HASH=0x3DB42B48
CAPABILITIES=0x00000007
STOP_LATCHED=0
HEARTBEAT_COUNT=1
CRC_REJECT_COUNT=1
LAST_HEARTBEAT_MS=2303
SAFE_STOP_LATCH_CLEAR=OK
```

Verified behavior:

1. The STM32 and host exchange protocol-v1 frames successfully.
2. A deliberately corrupted CRC frame is rejected without motion.
3. A valid heartbeat is counted.
4. `SAFE_STOP` latches the command path without commanding motion.
5. `CLEAR_FAULT` reads all six positions and clears the latch only after the
   configured raw safety ranges pass.
6. A transient servo-read failure keeps the stop latched; retry can recover
   only after the safety read succeeds.
7. ASCII diagnostics are suppressed after entering binary mode, preventing
   mixed framing on the VCP link.
8. A 500 ms heartbeat loss latches the stop; renewed heartbeat plus a passing
   six-axis position check is required before clearing it.

## Deferred expansion work

- Multi-sample timestamped setpoint queue and stale/underflow handling
- Final robot-coordinate joint zero/sign calibration against the URDF
- Raspberry Pi transport integration and reconnection policy

## Binary setpoint bring-up results

- Six-axis `+52155 urad` command accepted and executed atomically.
- Positive targets mapped to raw `[2082, 2082, 2014, 2014, 2082, 2014]`.
- First outward test maximum error: 19 raw.
- Six-axis zero-radian home return completed with maximum error: 5 raw.
- Motion executor remained non-blocking at a 20 ms service period while host
  heartbeats continued.

## Active-motion SAFE_STOP and recovery

```text
PREFLIGHT_POSITIONS=[2052, 2050, 2051, 2045, 2053, 2044]
MOTION_ACCEPTED_STOP_SCHEDULED_400MS
SAFE_STOP_SENT_DURING_MOTION
BINARY_MOTION_SAFE_STOP_OK
RESET_THEN_RUN_HOME_RECOVERY

PREFLIGHT_POSITIONS=[2053, 2050, 2051, 2045, 2054, 2044]
MOTION_ACCEPTED MODE=home SAMPLES=1 STATE=3
BINARY_MOTION_OK MODE=home TARGET_URAD=[0, 0, 0, 0, 0, 0] MAX_ERROR_RAW=10
```

Verified behavior:

1. `SAFE_STOP` interrupted an active six-axis trajectory before completion.
2. The motion executor reported the stopped state and kept the command path
   latched.
3. After reset, all six axes returned to the calibrated zero-radian home.
4. Final recovery maximum error was 10 raw, approximately 0.88 degrees at the
   servo output shaft.

## Modular firmware regression

The monolithic application was separated into `servo_bus`, `binary_control`,
`single_arm_app`, and `single_arm_config`. The generated `main.c` now contains
only HAL initialization and application lifecycle calls.

```text
BINARY_SMOKE_OK
PROTOCOL_VERSION=1
JOINT_COUNT=6
FIRMWARE_VERSION=0x00020500
CALIBRATION_HASH=0x3DB42B48
CAPABILITIES=0x00000007
STOP_LATCHED=0
HEARTBEAT_COUNT=1
CRC_REJECT_COUNT=1

PREFLIGHT_POSITIONS=[2051, 2050, 2051, 2047, 2053, 2044]
MOTION_ACCEPTED_STOP_SCHEDULED_800MS TARGET_DEG=8
SAFE_STOP_SENT_DURING_MOTION
BINARY_MOTION_SAFE_STOP_OK

PREFLIGHT_POSITIONS=[2101, 2097, 2011, 2002, 2099, 1998]
MOTION_ACCEPTED MODE=home SAMPLES=1 STATE=3
BINARY_MOTION_OK MODE=home TARGET_URAD=[0, 0, 0, 0, 0, 0] MAX_ERROR_RAW=5
```

Regression result: protocol identity, calibration hash, six-axis motion,
active-motion SAFE_STOP, and post-stop home recovery all remained valid after
the module split.
