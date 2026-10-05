# Dobot Magician E6 — quick guide

## Start up

**1. Power on the robot**

Check the red emergency stop is released, switch on at the wall, then **tap**
the power button on the base. Do not hold it.

⏱ Wait **30–60 s** until the light is **steady blue**.

**2. Connect the network**

```bash
nmcli con up dobot-e6
```

**3. Load the environment**

```bash
cd "/home/yz22/Documents/code/Dobot arm"
source setup_dobot.bash
```

**4. Send the arm home**

```bash
python3 src/dobot_e6_hw/scripts/go_home.py --speed 5
```

⏱ Wait until it prints **`Arm at home pose`**.

**5. Start the program**

```bash
ros2 launch dobot_e6_hw real_hw.launch.py robot_ip:=192.168.5.1
```

⏱ Wait about **15 s** until the light is **flashing green slowly**, then
**25 s more** — until `Calibration complete` appears — before touching the
controller. About **40 s** in total.

**Stop the program:** press `Ctrl+C` in the same terminal. The light returns to
steady blue.

**Turn off the robot:** after stopping the program, **hold** the power button
until the light **flashes red**, then release. The light goes off.

**Restart:** press `Ctrl+C`, then repeat **steps 4–5**. If the robot was turned
off or the emergency stop was pressed, repeat from **step 1**.

## Joystick

![Controller map](img/controller-photo.svg)
