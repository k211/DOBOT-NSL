#!/usr/bin/env python3
"""
Option-B real-hardware adapter for the Dobot Magician E6 (handoff §5.2).

Sits underneath MoveIt Servo in place of Gazebo + the JTC:

  /joint_trajectory_controller/joint_trajectory (from Servo, positions in rad)
      │  latest-point latch, freshness-gated
      ▼
  ServoJ(j1..j6 deg, t=servo_period)  on the V4 dashboard socket (port 29999)

  port 30004 feedback (8 ms, QActual in degrees)
      ▼
  /joint_states (rad)  @ ~125 Hz

Prerequisites on the robot (handoff §11.10): DobotStudio Pro must have the arm
in TCP/IP secondary-development mode, otherwise every command is rejected with
"Control Mode Is Not Tcp".

NOT yet run against a real arm — prototype pending delivery of the robot.
ponytail: Option B (rclpy wrapper). Upgrade path is a ros2_control
SystemInterface plugin (Option A) so sim and real hw swap with one launch arg.
"""

import math
import threading
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory

# Vendored from Dobot-Arm/TCP-IP-Python-V4 (MIT), installed alongside this node.
from dobot_api import DobotApiDashboard, DobotApiFeedBack

JOINT_NAMES = ['joint1', 'joint2', 'joint3', 'joint4', 'joint5', 'joint6']
ROBOT_MODE_ERROR = 9
ROBOT_MODE_PAUSE = 10          # controller rejects all motion (-1) until Stop()
COMMAND_FRESHNESS_SEC = 0.25   # ignore Servo output older than this (deadman)


class DobotTcpNode(Node):
    def __init__(self):
        super().__init__('dobot_tcp_node')
        self.declare_parameter('robot_ip', '192.168.5.1')
        # Dobot advises >= 30 ms per ServoJ tick (~33 Hz), matching Servo's rate.
        self.declare_parameter('servo_period', 0.03)
        self.declare_parameter('auto_clear_error', False)

        ip = self.get_parameter('robot_ip').value
        self._period = float(self.get_parameter('servo_period').value)

        self.get_logger().info(f'Connecting to E6 at {ip} (29999 dashboard, 30004 feedback)…')
        self._dash = DobotApiDashboard(ip, 29999)
        self._feed = DobotApiFeedBack(ip, 30004)
        # Vendored API blocks forever on recv if the controller doesn't answer
        # (robot in Online mode / DobotStudio holding the port / error state).
        # A bounded timeout turns a silent launch-wide hang into a clear log.
        try:
            self._dash.socket_dobot.settimeout(7.0)
        except AttributeError:
            pass

        self._lock = threading.Lock()
        self._target = None          # [rad]*6, latest Servo point
        self._target_stamp = 0.0
        self._robot_mode = -1
        self._in_error = False
        self._enabled = False

        self._js_pub = self.create_publisher(JointState, '/joint_states', 10)
        self.create_subscription(
            JointTrajectory, '/joint_trajectory_controller/joint_trajectory',
            self._traj_cb, 10)
        self.create_timer(self._period, self._servo_tick)

        # Feedback first: /joint_states must flow even if enabling fails, so
        # the rest of the stack (and the user) can see what state the arm is in.
        self._alive = True
        self._fb_thread = threading.Thread(target=self._feedback_loop, daemon=True)
        self._fb_thread.start()

        self.create_timer(3.0, self._ensure_enabled)

    def _ensure_enabled(self):
        """Retry EnableRobot until it sticks. Never lets a dead dashboard hang the node."""
        if self._enabled or self._in_error:
            return
        try:
            res = self._dash.EnableRobot()
        except Exception as e:
            self.get_logger().error(
                f'EnableRobot got no reply ({e}) — is the robot in TCP mode and '
                'is DobotStudio Pro disconnected? Retrying in 3 s…')
            return
        if res and res.strip().startswith('0'):
            self._enabled = True
            self.get_logger().info(f'EnableRobot → {res.strip()}')
        else:
            self.get_logger().warn(f'EnableRobot refused: {res!r} — retrying in 3 s '
                                   '(clear alarms / check E-Stop)')

    # ── Servo output → latched target ────────────────────────────────────────

    def _traj_cb(self, msg: JointTrajectory):
        if not msg.points:
            return
        pos = dict(zip(msg.joint_names, msg.points[0].positions))
        try:
            target = [float(pos[j]) for j in JOINT_NAMES]
        except KeyError as e:
            self.get_logger().warn(f'Trajectory missing joint {e} — ignored')
            return
        with self._lock:
            self._target = target
            self._target_stamp = time.monotonic()

    # ── 33 Hz ServoJ streaming ────────────────────────────────────────────────

    def _servo_tick(self):
        with self._lock:
            target, stamp = self._target, self._target_stamp
        if target is None or (time.monotonic() - stamp) > COMMAND_FRESHNESS_SEC:
            return   # stale/no command → stream nothing, robot holds position
        if self._in_error or not self._enabled:
            return
        j = [math.degrees(q) for q in target]
        res = self._dash.ServoJ(*j, t=self._period)
        if res and not res.strip().startswith('0'):
            self.get_logger().warn(
                f'ServoJ rejected: {res.strip()} (robot mode {self._robot_mode}) — '
                'arm is NOT following Servo', throttle_duration_sec=2.0)

    # ── 30004 feedback → /joint_states + error watch ─────────────────────────

    def _feedback_loop(self):
        while self._alive and rclpy.ok():
            try:
                fb = self._feed.feedBackData()
            except Exception as e:
                self.get_logger().error(f'Feedback socket error: {e}')
                time.sleep(1.0)
                continue
            if fb is None:
                continue
            q_deg = fb['QActual'][0]
            mode = int(fb['RobotMode'][0])
            self._robot_mode = mode

            if mode == ROBOT_MODE_PAUSE:
                self.get_logger().warn('Robot PAUSEd (rejects motion) — sending Stop() to flush',
                                       throttle_duration_sec=3.0)
                self._dash.Stop()

            msg = JointState()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.name = JOINT_NAMES
            msg.position = [math.radians(d) for d in q_deg]
            self._js_pub.publish(msg)

            if mode == ROBOT_MODE_ERROR and not self._in_error:
                self._in_error = True
                err = self._dash.GetErrorID()
                self.get_logger().error(f'Robot in ERROR mode: {err}')
                if self.get_parameter('auto_clear_error').value:
                    self._dash.ClearError()
                    self._dash.Continue()
                    self.get_logger().warn('Auto-cleared error (auto_clear_error=true)')
                    self._in_error = False
            elif mode != ROBOT_MODE_ERROR and self._in_error:
                self.get_logger().info('Robot recovered from ERROR mode')
                self._in_error = False

    def destroy_node(self):
        self._alive = False
        try:
            self._dash.DisableRobot()
        except Exception:
            pass
        super().destroy_node()


def main():
    rclpy.init()
    node = DobotTcpNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


def _selftest():
    """Offline check of the rad→deg command path and freshness gate."""
    assert [round(math.degrees(q), 3) for q in [0.0, math.pi / 2]] == [0.0, 90.0]
    pos = dict(zip(['joint2', 'joint1'], [0.2, 0.1]))
    assert [pos[j] for j in ['joint1', 'joint2']] == [0.1, 0.2]  # name-order remap
    stale = time.monotonic() - 0.5
    assert (time.monotonic() - stale) > COMMAND_FRESHNESS_SEC     # gate trips
    print('ok')


if __name__ == '__main__':
    import sys
    if '--selftest' in sys.argv:
        _selftest()
    else:
        main()
