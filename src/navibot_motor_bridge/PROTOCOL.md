# Navibot wheel bus protocol v1

Transport: half-duplex two-wire RS485, 115200 baud, 8 data bits, no parity,
1 stop bit. Pi is sole master; front Nano address 1, rear Nano address 2.
Use an automatic-direction USB-RS485 adapter on the Pi. Nanos control DE/RE.
Each Nano needs its own transceiver. Only the addressed Nano replies.
Wire A/B consistently, provide a signal reference appropriate for the
transceivers, and terminate at the two physical bus ends only. Check onboard
termination/bias resistors. Motor current must not flow through signal grounds.

## Packet

All multi-byte fields are little-endian. No text, newline, or byte escaping.

| Offset | Field | Bytes |
|---|---|---|
| 0 | Sync AA 55 | 2 |
| 2 | Version = 01 | 1 |
| 3 | Nano address (1 or 2) | 1 |
| 4 | Type | 1 |
| 5 | Sequence | 1 |
| 6 | Payload length (maximum 16) | 1 |
| 7 | Payload | length |
| 7 + length | CRC-16/MODBUS, low byte first | 2 |

CRC covers version through the final payload byte, excludes sync and CRC.
Initial value FFFF, reflected polynomial A001, no final XOR.
Reference: CRC of ASCII `123456789` is 4B37.
Receiver searches sync, validates version, length, CRC, address, message type
and payload before accepting a command. Reset incomplete frames after 20 ms
without another byte. Invalid packets never reset the command watchdog.

## Set RPM and request feedback: type 01, payload length 4

| Payload offset | Type | Meaning |
|---|---|---|
| 0 | int16 | Left target RPM times 10 |
| 2 | int16 | Right target RPM times 10 |

Positive wheel speed drives the robot forward, regardless of motor mounting.
100 = +10 RPM, -100 = -10 RPM. Reject targets outside the configured limit
(default +/-135 RPM). Sequence wraps modulo 256 and is echoed by the reply.
Repeated identical commands are valid and refresh the watchdog.
There is no broadcast command and no unsolicited feedback.

## Feedback: type 81, payload length 14

| Payload offset | Type | Meaning |
|---|---|---|
| 0 | int16 | Measured left RPM times 10 |
| 2 | int16 | Measured right RPM times 10 |
| 4 | int16 | Left applied duty, -1000 to +1000 |
| 6 | int16 | Right applied duty, -1000 to +1000 |
| 8 | uint32 | Nano millis at RPM measurement, wraps naturally |
| 12 | uint16 | Status bits |

Status bit 0: command watchdog previously expired (clear on valid command).
Bit 1: RPM measurement not yet valid. Bit 2: controller fault.
Other bits reserved, zero. Feedback address identifies the replying Nano.
Snapshot encoder/RPM values atomically where required on the 8-bit Nano.

Respond promptly, preferably within 2 ms after the final request byte.
Allow approximately 200 us after receiving the full request before enabling
transmit to allow adapter turnaround; verify this on the chosen USB adapter.
Finish the entire response within the Pi's 12 ms reply deadline. Use Serial.flush()
to wait for the final stop bit before releasing DE. No Serial.print debug text
on this UART. Pi ignores local echoes, wrong address/type/sequence and bad CRC.
A reply timeout ends the transaction; never send a delayed reply afterward.

## Control ownership and stops

Nano runs two fixed-rate PI loops (initially 100 Hz), performs encoder speed
estimation, output limiting, anti-windup and controlled reversal. Pi sends RPM,
not PWM. Encoder calibration initially approximately 1000 counts/output-shaft
revolution with A CHANGE decoding; measure this value for each wheel.

Nano must start with PWM zero and reset PI state. At 250 ms without a valid
addressed command, force PWM zero and reset the integrator. Target zero means
stop: clear integrator and disable drive; select coast initially. A physical
emergency stop must remove motor drive independently of software.

Pi polls alternating addresses at 50 total transactions/sec (25 per Nano).
It commands zero after 250 ms without a fresh ROS command. Loss of feedback
from either Nano for 250 ms, RPM-not-valid or a controller fault inhibits both
controllers; a fresh ROS command is needed after health recovers. Shutdown
attempts zero commands; the Nano watchdog is essential if the Pi disappears.
The bridge only accepts new targets while connected. Never resume a stored
nonzero target automatically after serial reconnection.
