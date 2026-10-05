"""Real-hardware teleop with rotations pivoting on the bare flange.

Identical to real_hw.launch.py except the teleop pivot point (TCP) is at the
flange itself, (0, 0, 0), instead of out at the probe. Use it to compare, or
whenever the probe offset is in doubt.

    ros2 launch dobot_e6_hw real_hw_flange.launch.py robot_ip:=192.168.5.1
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    base = os.path.join(get_package_share_directory('dobot_e6_hw'),
                        'launch', 'real_hw.launch.py')
    return LaunchDescription([
        DeclareLaunchArgument('robot_ip', default_value='192.168.5.1'),
        DeclareLaunchArgument('probe', default_value='true'),
        DeclareLaunchArgument('collision_level', default_value='2'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(base),
            launch_arguments={
                'robot_ip': LaunchConfiguration('robot_ip'),
                'probe': LaunchConfiguration('probe'),
                'collision_level': LaunchConfiguration('collision_level'),
                'tcp_x': '0.0', 'tcp_y': '0.0', 'tcp_z': '0.0',
            }.items()),
    ])
