# Navibot camera

ROS 2 Lyrical bringup for the Pi Camera V2 (IMX219), using the upstream
camera_ros node. Defaults: requested 640x480, approximately 15 FPS,
1640x1232 sensor mode to avoid VGA sensor cropping. The driver may adjust
unsupported stream settings; verify the startup log on the actual sensor.

## Setup and run

```bash
~/setup-camera.sh
source /opt/ros/lyrical/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 launch navibot_camera camera.launch.py
```

Topics: `/camera/image_raw` and `/camera/camera_info`. The image frame is
`camera_optical_frame` (x right, y down, z forward). Its transform to the
robot must be supplied from measured mounting geometry, not guessed here.

The image is uncalibrated initially. Supply real calibration data using:

```bash
ros2 launch navibot_camera camera.launch.py camera_info_url:=file:///absolute/path/calibration.yaml
```

Do not use zero-initialized camera intrinsics for geometry or rectification.
Compression requires an installed image_transport plugin; this package does
not promise compressed topics.

## Verify streaming (another terminal with both setups sourced)

```bash
ros2 topic hz /camera/image_raw --qos-reliability best_effort
ros2 topic echo /camera/camera_info --once --qos-reliability best_effort
```

## Camera not detected

`cam -l` must list the IMX219. `/dev/video10` and similar codec/ISP devices
alone do not prove a camera is connected. Boot configuration currently has
`camera_auto_detect=1`. If no sensor appears, shut the Pi down and disconnect
power before checking the CSI connector and ribbon orientation. Reboot and
check `cam -l` again. Do not reconnect a CSI cable while powered.

Build validation alone does not test the external camera_ros executable,
libcamera compatibility, physical sensor, image stream, or calibration.

## Pi 4 libcamera runtime workaround

On this Pi, ROS libcamera 0.7.2 enumerates the camera but its isolated IPA
helper aborts with `A list of V4L2 controls requires a ControlInfoMap`.
Standalone capture and ROS streaming work using Ubuntu libcamera 0.7.0.
The launch file preloads Ubuntu's two libcamera libraries and selects its
matching IPA modules and proxy, scoped to the camera process and children.
Both packages remain installed; no global library paths are changed.
This launch configuration is specific to this Ubuntu ARM64 installation.
Recheck the workaround after libcamera package upgrades.

The requested libcamera format is RGB888; the verified ROS image encoding is
`bgr8` (640x480, 921600 bytes per frame). Calibration
is still required: uncalibrated CameraInfo can contain zero dimensions and
intrinsics even while image capture is working.

## Configuration

Edit [config/camera.yaml](../config/camera.yaml), or provide a configuration file:

```bash
ros2 launch navibot_camera camera.launch.py config:=/absolute/path/camera.yaml
```

“Current” below means the value in this package's YAML, rather than the
upstream driver's default. Limits were checked against the driver and this
Pi's libcamera output; mode-dependent limits are not universal guarantees.

| Parameter | Current | Minimum | Maximum | Allowed values / constraints |
|---|---|---|---|---|
| `camera` | `0` | `0` (index) | Number of detected cameras minus 1 | Zero-based index, or an exact libcamera camera ID string. Only index `0` is available with one camera. |
| `role` | `video` | N/A | N/A | `raw`, `still`, `video`, `viewfinder`. |
| `format` | `RGB888` | N/A | N/A | Current video startup reported `NV21`, `XBGR8888`, `BGR888`, `RGB888`, `XRGB8888`, `YUYV`, `UYVY`. Availability depends on role and runtime. |
| `width` | `640` pixels | `64` pixels reported | `3280` pixels reported | Pipeline output envelope; valid dimensions depend on format and height. Unsupported requests may be adjusted. |
| `height` | `480` pixels | `64` pixels reported | `2464` pixels reported | Pipeline output envelope; valid dimensions depend on format and width. These bounds do not guarantee every width/height combination. |
| `sensor_mode` | `1640:1232` | Mode-dependent | Sensor dimensions up to `3280:2464` | A supported discrete raw mode in `width:height` form; not a continuous numeric range. Empty string selects automatically. |
| `FrameDurationLimits` | `[66667, 66667]` microseconds | Sensor/mode-dependent; query reported `33333` | Sensor/mode-dependent; query reported `250000000` | Two positive frame durations `[shortest, longest]`, with shortest ≤ longest. The quoted bounds came from a non-capturing query using its default configuration, not a guarantee for all sensor modes. |
| `orientation` | `0` degrees | `0` | `270` | Discrete values `0`, `90`, `180`, `270`; hardware may adjust the requested orientation. |
| `frame_id` | `camera_optical_frame` | N/A | N/A | Frame name string. Use a nonempty TF-compatible name; x right, y down, z forward. |
| `camera_info_url` (launch argument) | Empty; driver chooses default file | N/A | N/A | Calibration URL, e.g. `file:///absolute/path/calibration.yaml`. |

`width`, `height`, format, role, sensor selection, orientation, frame ID, and
calibration URL are startup settings: restart the node after changing them.
No robot-to-camera transform is published by this package.

For a fixed requested FPS, use equal frame-duration entries:

```text
frame_duration_us = 1,000,000 / requested_FPS
15 FPS ≈ [66667, 66667]
20 FPS = [50000, 50000]
30 FPS ≈ [33333, 33333]
```

These examples are requests; achievable FPS depends on the selected sensor
mode, exposure, and processing load. The current configuration was verified
at approximately 15 FPS. Do not derive maximum camera FPS from output size
alone or assume the full sensor resolution supports the fastest mode.

To inspect current limits without starting a ROS camera node or capturing:

```bash
env -u LD_LIBRARY_PATH cam -c 1 --list-controls -I
```

`cam` uses **1-based** camera indices; the ROS `camera` index is **0-based**.
If another process owns the camera, this query may fail. Its default stream
configuration can report different control limits from the running ROS node.
When your camera node is already running, inspect its parameter descriptors:

```bash
ros2 param describe /camera FrameDurationLimits
ros2 param describe /camera orientation
```

Reference: [camera_ros 0.7.0 parameter declarations](https://github.com/christianrauch/camera_ros/blob/0.7.0/src/CameraNode.cpp).

## View images

On a computer with ROS 2, `rqt_image_view`, and a graphical desktop:

```bash
ros2 run rqt_image_view rqt_image_view
```

Select `/camera/image_raw`. For viewing from another computer, ROS discovery
must work between it and the Pi, and their `ROS_DOMAIN_ID` values must match.
A VS Code remote terminal alone does not display a GUI. There is currently
no browser viewer in this package.

## Validation status

On this Pi, the saved launch configuration delivered 60 color images and
60 CameraInfo messages at approximately 15 FPS with the runtime workaround.
CameraInfo remains uncalibrated; zero dimensions/intrinsics are expected
until a real calibration is supplied. The stream-adjustment warning is
acceptable when the resulting dimensions and format are as intended.
