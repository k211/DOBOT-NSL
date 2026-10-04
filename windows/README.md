# Windows teleoperation

Minimal joystick control of the Dobot Magician E6 with **no ROS, no MoveIt and
no Gazebo**. One Python file, three pip packages. Runs identically on Windows,
Linux and macOS.

## How it differs from the ROS stack

The ROS stack converts the joystick's Cartesian twist into joint angles with
MoveIt Servo, and MoveIt has no supported Windows build. The robot's own
`ServoP` command accepts a Cartesian pose directly and runs the inverse
kinematics inside the controller, so MoveIt is not needed at all.

| | ROS stack (Linux) | `windows_teleop.py` |
|---|---|---|
| Inverse kinematics | MoveIt Servo, on the PC | the robot's controller |
| Singularity handling | decelerate at κ 60, stop at 100 | **none** — see below |
| Haptic rumble | yes (`evdev`, Linux only) | no |
| Simulation | Gazebo | no |
| Install | ROS 2 Humble + MoveIt + colcon | `pip install pygame numpy requests` |

### What you give up

**Singularity protection.** MoveIt Servo measured the Jacobian condition number
and slowed the arm down before it got into trouble. `ServoP` has no equivalent.
The controller refuses poses it cannot reach, but its behaviour *approaching* a
singularity is untested on this arm. Mitigations built in:

- Rates are low by default (30 mm/s, 12–17 °/s).
- The commanded pose is re-seeded from the real pose every time you release the
  deadman, so it can never drift away from the arm.
- If the commanded pose runs more than 25 mm ahead of the actual pose, the
  script stops and re-seeds rather than letting the gap become a lunge.
- The homing combo uses a joint-space move, which escapes any pose including a
  singularity.

## Install

```
pip install pygame numpy requests
```

Copy these three files into one folder:

```
windows_teleop.py          this folder
dobot_api.py               from src/dobot_e6_hw/scripts/
home_pose.py               from src/dobot_e6_hw/scripts/
```

Set the laptop's wired adapter to a static `192.168.5.x` address (for example
`192.168.5.10`, mask `255.255.255.0`, **no gateway**) and connect it to the
robot's **LAN1** port. Check with `ping 192.168.5.1`.

## First run on a new machine — do not skip

Two things must be measured rather than assumed. Guessing either one has
already produced a runaway on this project.

### 1. Gamepad indices

```
python windows_teleop.py --map
```

Does not touch the robot. Press each control and note the numbers, then edit the
config block at the top of `windows_teleop.py`. The defaults were measured on
Linux with the `hid-playstation` driver; Windows uses a different backend and
the indices **will** differ.

### 2. Cartesian axis signs

```
python windows_teleop.py --probe
```

Moves the arm 12 mm along each axis in turn, slowly, pausing between each. Watch
which way it actually goes from where you stand, then set `DPAD_LR`, `DPAD_UD`,
`LSTICK` and `YAW_SIGN`.

This step is necessary because **the Dobot's coordinate frame is not the ROS
frame**. At one recorded pose, ROS read the flange at `(-90, 232, 423)` mm while
the robot reported `(-300, -91, 367)` mm — different origin *and* orientation. The
signs worked out for the ROS stack do not carry over.

## Driving

```
python windows_teleop.py
```

Hold the deadman button the whole time; release it and the arm stops. Homing is
the three-button combo held for one second. `Ctrl+C` disables the arm and exits.

Default layout, matching the Linux stack:

| Control | Motion |
|---|---|
| L1 | deadman — hold or nothing moves |
| R1 | turbo ×1.5 |
| D-pad ◄ ► | translate operator left / right |
| D-pad ▲ ▼ | translate away from / toward operator |
| Left stick ↑↓ | up / down |
| Right stick ↑↓ | yaw |
| □ / ○ | pitch |
| △ / ✕ | roll |
| L1 + L2 + R2, 1 s | home |

## Safety

The arm is **position controlled** and does not yield. It will not stop when it
meets your hand, the bench, or the phantom — it keeps driving toward the
commanded pose. Keep the emergency stop within reach, and release the deadman
the instant the probe makes contact.
