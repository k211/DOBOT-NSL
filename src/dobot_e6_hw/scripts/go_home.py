#!/usr/bin/env python3
"""Joint-space MovJ to the safe home pose, with live diagnostics.

Joint moves bypass IK, so this works from any pose including singularities.
Prints RobotMode / ErrorID / joint angles during the move so a failed or
aborted motion says WHY instead of silently stopping.

Run with real_hw.launch.py STOPPED (needs the 29999 dashboard socket):

    python3 src/dobot_e6_hw/scripts/go_home.py [robot_ip]
"""

import math
import re
import sys
import time

from dobot_api import DobotApiDashboard

# Max-margin pose from a Pinocchio kappa scan of the URDF: kappa≈16.5 vs 36
# for the old SRDF "home" (Servo singularity threshold is 60). Elbow bent,
# wrist bent, tool pointing down, arm toward +Y — same side as the old home.
HOME_RAD = [0.0, 0.0, 1.84, 0.0, -1.38, 0.0]

MODE = {1: 'INIT', 2: 'BRAKE_OPEN', 3: 'POWEROFF', 4: 'DISABLED', 5: 'IDLE',
        6: 'DRAG', 7: 'RUNNING', 8: 'SINGLE_MOVE', 9: 'ERROR', 10: 'PAUSE', 11: 'JOG'}
TIMEOUT_SEC = 90


def braces(reply):
    """'0,{a,b,c},Cmd();' → 'a,b,c' (or None on malformed reply)."""
    m = re.search(r'\{(.*)\}', reply)
    return m.group(1) if m else None


def mode_of(dash):
    return int(braces(dash.RobotMode()))


def angles_of(dash):
    return [round(float(v), 1) for v in braces(dash.GetAngle()).split(',')]


def main():
    ip = sys.argv[1] if len(sys.argv) > 1 else '192.168.5.1'
    dash = DobotApiDashboard(ip, 29999)
    dash.socket_dobot.settimeout(7.0)

    print('mode:', MODE.get(mode_of(dash)), ' errors:', braces(dash.GetErrorID()))
    print('ClearError →', dash.ClearError().strip())
    res = dash.EnableRobot()   # load=0 kg — no payload check to fail
    print('EnableRobot →', res.strip())
    if not res.strip().startswith('0'):
        sys.exit('Enable refused — check E-Stop / TCP mode in DobotStudio Pro')

    for _ in range(10):        # wait for IDLE; flush a leftover PAUSEd queue
        m = mode_of(dash)
        if m == 5:
            break
        if m == 10:            # PAUSE blocks all motion commands (MovJ → -1)
            print('Stop (flush paused queue) →', dash.Stop().strip())
        time.sleep(0.5)
    print('mode:', MODE.get(mode_of(dash)))

    target = [round(math.degrees(q), 1) for q in HOME_RAD]
    print('controller angles now:', angles_of(dash), ' target:', target)
    res = dash.MovJ(*target, 1, v=20).strip()
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
