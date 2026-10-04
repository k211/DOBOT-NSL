# Dobot Magician E6 — ultrasound teleoperation manual

How to connect, run, drive and pack down the arm for live probe-on-phantom
demonstrations. Written for engineers who have not worked with a robot arm
before.

**[⬇ Download the manual as a PDF](https://github.com/k211/DOBOT-NSL/raw/main/docs/E6-Exhibition-Manual.pdf)** — sections 1–7, the operating
manual, in one file for sharing or printing. Sections 8 and 9 are developer
material and stay here in the repository.

---

## Before anything else

> ⚠️ **The arm is position controlled. It does not feel you.**
> It moves where the joystick tells it and keeps pushing to stay there. It will
> not stop for your hand, the bench, or the phantom. See **[Safety](01-safety.md)**.

| Emergency | Start | Stop |
|---|---|---|
| Hit the **red mushroom button** on the base | `nmcli con up dobot-e6`, home the arm, then `ros2 launch dobot_e6_hw real_hw.launch.py robot_ip:=192.168.5.1` | `Ctrl+C` in that terminal |

**Do not touch the controller until the LED is flashing green slowly**, then wait
a further 25 seconds for calibration. [§4](04-running.md)

---

## Contents

### Before you touch it
| | |
|---|---|
| **[1. Safety and the emergency stop](01-safety.md)** | Read first. The deadman principle, supervising visitors |
| **[2. Status lights](02-status-lights.md)** | What each colour and flash rate means |

### Setting up
| | |
|---|---|
| **[3. Unpacking, packing and connecting](03-setup.md)** | The DobotStudio Pro posture procedure, the four cables, powering on |
| **[4. Running and stopping](04-running.md)** | Network, homing, launch, and when it is safe to drive |

### Driving
| | |
|---|---|
| **[5. Joystick controls](05-joystick.md)** | Full control map, operator-relative directions, the homing key |

### Scanning
| | |
|---|---|
| **[6. The probe: payload and contact force](06-scanning.md)** | Fitting the probe, and what happens when it presses on the phantom |

### When things go wrong
| | |
|---|---|
| **[7. Limits, faults and recovery](07-troubleshooting.md)** | Why a stopped arm is usually normal, symptom table, the full restart |

### Other machines
| | |
|---|---|
| **[8. Running on Windows](08-windows.md)** | The ROS-free teleop, and what it gives up |
| **[9. Reference](09-reference.md)** | Specs, network, home pose, file locations, tuning |

---

## Pre-exhibition checklist

Work through this the day before, not on the morning.

- [ ] Arm unfolded from the packing posture with DobotStudio Pro — [§3](03-setup.md)
- [ ] Arm bolted to the bench, emergency stop within the operator's reach
- [ ] `ping 192.168.5.1` replies
- [ ] `go_home.py --speed 5` completes
- [ ] Program starts, LED flashes green slowly, then `Calibration complete`
- [ ] Controller drives all six directions — [§5](05-joystick.md)
- [ ] Homing key works: **L1 + L2 + R2** held one second
- [ ] Probe fitted, assembly weighed, **under 750 g**
- [ ] ⚠️ **Payload declared in software** — [§6](06-scanning.md). **Not yet implemented**
- [ ] Phantom positioned so the arm can reach it without stretching to full extent
- [ ] Spare USB-C cable for the controller
- [ ] Windows laptop available for pack-down — [§3](03-setup.md)
- [ ] This manual printed or on a phone

## Known gaps

| Gap | Impact | Status |
|---|---|---|
| Payload is declared as 0 kg | Collision detection may fire spuriously once the probe is fitted | **Needs doing** — weigh the probe first |
| No force/torque sensor | No contact-force feedback or force control while scanning | Hardware not fitted |
| `ServoP` untested | The Windows teleop depends on it | Run `--probe` on the real arm first |

---

*Revision 2026-10-04 · figures from the manufacturer's user guide V1.3 · control
mapping and thresholds measured on this specific robot and controller*
