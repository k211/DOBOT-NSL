# 9. Packing down

[← Troubleshooting](08-troubleshooting.md) · [Contents](README.md) · [Next: Running on Windows →](10-windows.md)

The arm has a dedicated **packing posture** that folds it to fit the original
foam. It is **not** the same as the home pose this software uses.

---

## Three different poses — do not confuse them

| Pose | What it is | Where it comes from |
|---|---|---|
| **Home posture** (manufacturer's §4.2) | All joints at **0°**, arm vertical, with alignment marks on each joint | Mechanical calibration reference, used after a collision |
| **Our teleop home** | `[0, −19.24, 117.25, −8.02, −90, 0]°` | Chosen for this project: flange parallel to the bench, wide singularity margin |
| **Packing posture** | A compact fold that fits the foam | A **DobotStudio Pro** feature |

## Packing posture needs DobotStudio Pro

> The packing posture is a function of Dobot's own software, and the joint angles
> for it are **not published anywhere** — not in the user guide, and there is no
> command for it in the robot's network interface. You need **DobotStudio Pro**.
> The **Android app** works, so no Windows machine is required.

## Order of operations

1. **Stop the program** with `Ctrl+C`. DobotStudio and this software cannot both
   control the arm.
2. Remove the probe and any tooling from the flange.
3. Connect **DobotStudio Pro** to the arm.
4. Go to **Settings → Basic → Packing Pose** and **long-press** *"Move to this
   position"*. The long press is deliberate — it cannot be triggered by accident.
5. Watch the fold happen. The arm is bolted to the bench, so **check the path
   does not drive it into the benchtop**. Hand near the e-stop.
6. Power off: **hold** the power button for 1.5 s until the light flashes red
   fast, then release.
7. Switch off at the wall and disconnect the cables.
8. Unbolt the base.
9. Lift with two people, keeping the folded posture, and lower it into the foam.

> ⚠️ **Do not transport it in any other pose.** The manufacturer requires the
> packing posture with working brakes before it goes in the box — the brakes are
> what hold the pose once power is off. Transporting it folded wrongly risks
> damaging the joints, and the foam will not support it.

## Make this repeatable

Once the arm is in the packing posture, the joint angles can be read straight off
it and saved into the project, so future pack-downs become a single command with
no DobotStudio at all.

This is the same approach that removed the Windows dependency from everything
else in this system — ask for it the first time you use the app.

---

[← Troubleshooting](08-troubleshooting.md) · [Contents](README.md) · [Next: Running on Windows →](10-windows.md)
