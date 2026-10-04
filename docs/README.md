# Dobot Magician E6 — ultrasound teleoperation manual

How to connect, run, drive and pack down the arm for live probe-on-phantom
demonstrations. Written for engineers who have not worked with a robot arm
before.

**[📄 Download the whole manual as a PDF](E6-Exhibition-Manual.pdf)** — one file,
all sections, for sharing with colleagues.

---

## Before anything else

> ⚠️ **The arm is position controlled. It does not feel you.**
> It moves where the joystick tells it and keeps pushing to stay there. It will
> not stop for your hand, the bench, or the phantom. See **[Safety](01-safety.md)**.

| Emergency | Start | Stop |
|---|---|---|
| Hit the **red mushroom button** on the base | `nmcli con up dobot-e6` then `ros2 launch dobot_e6_hw real_hw.launch.py robot_ip:=192.168.5.1` | `Ctrl+C` in that terminal |

---

## Contents

### Getting going
| | |
|---|---|
| **[1. Safety and the emergency stop](01-safety.md)** | Read first. The deadman principle, rules for the stand |
| **[2. Unpacking and connecting](02-setup.md)** | Four cables, and powering on without switching it off by mistake |
| **[3. Running and stopping](03-running.md)** | The commands, what a good startup looks like, homing from the keyboard |

### Driving
| | |
|---|---|
| **[4. Joystick controls](04-joystick.md)** | Full control map, operator-relative directions, the homing key |
| **[5. Status lights](05-status-lights.md)** | What each colour and flash rate means |

### Scanning
| | |
|---|---|
| **[6. The probe: payload and contact force](06-scanning.md)** | Fitting the probe, and what happens when it presses on the phantom |
| **[7. Joint limits and singularities](07-limits.md)** | What the arm does at its limits, and when a restart is needed |

### When things go wrong
| | |
|---|---|
| **[8. Troubleshooting](08-troubleshooting.md)** | Symptom table, the full restart, health checks |

### Packing and other machines
| | |
|---|---|
| **[9. Packing down](09-packing.md)** | The packing posture, and why it needs DobotStudio Pro |
| **[10. Running on Windows](10-windows.md)** | The ROS-free teleop, and what it gives up |
| **[11. Reference](11-reference.md)** | Specs, network, home pose, file locations, tuning |

---

## Pre-exhibition checklist

Work through this the day before, not on the morning.

- [ ] Arm bolted to the bench, emergency stop within the operator's reach
- [ ] `ping 192.168.5.1` replies
- [ ] Program starts, reaches `Servo started`, then `Calibration complete`
- [ ] Controller drives all six directions — see [§4](04-joystick.md)
- [ ] Homing key works: **L1 + L2 + R2** held one second
- [ ] Probe fitted, assembly weighed, **under 750 g**
- [ ] ⚠️ **Payload declared in software** — [see §6](06-scanning.md#software--tell-the-controller-about-the-load). **Not yet implemented**
- [ ] Phantom positioned so the arm can reach it without stretching to full extent
- [ ] Spare USB-C cable for the controller
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
