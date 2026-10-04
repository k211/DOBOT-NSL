# 11. Reference

[← Running on Windows](10-windows.md) · [Contents](README.md)

---

## Robot specification

| | |
|---|---|
| Maximum load | **750 g** including all tooling |
| Maximum reach | 450 mm radius |
| Repeatability | ±0.1 mm |
| Maximum tool speed | 0.5 m/s (this setup uses 0.03 m/s) |
| Maximum joint speed | 120°/s |
| Mass | 7.2 kg |
| Power | 100–240 V AC, 50/60 Hz |
| Joint travel | J1 ±360°, J2 ±135°, J3 ±154°, J4 ±160°, J5 ±173°, J6 ±360° |

## Network

| | |
|---|---|
| Robot LAN1 | `192.168.5.1` |
| Laptop wired port | `enp59s0` at `192.168.5.10` |
| Network profile | `dobot-e6` — does **not** auto-connect; bring it up by hand |
| Dashboard port | 29999 (commands) |
| Feedback port | 30004 (joint states, 8 ms) |

## Home pose

Chosen so the flange sits **parallel to the bench** while keeping a wide
singularity margin (κ ≈ 15.9, versus the Servo stop threshold of 100):

```
J1    0.00°      J4   -8.02°
J2  -19.24°      J5  -90.00°
J3  117.25°      J6    0.00°
```

Defined once in `src/dobot_e6_hw/scripts/home_pose.py` and shared by `go_home.py`
and the controller homing key, so the two cannot disagree.

## Where things live

| | |
|---|---|
| Workspace | `/home/yz22/Documents/code/Dobot arm` |
| Joystick mapping | `src/dobot_e6_bringup/config/joy_params.yaml` |
| Home pose + motion profile | `src/dobot_e6_hw/scripts/home_pose.py` |
| Standalone homing | `src/dobot_e6_hw/scripts/go_home.py` |
| Robot interface | `src/dobot_e6_hw/scripts/dobot_tcp_node.py` |
| Teleop mapping logic | `src/dobot_e6_bringup/scripts/joy_to_servo.py` |
| Haptics | `src/dobot_e6_bringup/scripts/haptic_feedback.py` |
| Windows teleop | `windows/windows_teleop.py` |

## Tuning for the stand

All in `joy_params.yaml`. Edit, then restart the program — **no rebuild needed**,
the workspace is symlink-installed.

| Setting | Now | Effect |
|---|---|---|
| `scale_linear` | 0.03 | Translation speed, m/s |
| `scale_angular` | 0.2 | Roll and pitch rate, rad/s |
| `scale_angular_yaw` | 0.3 | Yaw rate, rad/s |
| `scale_turbo` | 1.5 | Turbo multiplier — **set to 1.0 to disable turbo for public use** |

## Servo thresholds

| Setting | Value | Meaning |
|---|---|---|
| `lower_singularity_threshold` | 60 | Start decelerating |
| `hard_stop_singularity_threshold` | 100 | Stop |
| `joint_limit_margin` | 0.1 rad | Stop 5.7° before a joint limit |
| `check_collisions` | false | **MoveIt collision checking is off** |
| Rumble threshold | ≈25 | Auto-calibrated at every launch |

## Rebuilding

Only needed if you add or rename a file, or change `CMakeLists.txt`:

```bash
cd "/home/yz22/Documents/code/Dobot arm"
source /opt/ros/humble/setup.bash
source .venv/bin/activate
colcon build --symlink-install
```

Editing Python or YAML needs **no** rebuild — just restart the program.

---

[← Running on Windows](10-windows.md) · [Contents](README.md)
