# Dobot Magician E6 — ultrasound teleoperation

Operating manual and control software for the **Dobot Magician E6** ultrasound
demonstration at **NSL**. A PS5 DualSense controller drives the arm, and the
operator feels gamepad rumble as the arm approaches a kinematic singularity.

---

## Documentation

Everything operational lives in **[`docs/`](docs/)**. Take the
**[single-file PDF](docs/E6-Exhibition-Manual.pdf)** to share or print.

| | |
|---|---|
| **[1. Safety and the emergency stop](docs/01-safety.md)** | Read first. The deadman principle, supervising visitors |
| **[2. Status lights](docs/02-status-lights.md)** | What each colour and flash rate means |
| **[3. Unpacking, packing and connecting](docs/03-setup.md)** | The DobotStudio Pro posture procedure, cabling, powering on |
| **[4. Running and stopping](docs/04-running.md)** | Network, homing, launch, and when it is safe to drive |
| **[5. Joystick controls](docs/05-joystick.md)** | Full control map and the homing key |
| **[6. The probe: payload and contact force](docs/06-scanning.md)** | Fitting the probe, and what happens when it presses on the phantom |
| **[7. Limits, faults and recovery](docs/07-troubleshooting.md)** | Why a stopped arm is usually normal, symptom table, the full restart |
| **[8. Running on Windows](docs/08-windows.md)** | The ROS-free teleop, and what it gives up |
| **[9. Reference](docs/09-reference.md)** | Specs, network, home pose, file locations, tuning |

> ⚠️ **The arm is position controlled — it does not feel you.** It will not stop
> for your hand, the bench, or the phantom. Read
> [Safety](docs/01-safety.md) before operating it.

## Quick start

```bash
nmcli con up dobot-e6
cd "/home/yz22/Documents/code/Dobot arm"
source setup_dobot.bash
python3 src/dobot_e6_hw/scripts/go_home.py --speed 5
ros2 launch dobot_e6_hw real_hw.launch.py robot_ip:=192.168.5.1
```

Wait for the **slow-flashing green** light, then 25 s more for calibration.
`Ctrl+C` stops everything. Full detail in [§4](docs/04-running.md).

## Windows

[`windows/`](windows/) holds a ROS-free teleop that uses the robot's own
Cartesian servo command, for machines that cannot run this stack — MoveIt has no
supported Windows build. **It is not yet verified against the arm**; see
[§8](docs/08-windows.md) before relying on it.

## Layout

```
docs/                     operating manual (Markdown + PDF)
windows/                  ROS-free teleop for Windows
src/
├── dobot_e6_description/ ME6 URDF, meshes and SRDF
├── dobot_e6_bringup/     Servo config, teleop mapping, haptics
│   ├── config/joy_params.yaml      controller mapping
│   └── scripts/joy_to_servo.py     joystick → Cartesian twist
│       scripts/haptic_feedback.py  singularity rumble
└── dobot_e6_hw/          real-hardware adapter
    ├── scripts/dobot_tcp_node.py   Servo → ServoJ @ 33 Hz, port 29999
    ├── scripts/go_home.py          joint-space move to the safe pose
    ├── scripts/home_pose.py        shared home pose and motion profile
    └── scripts/dobot_api.py        vendored Dobot TCP-IP-Python-V4 (MIT)
```

## Requirements

- Ubuntu 22.04 with **ROS 2 Humble**, MoveIt 2 + MoveIt Servo (ROS 2 Jazzy also
  works; the launch files pick the right Servo API from `$ROS_DISTRO`)
- Python: `pinocchio`, `numpy<2`, `evdev`
- PS5 DualSense controller over USB
- Arm reachable at `192.168.5.1`, PC on `192.168.5.x`. The arm must be in TCP/IP
  control mode, which the software claims itself with `RequestControl()` at every
  startup — **no DobotStudio Pro or Windows machine needed** for normal running

### Building

Only needed after adding or renaming a file. Editing Python or YAML needs no
rebuild.

```bash
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src --rosdistro "$ROS_DISTRO" -y

# Humble's Pinocchio needs NumPy 1.x, kept isolated from newer system versions
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install "numpy<2"

colcon build --symlink-install
```
