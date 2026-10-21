"""Start the libcamera driver with robot camera defaults."""
import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    default_config = str(
        Path(get_package_share_directory('navibot_camera')) / 'config' / 'camera.yaml'
    )
    return LaunchDescription([
        DeclareLaunchArgument('config', default_value=default_config),
        DeclareLaunchArgument('camera_info_url', default_value=''),
        Node(
            package='camera_ros',
            executable='camera_node',
            name='camera',
            output='screen',
            # ROS libcamera 0.7.2 crashes in the Pi 4 IPA serializer here.
            # Pin only camera libraries and helpers to Ubuntu's tested 0.7.0.
            # This environment also propagates to the isolated IPA helper.
            additional_env={
                'LD_PRELOAD': ':'.join(filter(None, [
                    '/usr/lib/aarch64-linux-gnu/libcamera.so.0.7',
                    '/usr/lib/aarch64-linux-gnu/libcamera-base.so.0.7',
                    os.environ.get('LD_PRELOAD', ''),
                ])),
                'LIBCAMERA_IPA_MODULE_PATH': '/usr/lib/aarch64-linux-gnu/libcamera/ipa',
                'LIBCAMERA_IPA_PROXY_PATH': '/usr/libexec/aarch64-linux-gnu/libcamera',
            },
            parameters=[
                LaunchConfiguration('config'),
                {'camera_info_url': ParameterValue(
                    LaunchConfiguration('camera_info_url'), value_type=str)},
            ],
        ),
    ])
