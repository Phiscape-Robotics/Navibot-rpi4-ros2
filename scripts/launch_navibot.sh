#!/usr/bin/env bash
# Start Navibot's camera, LiDAR, and RS485 motor bridge in one terminal.
#
# Optional environment overrides:
#   MOTOR_PORT=/dev/serial/by-id/<RS485-adapter> ./scripts/launch_navibot.sh
#   LIDAR_PORT=/dev/serial/by-id/<lidar-adapter> ./scripts/launch_navibot.sh

set -Eeo pipefail

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

source "$ros_setup"
source "$workspace_setup"
set -u

motor_port="${MOTOR_PORT:-/dev/ttyUSB0}"
lidar_port="${LIDAR_PORT:-}"
log_dir="$workspace_dir/logs"
mkdir -p "$log_dir"
pids=()
names=()
logs=()

start_launch() {
    local name=$1
    local log_file=$2
    shift 2
    : > "$log_file"
    "$@" > "$log_file" 2>&1 &
    pids+=("$!")
    names+=("$name")
    logs+=("$log_file")
}

cleanup() {
    trap - EXIT INT TERM
    for pid in "${pids[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -INT "$pid" 2>/dev/null || true
        fi
    done
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
}
trap cleanup EXIT INT TERM

start_launch "Camera" "$log_dir/camera.log" \
    ros2 launch navibot_camera camera.launch.py

if [[ -n "$lidar_port" ]]; then
    start_launch "LiDAR" "$log_dir/lidar.log" \
        ros2 launch navibot_lidar lidar.launch.py "port:=$lidar_port"
else
    start_launch "LiDAR" "$log_dir/lidar.log" \
        ros2 launch navibot_lidar lidar.launch.py
fi

start_launch "Motor bridge" "$log_dir/motor_bridge.log" \
    ros2 launch navibot_motor_bridge motors.launch.py "port:=$motor_port"

sleep 2
all_started=true
for index in "${!pids[@]}"; do
    if kill -0 "${pids[index]}" 2>/dev/null; then
        echo "${names[index]}: launched (${logs[index]})"
    else
        echo "${names[index]}: failed to launch; see ${logs[index]}" >&2
        all_started=false
    fi
done
if [[ "$all_started" != true ]]; then
    exit 1
fi

wait "${pids[@]}"
