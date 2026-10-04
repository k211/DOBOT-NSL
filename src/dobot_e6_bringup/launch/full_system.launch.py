import os
import xacro
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, OpaqueFunction, RegisterEventHandler, TimerAction
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, PathJoinSubstitution
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory


def launch_setup(context, *args, **kwargs):
    bringup_dir = get_package_share_directory('dobot_e6_bringup')
    # MoveIt Servo changed its parameter schema after Humble.
    servo_config = ('servo_params_humble.yaml'
                    if os.environ.get('ROS_DISTRO') == 'humble'
                    else 'servo_params.yaml')
    servo_params_file = os.path.join(bringup_dir, 'config', servo_config)
    servo_moveit_params_file = os.path.join(bringup_dir, 'config', 'servo_moveit_params.yaml')
    joy_params_file = os.path.join(bringup_dir, 'config', 'joy_params.yaml')
    controllers_file = os.path.join(bringup_dir, 'config', 'ros2_controllers.yaml')
    initial_positions_file = os.path.join(bringup_dir, 'config', 'initial_positions_e6.yaml')

    # robot_description via xacro. The wrapper seeds the gz joints with the SRDF
    # "home" pose (all-zeros is a real singularity on the ME6 — cond number = inf),
    # so unlike the Kinova the arm never spawns singular; home_arm below is then
    # just a fast no-op move that still gates servo/box startup ordering.
    # Use xacro's Python API instead of launch Command: the latter invokes a
    # shell and splits workspace paths containing spaces (for example,
    # "Dobot arm") into multiple arguments.
    robot_description = xacro.process_file(
        os.path.join(bringup_dir, 'robots', 'probe_wrapper_e6.urdf.xacro'),
        mappings={
            'simulation_controllers': controllers_file,
            'initial_positions_file': initial_positions_file,
        },
    ).toxml()

    # --- 1. Sim bring-up (Gazebo Harmonic, mirrors kortex_sim_control) ---
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='both',
        parameters=[{'robot_description': robot_description, 'use_sim_time': True}],
    )

    gz_args = (' -s -r -v 3 empty.sdf'
               if os.environ.get('ROS_DISTRO') == 'humble'
               else ' -s -r -v 3 empty.sdf --physics-engine gz-physics-bullet-featherstone-plugin')
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            get_package_share_directory('ros_gz_sim'), '/launch/gz_sim.launch.py']),
        launch_arguments={'gz_args': gz_args}.items(),
    )

    # URDF world_joint fixes the model to the world at z=0.03, so spawn at origin.
    gz_spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=['-string', robot_description,
                   '-name', 'me6_robot', '-allow_renaming', 'true',
                   '-x', '0.0', '-y', '0.0', '-z', '0.0'],
    )

    clock_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen',
    )

    jsb_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster', '-c', '/controller_manager'],
    )
    jtc_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_trajectory_controller', '-c', '/controller_manager'],
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='log',
        parameters=[{'use_sim_time': True}],
        arguments=['-d', os.path.join(bringup_dir, 'rviz', 'view_robot.rviz')],
    )

    # --- FT sensor plumbing ---
    # gz force_torque publishes gz.msgs.Wrench (no header). Bridge it to
    # geometry_msgs/Wrench on /ft_sensor, then ft_relay stamps it as
    # WrenchStamped on /ft_sensor/wrench for the haptic node.
    ft_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='ft_bridge',
        parameters=[{'use_sim_time': True}],
        arguments=['/ft_sensor@geometry_msgs/msg/Wrench[gz.msgs.Wrench'],
        output='screen',
    )
    ft_relay = Node(
        package='dobot_e6_bringup',
        executable='ft_relay.py',
        name='ft_relay',
        parameters=[{'use_sim_time': True, 'frame_id': 'us_probe_link'}],
        output='screen',
    )

    # --- 2. MoveIt Servo as a component in a multi-threaded container ---
    # component_container_mt keeps the executor spinning on multiple threads,
    # allowing joint_state callbacks to fire while init blocks on
    # waitForCompleteState (the standalone binary deadlocks — handoff §11.7).
    servo_container = TimerAction(
        period=20.0,
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
                            {'robot_description': robot_description},
                        ],
                    ),
                ],
                output='screen',
            ),
        ],
    )

    # --- 3. Homing move ---
    # The arm already spawns at home (see xacro), but keeping the homing action
    # preserves the load-bearing launch ordering: servo activation and box spawn
    # fire only on its OnProcessExit (handoff §11.1).
    home_node = Node(
        package='dobot_e6_bringup',
        executable='home_arm.py',
        name='home_arm',
        parameters=[{'initial_positions_file': initial_positions_file}],
        output='screen',
    )

    # --- 4. Activate servo twist mode — only AFTER homing completes ---
    activate_servo_node = Node(
        package='dobot_e6_bringup',
        executable='activate_servo.py',
        name='activate_servo',
        output='screen',
    )

    # --- Green box ---
    # Spawn AFTER homing so it never appears mid controller-config (§11.1).
    # 0.25x0.25x0.15 box under the probe-down home pose: probe tip is at
    # world (-0.084, 0.343, 0.287); box top face at world z=0.15.
    green_box_sdf = os.path.join(bringup_dir, 'models', 'green_box.sdf')
    spawn_box_node = Node(
        package='ros_gz_sim',
        executable='create',
        name='spawn_green_box',
        arguments=['-file', green_box_sdf, '-name', 'green_box',
                   '-x', '-0.08', '-y', '0.34', '-z', '0.075'],
        output='screen',
    )

    # Mirror the gz box as an RViz Marker (RViz can't see gz models).
    green_box_marker = Node(
        package='dobot_e6_bringup',
        executable='green_box_marker.py',
        name='green_box_marker',
        output='screen',
    )

    activate_after_home = RegisterEventHandler(
        OnProcessExit(
            target_action=home_node,
            on_exit=[activate_servo_node, spawn_box_node],
        )
    )

    # --- 5. Joy node ---
    joy_node = Node(
        package='joy',
        executable='joy_node',
        name='joy_node',
        parameters=[joy_params_file],
        output='screen',
    )

    # --- 6. Joy-to-servo bridge (DualSense: sticks + L2/R2, L1 deadman) ---
    teleop_node = Node(
        package='dobot_e6_bringup',
        executable='joy_to_servo.py',
        name='joy_to_servo_node',  # must match key in joy_params.yaml
        parameters=[joy_params_file],
        output='screen',
    )

    # --- 7. Haptic feedback ---
    haptic_node = Node(
        package='dobot_e6_bringup',
        executable='haptic_feedback.py',
        name='haptic_feedback',
        output='screen',
    )

    return [
        gz_sim, gz_spawn_robot, clock_bridge, robot_state_publisher,
        jsb_spawner, jtc_spawner,
        home_node, servo_container, activate_after_home,
        joy_node, teleop_node, haptic_node, green_box_marker,
        rviz_node, ft_bridge, ft_relay,
    ]


def generate_launch_description():
    return LaunchDescription([OpaqueFunction(function=launch_setup)])
