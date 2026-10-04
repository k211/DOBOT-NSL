# 2. Unpacking and connecting

[← Safety](01-safety.md) · [Contents](README.md) · [Next: Running and stopping →](03-running.md)

Four cables, and only one of them goes to the laptop. Getting that wrong is the
most common setup mistake.

---

## Unpacking

1. Open the box flat on the floor or a sturdy table. The arm weighs **7.2 kg**
   and is awkward — **use two people**.
2. Lift by the **base and upper arm together**, keeping the folded posture it was
   packed in. Do not lift it by the forearm or the wrist.
3. **Bolt the base down before doing anything else.** An unbolted arm will tip
   itself over the moment it moves.
4. Keep the box and foam — you need them to get home again.

> ⚠️ The arm reaches 450 mm and can move its tool at 0.5 m/s. A 7.2 kg arm doing
> that on an unsecured base will walk off the bench. **Mount it before powering on.**

## The connections

![Connection diagram](img/connections.svg)

| Order | Cable | From | To |
|---|---|---|---|
| 1 | Emergency stop | E-stop switch | **Robot base** e-stop port (usually pre-fitted) |
| 2 | Power | Robot base | Wall socket — leave switched off for now |
| 3 | Ethernet | Robot **LAN1** | Laptop wired port |
| 4 | USB-C | PS5 controller | **Laptop** |

> **The controller plugs into the laptop, never into the robot.** The USB socket
> on the robot base is for a WiFi dongle or file transfer only — a controller
> plugged in there does nothing.

LAN1 is the port fixed at `192.168.5.1`. LAN2 is a different subnet and will not
work. Connect everything **before** switching on at the wall.

## Network on the laptop

The wired adapter needs a static address on the robot's subnet, with **no
gateway** — otherwise traffic for the robot goes out over WiFi instead.

```bash
nmcli con up dobot-e6      # the profile already exists on this laptop
ping -c3 192.168.5.1
```

If the profile is missing, recreate it once:

```bash
sudo nmcli con add type ethernet ifname enp59s0 con-name dobot-e6 \
  ip4 192.168.5.10/24 ipv4.never-default yes
```

## Powering the arm on

> ⚠️ **Tap it — do not hold it.**
> A short press **under 0.5 s** switches the arm **on**. **Holding for 1.5 s is
> the shut-down gesture.** If you press and hold you will see the light flash and
> then die when you let go — that is the robot booting and then being told to
> switch off. Every other button on the robot uses long-press to activate; the
> power button is the exception.

1. Check the e-stop is **not latched**. If pressed in, rotate to release.
2. Switch on at the wall.
3. **Quick tap** the power button on the base. Finger off immediately.
4. Watch the LED ring: blue fast flash (booting, 30–60 s) → **steady blue**.

**Steady blue is the ready state** — powered and healthy, waiting for the
program. [More on the lights →](05-status-lights.md)

---

[← Safety](01-safety.md) · [Contents](README.md) · [Next: Running and stopping →](03-running.md)
