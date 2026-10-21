# Navibot Raspberry Pi 4 ROS 2 workspace

ROS 2 Lyrical packages for Navibot's YDLIDAR X2, Pi Camera V2 (IMX219),
and USB-RS485 motor controller bridge.

## Packages

| Package | Purpose | Documentation |
| --- | --- | --- |
| `navibot_lidar` | X2 configuration and launch file | [LiDAR setup](src/navibot_lidar/docs/README.md) |
| `navibot_camera` | Camera configuration and launch file | [Camera setup](src/navibot_camera/docs/README.md) |
| `navibot_motor_bridge` | Four-wheel RPM commands and feedback through two Nano controllers | [Motor setup](src/navibot_motor_bridge/docs/README.md), [firmware protocol](src/navibot_motor_bridge/PROTOCOL.md) |
| `ydlidar_ros2_driver` | Manufacturer's ROS driver with local Lyrical compatibility changes | [Driver README](src/ydlidar_ros2_driver/README.md) |

## Prerequisites

- ROS 2 Lyrical installed at `/opt/ros/lyrical`, with `colcon` and the packages' ROS dependencies.
- YDLIDAR SDK installed separately. This Pi uses `~/.local/ydlidar_sdk`.
  The SDK revision and CMake compatibility patch are documented in the
  [LiDAR guide](src/navibot_lidar/docs/README.md#upstream-versions-and-local-changes).
- `camera_ros` and a working libcamera installation for the camera.
- `python3-serial` for the motor bridge, and serial-device permissions (typically the `dialout` group).

The camera launch file selects Ubuntu ARM64 libcamera libraries and IPA helpers
at explicit system paths as a workaround verified on this Pi. Review the
[runtime workaround](src/navibot_camera/docs/README.md#pi-4-libcamera-runtime-workaround)
before using it on another installation.

## Clone and build

```bash
git clone https://github.com/Phiscape-Robotics/Navibot-rpi4-ros2.git ~/ros2_ws
cd ~/ros2_ws
source /opt/ros/lyrical/setup.bash
colcon build --symlink-install --parallel-workers 1 --cmake-args \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_STANDARD=17 \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DBUILD_TESTING=OFF \
  -Dydlidar_sdk_DIR="$HOME/.local/ydlidar_sdk/lib/cmake/ydlidar_sdk"
source install/setup.bash
```

Install the SDK and other prerequisites before building. Adjust `ydlidar_sdk_DIR`
if the SDK is installed elsewhere. The driver source is included directly;
no submodule initialization is needed. Generated `build/`, `install/`, and `log/`
directories are ignored by Git.

The package guides also reference `~/setup-lidar.sh` and `~/setup-camera.sh`.
Those are helpers on the original Pi and are not included in this repository.

## Launch

In each terminal, first source ROS and the workspace:

```bash
source /opt/ros/lyrical/setup.bash
source ~/ros2_ws/install/setup.bash
```

Run each device in a separate terminal:

```bash
# YDLIDAR X2; override port if the configured adapter path differs.
ros2 launch navibot_lidar lidar.launch.py

# Pi Camera V2.
ros2 launch navibot_camera camera.launch.py

# Motor bridge; replace the placeholder with the RS485 adapter's actual path.
ros2 launch navibot_motor_bridge motors.launch.py port:=/dev/serial/by-id/YOUR_RS485_ADAPTER
```

Find serial devices with `ls -l /dev/serial/by-id/`. Use separate device paths
for the LiDAR and motor adapter. The motor controllers require firmware matching
the documented protocol; Nano firmware is not included. For initial motor tests,
lift all wheels clear and have a motor-power stop ready.

## Main interfaces

| Topic | Type | Purpose |
| --- | --- | --- |
| `/scan` | `sensor_msgs/msg/LaserScan` | LiDAR scans |
| `/camera/image_raw` | `sensor_msgs/msg/Image` | Camera images |
| `/camera/camera_info` | `sensor_msgs/msg/CameraInfo` | Camera calibration information |
| `/motor_bridge/target_rpm` | `std_msgs/msg/Float64MultiArray` | Four signed wheel RPM targets |
| `/motor_bridge/wheel_rpm` | `std_msgs/msg/Float64MultiArray` | Wheel speed feedback |
| `/motor_bridge/wheel_duty` | `std_msgs/msg/Float64MultiArray` | Applied motor duty |
| `/motor_bridge/status` | `std_msgs/msg/String` | Controller freshness and status |

Wheel arrays use `front_left, front_right, rear_left, rear_right` order.
Motor commands must be refreshed; the default command timeout is 250 ms.

Check sensor output in another sourced terminal:

```bash
ros2 topic hz /scan --qos-reliability best_effort
ros2 topic hz /camera/image_raw --qos-reliability best_effort
ros2 topic echo /motor_bridge/status
```

## Validation and remaining integration

The package guides record successful LiDAR streaming and camera streaming at
approximately 15 FPS on this Pi. Camera calibration and measured sensor mounting
transforms are still required. The motor bridge has protocol and simulated
serial integration tests; physical RS485 and motor operation remain unverified.
This workspace does not yet provide a complete navigation stack, `cmd_vel`
conversion, or wheel odometry.

Run the motor bridge tests without driving hardware:

```bash
source /opt/ros/lyrical/setup.bash
cd ~/ros2_ws/src/navibot_motor_bridge
python3 -m unittest discover -s test -v
```

The included YDLIDAR driver retains its [upstream license](src/ydlidar_ros2_driver/LICENSE.txt).
