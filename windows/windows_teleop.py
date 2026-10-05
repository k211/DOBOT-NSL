#!/usr/bin/env python3
"""Minimal cross-platform teleoperation of the Dobot Magician E6.

No ROS, no MoveIt, no Gazebo, no Linux-only input APIs. A gamepad is read with
pygame and Cartesian servo targets are streamed straight to the robot, which
runs the inverse kinematics inside its own controller. Runs the same on
Windows, Linux and macOS.

WHY THIS EXISTS
---------------
The ROS stack in this repository converts a joystick twist into joint angles
using MoveIt Servo, and MoveIt is the one dependency with no supported Windows
build. The robot's own `ServoP` command takes a Cartesian pose directly, so the
IK moves into the controller and MoveIt disappears.

WHAT YOU GIVE UP versus the ROS stack
-------------------------------------
MoveIt Servo measured the Jacobian condition number and decelerated near
singularities (threshold 60) before hard-stopping (100). `ServoP` has no
equivalent: the controller will refuse poses it cannot reach, but how it
behaves *approaching* a singularity is untested on this arm. Keep the rates low,
and remember the homing combo escapes via joint space from any pose.

There is also no haptic feedback here. That was deliberate -- it needed
`evdev`, which is Linux-only.

SETUP
-----
    pip install pygame numpy requests

Keep these three files together in one folder:
    windows_teleop.py      this file
    dobot_api.py           from src/dobot_e6_hw/scripts/
    home_pose.py           from src/dobot_e6_hw/scripts/

USAGE
-----
    python windows_teleop.py --map      identify your pad; does NOT touch the robot
    python windows_teleop.py --probe    verify Cartesian axis signs; small slow moves
    python windows_teleop.py            drive

FIRST RUN ON A NEW MACHINE -- DO NOT SKIP
-----------------------------------------
Two things must be re-measured, and guessing either one has already caused a
runaway on this project once:

1. Button and axis indices. The defaults below were measured on Linux with the
   hid-playstation driver. Windows enumerates a DualSense through a different
   backend and the indices WILL differ. Run `--map`.

2. Cartesian axis signs. The Dobot's coordinate frame is NOT the ROS base_link
   frame -- at one recorded pose ROS read (-90, 232, 423) mm where the robot
   reported (-300, -91, 367) mm. Different origin and orientation. Run
   `--probe`, which nudges one axis at a time and prints what actually moved.
"""

import argparse
import math
import os
import re
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, '..', 'src', 'dobot_e6_hw', 'scripts')):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from dobot_api import DobotApiDashboard          # noqa: E402
from home_pose import (PROBE_TCP_MM, COLLISION_LEVEL, enable_with_payload,   # noqa: E402
                       home_deg, set_collision_level)

# ── configuration ───────────────────────────────────────────────────────────

ROBOT_IP = '192.168.5.1'
RATE_HZ = 33.0                  # Dobot advises >= 30 ms between ServoP commands

# Motion rates. ServoP speaks millimetres and degrees.
LIN_MM_S = 30.0                 # 0.03 m/s, matching the ROS stack
ROLL_PITCH_DEG_S = 12.0         # 0.2 rad/s
YAW_DEG_S = 17.0                # 0.3 rad/s
TURBO_FACTOR = 1.8

# Gamepad indices -- MEASURED ON LINUX. Re-measure with --map on Windows.
BTN_DEADMAN = 4                 # L1
BTN_TURBO = 5                   # R1
BTN_HOME_COMBO = (4, 6, 7)      # L1 + L2 + R2, all held
HOME_HOLD_SEC = 1.0
BTN_ROLL_PLUS, BTN_ROLL_MINUS = 2, 0        # triangle / cross
BTN_PITCH_PLUS, BTN_PITCH_MINUS = 3, 1      # square / circle
AX_DPAD_LR, AX_DPAD_UD = 6, 7
AX_LSTICK_UD = 1
AX_RSTICK_UD = 4
STICK_DEADZONE = 0.12

