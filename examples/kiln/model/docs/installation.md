---
id: installation
title: Installation
audience: [owner, engineer]
order: 10
depends_on: [req://REQ-008, req://REQ-009, req://REQ-018, req://REQ-019, part://stand, part://outer-shell, part://guard-shell, part://m6x50-bolt, part://m6-rivnut, part://controller-box, part://pid-controller, part://limit-controller, part://contactor, part://ssr, part://door-switch, part://earth-stud, part://m20-gland, part://rating-label, part://supply-terminal-block, part://earth-terminal, part://control-fuse, part://ssr-heat-sink, part://element-tail-connector, param://circuit-rating, param://mains-voltage]
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
of the operator. Nothing else may be plugged into that circuit: it serves the kiln alone.
The element draws {{ P["element-power"] }}. The rating
label on the controller box front ({{ part("rating-label").name }}) says: "Dedicated
{{ P["circuit-rating"] }} circuit at {{ P["mains-voltage"] }}. Installation by a licensed
electrician only."

## Wiring

The wiring is drawn below from the kiln's model: what connects to what, with which cable,
through which gland in the controller box base, and where each earth lead goes. The same
wiring is drawn as one diagram per circuit in the package's wiring folder and in the report's
Wiring section. **A licensed electrician still wires the kiln, to local code**, and decides
every point listed under "What the electrician decides" before the first firing. The terminal
numbers are read from the makers' datasheets; confirm each against the part in hand.

The temperature controller ({{ part("pid-controller").name }}) switches the element through
the solid-state relay ({{ part("ssr").name }}). The over-temperature limit controller
({{ part("limit-controller").name }}) and the door switch hold the contactor
({{ part("contactor").name }}) in, in series with the relay. {{ req("REQ-018").statement }}
**The door switch is required, not optional.** {{ req("REQ-009").statement }}

### {{ circuit("power").name }}

Protected by {{ circuit("power").protection }}.

{{ circuit("power").table }}

### {{ circuit("control").name }}

Protected by {{ circuit("control").protection }}. The door switch's pair leaves the box
through the middle gland and runs to the switch on the guard's right wall.

{{ circuit("control").table }}

### {{ circuit("sensing").name }}

Type K extension cable all the way from each probe's head to its controller, plus to plus.

{{ circuit("sensing").table }}

### Cable to buy

{% for row in cables_to_buy() %}- {{ row.label }}: {{ row.total_length_m }} m ({{ row.wires.split() | length }} wires)
{% endfor %}
The lengths are estimates from the placed parts with slack at each end; cut to fit.

### Terminal labels

Each of the {{ cable_schedule() | length }} wires carries a sleeve at both ends reading the
wire, then the device and terminal it lands on:

| Label | Lands on | Terminal |
|---|---|---|
{% for row in terminal_labels() %}| {{ row.label }} | {{ row.device }} | {{ row.terminal }} |
{% endfor %}

### What the electrician decides

- The site's dedicated circuit, its breaker and residual-current device, the isolator and the
  earthing arrangement (the drawings assume a TT installation because they ask for a
  residual-current device).
- The control fuse's rating, from the contactor coil's and the controllers' draw.
- The limit controller's relay is rated for a resistive load only and switches the
  contactor's coil: confirm it with the maker, or let it drive a relay rated for a coil.
- The door switch's mounting, so that opening the door opens its contact 31-32 (the one
  with a direct opening action).
- The relay's heat sink at the element's current, the cover over the element tails'
  connector at the back, and the ratings of the supply terminal block and the earth terminal.

## Earth bonding

Every metal part has its own earth stud ({{ part("earth-stud").name }}) on bare metal: the inner
shell, the guard, the door guard, the stand and the controller box, and the lid and the door
tray, which come off or open and so are bonded by a flexible lead. The hinge post and the
latch keeper reach earth through their bolts to the guard; the electrician tests that joint.
{{ req("REQ-019").statement }}

{{ circuit("earth").table }}

## Mounting the body

1. Place the {{ part("stand").name | lower }} and check it stands level.
2. Lift the body onto the stand with two people before it is lined: the inner shell with its
   standoffs inside the guard, without fiber, bricks or door (see the report's mass figure).
   Bolt it down at the four bottom corners from inside the shell, through the bottom standoffs
   and the guard into the rivet nuts in the stand's top rails, with M6 × 50 bolts
   ({{ part("m6x50-bolt").name }}).
3. Line the body, hang the door and the controls as described in the assembly manual.

## First firing and checks

Before the first firing the electrician tests, and records:

- the earth readings: {{ req("REQ-019").verify.note }}
- the over-temperature cut-out: {{ req("REQ-018").verify.note }}
- the door switch: {{ req("REQ-009").verify.note }}

Then run a slow first firing to 200 degC with the door closed (the door switch will not let
the element heat with it open) and hold it there until no more steam comes from the door
edge; this drives the moisture out of the brick, the mortar and the fiber.
