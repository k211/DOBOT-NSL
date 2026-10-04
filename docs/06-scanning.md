# 6. The probe: payload and contact force

[← Joystick controls](05-joystick.md) · [Contents](README.md) · [Next: Joint limits and singularities →](07-limits.md)

The two questions that matter most for scanning: what changes when you fit the
probe, and what happens when it presses on the phantom.

---

## Fitting the probe

### Mechanical — stay under 750 g

The E6's rated maximum load is **750 g**, and that budget covers **everything**
you bolt on: probe, adapter plate, bolts, and any cable weight the arm actually
carries. A typical clinical probe is 200–500 g, so there is room — but weigh the
assembled tool rather than guessing.

- Mount to the **four M6 threaded holes** in the end flange.
- Use the 6 mm locating hole with a dowel pin if you need repeatable alignment.
- **Strain-relieve the probe cable** to the forearm. A cable that snags mid-scan
  drags the arm off course, and the arm will not notice.
- Keep the probe's mass close to the flange. Weight hung far out loads the wrist
  joints much harder than the same weight held close.

### Software — tell the controller about the load

> ⚠️ **Not yet configured — action needed before the exhibition.**
>
> The program currently enables the arm declaring a payload of **0 kg**. That was
> deliberate during commissioning: a zero payload skips the controller's load
> check, which otherwise refuses to enable when the configured weight does not
> match reality.
>
> With a probe fitted and the payload still zero, the controller's internal model
> of the arm is wrong. The practical consequence is **collision detection firing
> spuriously** — the arm reads the probe's weight as an unexplained force — plus
> slightly degraded gravity compensation.
>
> The fix is one `SetPayload()` call with the real mass and its offset from the
> flange, wired into startup. **This has not been implemented yet.** Weigh the
> probe assembly first.

### Re-home after fitting

Stop and restart the program once the probe is on. The haptic calibration
measures the arm at rest, and it should do that with the final tool attached.

---

## Contact force on the phantom

> ⚠️ **The arm does not yield.** This is the most important thing in this manual.
>
> The arm is **position controlled**. When the probe meets the phantom it does
> **not** sense the contact and does **not** back off. It keeps driving toward the
> position your joystick commanded, pressing harder the further you push past the
> surface. It behaves like a clamp, not like a hand.

### What actually happens when you press down

1. You hold **L1** and push the left stick down. The arm descends at 0.03 m/s.
2. The probe touches the phantom. **Nothing changes** — no resistance is felt by
   the software, no rumble, no slowing.
3. Keep pushing and the arm keeps descending, deforming the phantom and loading
   the probe.
4. Eventually either the controller's **collision detection** trips and raises an
   alarm, or it does not — and the force keeps climbing.

Step 4 is the uncomfortable one. Collision detection is a safety backstop with a
threshold, designed to notice a crash, **not** to regulate scanning pressure.

### How much force can it generate?

**Dobot does not publish a maximum force figure for the E6.** The 750 g load
rating is *not* a force limit — it describes what the arm can carry and
accelerate, and a position-controlled arm pressing into a rigid object can
generate substantially more than the weight it is rated to lift.

Treat the pressing force as **unknown and potentially much higher than you
expect**.

### How to scan safely, given all of the above

- **Approach in small taps.** Tap the stick down, release, look. Do not hold it
  down and watch.
- **Release L1 the instant the probe touches.** That freezes the arm.
- **Judge pressure by eye** — watch how far the phantom surface deforms. That is
  your only feedback.
- **Never put a hand between probe and phantom** to check contact.
- **Do not use turbo** for approach moves.
- Use a **compliant phantom** if you have the choice. Against something rigid, a
  small over-travel becomes a large force very quickly.

### If you need real force control

Proper scanning pressure needs a **wrist force/torque sensor**. The software
already has a contact-force rumble cue written and waiting — it needs a sensor
publishing on `/ft_sensor/wrench`, and none is fitted. With that hardware the arm
could hold a target *force* instead of a target *position*.

That is the correct engineering answer for scanning, and it is a hardware
addition, not a software setting.

---

---

[← Joystick controls](05-joystick.md) · [Contents](README.md) · [Next: Joint limits and singularities →](07-limits.md)
