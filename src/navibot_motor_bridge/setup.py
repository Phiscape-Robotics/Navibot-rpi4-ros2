from glob import glob
from setuptools import setup
setup(
    name='navibot_motor_bridge', version='0.1.0',
    packages=['navibot_motor_bridge'],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/navibot_motor_bridge']),
        ('share/navibot_motor_bridge', ['package.xml', 'PROTOCOL.md']),
        ('share/navibot_motor_bridge/config', glob('config/*.yaml')),
        ('share/navibot_motor_bridge/launch', glob('launch/*.py')),
    ],
    install_requires=['setuptools', 'pyserial'],
    entry_points={'console_scripts': ['motor_bridge = navibot_motor_bridge.bridge:main']},
)
