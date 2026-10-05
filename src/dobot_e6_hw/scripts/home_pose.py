"""Shared safe-home joint pose and homing motion profile for the Magician E6.

Imported by both go_home.py (standalone, launch stopped) and dobot_tcp_node.py
(controller homing key, launch running) so the two can never disagree about
where "home" is or how fast to get there.
"""

import math

# Level home: the flange (Link6) points straight DOWN, so the tool face sits
# parallel to the bench — kappa 15.92, tilt 0.01 deg, arm toward +Y.
#
# Found by a Pinocchio search over J2..J5 (J1 held at 0 so the arm keeps facing
# +Y) that required the flange Z axis within a few degrees of vertical and then
# minimised the Jacobian condition number. Servo decelerates at kappa 60, so
# 15.92 leaves a wide margin.
#
# This REPLACES the earlier [0, 0, 1.84, 0, -1.38, 0]. That pose was picked for
# singularity margin alone with no orientation constraint, and its code comment
# claiming "tool pointing down" was wrong: the flange sat 18.8 deg off vertical,
# clearly visible on the real arm. The pose below is better on both counts —
# level AND a slightly lower kappa (15.92 vs 16.54).
HOME_RAD = [0.0, -0.3358, 2.0464, -0.13998, -1.5708, 0.0]

# Deliberately gentle. Homing runs when the arm is somewhere unknown, possibly
# with an audience close by, so it must be slow enough to watch and to abort
# with the E-Stop. A LOW acceleration ratio is what makes the start and stop
# feel smooth rather than snatched: it lengthens the trapezoidal ramp at both
# ends of the move, so keep accel well below speed.
HOME_SPEED_RATIO  = 10    # MovJ v — per-instruction speed ratio, (0, 100]
HOME_ACCEL_RATIO  = 3     # MovJ a — per-instruction acceleration ratio
HOME_GLOBAL_SPEED = 40    # SpeedFactor — global ratio multiplied into the above
HOME_TIMEOUT_SEC  = 180   # a deliberately slow ~90 deg move takes a while


# Probe payload: probe + 3D-printed holder, as fitted for the NSL demonstration.
# Centre of mass is in the robot's default tool frame (the flange), in mm.
# Declared to the controller at every enable so its dynamic model -- and with it
# collision detection -- matches what is actually on the flange.
PROBE_PAYLOAD_KG = 0.355
PROBE_COM_MM = (0.0, 65.0, 50.0)

# Tool centre point for the WINDOWS teleop: the probe FACE, where rotations
# pivot. This is not the centre of mass above -- they are different points.
# The ROS stack sets the same point via the tcp_x/y/z launch args, measured as
# (0, 65, 98) mm in the URDF Link6 frame. SetTool() works in Dobot's own flange
# frame; that the two frames agree is assumed, not verified -- check with
# windows_teleop.py --probe before relying on it.
PROBE_TCP_MM = (0.0, 65.0, 98.0)

# isCheck=0: do not let the controller verify the load and auto-disable on a
# mismatch. That check is untested on this arm, and a false trip would block the
# demonstration; running without the probe is handled by an explicit switch
# instead (probe:=false / --no-probe).
PAYLOAD_CHECK = 0


def enable_with_payload(dash, probe=True):
    """EnableRobot with the probe payload declared, or with none if probe=False."""
    if probe:
        return dash.EnableRobot(PROBE_PAYLOAD_KG, *PROBE_COM_MM, isCheck=PAYLOAD_CHECK)
    return dash.EnableRobot()


def home_deg():
    """Home pose in degrees, as the Dobot TCP API expects it."""
    return [round(math.degrees(q), 3) for q in HOME_RAD]
