#!/usr/bin/env python3
"""Joint-space MovJ to the safe home pose, with live diagnostics.

Joint moves bypass IK, so this works from any pose including singularities.
Prints RobotMode / ErrorID / joint angles during the move so a failed or
aborted motion says WHY instead of silently stopping.

Run with real_hw.launch.py STOPPED (needs the 29999 dashboard socket):

    python3 src/dobot_e6_hw/scripts/go_home.py [robot_ip]
    python3 src/dobot_e6_hw/scripts/go_home.py --speed 5    # slower still

Speed is deliberately low by default: this is the move you run when you do not
know where the arm is, so it should be slow enough to hit the E-Stop during.
Effective rate = --global x --speed (both percentages of the controller's
configured joint speed), so the defaults below are ~5% of full speed.
"""

import argparse
import math
import re
import sys
import time

from dobot_api import DobotApiDashboard
from home_pose import (HOME_ACCEL_RATIO, HOME_GLOBAL_SPEED, HOME_RAD,
                       HOME_SPEED_RATIO, HOME_TIMEOUT_SEC, home_deg)

MODE = {1: 'INIT', 2: 'BRAKE_OPEN', 3: 'POWEROFF', 4: 'DISABLED', 5: 'IDLE',
        6: 'DRAG', 7: 'RUNNING', 8: 'SINGLE_MOVE', 9: 'ERROR', 10: 'PAUSE', 11: 'JOG'}
SPEED_RATIO  = HOME_SPEED_RATIO
ACCEL_RATIO  = HOME_ACCEL_RATIO
GLOBAL_SPEED = HOME_GLOBAL_SPEED
TIMEOUT_SEC  = HOME_TIMEOUT_SEC


def braces(reply):
    """'0,{a,b,c},Cmd();' → 'a,b,c' (or None on malformed reply)."""
    m = re.search(r'\{(.*)\}', reply)
    return m.group(1) if m else None


def mode_of(dash):
    b = braces(dash.RobotMode())
    if b is None:
        sys.exit('Robot not answering in TCP mode — RequestControl() did not take. '
                 'Check the arm is powered (steady blue) and pingable.')
    return int(b)


def angles_of(dash):
    return [round(float(v), 1) for v in braces(dash.GetAngle()).split(',')]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('robot_ip', nargs='?', default='192.168.5.1')
    ap.add_argument('--speed', type=int, default=SPEED_RATIO,
                    help=f'MovJ speed ratio 1-100 (default {SPEED_RATIO})')
    ap.add_argument('--accel', type=int, default=ACCEL_RATIO,
                    help=f'MovJ acceleration ratio 1-100 (default {ACCEL_RATIO})')
    ap.add_argument('--global-speed', type=int, default=GLOBAL_SPEED,
                    dest='global_speed',
                    help=f'SpeedFactor global ratio 1-100 (default {GLOBAL_SPEED})')
    args = ap.parse_args()
    for name in ('speed', 'accel', 'global_speed'):
        v = getattr(args, name)
        if not 1 <= v <= 100:
            ap.error(f'--{name.replace("_", "-")} must be in 1..100, got {v}')

    ip = args.robot_ip
    dash = DobotApiDashboard(ip, 29999)
    dash.socket_dobot.settimeout(7.0)

    # A freshly powered controller rejects every command with 'Control Mode Is
    # Not Tcp' until a client claims control. This is the Linux-native
    # equivalent of flipping the mode in DobotStudio Pro, and it has to be
    # re-sent after each power cycle.
    print('RequestControl →', dash.RequestControl().strip())

    print('mode:', MODE.get(mode_of(dash)), ' errors:', braces(dash.GetErrorID()))
    print('ClearError →', dash.ClearError().strip())
    res = dash.EnableRobot()   # load=0 kg — no payload check to fail
    print('EnableRobot →', res.strip())
    if not res.strip().startswith('0'):
        sys.exit('Enable refused — check the E-Stop is released and that '
                 'RequestControl() succeeded above')

    for _ in range(10):        # wait for IDLE; flush a leftover PAUSEd queue
        m = mode_of(dash)
        if m == 5:
            break
        if m == 10:            # PAUSE blocks all motion commands (MovJ → -1)
            print('Stop (flush paused queue) →', dash.Stop().strip())
        time.sleep(0.5)
    print('mode:', MODE.get(mode_of(dash)))

    print(f'SpeedFactor({args.global_speed}) →',
          dash.SpeedFactor(args.global_speed).strip())

    target = home_deg()
    print('controller angles now:', angles_of(dash), ' target:', target)
    print(f'moving at v={args.speed} a={args.accel} '
          f'x global {args.global_speed}% '
          f'(~{args.speed * args.global_speed / 100.0:.1f}% of full speed)')
    # The arm is enabled and brakes are off by this point, so the motion can
    # begin the instant MovJ lands. Count down first: an unannounced move is
    # alarming when you are standing next to the arm.
    for n in range(3, 0, -1):
        print(f'  moving in {n}…', flush=True)
        time.sleep(1.0)
    res = dash.MovJ(*target, 1, a=args.accel, v=args.speed).strip()
    print('MovJ →', res)
    if not res.startswith('0'):
        sys.exit('MovJ rejected — mode above must be IDLE. If it is stuck in PAUSE '
                 'or DISABLED, power-cycle the arm and rerun.')

    t0 = time.monotonic()
    seen_running = False
    while time.monotonic() - t0 < TIMEOUT_SEC:
        m = mode_of(dash)
        print(f'  t={time.monotonic()-t0:4.1f}s mode={MODE.get(m, m)} angles={angles_of(dash)}')
        if m == 9:
            sys.exit(f'ROBOT ERROR during move — GetErrorID: {braces(dash.GetErrorID())}\n'
                     'Look the codes up in the E6 alarm list. A collision alarm here '
                     'means collision detection is false-triggering (payload config); '
                     'try SetCollisionLevel(0) or fix payload in DobotStudio.')
        seen_running = seen_running or m == 7
        if seen_running and m == 5:
            break
        time.sleep(0.5)
    else:
        sys.exit('Timed out — move never finished (mode above shows where it hung)')

    final = angles_of(dash)
    err = max(abs(a - b) for a, b in zip(final, target))
    print(f'Done. final={final} target={target} max_err={err:.1f} deg')
    if err > 2.0:
        print('WARNING: arm did NOT reach the target — motion was cut short.')
    else:
        print('Arm at home pose. Restart real_hw.launch.py.')


if __name__ == '__main__':
    main()
