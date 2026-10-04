# 4. Running and stopping the program

[← Unpacking, packing and connecting](03-setup.md) · [Contents](README.md) · [Next: Joystick controls →](05-joystick.md)

Everything runs from one terminal on the **Linux laptop**. **There is no timer
and no auto-shutdown** — it runs until you stop it.

---

## 1. Network

Needed after every laptop reboot. The wired adapter carries a static address on
the robot's subnet with **no gateway**, otherwise traffic for the robot leaves
over WiFi instead.

```bash
nmcli con up dobot-e6
ping -c3 192.168.5.1          # must reply before going further
```

If the profile is ever missing, recreate it once:

```bash
sudo nmcli con add type ethernet ifname enp59s0 con-name dobot-e6 \
  ip4 192.168.5.10/24 ipv4.never-default yes
```

## 2. Load the environment

```bash
cd "/home/yz22/Documents/code/Dobot arm"
source setup_dobot.bash
```

## 3. Send the arm to its teleop home

Run this **before** launching. It needs the robot's command port, which the
running program holds open — so it will not work once the launch is up.

```bash
python3 src/dobot_e6_hw/scripts/go_home.py --speed 5
```

It counts down from three before moving, prints joint angles as it goes, and
travels slowly. The click as it starts is the joint brakes releasing — normal
whenever a disabled arm is enabled.

## 4. Launch

```bash
ros2 launch dobot_e6_hw real_hw.launch.py robot_ip:=192.168.5.1
```

---

## What a good startup looks like

![Startup timeline](img/startup-timeline.svg)

Watch for these four lines:

```
[dobot_tcp_node]:  RequestControl → 0,{},RequestControl();
[dobot_tcp_node]:  EnableRobot → 0,{},EnableRobot();
[activate_servo]:  Servo started — hold L1 and move the sticks to drive.
[haptic_feedback]: Calibration complete — peak_cond=16.5 LOWER=24.8 HARDSTOP=44.7
```

> ### Wait for the slow-flashing green light
>
> **Do not touch the controller until the LED ring is flashing green slowly.**
> That is the arm's own confirmation that it is enabled and accepting remote
> commands — about 15 seconds after launch.
>
> Then keep your hands off for a further **25 seconds**, until
> `Calibration complete` appears. That window measures how the arm behaves at
> rest to tune the rumble warning. Move the arm during it and the warning will be
> mis-tuned — you will get buzzing at rest, or no warning when you need one.
>
> Allow about **40 seconds** from launch to driving.
> [More on the lights →](02-status-lights.md)

`RequestControl()` is what claims TCP control of the arm. It runs at **every**
startup because the grant does not survive a power cycle. No DobotStudio Pro and
no Windows machine is needed for this part.

## Stopping

Press **`Ctrl+C`** in the terminal running the launch and wait for the prompt to
come back. The software disables the arm on the way out, so the LED returns to
**steady blue**. That is the clean, finished state — there is nothing else to
shut down.

## Homing while the program is running

Use the controller: hold **L1 + L2 + R2** for one second.

`go_home.py` only works with the launch stopped, so it is for before you start
or after an error — not during a demonstration.

## Health checks (optional)

Only needed if something looks wrong. Run in a **second** terminal with the
program still going:

```bash
source setup_dobot.bash
ros2 topic echo /servo_node/status      # 0 = no warnings
ros2 topic echo /joint_states --once    # do the angles match the real pose?
ping -c3 192.168.5.1                    # network alive?
ls /dev/input/js0                       # controller present?
```

---

---

[← Unpacking, packing and connecting](03-setup.md) · [Contents](README.md) · [Next: Joystick controls →](05-joystick.md)
