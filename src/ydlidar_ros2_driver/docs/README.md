# Manufacturer YDLIDAR driver

This is the manufacturer's `humble` branch, adapted locally for ROS 2 Lyrical.
Use the robot launch package rather than the upstream default launch files:

```bash
source ~/ros2_ws/install/setup.bash
ros2 launch navibot_lidar lidar.launch.py
```

See [Navibot LiDAR documentation](../../navibot_lidar/docs/README.md).
CMake changes replace removed ament_target_dependencies calls with imported
CMake targets and select C++17. The driver and SDK commits and saved patches
are recorded in the Navibot documentation. Upstream runtime source is unchanged.
