# 7. Limits, faults and recovery

[← The probe: payload and contact force](06-scanning.md) · [Contents](README.md) · [Next: Running on Windows →](08-windows.md)

What to do when the arm stops, misbehaves, or shows a red light. Start at the
top — most "faults" are the arm behaving correctly at a limit.

---

## First: a stopped arm is usually not a fault

> ✅ When the arm reaches a joint limit or a singularity it **stops moving and
> holds position**. It does not shut down, power off, drop, or raise an error.
> Motion simply stops being commanded. **No restart is needed** — drive back out
> the way you came.

Check this before assuming something is broken. The giveaway is a **steady or
slow-flashing green** light and no error in the terminal.

## Singularities

A singularity is a pose where the arm loses the ability to move in some
direction, typically when joints line up. Near one, small tool movements demand
enormous joint speeds, so the software intervenes early.

Closeness is measured by the **condition number (κ)**: low is healthy, high is
dangerous.

![Condition number scale](img/kappa-scale.svg)

| κ | What happens |
|---|---|
| ~16 | The home pose. Healthy |
| ~25 | **Controller rumbles.** Re-measured at every launch, so the exact figure varies |
| 60 | **The arm automatically slows down** |
| 100 | **The arm stops** and holds position |

You get three escalating warnings before anything stops.

## Joint limits

The software stops commanding motion **0.1 radians (about 5.7°) before** a joint
reaches its limit, so the arm never runs into its own hard stops. You will also
feel rumble as a joint nears its limit.

| Joint | Travel | Joint | Travel |
|---|---|---|---|
| J1 base | ±360° | J4 wrist 1 | ±160° |
| J2 shoulder | ±135° | J5 wrist 2 | ±173° |
| J3 elbow | ±154° | J6 flange | ±360° |

## Getting unstuck

1. **Release L1.**
2. Press it again and drive **in the opposite direction** to the one that got you
   stuck.
3. If that does not free it, hold **L1 + L2 + R2** for a second to home the arm.
   Homing moves joint by joint, so it works from poses that ordinary Cartesian
   driving cannot escape.

> ⚠️ Homing takes the **direct joint-space route with no collision checking**. From
> a twisted wrist that is harmless, but if the arm is somewhere awkward, watch the
> first second with a hand near the e-stop, and move the phantom clear first.

---

## Symptom table

| Symptom | Most likely cause | Fix |
|---|---|---|
| Arm does not move when L1 is held | You just homed it — teleop is deliberately disarmed | **Release L1 and press it again.** By design |
| Still does not move; LED green | Joint limit or singularity reached | Drive the other way, or home it — see above |
| Arm stops part-way through a move | Same. Not a fault | Drive the other way |
| Every command rejected, `Control Mode Is Not Tcp` | DobotStudio is connected and holding the arm | Close DobotStudio completely, then restart. The software claims control automatically at startup |
| Launch hangs with no output | Wrong IP, robot off, or no network | `ping -c3 192.168.5.1`. If it fails, `nmcli con up dobot-e6` |
| Constant rumble, arm clearly fine and not moving | The arm is silently refusing commands, so the software's idea of its pose drifts | Look for `ServoJ rejected` in the terminal. Full restart |
| Rumbles at rest right after startup | The arm was moved during the 25 s calibration window | Restart and keep hands off for the first 40 s |
| Red light | Alarm or collision detected | Full restart. If it returns immediately, power-cycle the arm |
| Controller does nothing at all | USB not detected | Unplug and replug. Check `ls /dev/input/js0`. Restart the program |
| Arm drifts with nobody touching anything | Stick drift on a worn controller | Release L1. Restart; if it persists the controller needs replacing |
| Collision alarms while scanning | Payload still declared as 0 kg | [See §6](06-scanning.md#software--tell-the-controller-about-the-load) |

## Does it need a restart?

| Situation | Restart? |
|---|---|
| Singularity or joint limit reached | **No** — drive back out |
| Rumbling constantly but the arm is fine | **No** — home it |
| Arm dead right after homing | **No** — release L1 and press it again |
| Emergency stop pressed | **Yes** — release it first |
| Red light / alarm state | **Yes** |
| Arm ignores the controller entirely | **Yes** |
| Network dropped, ping fails | **Yes** — and re-run `nmcli con up dobot-e6` |

## The full restart

![Restart sequence](img/restart-flow.svg)

```bash
# 1. Ctrl+C in the terminal running the launch
# 2. release the emergency stop if it is latched (rotate it)

nmcli con up dobot-e6
ping -c3 192.168.5.1

cd "/home/yz22/Documents/code/Dobot arm"
source setup_dobot.bash
python3 src/dobot_e6_hw/scripts/go_home.py --speed 5
ros2 launch dobot_e6_hw real_hw.launch.py robot_ip:=192.168.5.1

# 5. wait for the slow-flashing green light, then 25 s more for calibration
```

If a red light persists after a full restart, power-cycle the arm: **hold** the
power button 1.5 s to switch off, wait ten seconds, then **tap** once to switch
on.

## Reading the launch output

| Line | Means |
|---|---|
| `RequestControl → 0,{}` | TCP control claimed. Good |
| `EnableRobot → 0,{}` | Arm enabled. Good |
| `Servo started` | Ready to drive |
| `Calibration complete` | Rumble threshold tuned. Safe to touch the controller |
| `ServoJ rejected: ...` | **The arm is refusing motion.** Check mode and alarms |
| `RequestControl refused` | Something else holds the arm — close DobotStudio |
| `Robot PAUSEd` | Controller stuck in pause; the software sends `Stop()` to flush it |

Diagnostic commands are in [§4 Running and stopping](04-running.md#health-checks-optional).

---

---

[← The probe: payload and contact force](06-scanning.md) · [Contents](README.md) · [Next: Running on Windows →](08-windows.md)
