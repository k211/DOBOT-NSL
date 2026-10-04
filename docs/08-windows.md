# 8. Running on Windows

[← Limits, faults and recovery](07-troubleshooting.md) · [Contents](README.md) · [Next: Reference →](09-reference.md)

A second, ROS-free teleop lives in [`windows/`](../windows/) for machines that
cannot run the Linux stack.

---

## Why a separate program

The Linux stack converts the joystick's Cartesian twist into joint angles using
**MoveIt Servo**, and MoveIt has no supported Windows build. But the robot's own
**`ServoP`** command accepts a Cartesian pose directly and runs the inverse
kinematics *inside the controller* — so MoveIt is not needed at all.

| | Linux stack | `windows_teleop.py` |
|---|---|---|
| Inverse kinematics | MoveIt Servo, on the PC | the robot's controller |
| Singularity handling | slow at κ 60, stop at κ 100 | **none** — see below |
| Haptic rumble | yes | no (needs `evdev`, Linux-only) |
| Simulation | Gazebo | no |
| Install | ROS 2 Humble + MoveIt + colcon | `pip install pygame numpy requests` |

## What you give up

> ⚠️ **Singularity protection.** MoveIt Servo measured the condition number and
> slowed the arm before it got into trouble. `ServoP` has no equivalent. The
> controller refuses poses it cannot reach, but its behaviour *approaching* a
> singularity is **untested on this arm**.

Four mitigations are built in: low default rates; the commanded pose re-seeded
from the real pose on every deadman release; a 25 mm cap on how far the commanded
pose may lead the actual one before the script stops; and a homing combo that
escapes via joint space.

## Install

```
pip install pygame numpy requests
```

Copy three files into one folder:

```
windows_teleop.py        from windows/
dobot_api.py             from src/dobot_e6_hw/scripts/
home_pose.py             from src/dobot_e6_hw/scripts/
```

Set the wired adapter to a static `192.168.5.x` address, mask `255.255.255.0`,
**no gateway**, connected to the robot's **LAN1** port. Check with
`ping 192.168.5.1`.

## First run — do not skip

Two things must be **measured**, not assumed. Guessing either has already caused
a runaway on this project.

### 1. Gamepad indices

```
python windows_teleop.py --map
```

Does not touch the robot. Press each control, note the numbers, edit the config
block at the top of the file. Windows enumerates a DualSense through a different
backend, so the Linux indices **will** differ.

### 2. Cartesian axis signs

```
python windows_teleop.py --probe
```

Moves the arm 12 mm along each axis in turn, pausing between each. Watch which
way it actually goes from where you stand, then set the sign constants.

This is necessary because **the Dobot frame is not the ROS frame**. At one
recorded pose, ROS read the flange at `(−90, 232, 423)` mm while the robot
reported `(−300, −91, 367)` mm — different origin *and* orientation. The signs
worked out for the Linux stack do not carry over.

## Driving

```
python windows_teleop.py
```

Same layout as [§5](05-joystick.md): deadman held throughout, three-button combo
for homing, `Ctrl+C` to disable and exit.

> ⚠️ Everything in [§1 Safety](01-safety.md) and
> [§6 Contact force](06-scanning.md) applies unchanged. The arm is still position
> controlled and still does not yield.

---

---

---

[← Limits, faults and recovery](07-troubleshooting.md) · [Contents](README.md) · [Next: Reference →](09-reference.md)
