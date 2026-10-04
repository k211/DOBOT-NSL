# 1. Safety and the emergency stop

[← Contents](README.md) · [Next: Unpacking and connecting →](02-setup.md)

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

- One named operator holds the controller. Visitors watch.
- Nobody puts a hand inside the arm's reach while the program is running — it
  sweeps a **450 mm radius** sphere around its base.
- Keep the phantom, gel and probe cable clear of the arm's path.
- If you are unsure what the arm is about to do, **release L1**. That is always
  safe and always stops it.
- Do not use turbo (**R1**) for approach moves near the phantom or a person.

## Things that are safe, and often mistaken for faults

| | |
|---|---|
| A clicking sound when the arm enables | Joint brakes releasing. Normal and unavoidable |
| A fan running constantly | The control computer lives in the base |
| The arm stopping dead mid-move | Usually a joint limit or singularity. [See §7](07-limits.md) |
| The controller buzzing | Singularity proximity warning, not contact force |

---

[← Contents](README.md) · [Next: Unpacking and connecting →](02-setup.md)
