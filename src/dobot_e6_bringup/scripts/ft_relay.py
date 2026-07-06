#!/usr/bin/env python3
"""Wrap the bridged gz Wrench into a WrenchStamped on /ft_sensor/wrench.

The gz force_torque sensor publishes gz.msgs.Wrench, which ros_gz_bridge maps
to geometry_msgs/msg/Wrench (no header). The haptic node wants WrenchStamped,
so this just adds a stamp + frame_id. ~20 lines; no bridge mapping exists for
WrenchStamped, hence the relay.
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Wrench, WrenchStamped


class FtRelay(Node):
    def __init__(self):
        super().__init__('ft_relay')
        self.frame_id = self.declare_parameter('frame_id', 'us_probe_link').value
        self.pub = self.create_publisher(WrenchStamped, '/ft_sensor/wrench', 10)
        self.create_subscription(Wrench, '/ft_sensor', self.cb, 10)

    def cb(self, msg):
        out = WrenchStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = self.frame_id
        out.wrench = msg
        self.pub.publish(out)


def main():
    rclpy.init()
    rclpy.spin(FtRelay())
    rclpy.shutdown()


if __name__ == '__main__':
    main()
