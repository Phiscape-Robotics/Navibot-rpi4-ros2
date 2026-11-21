#!/usr/bin/env bash
# Launch one Navibot device and save its console output under logs/.
# Usage: ./scripts/launch_device.sh camera
#        ./scripts/launch_device.sh lidar port:=/dev/ttyUSB1
#        ./scripts/launch_device.sh motor_bridge port:=/dev/ttyUSB0

set -Eeuo pipefail

workspace_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ros_setup=/opt/ros/lyrical/setup.bash
workspace_setup="$workspace_dir/install/setup.bash"

if [[ ! -r "$ros_setup" ]]; then
    echo "ROS setup not found: $ros_setup" >&2
    exit 1
fi
if [[ ! -r "$workspace_setup" ]]; then
    echo "Workspace is not built: $workspace_setup" >&2
    exit 1
fi

device=${1:-}
if [[ $# -gt 0 ]]; then
    shift
fi

case "$device" in
    camera)
        launch=(ros2 launch navibot_camera camera.launch.py "$@")
        log_file="$workspace_dir/logs/camera.log"
        ;;
    lidar)
        launch=(ros2 launch navibot_lidar lidar.launch.py "$@")
        log_file="$workspace_dir/logs/lidar.log"
        ;;
    motor_bridge)
        launch=(ros2 launch navibot_motor_bridge motors.launch.py "$@")
        log_file="$workspace_dir/logs/motor_bridge.log"
        ;;
    *)
        echo "Usage: $0 {camera|lidar|motor_bridge} [launch arguments...]" >&2
        exit 2
        ;;
esac

source "$ros_setup"
source "$workspace_setup"
mkdir -p "$workspace_dir/logs"
"${launch[@]}" 2>&1 | tee "$log_file"
