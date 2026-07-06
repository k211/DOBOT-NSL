#!/usr/bin/env python3
"""
Moves the Dobot ME6 arm to the home position at startup via the
follow_joint_trajectory action (more reliable than the raw topic because
the action server handles timing, rejects old goals, and reports errors).

Launched by full_system.launch.py.  Uses wait_for_server so no fixed delay
is needed in the launch file — it fires as soon as the JTC is ready.
"""

import sys
import yaml
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint
from builtin_interfaces.msg import Duration

JOINT_NAMES = [
    'joint1', 'joint2', 'joint3', 'joint4', 'joint5', 'joint6',
]
ACTION_NAME = '/joint_trajectory_controller/follow_joint_trajectory'
MOVE_DURATION_SEC = 5


class HomeArm(Node):
    def __init__(self):
        super().__init__('home_arm')
        self.declare_parameter('initial_positions_file', '')
        self._client = ActionClient(self, FollowJointTrajectory, ACTION_NAME)

    def run(self):
        path = self.get_parameter('initial_positions_file').get_parameter_value().string_value
        if not path:
            self.get_logger().error('initial_positions_file parameter is empty — skipping homing')
            return

        try:
            with open(path) as f:
                positions = yaml.safe_load(f)
        except Exception as e:
            self.get_logger().error(f'Cannot read {path}: {e}')
            return

        self.get_logger().info('Waiting for joint_trajectory_controller action server…')
        if not self._client.wait_for_server(timeout_sec=60.0):
            self.get_logger().error('Action server not available after 60 s — skipping homing')
            return

        # Build the goal.
        # header.stamp MUST be in sim time so the JTC (which also uses sim time)
        # doesn't compute the trajectory start as being billions of seconds in the
        # future (wall clock epoch >> sim epoch).
        # stamp=0 means "start immediately on receipt" — the JTC sets the real
        # start time when it gets the message.  Using a non-zero sim-time stamp
        # makes the JTC compute an absolute deadline (stamp + time_from_start);
        # any DDS/wait_for_server latency eats into that window and silently
        # drops large multi-joint moves.
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = JOINT_NAMES
        # header.stamp left at default zero

        pt = JointTrajectoryPoint()
        pt.positions  = [float(positions.get(j, 0.0)) for j in JOINT_NAMES]
        pt.velocities = [0.0] * len(JOINT_NAMES)
        pt.time_from_start = Duration(sec=MOVE_DURATION_SEC, nanosec=0)
        goal.trajectory.points = [pt]

        pos_str = '  '.join(f'{j}={v:.2f}' for j, v in zip(JOINT_NAMES, pt.positions))
        self.get_logger().info(f'Sending homing goal ({MOVE_DURATION_SEC}s): {pos_str}')

        # The action server can exist while the JTC is still 'inactive' (its
        # activation races this node, since the arm already spawns at home and
        # wait_for_server returns early). A rejected goal here would fire the
        # OnProcessExit gate (servo + box spawn) mid controller-config — the
        # exact trap §11.1 exists to avoid. Retry until the JTC accepts.
        goal_handle = None
        for attempt in range(15):
            send_future = self._client.send_goal_async(goal)
            rclpy.spin_until_future_complete(self, send_future)
            goal_handle = send_future.result()
            if goal_handle.accepted:
                break
            self.get_logger().warn(
                f'Homing goal rejected (controller not active yet?) — retry {attempt + 1}/15')
            import time
            time.sleep(2.0)
        if goal_handle is None or not goal_handle.accepted:
            self.get_logger().error('Homing goal was REJECTED by the controller')
            return

        self.get_logger().info('Homing goal accepted, waiting for completion…')
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=MOVE_DURATION_SEC + 5.0)

        result = result_future.result()
        if result:
            ec = result.result.error_code
            if ec == FollowJointTrajectory.Result.SUCCESSFUL:
                self.get_logger().info('Arm reached Home position — ready for servo control.')
            else:
                self.get_logger().warn(f'Homing finished with error_code={ec}')
        else:
            self.get_logger().warn('Did not receive a result within timeout (motion may still be running)')


def main():
    rclpy.init()
    node = HomeArm()
    node.run()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
