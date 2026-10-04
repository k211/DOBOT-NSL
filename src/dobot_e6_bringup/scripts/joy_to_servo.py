#!/usr/bin/env python3
"""
Converts /joy (DualSense PS5) to TwistStamped for MoveIt Servo.

Control layout. The operator stands IN FRONT of the arm facing it, and every
translation is expressed from the operator's point of view:

  L1              deadman — nothing moves unless it is held
  R1              turbo (scale_turbo)
  D-pad < / >     translate to the operator's left / right
  D-pad ^ / v     translate away from / toward the operator
  Left stick ^v   translate up / down          (proportional)
  Right stick ^v  yaw                          (proportional, own scale)
  [] / O          pitch
  /\ / X          roll
  L2 / R2         unused

Geometry: base_link has the arm extending toward +Y — confirmed by Pinocchio FK
at the home pose, which puts the tool at x=-0.095 y=+0.239. The operator
therefore stands at +Y looking down -Y, which makes

    operator forward = -Y          operator left = +X

so the robot's right is the operator's left. The dpad_*_to_* parameters carry
those signs; flip one if the operator moves to a different side of the arm.

Axis/button indices MEASURED on this pad (Sony Interactive Entertainment
Wireless Controller, hid-playstation driver) as reported by ROS joy_node:

  axes[0] L-stick X              buttons[0]  X  (SOUTH)
  axes[1] L-stick Y   UP   = +1  buttons[1]  O  (EAST)
  axes[2] L2 analog              buttons[2]  /\ (NORTH)
  axes[3] R-stick X              buttons[3]  [] (WEST)
  axes[4] R-stick Y              buttons[4]  L1
  axes[5] R2 analog              buttons[5]  R1
  axes[6] D-pad X     LEFT = +1  buttons[6,7]   L2/R2 digital
  axes[7] D-pad Y     UP   = +1  buttons[8..12] create, options, PS, L3, R3

joy_node reports D-pad LEFT as +1, which is INVERTED relative to the raw kernel
convention (ABS_HAT0X right = +1). Measure, do not assume.

NOTE on the triggers, which this layout no longer uses. Under hid-playstation
ABS_Z/ABS_RZ are raw 0..255 resting at 0, which the joystick API scales to -1.0
at rest and +1.0 fully pressed — the OPPOSITE of the hid-sony/DS4 convention
(+1.0 at rest). An earlier revision read them with max(0, -raw) and therefore
commanded FULL velocity on an untouched trigger. If motion is ever put back on
L2/R2: map rest to zero explicitly, and ignore a trigger until it has been
observed at rest at least once, so a trigger already squeezed at startup cannot
produce motion.

Parameters (loaded from joy_params.yaml under joy_to_servo_node):
  axis_dpad_lr, axis_dpad_ud, dpad_lr_to_x, dpad_ud_to_y
  axis_linear_z, linear_z_sign
  axis_angular_yaw, angular_yaw_sign
  button_roll_plus, button_roll_minus, button_pitch_plus, button_pitch_minus
  enable_button, enable_turbo_button
  scale_linear, scale_angular, scale_angular_yaw, scale_turbo, frame_id
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from geometry_msgs.msg import TwistStamped


def _enabled(buttons, en_btn: int) -> bool:
    """L1 deadman gate: True only when the enable button exists and is held.
    Missing/out-of-range button -> not enabled (fail safe = no motion)."""
    return 0 <= en_btn < len(buttons) and bool(buttons[en_btn])


def _button_pair(buttons, plus_btn: int, minus_btn: int) -> float:
    """Two opposed buttons -> +1.0 / -1.0 / 0.0.

    Returns 0.0 when neither is held AND when both are (they cancel), so a
    fumbled two-button press stands still rather than picking a direction.
    Out-of-range indices count as not held, keeping the failure mode at zero.
    """
    plus = 0 <= plus_btn < len(buttons) and bool(buttons[plus_btn])
    minus = 0 <= minus_btn < len(buttons) and bool(buttons[minus_btn])
    return float(plus) - float(minus)


class JoyToServo(Node):
    def __init__(self):
        super().__init__('joy_to_servo_node')  # must match key in joy_params.yaml

        # linear — D-pad for X/Y (operator-relative), left stick for Z
        self.declare_parameter('axis_dpad_lr', 6)
        self.declare_parameter('axis_dpad_ud', 7)
        self.declare_parameter('dpad_lr_to_x', 1.0)
        self.declare_parameter('dpad_ud_to_y', -1.0)
        self.declare_parameter('axis_linear_z', 1)
        self.declare_parameter('linear_z_sign', 1.0)

        # angular — right stick for yaw, shape buttons for roll and pitch.
        # Yaw carries its own scale because it is the one rotation the operator
        # drives continuously while re-aiming the tool, so it wants more rate
        # than roll/pitch trims do.
        self.declare_parameter('axis_angular_yaw', 4)
        self.declare_parameter('angular_yaw_sign', 1.0)
        self.declare_parameter('button_roll_plus', 2)    # triangle
        self.declare_parameter('button_roll_minus', 0)   # cross
        self.declare_parameter('button_pitch_plus', 3)   # square
        self.declare_parameter('button_pitch_minus', 1)  # circle

        self.declare_parameter('enable_button', 4)       # L1
        self.declare_parameter('enable_turbo_button', 5)  # R1
        self.declare_parameter('scale_linear', 0.03)
        self.declare_parameter('scale_angular', 0.2)
        self.declare_parameter('scale_angular_yaw', 0.3)
        self.declare_parameter('scale_turbo', 1.8)
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
        s_lin  = gp('scale_linear')      * factor
        s_ang  = gp('scale_angular')     * factor
        s_yaw  = gp('scale_angular_yaw') * factor

        def ax(i: int) -> float:
            return float(msg.axes[i]) if 0 <= i < len(msg.axes) else 0.0

        t = TwistStamped()
        t.header.stamp    = self.get_clock().now().to_msg()
        t.header.frame_id = gp('frame_id')
        # D-pad LEFT reads +1 and operator-left is +X, so dpad_lr_to_x = +1.
        # D-pad UP reads +1 and operator-forward is -Y, so dpad_ud_to_y = -1.
        t.twist.linear.x  = ax(gp('axis_dpad_lr')) * gp('dpad_lr_to_x') * s_lin
        t.twist.linear.y  = ax(gp('axis_dpad_ud')) * gp('dpad_ud_to_y') * s_lin
        t.twist.linear.z  = ax(gp('axis_linear_z')) * gp('linear_z_sign') * s_lin
        t.twist.angular.x = _button_pair(msg.buttons, gp('button_roll_plus'),
                                         gp('button_roll_minus')) * s_ang
        t.twist.angular.y = _button_pair(msg.buttons, gp('button_pitch_plus'),
                                         gp('button_pitch_minus')) * s_ang
        t.twist.angular.z = (ax(gp('axis_angular_yaw'))
                             * gp('angular_yaw_sign') * s_yaw)
        self._pub.publish(t)


def main():
    rclpy.init()
    node = JoyToServo()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


def _selftest():
    assert _enabled([0, 0, 1], 2) is True          # L1 held
    assert _enabled([0, 0, 0], 2) is False         # L1 released
    assert _enabled([1, 1], 9) is False            # index out of range -> no motion
    assert _enabled([], 0) is False                # no buttons yet -> no motion

    # buttons = [cross, circle, triangle, square]
    assert _button_pair([0, 0, 1, 0], 2, 0) == 1.0    # triangle -> +roll
    assert _button_pair([1, 0, 0, 0], 2, 0) == -1.0   # cross    -> -roll
    assert _button_pair([0, 0, 0, 0], 2, 0) == 0.0    # neither  -> still
    assert _button_pair([1, 0, 1, 0], 2, 0) == 0.0    # both     -> cancel, still
    assert _button_pair([0, 0, 0, 1], 3, 1) == 1.0    # square   -> +pitch
    assert _button_pair([0, 1, 0, 0], 3, 1) == -1.0   # circle   -> -pitch
    assert _button_pair([], 3, 1) == 0.0              # no buttons -> still
    assert _button_pair([0, 0], 9, 10) == 0.0         # out of range -> still
    print("ok")


if __name__ == '__main__':
    import sys
    if '--selftest' in sys.argv:
        _selftest()
    else:
        main()
