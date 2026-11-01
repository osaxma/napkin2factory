---
id: assembly
title: Assembly
audience: [owner, engineer, manufacturer]
order: 15
depends_on: [asm://kiln, asm://door, asm://controls, asm://lining, part://outer-shell, part://guard-shell, part://stand, part://m6-standoff-25, part://m6-standoff-40, part://m6x16-bolt, part://m6x50-bolt, part://m6-rivnut, part://earth-stud, part://liner-slab, part://liner-side, part://liner-back, part://fiber-slab, part://fiber-side, part://fiber-back, part://refractory-mortar, part://heating-element, part://ceramic-bush, part://thermocouple, part://hinge-post, part://latch-keeper, part://door-tray, part://door-fiber, part://door-brick, part://door-guard, part://fiber-anchor, part://fiber-gasket, part://hinge, part://latch, part://controller-box, part://controller-lid, part://pid-controller, part://limit-controller, part://ssr, part://contactor, part://lid-screw, part://door-switch, part://m20-gland, part://rating-label, iface://guard-standoff-left, iface://guard-standoff-right, iface://guard-standoff-top, iface://guard-standoff-bottom, iface://shell-frame-mount, iface://door-guard-standoff, iface://guard-hinge-post, iface://guard-latch-keeper, iface://controller-mount, iface://controller-lid-seat, iface://hinge-lower, iface://hinge-upper, iface://latch-catch]
---

# Assembly

Work on a clean bench. Wear gloves and a dust mask when handling brick and fiber board. The
kiln is built from two units, each put together on its own: the controls and the door. The
final assembly then puts the body on its stand, lines it, and hangs the two units on it. Do
the final assembly's sections in order: some fixings cannot be reached once the lining is in.

Each step starts with its parts list and the joints it closes; the item numbers are the ones
on that unit's assembly sheet.

## 1. The controls

{{ build_step("asm://controls") }}

1. Fit the temperature controller ({{ part("pid-controller").name }}) and the limit controller
   ({{ part("limit-controller").name }}) through the two front cutouts of the controller box
   ({{ part("controller-box").name }}), and the solid-state relay
   ({{ part("ssr").name }}) and the contactor ({{ part("contactor").name }}) on its base. Fit
   the box's earth stud.
2. Fit the three cable glands ({{ part("m20-gland").name }}) in the base.
3. The electrician wires the box (installation manual) and can test it on the bench before
   it is hung. Leave the lid off until the element, the thermocouples and the door switch are
   connected in the final assembly (section 3.7).
4. Then screw the lid ({{ part("controller-lid").name }}) on with the four self-tapping
   screws, drilled on assembly.
5. Rivet the rating label ({{ part("rating-label").name }}) to the box front.

## 2. The door

{{ build_step("asm://door") }}

1. Bond the fiber plug ({{ part("door-fiber").name }}) to the inner face of the door tray
   ({{ part("door-tray").name }}) with refractory adhesive, and hold it with the four fiber
   anchors ({{ part("fiber-anchor").name }}) through holes drilled in the tray face.
2. Bed the door brick slab on the plug's inner face with
   refractory mortar. The plug and slab taper {{ P["door-plug-taper"] }} towards the chamber;
   keep the narrow end inwards.
3. Lay the fiber gasket strip around the slab's inner face; it
   seals against the front of the brick box.
4. Fit the door guard ({{ part("door-guard").name }}) on four 25 mm standoffs bolted through
   the tray face, outside the plug. Its hinge parts and latch body are welded on by the shop
   before coating. Fit its earth stud.

## 3. The final assembly

{{ build_step("asm://kiln") }}

### 3.1 Standoffs on the inner shell (before any lining)

1. Lay the inner shell ({{ part("outer-shell").name }}) on its back, opening up.
2. Fit twelve of the 25 mm standoffs ({{ part("m6-standoff-25").name }}), four on each of the
   left, right and top walls: an M6 × 16 bolt from inside the shell through each hole,
   tightened into a standoff on the outside. The bolt heads end up under the fiber board, so
   this must be done first. The four bottom standoffs go in on the stand (section 3.3).
3. Fit the shell's earth stud ({{ part("earth-stud").name }}) on bare metal at the back,
   scraping the coating off under the serrated washers.

### 3.2 Bolt the guard on

Before the guard goes on, bolt the four 40 mm standoffs ({{ part("m6-standoff-40").name }})
to the outside of its right wall from inside; the controls hang on them later. Slide the
ventilated guard ({{ part("guard-shell").name }}) over the shell from the back so its vent
slots are low on the sides and on top, and bolt it to the twelve standoffs from outside. Fit
its earth stud.

### 3.3 Put the body on the stand

1. Place the stand ({{ part("stand").name }}) and check it stands level.
2. With two people, lift the shell and the guard, not yet lined and so the lightest the body
   will be, onto the stand, the guard's bottom holes over the rivet nuts in the top rails.
3. At each bottom corner, put an M6 × 50 bolt ({{ part("m6x50-bolt").name }}) from inside the
   shell through the shell, a 25 mm standoff in the gap and the guard's bottom wall into the
   rail's rivet nut ({{ part("m6-rivnut").name }}), and tighten it. These four bolts carry the
   lining's weight into the stand, and their heads end up under the fiber floor.

### 3.4 Line the shell

1. Fiber boards first: a floor board ({{ part("fiber-slab").name }}), the back board
   ({{ part("fiber-back").name }}), the two side boards ({{ part("fiber-side").name }}), then
   the roof board. Each wall is {{ P["fiber-thickness"] }} of board; butt the joints tight and
   keep the tail and thermocouple holes in the back board in line with the shell's holes.
2. Then the bricks, bedded in refractory mortar: the floor slab, the two side liners with
   their grooves facing the chamber and open towards the door, the back liner between them,
   then the roof slab. Leave
   {{ P["lining-clearance"] }} between the brick box and the fiber on every side.
3. Push a ceramic bush ({{ part("ceramic-bush").name }}) into each element tail hole, and lay
   the element ({{ part("heating-element").name }}) in the grooves with its tails out through
   the bushes and the guard's rear openings.
4. Slide the two thermocouples ({{ part("thermocouple").name }}) in from the back through the
   guard, the shell, the fiber and the brick.

### 3.5 Hinge post and latch keeper

Bolt the hinge post to the guard's left wall with four M6
bolts and nuts, and the latch keeper ({{ part("latch-keeper").name }}) to the right wall with
two. The hinge parts on the post are welded on by the shop before coating.

### 3.6 Hang the door

With two people (the door is heavy), hang the door on the hinges of the hinge post. Close it
and check that the plug enters the opening without touching on any side and that the latch
({{ part("latch").name }}) draws it onto the gasket. Swing it fully open and check the plug's
corner clears the opening's edge.

### 3.7 Hang the controls

Hang the controls on the four 40 mm standoffs beside the guard's right wall, which gives
{{ P["controller-standoff"] }} of free air. The door switch is packed loose: fit it where the
closed door operates it. The electrician sets its position, connects the element, the
thermocouples and the door switch to the controls (installation manual), and then the lid
goes on (section 1).
