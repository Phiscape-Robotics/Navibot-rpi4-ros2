# Navibot motor bridge

ROS 2 USB-RS485 bus master for front/rear classic Nanos with local speed PI.
See [PROTOCOL.md](../PROTOCOL.md) for the Nano firmware contract. Firmware is not included.

```bash
source /opt/ros/lyrical/setup.bash
cd ~/ros2_ws
colcon build --symlink-install --packages-select navibot_motor_bridge
source install/setup.bash
ls -l /dev/serial/by-id/
ros2 launch navibot_motor_bridge motors.launch.py port:=/dev/serial/by-id/YOUR_ADAPTER
```

Default port is /dev/ttyUSB0. Prefer the by-id path when available, especially
when connecting the USB LiDAR too. User rpi already belongs to dialout.
Python dependency: python3-serial (installed on this Pi).

Topics (Float64MultiArray order: front_left, front_right, rear_left, rear_right):

- `/motor_bridge/target_rpm`: four signed RPM targets, +/-135 initially.
  Publish repeatedly; command expires after 250 ms. Invalid commands request zero.
- `/motor_bridge/wheel_rpm`: measured wheel RPM; disconnected/stale wheels are NaN.
- `/motor_bridge/wheel_duty`: applied duty percentage, -100 to +100; stale is NaN.
- `/motor_bridge/status`: String containing freshness, Nano flags and sample times.

Feedback ROS topics publish at 5 Hz; serial feedback arrives at 25 Hz per Nano.
Values combine latest readings from independently polled controllers, not a
synchronized four-wheel snapshot. This is not yet a cmd_vel/odometry interface;
wheel diameter, track width and steering geometry are still needed.

For an initial test, lift all four wheels clear and have a motor-power stop ready.
Only test after both Nanos implement the documented watchdog and protocol.

```bash
ros2 topic echo /motor_bridge/status
# In another sourced terminal: run briefly, then Ctrl-C to let targets expire.
ros2 topic pub -r 10 /motor_bridge/target_rpm std_msgs/msg/Float64MultiArray '{data: [10.0, 10.0, 10.0, 10.0]}'
```

Do not run concurrent serial applications on the same adapter. Automatic
transmit/receive turnaround must be verified for the actual USB adapter.
A GPIO/MAX485 interface is not configured by this package.

Tests, including two simulated Nanos over a Linux pseudo-terminal:

```bash
source /opt/ros/lyrical/setup.bash
cd ~/ros2_ws/src/navibot_motor_bridge
python3 -m unittest discover -s test -v
```

Hardware validation remains necessary: serial adapter direction switching,
bus wiring, Nano firmware, encoder calibration and actual motor response.

## Configuration

Defaults are in [config/motors.yaml](../config/motors.yaml).

| Parameter | Default | Purpose |
|---|---|---|
| `port` | `/dev/ttyUSB0` | USB adapter serial device; overridable at launch |
| `baudrate` | `115200` | Bus baud rate, 8N1 |
| `front_address` | `1` | Nano controlling front-left and front-right |
| `rear_address` | `2` | Nano controlling rear-left and rear-right |
| `poll_rate` | `50.0` | Total bus transactions per second |
| `reply_timeout` | `0.012` | Reply deadline in seconds |
| `command_timeout` | `0.25` | Maximum ROS target age in seconds |
| `feedback_timeout` | `0.25` | Maximum Nano feedback age in seconds |
| `max_rpm` | `135.0` | Maximum absolute target RPM |

The reply timeout must be shorter than the polling interval. Changing the
baud rate or RPM limit requires matching Nano firmware settings.

## Connection and stop behavior

The bridge retries an unavailable adapter every two seconds. It opens the
port exclusively, starts with zero targets, and requires fresh commands
after reconnecting. It accepts nonzero targets only when both controllers
have fresh feedback without RPM-invalid or controller-fault status flags.
If communication health is lost, targets are inhibited until health recovers
and a fresh ROS command arrives. Stop commands are attempted on shutdown.

Each Nano must independently force PWM off after 250 ms without a valid
addressed command. The Pi cannot guarantee delivery of a stop packet when
the cable, adapter, or Pi fails.

## Troubleshooting

- **No such file:** connect the adapter and check `/dev/serial/by-id/` and
  `/dev/ttyUSB*`; select the actual port through the launch argument.
- **Permission denied:** check membership of `dialout`; a new login is needed
  after changing group membership. Do not make the port world-writable.
- **Port busy:** stop other serial terminals or bridge processes.
- **Feedback is NaN or freshness is false:** check Nano addresses, firmware,
  baud rate, wiring, CRC, and adapter direction switching.
- **Targets remain zero:** check target message length/order, RPM range,
  publication frequency, and both Nano status flags.

## Validation status

Protocol and pseudo-terminal integration tests passed, including signed
commands to both Nanos, fragmented replies, bad checksums, wrong sequences,
command expiry, feedback loss, recovery, and shutdown zero commands.
The installed launch command was also checked with the adapter absent.
Physical USB-RS485 communication and motor operation have not been verified.
