---
id: installation
title: Installation
audience: [owner, engineer]
order: 10
depends_on: [req://REQ-008, req://REQ-009, req://REQ-018, req://REQ-019, part://stand, part://outer-shell, part://guard-shell, part://controller-box, part://pid-controller, part://limit-controller, part://contactor, part://ssr, part://door-switch, part://earth-stud, part://m20-gland, part://rating-label, param://circuit-rating, param://mains-voltage]
---

# Installation

## Where to put it

Stand the kiln on a non-combustible floor with at least 500 mm of free air on every side
and above. The body is {{ P["guard-outer-width"] }} wide by {{ P["guard-outer-depth"] }} deep
on a {{ P["stand-height"] }} stand; the controller box hangs on the right side, so allow just
under 1 m of width in all (the report gives the exact figure). Leave {{ P["door-clearance"] }}
beside the hinge side (left) for the door to swing {{ P["door-swing"] }}.

**Ventilation.** The room needs ventilation to the outside for the firing fumes. The guards
are cooled by air that enters through the slots low in the side walls and leaves through the
slots in the top: never put anything on top of the kiln or against its sides, and keep the
door guard's top and bottom slots clear.

## Power

**A licensed electrician must install a dedicated {{ P["circuit-rating"] }} circuit at
{{ P["mains-voltage"] }}** with a residual-current device and a local isolator within reach
of the operator. The element draws {{ P["element-power"] }}. The rating
label on the controller box front ({{ part("rating-label").name }}) says: "Dedicated
{{ P["circuit-rating"] }} circuit at {{ P["mains-voltage"] }}. Installation by a licensed
electrician only."

This package has no wiring diagram. The electrician wires, to local code:

- the temperature controller ({{ part("pid-controller").name }}), its thermocouple and the
  solid-state relay ({{ part("ssr").name }}) that switches the element;
- the over-temperature limit controller ({{ part("limit-controller").name }}) and the
  contactor ({{ part("contactor").name }}). {{ req("REQ-018").statement }}
- the door switch, wired into the contactor's coil circuit. **The door switch is required,
  not optional.** {{ req("REQ-009").statement }}
- the cables through the three cable glands in the controller box base: mains in, element,
  thermocouples ({{ part("m20-gland").name }}).

## Earth bonding

Every metal part has its own earth stud ({{ part("earth-stud").name }}) on bare metal: the inner
shell, the guard, the door guard, the stand and the controller box. The electrician runs an
earth lead from each stud to the earth terminal in the controller box.
{{ req("REQ-019").statement }}

## Mounting the body

1. Place the {{ part("stand").name | lower }} and check it stands level.
2. Lift the body onto the stand with two people, with the bricks and the door out: the body
   alone is still heavy (see the report's mass figure). Bolt the guard to the stand through
   its four mounting holes into the rivet nuts in the stand's top rails with
   M6 bolts ({{ part("m6x16-bolt").name }}).
3. Fit the bricks, the door and the controller box as described in the assembly manual.

## First firing and checks

Before the first firing the electrician tests, and records:

- the earth readings: {{ req("REQ-019").verify.note }}
- the over-temperature cut-out: {{ req("REQ-018").verify.note }}
- the door switch: {{ req("REQ-009").verify.note }}

Then run a slow first firing to 200 degC with the door closed (the door switch will not let
the element heat with it open) and hold it there until no more steam comes from the door
edge; this drives the moisture out of the brick, the mortar and the fiber.
