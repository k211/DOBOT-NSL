# NSL Dobot — hardware checklist

**Responsible:** Yixuan Zheng
**Event:** ______________________  **Date:** ____________

Tick **Out** when it goes into the box, **Back** when it comes home. Anything
left blank in the Back column is still at the venue.

---

## Robot

| Out | Back | Item | Qty | Notes |
|:-:|:-:|---|:-:|---|
| ☐ | ☐ | Dobot Magician E6 arm | 1 | In **packing posture**, in original box and foam |
| ☐ | ☐ | Robot power cable / charger | 1 | |
| ☐ | ☐ | **Emergency-stop switch and cable** | 1 | The arm cannot be enabled without it. Check it is not left plugged into the bench |
| ☐ | ☐ | Ethernet cable, robot LAN1 → laptop | 1 | |
| ☐ | ☐ | Spare Ethernet cable | 1 | |
| ☐ | ☐ | USB-C/USB-A → Ethernet adapter | 1 | Only if a laptop has no Ethernet port |
| ☐ | ☐ | Screws for bolting the base down | set | M6. Count them out and back |
| ☐ | ☐ | Screwdrivers / Allen keys | set | To match the base and flange screws |
| ☐ | ☐ | Bench clamps | 2 | Backup if the venue table cannot take screws |

## Ultrasound

| Out | Back | Item | Qty | Notes |
|:-:|:-:|---|:-:|---|
| ☐ | ☐ | Ballater ultrasound probes | 2 | Charged the night before |
| ☐ | ☐ | Probe chargers | 2 | |
| ☐ | ☐ | iPad | 1 | Charged; ultrasound app installed and signed in |
| ☐ | ☐ | iPad charger and cable | 1 | |
| ☐ | ☐ | 3D-printed probe holders | all | Plus a spare if one exists — they crack |
| ☐ | ☐ | Leg phantom | 1 | |
| ☐ | ☐ | Ultrasound gel | 1 | Check it is not nearly empty |
| ☐ | ☐ | Paper towels / wipes | 1 pack | For gel on the probe, phantom and hands |
| ☐ | ☐ | Cable ties / Velcro straps | 10 | Strain-relieve the probe cable to the forearm |

## Computers and controllers

| Out | Back | Item | Qty | Notes |
|:-:|:-:|---|:-:|---|
| ☐ | ☐ | Yixuan's Dell laptop (sie182) | 1 | Runs the teleop. Ubuntu, ROS 2 Humble |
| ☐ | ☐ | Dell charger | 1 | |
| ☐ | ☐ | Lenovo student laptop 1 | 1 | Windows, **DobotStudio Pro** — needed to unpack and pack the arm |
| ☐ | ☐ | Lenovo charger | 1 | |
| ☐ | ☐ | PS5 DualSense controllers | 2 | Charged |
| ☐ | ☐ | USB-C cables for the controllers | 2 | Data-capable, not charge-only |

## Power and stand

| Out | Back | Item | Qty | Notes |
|:-:|:-:|---|:-:|---|
| ☐ | ☐ | Extension lead / power strip | 2 | Robot, two laptops, iPad, chargers: at least 6 sockets |
| ☐ | ☐ | Plug adapters | as needed | If the venue is abroad |
| ☐ | ☐ | Tape / barrier for the keep-out zone | 1 | Mark the arm's 450 mm reach on the table |
| ☐ | ☐ | "Robot in operation" sign | 1 | |

## Documents

| Out | Back | Item | Qty | Notes |
|:-:|:-:|---|:-:|---|
| ☐ | ☐ | Quick guide, printed | 2 | `docs/E6-Quick-Guide.pdf` — one for the operator, one spare |
| ☐ | ☐ | Full manual, printed | 1 | `docs/E6-Exhibition-Manual.pdf` |
| ☐ | ☐ | This checklist | 1 | |

---

## The night before

| Done | Check |
|:-:|---|
| ☐ | Everything above charged: probes, iPad, both laptops, both controllers |
| ☐ | Dell laptop: `nmcli con up dobot-e6` profile still present, repo up to date |
| ☐ | Lenovo laptop: DobotStudio Pro opens and connects |
| ☐ | Probe holder fits the probe and the flange |
| ☐ | Probe assembly weighed — **under 750 g** |

## At the venue, before visitors

| Done | Check |
|:-:|---|
| ☐ | Arm bolted down, e-stop within the operator's reach |
| ☐ | Arm unfolded with DobotStudio Pro — manual §3 |
| ☐ | Program running, LED flashing green slowly — manual §4 |
| ☐ | Controller drives all six directions; homing key works |
| ☐ | Keep-out zone marked |

## Packing up

| Done | Check |
|:-:|---|
| ☐ | Arm folded into **packing posture** with DobotStudio Pro before power-off |
| ☐ | Every **Back** box above ticked — especially e-stop, screws and chargers |
| ☐ | Gel wiped off probes and phantom before they go in the bag |
