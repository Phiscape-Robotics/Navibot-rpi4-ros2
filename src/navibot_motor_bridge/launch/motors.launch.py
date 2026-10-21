from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = str(Path(get_package_share_directory('navibot_motor_bridge')) / 'config/motors.yaml')
    return LaunchDescription([
        DeclareLaunchArgument('port', default_value='/dev/ttyUSB0'),
        Node(package='navibot_motor_bridge', executable='motor_bridge',
             name='motor_bridge', output='screen',
             parameters=[config, {'port': LaunchConfiguration('port')}]),
    ])
