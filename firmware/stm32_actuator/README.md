# STM32 Single-Arm Actuator Controller

This directory starts with a hardware-independent C11 core. It is intentionally kept separate from STM32 HAL and FreeRTOS so protocol, safety transitions, and bounded buffering can be tested on a host before any servo is energized.

## Implemented core

- COBS framing and CRC-32C
- protocol v1 frame validation and byte-stream resynchronization
- fail-closed `BOOT → SAFE_DISABLED → ARMED → ACTIVE` safety state machine
- heartbeat-loss transition to `HOLD`
- latched `FAULT` and physical `ESTOPPED` states
- six-joint bounded, atomic setpoint queue
- message IDs generated from `protocol/message_ids.json`

This directory contains portable code that is linked into the CubeIDE board
project and tested independently on the host. STM32 startup, HAL, STS3215 bus
access, and flash configuration remain in the board project; joint-unit
calibration conversion is part of this portable core.

## Host build

```powershell
cmake -S firmware/stm32_actuator -B build/stm32_actuator-host
cmake --build build/stm32_actuator-host --config Debug
ctest --test-dir build/stm32_actuator-host -C Debug --output-on-failure
```

On Windows, run those commands from a Visual Studio developer shell if CMake is not already on `PATH`.

## Planned board boundary

- Host/Pi link: STLINK-V3E VCP through the NUCLEO default `LPUART1` route (`PA2/PA3`)
- Single servo bus: separate `USART1` route (`PC4/PC5`)
- Control loop: hardware timer tick, rate to be fixed after read-only bus timing measurements
- UART RX: DMA/ring buffer; parsing remains outside ISR context
- Servo TX/RX: bounded transactions with explicit timeout; no blocking call in the control tick

Pin routing must be confirmed against the physical NUCLEO board revision before wiring or generating the CubeMX project.

## Generated protocol header

```powershell
python tools/generate_protocol_header.py
python tools/generate_protocol_header.py --check
```

The checked-in header must always match the machine-readable manifest.
