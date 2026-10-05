"""Real-hardware bringup (Option B, handoff §5.2) — UNTESTED until the arm arrives.

Same ROS graph as full_system.launch.py above the robot layer; the bottom layer
(Gazebo + JTC) is replaced by dobot_tcp_node. No FT sensor yet: the contact cue
needs the external wrist F/T sensor (§0.5) publishing on /ft_sensor/wrench.

The TCP node claims control authority itself via RequestControl() at startup,
so no DobotStudio Pro session is required.
"""
import os
import xacro
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, TimerAction
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import ComposableNodeContainer, Node
from launch_ros.descriptions import ComposableNode
from ament_index_python.packages import get_package_share_directory


def launch_setup(context, *args, **kwargs):
    bringup_dir = get_package_share_directory('dobot_e6_bringup')
    servo_config = ('servo_params_humble.yaml'
                    if os.environ.get('ROS_DISTRO') == 'humble'
                    else 'servo_params.yaml')
    servo_params_file = os.path.join(bringup_dir, 'config', servo_config)
    servo_moveit_params_file = os.path.join(bringup_dir, 'config', 'servo_moveit_params.yaml')
    joy_params_file = os.path.join(bringup_dir, 'config', 'joy_params.yaml')
    controllers_file = os.path.join(bringup_dir, 'config', 'ros2_controllers.yaml')
    initial_positions_file = os.path.join(bringup_dir, 'config', 'initial_positions_e6.yaml')
    robot_ip = LaunchConfiguration('robot_ip').perform(context)
    probe = LaunchConfiguration('probe').perform(context).lower() in ('true', '1', 'yes')

    # Same wrapper xacro as sim: gazebo/ros2_control tags are inert without gz.
    robot_description = xacro.process_file(
        os.path.join(bringup_dir, 'robots', 'probe_wrapper_e6.urdf.xacro'),
        mappings={
            'simulation_controllers': controllers_file,
            'initial_positions_file': initial_positions_file,
            # Teleop pivot point, metres in the Link6 frame. real_hw_flange.launch.py
            # passes 0 0 0 to pivot on the bare flange instead.
            'tcp_x': LaunchConfiguration('tcp_x').perform(context),
            'tcp_y': LaunchConfiguration('tcp_y').perform(context),
            'tcp_z': LaunchConfiguration('tcp_z').perform(context),
        },
    ).toxml()

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='both',
        parameters=[{'robot_description': robot_description}],
    )

    tcp_node = Node(
        package='dobot_e6_hw',
        executable='dobot_tcp_node.py',
        name='dobot_tcp_node',
        parameters=[{'robot_ip': robot_ip, 'probe': probe}],
        output='screen',
    )

    # Servo consumes /joint_states from the TCP node; its trajectory output is
    # consumed back by the TCP node. use_sim_time must be off → override the
    # sim-tuned yaml here rather than duplicating it.
    servo_container = TimerAction(
        period=5.0,
        actions=[
            ComposableNodeContainer(
                name='servo_container',
                namespace='',
                package='rclcpp_components',
                executable='component_container_mt',
                composable_node_descriptions=[
                    ComposableNode(
                        package='moveit_servo',
                        plugin='moveit_servo::ServoNode',
                        name='servo_node',
                        parameters=[
                            servo_params_file,
                            servo_moveit_params_file,
                            {'robot_description': robot_description,
                             'use_sim_time': False,
                             **({'moveit_servo.use_gazebo': False}
                                if os.environ.get('ROS_DISTRO') == 'humble'
                                else {})},
                        ],
                    ),
                ],
                output='screen',
            ),
        ],
    )

    activate_servo_node = TimerAction(
        period=15.0,
        actions=[Node(
            package='dobot_e6_bringup',
            executable='activate_servo.py',
            name='activate_servo',
            output='screen',
        )],
    )

    joy_node = Node(
        package='joy',
        executable='joy_node',
        name='joy_node',
        parameters=[joy_params_file],
        output='screen',
    )
    teleop_node = Node(
        package='dobot_e6_bringup',
        executable='joy_to_servo.py',
        name='joy_to_servo_node',
        parameters=[joy_params_file],
        output='screen',
    )
    haptic_node = Node(
        package='dobot_e6_bringup',
        executable='haptic_feedback.py',
        name='haptic_feedback',
        output='screen',
    )

    return [robot_state_publisher, tcp_node, servo_container,
            activate_servo_node, joy_node, teleop_node, haptic_node]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('robot_ip', default_value='192.168.5.1',
                              description='E6 LAN1 wired IP'),
        DeclareLaunchArgument('tcp_x', default_value='0.065',
                              description='Teleop pivot offset from the flange, m (Link6 X)'),
        DeclareLaunchArgument('tcp_y', default_value='0.0',
                              description='Teleop pivot offset from the flange, m (Link6 Y)'),
        DeclareLaunchArgument('tcp_z', default_value='0.098',
                              description='Teleop pivot offset from the flange, m (Link6 Z)'),
        DeclareLaunchArgument('probe', default_value='true',
                              description='Is the ultrasound probe fitted? Sets the '
                                          'payload declared to the controller'),
        OpaqueFunction(function=launch_setup),
    ])
