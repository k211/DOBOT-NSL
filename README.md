# Haptic Teleoperation of a Dobot Magician E6 with Singularity Feedback

Final-year dissertation project: teleoperate a **Dobot Magician E6** 6-axis arm
with a **PS5 DualSense** controller and feed kinematic information back to the
operator as **gamepad rumble** — primarily proximity to a **kinematic
singularity** (Jacobian condition number), plus joint-limit proximity and
contact force. Ported from an earlier Kinova Gen3 implementation.

Runs identically against **Gazebo simulation** and the **real arm** — the same
MoveIt Servo + haptics stack sits on top of either backend.

## System requirements

- Ubuntu 24.04, **ROS 2 Jazzy**, Gazebo Harmonic (sim only), MoveIt 2 + MoveIt Servo
- Python: `pinocchio` (Jacobian/condition number), `numpy`
- PS5 DualSense controller (USB; rumble via the `joy` driver)
- Real arm: Dobot Magician E6 reachable at `192.168.5.1` (PC on `192.168.5.x`),
  controller switched to **TCP/IP secondary-development mode** once via
  DobotStudio Pro (Windows-only; a VirtualBox VM works)

## How the system works

```
DualSense ──joy──► joy_to_servo.py ──TwistStamped──► MoveIt Servo ──► joint commands
                                                                          │
              sim:  gz_ros2_control + joint_trajectory_controller (Gazebo) │
              real: dobot_tcp_node.py → ServoJ @ 33 Hz on TCP port 29999 ◄─┘
                                        feedback (port 30004, 8 ms) → /joint_states

/joint_states ──► haptic_feedback.py ── Pinocchio Jacobian → κ = σ_max/σ_min
                                        └─► DualSense rumble (κ, joint limits, |F|)
```

- **Teleop**: hold **L1** (deadman), sticks = X/Y + yaw/pitch, **R2/L2** = up/down.
  MoveIt Servo turns the twist into singularity-aware joint motion and
  decelerates/halts near singularities (thresholds 60/100, raised from the
  17/25 defaults because the E6 working poses sit around κ 16–36).
- **Haptics**: `haptic_feedback.py` rebuilds the Jacobian each `/joint_states`
  message, smooths κ with an EMA, auto-calibrates its rumble threshold during a
  25 s quiet window, and drives rumble intensity as
  max(singularity, joint-limit, contact-force) cues.
- **Real-hardware adapter** (`dobot_e6_hw`): a thin rclpy node that latches the
  latest Servo output (freshness-gated deadman, 0.25 s) and streams it as
  `ServoJ` on the E6's V4 dashboard port **29999**; joint feedback arrives on
  port **30004** and is republished as `/joint_states` at ~125 Hz. Rejected
  commands are logged, and a PAUSEd controller is flushed automatically.

## Layout

```
src/
├── dobot_e6_description/   # ME6 URDF/meshes/SRDF (vendored from DOBOT_6Axis_ROS2_V4)
├── dobot_e6_bringup/       # sim bringup: Gazebo launch, Servo config, haptics, teleop
│   ├── robots/probe_wrapper_e6.urdf.xacro   # probe + gz FT sensor + gz_ros2_control
│   ├── launch/full_system.launch.py
│   └── config/  models/  rviz/  scripts/
└── dobot_e6_hw/            # real-hardware TCP adapter
    ├── scripts/dobot_tcp_node.py   # Servo → ServoJ @33 Hz; 30004 → /joint_states
    ├── scripts/go_home.py          # joint-space escape to a singularity-free pose
    ├── scripts/dobot_api.py        # vendored Dobot TCP-IP-Python-V4 (MIT)
    └── launch/real_hw.launch.py
```

(`vendor/` — upstream clones of `DOBOT_6Axis_ROS2_V4` and `TCP-IP-Python-V4`,
reference only — is not tracked; re-clone from Dobot-Arm on GitHub if needed.)

## Run — simulation

```bash
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install && source install/setup.bash
ros2 launch dobot_e6_bringup full_system.launch.py
```

## Run — real arm

```bash
# 1. If the arm sits in a bad pose (or at power-on): move it to the safe home.
#    Joint-space MovJ, works even FROM a singularity. Launch file must be stopped.
python3 src/dobot_e6_hw/scripts/go_home.py

# 2. Teleop:
ros2 launch dobot_e6_hw real_hw.launch.py robot_ip:=192.168.5.1
```

The home pose `[0, 0, 1.84, 0, -1.38, 0]` rad (κ ≈ 16.5) was picked by scanning
the joint space with Pinocchio for maximum singularity margin.

## Errors to look out for (all encountered on real hardware)

| Symptom | Cause | Fix |
|---|---|---|
| Every TCP command rejected: `Control Mode Is Not Tcp` | Arm not in TCP/IP secondary-development mode, or DobotStudio still connected | Flip the mode in DobotStudio Pro once (it persists), disconnect Studio |
| Motion commands return `-1,{}`; arm twitches then freezes | Controller stuck in **PAUSE** mode (RobotMode 10), typically left over from a DobotStudio session. `ClearError()` does **not** clear it | Send `Stop()` to flush the paused queue — `go_home.py` and `dobot_tcp_node.py` do this automatically |
| Constant "close to singularity" + rumble while the arm is clearly fine and **not moving** | Arm silently rejecting `ServoJ`; MoveIt Servo integrates its *internal* commanded pose, which drifts into a virtual singularity while the real arm stands still | Fix whatever blocks motion (usually PAUSE above). `dobot_tcp_node` now logs `ServoJ rejected …` so this is visible |
| Singularity warning immediately at startup, arm genuinely near-singular | Arm powered on in (or manually pushed to) a singular pose — all-zeros is a true singularity (κ = ∞). Cartesian jog can't escape a singularity | `go_home.py` — joint-space moves bypass IK entirely |
| DobotStudio refuses to enable/jog: payload weight error | Configured payload doesn't match what's mounted | Set the real payload in Studio, or enable over TCP: `EnableRobot()` defaults to 0 kg and skips the check |
| Launch hangs silently at startup | Dashboard socket blocked forever on `recv` (robot off / wrong IP / Studio holding the port) | Node sets a 7 s socket timeout and logs the reason; check IP and that Studio is closed |
| Rumble at rest after calibration | Auto-calibration window caught noisy κ data | Raise `CALIBRATION_MARGIN` in `haptic_feedback.py` (1.5 → 2.0) |

## Verify

```bash
ros2 topic echo /joint_states --once     # angles must match the physical pose
ros2 topic echo /servo_node/status       # 0 = no warnings
ros2 control list_controllers            # (sim) both controllers active
```

## Status

- Sim pipeline verified 2026-07-02 (teleop, Servo decel/halt, contact-force ramp).
- Real hardware verified 2026-07-06: feedback path, `go_home.py`, and DualSense
  teleop with singularity rumble all working end-to-end.
- Contact-force cue on real hardware needs an external wrist F/T sensor
  publishing `/ft_sensor/wrench` (`WrenchStamped`); not yet fitted.
