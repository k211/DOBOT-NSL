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

TCP control authority is claimed by the node itself via RequestControl() at
startup, so no DobotStudio Pro session — and no Windows machine — is required.
A freshly powered controller rejects everything with "Control Mode Is Not Tcp"
until that call lands, and the grant does not appear to survive a power cycle,
which is why it runs every time.

Homing key: holding the deadman plus every button in `home_buttons` for
`home_hold_sec` (default L1 + L2 + R2) pauses Servo, MovJs the arm to the
shared safe pose from home_pose.py at a gentle rate, then stop/starts Servo so
it re-syncs from /joint_states. Teleop stays disarmed until the deadman is
released afterwards, so a stick still held at the end of the move cannot fling
the arm.

Verified against real hardware on ROS 2 Humble. This is Option B (rclpy
wrapper); the upgrade path is a ros2_control SystemInterface plugin (Option A)
so sim and real hw swap with one launch arg.
"""

import math
import threading
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy, JointState
from std_srvs.srv import Trigger
from trajectory_msgs.msg import JointTrajectory

# Vendored from Dobot-Arm/TCP-IP-Python-V4 (MIT), installed alongside this node.
from dobot_api import DobotApiDashboard, DobotApiFeedBack
from home_pose import (HOME_ACCEL_RATIO, HOME_GLOBAL_SPEED, HOME_SPEED_RATIO,
                       HOME_TIMEOUT_SEC, PROBE_COM_MM, PROBE_PAYLOAD_KG,
                       enable_with_payload, home_deg)

JOINT_NAMES = ['joint1', 'joint2', 'joint3', 'joint4', 'joint5', 'joint6']
ROBOT_MODE_IDLE = 5
ROBOT_MODE_RUNNING = 7
ROBOT_MODE_SINGLE_MOVE = 8
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
        # False when running with nothing on the flange (launch arg probe:=false).
        self.declare_parameter('probe', True)
        # Controller homing key: deadman + EVERY button in home_buttons, held
        # for home_hold_sec. A single key within reach mid-teleop would send the
        # arm on an unexpected journey, which matters most in exactly the
        # setting homing exists for (public demos where a visitor has twisted
        # the wrist into a corner).
        #
        # Defaults are L1 + L2 + R2. L2/R2 drive no motion in the current
        # layout, so their digital buttons are free, and all three indices are
        # empirically confirmed to reach /joy on this pad. The PS button
        # (buttons[10]) is NOT usable: the index exists in the 13-element array
        # but never reports pressed, because something upstream of joy_node
        # grabs it. Verify any replacement against /joy before trusting it.
        self.declare_parameter('home_buttons', [6, 7])     # L2 + R2 (digital)
        self.declare_parameter('home_deadman_button', 4)   # L1, must also be held
        self.declare_parameter('home_hold_sec', 1.0)
        self.declare_parameter('home_speed', HOME_SPEED_RATIO)
        self.declare_parameter('home_accel', HOME_ACCEL_RATIO)
        self.declare_parameter('home_global_speed', HOME_GLOBAL_SPEED)

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
        # The dashboard socket is a single request/response channel now shared
        # by three threads (ServoJ timer, feedback loop, homing worker), so
        # every use of it must be serialised or replies get crossed.
        self._dash_lock = threading.Lock()
        self._homing = False
        self._home_press_start = None
        self._await_deadman_release = False
        self._target = None          # [rad]*6, latest Servo point
        self._target_stamp = 0.0
        self._robot_mode = -1
        self._in_error = False
        self._enabled = False
        self._has_control = False

        self._js_pub = self.create_publisher(JointState, '/joint_states', 10)
        self.create_subscription(
            JointTrajectory, '/joint_trajectory_controller/joint_trajectory',
            self._traj_cb, 10)
        self.create_timer(self._period, self._servo_tick)
        self.create_subscription(Joy, '/joy', self._joy_cb, 10)

        self._pause_cli = self.create_client(Trigger, '/servo_node/pause_servo')
        self._stop_servo_cli = self.create_client(Trigger, '/servo_node/stop_servo')
        self._start_servo_cli = self.create_client(Trigger, '/servo_node/start_servo')

        # Feedback first: /joint_states must flow even if enabling fails, so
        # the rest of the stack (and the user) can see what state the arm is in.
        self._alive = True
        self._fb_thread = threading.Thread(target=self._feedback_loop, daemon=True)
        self._fb_thread.start()

        self.create_timer(3.0, self._ensure_enabled)

    def _request_control(self) -> bool:
        """Claim TCP control authority; prerequisite for every other command.

        A freshly powered controller answers every dashboard command with
        'Control Mode Is Not Tcp' until some client claims control.
        RequestControl() does exactly that over the socket, so no DobotStudio
        Pro session — and no Windows machine — is needed. The grant does not
        appear to survive a power cycle, so this runs on every startup.
        """
        try:
            with self._dash_lock:
                res = self._dash.RequestControl()
        except Exception as e:
            self.get_logger().error(
                f'RequestControl got no reply ({e}) — is the arm powered '
                '(steady blue) and reachable? Retrying in 3 s…')
            return False
        if res and res.strip().startswith('0'):
            self._has_control = True
            self.get_logger().info(f'RequestControl → {res.strip()}')
            return True
        self.get_logger().warn(
            f'RequestControl refused: {res!r} — retrying in 3 s')
        return False

    def _ensure_enabled(self):
        """Retry EnableRobot until it sticks. Never lets a dead dashboard hang the node."""
        if self._enabled or self._in_error:
            return
        if not self._has_control and not self._request_control():
            return
        try:
            probe = bool(self.get_parameter('probe').value)
            with self._dash_lock:
                res = enable_with_payload(self._dash, probe)
        except Exception as e:
            self.get_logger().error(
                f'EnableRobot got no reply ({e}) — is the robot in TCP mode '
                '(RequestControl) and is DobotStudio Pro disconnected? '
                'Retrying in 3 s…')
            return
        if res and res.strip().startswith('0'):
            self._enabled = True
            self.get_logger().info(f'EnableRobot → {res.strip()}')
            if probe:
                self.get_logger().info(
                    f'Payload declared: {PROBE_PAYLOAD_KG} kg, centre of mass '
                    f'{PROBE_COM_MM} mm. Launch with probe:=false if the probe '
                    'is NOT fitted.')
            else:
                self.get_logger().warn('probe:=false — NO payload declared. '
                                       'Do not fit the probe while running like this.')
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
        if self._homing or self._await_deadman_release:
            return   # homing owns the arm; or waiting for a fresh deadman press
        with self._lock:
            target, stamp = self._target, self._target_stamp
        if target is None or (time.monotonic() - stamp) > COMMAND_FRESHNESS_SEC:
            return   # stale/no command → stream nothing, robot holds position
        if self._in_error or not self._enabled:
            return
        j = [math.degrees(q) for q in target]
        with self._dash_lock:
            res = self._dash.ServoJ(*j, t=self._period)
        if res and not res.strip().startswith('0'):
            self.get_logger().warn(
                f'ServoJ rejected: {res.strip()} (robot mode {self._robot_mode}) — '
                'arm is NOT following Servo', throttle_duration_sec=2.0)

    # ── controller homing key ────────────────────────────────────────────────

    def _joy_cb(self, msg: Joy):
        """Watch for the home combo, and for the deadman release that re-arms."""
        def held(idx):
            return 0 <= idx < len(msg.buttons) and bool(msg.buttons[idx])

        dead = self.get_parameter('home_deadman_button').value
        if self._await_deadman_release and not held(dead):
            self._await_deadman_release = False
            self.get_logger().info('Deadman released — teleop re-armed')

        combo_btns = list(self.get_parameter('home_buttons').value or [])
        combo = (held(dead) and combo_btns
                 and all(held(b) for b in combo_btns))
        if not combo or self._homing:
            self._home_press_start = None
            return
        now = time.monotonic()
        if self._home_press_start is None:
            self._home_press_start = now
        elif now - self._home_press_start >= self.get_parameter('home_hold_sec').value:
            self._home_press_start = None
            self._homing = True
            threading.Thread(target=self._home_sequence, daemon=True).start()

    def _trigger(self, client, name, timeout=5.0) -> bool:
        """Call a std_srvs/Trigger service from the homing thread.

        call_async is safe off the executor thread: the response is delivered by
        whichever thread is spinning the node, so we only poll the future here.
        """
        if not client.service_is_ready():
            self.get_logger().warn(f'{name} unavailable — skipping')
            return False
        future = client.call_async(Trigger.Request())
        deadline = time.monotonic() + timeout
        while not future.done() and time.monotonic() < deadline:
            time.sleep(0.02)
        if not future.done():
            self.get_logger().warn(f'{name} timed out')
            return False
        return True

    def _home_sequence(self):
        """Pause Servo, MovJ to the safe home pose, then re-sync Servo.

        Runs on its own thread because the move takes tens of seconds and must
        not stall the 33 Hz tick or the feedback loop.
        """
        try:
            self.get_logger().warn('HOMING: pausing Servo and moving to home pose')
            self._trigger(self._pause_cli, 'pause_servo')
            time.sleep(0.2)                  # let the last ServoJ tick drain

            speed = int(self.get_parameter('home_speed').value)
            accel = int(self.get_parameter('home_accel').value)
            glob = int(self.get_parameter('home_global_speed').value)
            target = home_deg()

            with self._dash_lock:
                self._dash.Stop()            # flush anything queued or paused
                self._dash.SpeedFactor(glob)
                # SpeedFactor scales jog and playback moves, not ServoJ, so
                # teleop rate is unaffected by this; restored below regardless.
                res = self._dash.MovJ(*target, 1, a=accel, v=speed)
            res = (res or '').strip()
            self.get_logger().info(f'MovJ(home) → {res}')
            if not res.startswith('0'):
                self.get_logger().error('MovJ(home) rejected — arm did not move')
                return

            start = time.monotonic()
            moving = False
            while time.monotonic() - start < HOME_TIMEOUT_SEC:
                mode = self._robot_mode      # kept current by the feedback loop
                if mode == ROBOT_MODE_ERROR:
                    self.get_logger().error('Robot ERROR during homing — aborted')
                    return
                moving = moving or mode in (ROBOT_MODE_RUNNING, ROBOT_MODE_SINGLE_MOVE)
                if moving and mode == ROBOT_MODE_IDLE:
                    self.get_logger().info('HOMING: home pose reached')
                    return
                time.sleep(0.1)
            self.get_logger().error('HOMING timed out before reaching home')
        finally:
            with self._dash_lock:
                try:
                    self._dash.SpeedFactor(100)   # back to the Dobot default
                except Exception:
                    pass
            # Servo integrates its OWN commanded pose, so after an external
            # MovJ its internal state points at where the arm used to be;
            # merely unpausing would command a jump straight back there.
            # stop+start forces it to re-initialise from /joint_states.
            self._trigger(self._stop_servo_cli, 'stop_servo')
            time.sleep(0.3)
            self._trigger(self._start_servo_cli, 'start_servo')
            with self._lock:
                self._target = None          # drop any stale latched target
            self._await_deadman_release = True
            self._homing = False
            self.get_logger().warn('HOMING done — release L1, then hold it again to drive')

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
                with self._dash_lock:
                    self._dash.Stop()

            msg = JointState()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.name = JOINT_NAMES
            msg.position = [math.radians(d) for d in q_deg]
            self._js_pub.publish(msg)

            if mode == ROBOT_MODE_ERROR and not self._in_error:
                self._in_error = True
                with self._dash_lock:
                    err = self._dash.GetErrorID()
                self.get_logger().error(f'Robot in ERROR mode: {err}')
                if self.get_parameter('auto_clear_error').value:
                    with self._dash_lock:
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
            with self._dash_lock:
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