# Which Dobot Cartesian axis each control drives, and with what sign.
# UNVERIFIED on hardware -- run --probe before trusting these.
DPAD_LR = ('x', +1.0)           # D-pad left/right  -> operator left/right
DPAD_UD = ('y', -1.0)           # D-pad up/down     -> away/toward operator
LSTICK = ('z', +1.0)            # left stick up     -> up
YAW_SIGN = +1.0                 # right stick up    -> yaw one way

# Safety.
LEAD_LIMIT_MM = 25.0            # commanded pose may not run this far ahead of actual
LEAD_CHECK_HZ = 5.0
HOME_SPEED, HOME_ACCEL = 10, 3  # MovJ ratios for the homing move

AXIS_INDEX = {'x': 0, 'y': 1, 'z': 2, 'rx': 3, 'ry': 4, 'rz': 5}
MODE = {1: 'INIT', 2: 'BRAKE_OPEN', 3: 'POWEROFF', 4: 'DISABLED', 5: 'IDLE',
        6: 'DRAG', 7: 'RUNNING', 8: 'SINGLE_MOVE', 9: 'ERROR', 10: 'PAUSE', 11: 'JOG'}


# ── robot helpers ───────────────────────────────────────────────────────────

def braces(reply):
    """'0,{a,b,c},Cmd();' -> 'a,b,c', or None if the reply is malformed."""
    m = re.search(r'\{(.*)\}', reply or '')
    return m.group(1) if m else None


def get_pose(dash):
    """Current TCP pose as [x, y, z, rx, ry, rz] in mm and degrees."""
    body = braces(dash.GetPose())
    if body is None:
        raise RuntimeError('GetPose failed -- is the robot in TCP control mode?')
    return [float(v) for v in body.split(',')]


def get_mode(dash):
    body = braces(dash.RobotMode())
    return int(body) if body else -1


def connect(ip, probe=True):
    """Open the dashboard socket, claim control, clear alarms and enable."""
    print(f'connecting to {ip}:29999 ...')
    dash = DobotApiDashboard(ip, 29999)
    try:
        dash.socket_dobot.settimeout(7.0)
    except AttributeError:
        pass

    # A freshly powered controller rejects everything with "Control Mode Is Not
    # Tcp" until a client claims control. This is the Linux/Windows-native
    # equivalent of flipping the mode in DobotStudio Pro, and the grant does not
    # survive a power cycle, so it runs every time.
    print('RequestControl ->', (dash.RequestControl() or '').strip())
    print('ClearError     ->', (dash.ClearError() or '').strip())
    res = (enable_with_payload(dash, probe) or '').strip()
    print('payload        ->', 'probe declared' if probe else 'none (--no-probe)')

    # ServoP poses are those of the robot's global tool frame. Put tool 1 at the
    # probe so rotations pivot there rather than on the bare flange (tool 0).
    if probe:
        tcp = '{%g,%g,%g,0,0,0}' % PROBE_TCP_MM
        print('SetTool(1)     ->', (dash.SetTool(1, tcp) or '').strip(), tcp)
        print('Tool(1)        ->', (dash.Tool(1) or '').strip())
    else:
        print('Tool(0)        ->', (dash.Tool(0) or '').strip(), '(flange)')
    print('EnableRobot    ->', res)
    if not res.startswith('0'):
        sys.exit('Enable refused -- check the E-Stop is released and the arm is powered.')
    print(f'SetCollisionLevel({COLLISION_LEVEL}) ->', (set_collision_level(dash) or '').strip())

    for _ in range(20):
        m = get_mode(dash)
        if m == 5:                                 # IDLE
            break
        if m == 10:                                # PAUSE blocks all motion
            print('flushing paused queue ->', (dash.Stop() or '').strip())
        time.sleep(0.25)
    print('robot mode     ->', MODE.get(get_mode(dash), '?'))
    return dash


