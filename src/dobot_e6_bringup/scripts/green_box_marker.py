#!/usr/bin/env python3
"""Publish the green box as an RViz Marker so it shows up in RViz too.

RViz can't see Gazebo models — it only renders ROS topics. This mirrors the
gz-spawned green_box as a CUBE marker in the base_link frame.

The box is spawned in the gz world at (-0.08, 0.34, 0.075); the ME6 URDF fixes
base_link at world z=0.03 (world_joint), so in base_link the box center is
z=0.075-0.03=0.045. Position sits under the probe tip at the SRDF home pose
(FK: tip at (-0.084, 0.343, 0.257) in base_link, pointing down).
ponytail: these numbers must match the spawn args in full_system.launch.py
(minus the 0.03 base lift). If you move the box, change both.
"""
import rclpy
from rclpy.node import Node
from visualization_msgs.msg import Marker


class GreenBoxMarker(Node):
    def __init__(self):
        super().__init__('green_box_marker')
        pub = self.create_publisher(Marker, 'green_box_marker', 1)
        m = Marker()
        m.header.frame_id = 'base_link'
        m.ns = 'green_box'
        m.id = 0
        m.type = Marker.CUBE
        m.action = Marker.ADD
        m.pose.position.x = -0.08
        m.pose.position.y = 0.34
        m.pose.position.z = 0.075 - 0.03
        m.pose.orientation.w = 1.0
        m.scale.x, m.scale.y, m.scale.z = 0.25, 0.25, 0.15
        m.color.r, m.color.g, m.color.b, m.color.a = 0.1, 0.8, 0.1, 1.0

        def tick():
            m.header.stamp = self.get_clock().now().to_msg()
            pub.publish(m)
        self.create_timer(1.0, tick)  # re-publish so late RViz still catches it


def main():
    rclpy.init()
    rclpy.spin(GreenBoxMarker())


if __name__ == '__main__':
    main()
