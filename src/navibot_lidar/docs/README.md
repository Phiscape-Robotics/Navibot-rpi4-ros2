# Navibot YDLIDAR X2

ROS 2 Lyrical bringup for the serial X2 using the manufacturer's driver and SDK.
The SDK is installed under `~/.local/ydlidar_sdk`; no root install is required.

## Build and run

The local source trees are already fetched and patched for this system:

```bash
~/setup-lidar.sh
source /opt/ros/lyrical/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 launch navibot_lidar lidar.launch.py
```

The adapter currently uses this stable path:

```text
/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0
```

Override it for another device:

```bash
ros2 launch navibot_lidar lidar.launch.py port:=/dev/ttyUSB1
```

Do not point the motor bridge at the LiDAR port. The USB-RS485 adapter must
have a separate device path. Some CP2102 adapters share the same generic
serial number; if a second identical adapter is connected, use distinct
`/dev/serial/by-path/` paths or device-specific udev rules.

## Configuration

Edit [config/x2.yaml](../config/x2.yaml). A custom YAML file can be supplied
with `config:=/absolute/path/x2.yaml`; the launch `port` argument takes
precedence over the port in YAML.

| Parameter | Value | Meaning |
|---|---|---|
| `baudrate` | `115200` | X2 serial baud rate |
| `lidar_type` | `1` | Triangulation LiDAR |
| `device_type` | `0` | Serial connection |
| `isSingleChannel` | `true` | X2 single-channel protocol |
| `sample_rate` | `3` | Nominal 3 kHz sampling |
| `range_min`, `range_max` | `0.1`, `8.0` | Accepted range in metres |
| `angle_min`, `angle_max` | `-180.0`, `180.0` | Full scan in degrees |
| `frequency` | `6.0` | Requested scan frequency; X2 speed depends on motor PWM |
| `frame_id` | `laser_frame` | Scan coordinate frame |
| `support_motor_dtr` | `true` | Adapter motor control through DTR |
| `invalid_range_is_inf` | `true` | Invalid samples represented as infinity |

Actual scan rate depends on the motor and adapter. Check measured ROS output
rather than assuming the requested frequency is achieved. Verify forward
angle and rotation against real obstacles before using scans for navigation.
No mounting transform is invented or published by this package; add the
measured transform from the robot base to `laser_frame` during robot bringup.

## Topics and services

| Interface | Type | Purpose |
|---|---|---|
| `/scan` | `sensor_msgs/msg/LaserScan` | Range scan, SensorDataQoS/best effort |
| `/point_cloud` | `sensor_msgs/msg/PointCloud` | Upstream driver's point cloud |
| `/start_scan` | `std_srvs/srv/Empty` | Start scanning |
| `/stop_scan` | `std_srvs/srv/Empty` | Stop scanning |

In another sourced terminal:

```bash
ros2 topic hz /scan --qos-reliability best_effort
ros2 topic echo /scan --once --qos-reliability best_effort
ros2 service call /stop_scan std_srvs/srv/Empty '{}'
ros2 service call /start_scan std_srvs/srv/Empty '{}'
```

On a graphical ROS computer, open RViz2, set Fixed Frame to `laser_frame`,
add a LaserScan display for `/scan`, and use Best Effort reliability.
A VS Code SSH terminal alone does not provide a graphical display.

## Troubleshooting

- **No serial device:** check USB/power and `ls -l /dev/serial/by-id/`.
- **Permission denied:** the user needs dialout access; rpi is already a member.
- **No scans:** check that no other process owns the port, the X2 is spinning,
  and baud rate/single-channel settings match the device.
- **Incorrect distances or angles:** confirm model/configuration and test
  against stationary objects of known distance and direction.
- **Build errors after updating sources:** review the saved compatibility
  patches before rebuilding. Do not blindly reapply a patch twice.

## Upstream versions and local changes

- SDK: https://github.com/YDLIDAR/YDLidar-SDK
  commit `42a82ed10d2304094c111fc63dee8e4a229b79b7`.
- ROS driver: https://github.com/YDLIDAR/ydlidar_ros2_driver, branch `humble`,
  commit `4ef70d3f32a85704ade0be54b214f3763b1ab3e8`.
- [SDK CMake 4 patch](patches/sdk-cmake4.patch): replace removed OLD policies,
  use a target-file generator expression, and omit obsolete build-tree export
  installation, and export the user-local library search path. SDK compiler/runtime source is unchanged.
- [Driver Lyrical patch](patches/driver-lyrical.patch): C++17 and imported target
  linkage in place of removed ament_target_dependencies.

Manufacturer X2 configuration reference:
https://github.com/YDLIDAR/ydlidar_ros2_driver/blob/master/details.md

## Validation on this Pi

The connected CP2102 adapter resolved to `/dev/ttyUSB1` during validation.
Both packages built successfully on ROS 2 Lyrical. A bounded live capture
received 30 LaserScan messages at approximately 11.58 Hz, with 260 samples
per scan. The last scan contained 177 finite in-range returns, spanning
approximately 0.195 to 7.155 m, and frame `laser_frame`.
Configured limits were 0.1 to 8 m and -pi to +pi radians. These are observed
sensor readings, not a distance-accuracy calibration. Physical forward-angle
alignment and the mounting transform remain to be checked.

The SDK logged `Fail to get baseplate device information!`, then initialized,
reported healthy status, and streamed successfully. This message did not
prevent capture in this test; investigate if accompanied by missing scans
or other failures. The scanner stopped cleanly after the test.

Measured scan rate exceeded the requested 6 Hz. Verify and adjust the X2's
motor speed using its supported hardware/PWM control if a lower rate is
needed; do not assume changing `frequency` controls that hardware.
