"""Launch the manufacturer's X2 driver using robot-specific parameters."""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = str(Path(get_package_share_directory('navibot_lidar')) / 'config/x2.yaml')
    return LaunchDescription([
        DeclareLaunchArgument('config', default_value=config),
        DeclareLaunchArgument('port', default_value=(
            '/dev/serial/by-id/'
            'usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0')),
        Node(package='ydlidar_ros2_driver', executable='ydlidar_ros2_driver_node',
             name='lidar', output='screen',
             parameters=[LaunchConfiguration('config'),
                         {'port': LaunchConfiguration('port')}]),
    ])
