#!/usr/bin/env python3
"""Clear a collision alarm (yellow light) without moving the arm.

    python3 src/dobot_e6_hw/scripts/clear_alarm.py [robot_ip]

Run with the teleop program STOPPED: it needs the robot's command port, which
the running program holds.

Sends RequestControl, ClearError and Stop. Stop discards the paused motion, so
the interrupted move cannot resume. Continue() is deliberately never sent. The
arm is left disabled where it is; go_home.py or the launch re-enables it.

Prints the robot's status before and after so you can see what was wrong.
"""

import sys
import time

from dobot_api import DobotApiDashboard, DobotApiFeedBack

FIELDS = ('RobotMode', 'CollisionState', 'PauseCmdFlag', 'EnableStatus', 'ErrorStatus')


def status(ip):
    d = DobotApiFeedBack(ip, 30004).feedBackData()
    return {k: int(d[k][0]) for k in FIELDS}


def main():
    ip = sys.argv[1] if len(sys.argv) > 1 else '192.168.5.1'
    print('before:', status(ip))

    dash = DobotApiDashboard(ip, 29999)
    dash.socket_dobot.settimeout(7.0)
    for name in ('RequestControl', 'GetErrorID', 'ClearError', 'Stop'):
        print(f'{name:15s}->', getattr(dash, name)().strip())

    time.sleep(1.0)
    after = status(ip)
    print('after: ', after)
    if after['CollisionState'] or after['ErrorStatus'] or after['PauseCmdFlag']:
        sys.exit('Alarm not cleared. Check the emergency stop is released and '
                 'nothing is pressing on the arm, then run this again.')
    print('Cleared. Light should be steady blue. Start again from step 4.')


if __name__ == '__main__':
    main()