def go_home(dash):
    """Joint-space move to the safe pose. Works from anywhere, including a
    singularity, because joint moves bypass IK entirely."""
    print('\n*** HOMING ***')
    dash.Stop()
    target = home_deg()
    res = (dash.MovJ(*target, 1, a=HOME_ACCEL, v=HOME_SPEED) or '').strip()
    print('MovJ(home) ->', res)
    if not res.startswith('0'):
        print('homing rejected -- arm did not move')
        return
    start, moving = time.monotonic(), False
    while time.monotonic() - start < 180:
        m = get_mode(dash)
        if m == 9:
            print('robot ERROR during homing')
            return
        moving = moving or m in (7, 8)
        if moving and m == 5:
            print('home reached\n')
            return
        time.sleep(0.1)
    print('homing timed out\n')


# ── gamepad ─────────────────────────────────────────────────────────────────

def open_pad():
    import pygame
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        sys.exit('No gamepad found. Plug the controller in by USB and try again.')
    pad = pygame.joystick.Joystick(0)
    pad.init()
    print(f'gamepad: {pad.get_name()}  '
          f'({pad.get_numaxes()} axes, {pad.get_numbuttons()} buttons)')
    return pygame, pad


def dz(v):
    """Stick deadzone -- a worn stick that never quite centres must read zero."""
    return 0.0 if abs(v) < STICK_DEADZONE else v


def held(pad, idx):
    return 0 <= idx < pad.get_numbuttons() and bool(pad.get_button(idx))


def axis(pad, idx):
    return float(pad.get_axis(idx)) if 0 <= idx < pad.get_numaxes() else 0.0


# ── modes ───────────────────────────────────────────────────────────────────

def run_map():
    """Print live gamepad state. Never touches the robot."""
    pygame, pad = open_pad()
    print('\nPress buttons and move sticks. Ctrl+C to stop.')
    print('Note the indices, then edit the config block at the top of this file.\n')
    seen = {}
    try:
        while True:
            pygame.event.pump()
            pressed = [i for i in range(pad.get_numbuttons()) if pad.get_button(i)]
            moved = [f'axes[{i}]={pad.get_axis(i):+.2f}'
                     for i in range(pad.get_numaxes()) if abs(pad.get_axis(i)) > 0.6]
            for i in pressed:
                seen[i] = seen.get(i, 0) + 1
            line = ''
            if pressed:
                line += 'buttons ' + ','.join(str(i) for i in pressed) + '   '
            if moved:
                line += '  '.join(moved)
            if line:
                print('  ' + line, flush=True)
            time.sleep(0.12)
    except KeyboardInterrupt:
        print('\nbuttons seen:', sorted(seen) or 'none')


def run_probe(ip, probe=True):
    """Move a small distance along each Cartesian axis and report what changed.

    This is how you determine the sign constants without guessing. The ROS-frame
    signs do NOT carry over -- the Dobot uses its own coordinate frame.
    """
    dash = connect(ip, probe)
    try:
        step, period = 12.0, 0.03
        for ax in ('x', 'y', 'z'):
            start = get_pose(dash)
            print(f'\nnudging +{step:.0f} mm along Dobot {ax.upper()} ...')
            target = list(start)
            idx = AXIS_INDEX[ax]
            for i in range(40):                     # ~1.2 s of streaming
                target[idx] = start[idx] + step * (i + 1) / 40.0
                dash.ServoP(*target, t=period)
                time.sleep(period)
            time.sleep(0.6)
            end = get_pose(dash)
            d = [e - s for e, s in zip(end, start)]
            print(f'  moved dx={d[0]:+6.1f} dy={d[1]:+6.1f} dz={d[2]:+6.1f} mm')
            print('  -> watch the arm: which way did it go from where YOU stand?')
            input('  press Enter for the next axis ...')
    finally:
        shutdown(dash)


