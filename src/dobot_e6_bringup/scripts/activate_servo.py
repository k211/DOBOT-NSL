#!/usr/bin/env python3
"""
Waits for /servo_node/switch_command_type service and activates TWIST mode.
Launched automatically by full_system.launch.py so the user never has to
call switch_command_type manually.
"""

import rclpy
from rclpy.node import Node
from moveit_msgs.srv import ServoCommandType

TWIST = 1   # ServoCommandType::TWIST


class ActivateServo(Node):
    def __init__(self):
        super().__init__('activate_servo')

    def run(self):
        client = self.create_client(ServoCommandType, '/servo_node/switch_command_type')
        self.get_logger().info('Waiting for /servo_node/switch_command_type …')

        if not client.wait_for_service(timeout_sec=120.0):
            self.get_logger().error('switch_command_type service never appeared — servo may have crashed')
            return

        req = ServoCommandType.Request()
        req.command_type = TWIST
        future = client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)

        if future.result() and future.result().success:
            self.get_logger().info('Servo TWIST mode activated — hold button 9 (L1) and move sticks to drive.')
        else:
            self.get_logger().error('switch_command_type call failed')


def main():
    rclpy.init()
    node = ActivateServo()
    node.run()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
