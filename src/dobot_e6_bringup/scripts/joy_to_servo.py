#!/usr/bin/env python3
"""
Converts /joy (DualSense PS5) to TwistStamped for MoveIt Servo.

Sticks  → linear X/Y and angular yaw/pitch  (standard axes, range ±1)
R2 trigger → end-effector moves UP   (+Z)
L2 trigger → end-effector moves DOWN (-Z)

PS5 DualSense trigger convention (Linux joystick driver):
  rest (not pressed) = +1.0
  fully pressed      = -1.0
_normalize_trigger maps that range to [0.0 .. 1.0] so untouched triggers
produce zero velocity and the formula  z = R2_norm - L2_norm  gives a
clean [-1, +1] range with both triggers at rest → 0.

Parameters (loaded from joy_params.yaml under joy_to_servo_node):
  axis_linear_x, axis_linear_y
  axis_angular_yaw, axis_angular_pitch
  axis_l2, axis_r2
  enable_button, enable_turbo_button
  scale_linear, scale_angular, scale_turbo, frame_id
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from geometry_msgs.msg import TwistStamped


def _normalize_trigger(raw: float) -> float:
    """Map trigger axis to [0.0 .. 1.0] velocity magnitude.

    DualSense convention (Linux hid-playstation driver):
      +1.0  rest / not pressed
      -1.0  fully pressed
       0.0  uninitialized (before the first physical touch)

    max(0, -raw) maps all three correctly:
      +1.0 → 0.0  (rest → no velocity)
       0.0 → 0.0  (uninitialized → no velocity)
      -1.0 → 1.0  (fully pressed → full velocity)
    """
    return max(0.0, -raw)


def _enabled(buttons, en_btn: int) -> bool:
    """L1 deadman gate: True only when the enable button exists and is held.
    Missing/out-of-range button -> not enabled (fail safe = no motion)."""
    return 0 <= en_btn < len(buttons) and bool(buttons[en_btn])


class JoyToServo(Node):
    def __init__(self):
        super().__init__('joy_to_servo_node')  # must match key in joy_params.yaml

        self.declare_parameter('axis_linear_x', 1)
        self.declare_parameter('axis_linear_y', 0)
        self.declare_parameter('axis_angular_yaw', 2)
        self.declare_parameter('axis_angular_pitch', 3)
        self.declare_parameter('axis_l2', 4)
        self.declare_parameter('axis_r2', 5)
        self.declare_parameter('enable_button', 9)
        self.declare_parameter('enable_turbo_button', 10)
        self.declare_parameter('scale_linear', 0.1)
        self.declare_parameter('scale_angular', 0.3)
        self.declare_parameter('scale_turbo', 3.0)
        self.declare_parameter('frame_id', 'base_link')

        self._pub = self.create_publisher(
            TwistStamped, '/servo_node/delta_twist_cmds', 10)
        self._sub = self.create_subscription(Joy, '/joy', self._joy_cb, 10)

    def _zero_twist(self, frame_id: str) -> TwistStamped:
        t = TwistStamped()
        t.header.stamp    = self.get_clock().now().to_msg()
        t.header.frame_id = frame_id
        return t  # all twist fields default to 0.0

    def _joy_cb(self, msg: Joy):
        gp = lambda name: self.get_parameter(name).value  # noqa: E731

        en_btn    = gp('enable_button')
        turbo_btn = gp('enable_turbo_button')

        if not _enabled(msg.buttons, en_btn):
            # L1 released: actively command zero so Servo stops NOW. Just not
            # publishing lets Servo coast on its last twist until timeout — that
            # is the "stuck on last command / keeps drifting" bug.
            self._pub.publish(self._zero_twist(gp('frame_id')))
            return

        turbo  = turbo_btn < len(msg.buttons) and bool(msg.buttons[turbo_btn])
        factor = gp('scale_turbo') if turbo else 1.0
        s_lin  = gp('scale_linear')  * factor
        s_ang  = gp('scale_angular') * factor

        def ax(i: int) -> float:
            return float(msg.axes[i]) if i < len(msg.axes) else 0.0

        l2_vel = _normalize_trigger(ax(gp('axis_l2')))  # [0, 1] when pressed
        r2_vel = _normalize_trigger(ax(gp('axis_r2')))  # [0, 1] when pressed

        t = TwistStamped()
        t.header.stamp    = self.get_clock().now().to_msg()
        t.header.frame_id = gp('frame_id')
        t.twist.linear.x  = ax(gp('axis_linear_x'))       * s_lin
        t.twist.linear.y  = ax(gp('axis_linear_y'))        * s_lin
        t.twist.linear.z  = (r2_vel - l2_vel)              * s_lin  # R2=up, L2=down
        t.twist.angular.z = ax(gp('axis_angular_yaw'))     * s_ang
        t.twist.angular.y = ax(gp('axis_angular_pitch'))   * s_ang
        self._pub.publish(t)


def main():
    rclpy.init()
    node = JoyToServo()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


def _selftest():
    assert _enabled([0, 0, 1], 2) is True          # L1 held
    assert _enabled([0, 0, 0], 2) is False          # L1 released
    assert _enabled([1, 1], 9) is False             # index out of range -> no motion
    assert _enabled([], 0) is False                 # no buttons yet -> no motion
    print("ok")


if __name__ == '__main__':
    import sys
    if '--selftest' in sys.argv:
        _selftest()
    else:
        main()