def run_teleop(ip, probe=True):
    pygame, pad = open_pad()
    dash = connect(ip, probe)
    period = 1.0 / RATE_HZ
    lead_every = max(1, int(RATE_HZ / LEAD_CHECK_HZ))

    target = get_pose(dash)
    print(f'\nstart pose: ' + ' '.join(f'{v:.1f}' for v in target))
    print(f'\nHold button {BTN_DEADMAN} (deadman) to drive.')
    print(f'Home: hold buttons {"+".join(str(b) for b in BTN_HOME_COMBO)} '
          f'for {HOME_HOLD_SEC:.0f} s.  Ctrl+C to quit.\n')

    combo_since = None
    tick = 0
    was_live = False
    try:
        while True:
            loop_start = time.monotonic()
            pygame.event.pump()
            tick += 1

            # homing combo, checked before anything else
            if all(held(pad, b) for b in BTN_HOME_COMBO):
                combo_since = combo_since or loop_start
                if loop_start - combo_since >= HOME_HOLD_SEC:
                    combo_since = None
                    go_home(dash)
                    target = get_pose(dash)
                    was_live = False
                    continue
            else:
                combo_since = None

            if not held(pad, BTN_DEADMAN):
                # Deadman released. Re-seed from the real pose so the commanded
                # target can never drift away from where the arm actually is.
                if was_live:
                    target = get_pose(dash)
                    was_live = False
                time.sleep(period)
                continue

            if not was_live:
                target = get_pose(dash)             # fresh grip, fresh seed
                was_live = True

            f = TURBO_FACTOR if held(pad, BTN_TURBO) else 1.0
            lin = LIN_MM_S * f * period
            rot = ROLL_PITCH_DEG_S * f * period
            yaw = YAW_DEG_S * f * period

            target[AXIS_INDEX[DPAD_LR[0]]] += dz(axis(pad, AX_DPAD_LR)) * DPAD_LR[1] * lin
            target[AXIS_INDEX[DPAD_UD[0]]] += dz(axis(pad, AX_DPAD_UD)) * DPAD_UD[1] * lin
            target[AXIS_INDEX[LSTICK[0]]] += dz(axis(pad, AX_LSTICK_UD)) * LSTICK[1] * lin
            target[5] += dz(axis(pad, AX_RSTICK_UD)) * YAW_SIGN * yaw
            target[3] += (held(pad, BTN_ROLL_PLUS) - held(pad, BTN_ROLL_MINUS)) * rot
            target[4] += (held(pad, BTN_PITCH_PLUS) - held(pad, BTN_PITCH_MINUS)) * rot

            # If the arm cannot keep up -- unreachable pose, singularity, a
            # rejected command -- the commanded target runs away from reality
            # and the next accepted command becomes a lunge. Catch it early.
            if tick % lead_every == 0:
                actual = get_pose(dash)
                lead = math.dist(target[:3], actual[:3])
                if lead > LEAD_LIMIT_MM:
                    print(f'\n!! commanded pose is {lead:.0f} mm ahead of the arm '
                          f'-- stopping and re-seeding.')
                    print('   The arm is not following. Release the deadman, '
                          'check for an alarm, and try a different direction.\n')
                    target = actual
                    was_live = False
                    continue

            res = dash.ServoP(*target, t=period)
            if res and not (res or '').strip().startswith('0'):
                print('ServoP rejected:', (res or '').strip())
                target = get_pose(dash)

            slack = period - (time.monotonic() - loop_start)
            if slack > 0:
                time.sleep(slack)
    except KeyboardInterrupt:
        print('\nstopping ...')
    finally:
        shutdown(dash)


def shutdown(dash):
    try:
        dash.Stop()
        dash.DisableRobot()
        print('robot disabled.')
    except Exception as e:
        print('shutdown warning:', e)


# ── entry point ─────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--ip', default=ROBOT_IP, help=f'robot address (default {ROBOT_IP})')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--map', action='store_true',
                   help='print live gamepad indices; does not touch the robot')
    g.add_argument('--probe', action='store_true',
                   help='nudge each Cartesian axis to determine the sign constants')
    ap.add_argument('--no-probe', action='store_true',
                    help='the probe is NOT fitted: enable without declaring its payload')
    args = ap.parse_args()

    if args.map:
        run_map()
    elif args.probe:
        run_probe(args.ip, not args.no_probe)
    else:
        run_teleop(args.ip, not args.no_probe)


if __name__ == '__main__':
    main()
