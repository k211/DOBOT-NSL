# 1. Safety and the emergency stop

[Contents](README.md) · [Next: Status lights →](02-status-lights.md)

Read this before touching anything. The rest of the manual assumes you know
where the stop button is.

---

## The arm does not feel you

> ⚠️ This robot is **position controlled**. It moves to wherever the joystick
> tells it to go and keeps pushing to stay there. It does **not** stop when it
> meets your hand, the bench, or the phantom. There is no force sensor fitted.
>
> Treat every commanded move as something that will happen regardless of what is
> in the way.

## The emergency stop

The red mushroom button on a cable from the robot base is the only control that
stops the arm unconditionally. Press it and the arm halts all motion and locks.

- It **latches down** when pressed — it stays in until you release it.
- To release, **rotate** the button in the direction of the arrow marked on it.
- Alarms cannot be cleared and the arm cannot be enabled until it is released.
- Keep it within arm's reach of the operator, not buried behind the laptop.

## The deadman principle

Nothing moves unless **L1** is held down. This is deliberate: dropping the
controller, letting go in a panic, or walking away all stop the arm.

**Releasing L1 should be your first reflex** — it is faster and gentler than the
mushroom button. Save the emergency stop for when the arm is doing something you
did not command.

## Rules for the stand

Visitors **may** drive the arm — that is the point of the demonstration — but
only under direct supervision, and only within limits.

### Before handing the controller over

1. Show them **L1**: "hold this to move, let go and it stops."
2. Tell them to let go the moment anything surprises them.
3. Keep the controller tethered to your stand, or keep a hand on the cable.

### While a visitor is driving

- **Stay beside them with a hand near the emergency stop.** Supervision means
  watching the arm, not chatting over your shoulder.
- **Visitors drive in free space only.** *You* make any approach to the phantom —
  the arm cannot feel contact and will keep pressing. See
  [§6 Contact force](06-scanning.md#contact-force-on-the-phantom).
- Nobody puts a hand inside the arm's reach while the program is running. It
  sweeps a **450 mm radius** sphere around its base.
- Keep the phantom, gel and probe cable clear of the arm's path.
- If anyone is unsure what the arm is about to do, **release L1**. That is always
  safe and always stops it.

### Turbo is an operator control

> **Do not mention or demonstrate R1 to visitors.** Turbo multiplies every rate
> by **1.8**, and the whole reason visitor driving is safe is that the base rate
> is slow enough to watch and react to. Visitors should finish the demonstration
> without knowing the button exists.
>
> Keep it for yourself when you need to reposition the arm quickly between
> visitors — and never for an approach toward the phantom or a person.

If you would rather remove the risk entirely, set `scale_turbo` to `1.0` in
`joy_params.yaml` and restart. [See §9](09-reference.md#tuning-for-the-stand).

## Things that are safe, and often mistaken for faults

| | |
|---|---|
| A clicking sound when the arm enables | Joint brakes releasing. Normal and unavoidable |
| A fan running constantly | The control computer lives in the base |
| The arm stopping dead mid-move | Usually a joint limit or singularity. [See §7](07-troubleshooting.md) |
| The controller buzzing | Singularity proximity warning, not contact force |

---

---

---

[Contents](README.md) · [Next: Status lights →](02-status-lights.md)
