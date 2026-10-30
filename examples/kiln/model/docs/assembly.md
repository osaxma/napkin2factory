---
id: assembly
title: Assembly
audience: [owner, engineer, manufacturer]
order: 15
depends_on: [asm://kiln, asm://door, part://outer-shell, part://guard-shell, part://m6-standoff-25, part://m6-standoff-40, part://earth-stud, part://liner-slab, part://liner-side, part://liner-back, part://fiber-slab, part://fiber-side, part://fiber-back, part://refractory-mortar, part://heating-element, part://ceramic-bush, part://thermocouple, part://hinge-post, part://latch-keeper, part://door-tray, part://door-fiber, part://door-brick, part://door-guard, part://fiber-anchor, part://fiber-gasket, part://hinge, part://latch, part://controller-box, part://controller-lid, part://door-switch, part://m20-gland, part://rating-label, iface://guard-standoff-left, iface://guard-standoff-right, iface://guard-standoff-top, iface://guard-standoff-bottom, iface://door-guard-standoff, iface://guard-hinge-post, iface://guard-latch-keeper, iface://controller-mount]
---

# Assembly

Work on a clean bench. Wear gloves and a dust mask when handling brick and fiber board. Do
the steps in this order: some fixings cannot be reached once the lining is in.

## 1. Standoffs on the inner shell (before any lining)

1. Lay the inner shell ({{ part("outer-shell").name }}) on its back, opening up.
2. Fit the sixteen 25 mm standoffs ({{ part("m6-standoff-25").name }}), four on each of the
   left, right, top and bottom walls: an M6 bolt from inside the shell through each hole,
   tightened into a standoff on the outside. The bolt heads end up under the fiber board, so
   this must be done first.
3. Fit the shell's earth stud ({{ part("earth-stud").name }}) on bare metal at the back,
   scraping the coating off under the serrated washers.

## 2. Line the shell

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
   the bushes.

If the body has to be lifted onto its stand, stop after the fiber boards: do section 3, lift
the body onto the stand (installation manual), then lay the bricks and the element through
the front opening and fit the thermocouples last. The bricks are the heavy part of the lining.

## 3. Bolt the guard on

Slide the ventilated guard ({{ part("guard-shell").name }}) over the shell from the back so
its vent slots are low on the sides and on top, threading the element tails through its rear
openings, and bolt it to the sixteen standoffs from outside. Fit its earth stud. Then slide
the two thermocouples ({{ part("thermocouple").name }}) in from the back through the guard,
the shell, the fiber and the brick.

## 4. Hinge post and latch keeper

Bolt the hinge post to the guard's left wall with four M6
bolts and nuts, and the latch keeper ({{ part("latch-keeper").name }}) to the right wall with
two. The hinge parts on the post are welded on by the shop before coating.

## 5. The door, built as one unit

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

## 6. Hang the door

With two people (the door is heavy), hang the door on the hinges of the hinge post. Close it
and check that the plug enters the opening without touching on any side and that the latch
({{ part("latch").name }}) draws it onto the gasket. Swing it fully open and check the plug's
corner clears the opening's edge.

## 7. Controller box

1. Hang the controller box ({{ part("controller-box").name }}) beside the guard's right wall
   on four 40 mm standoffs ({{ part("m6-standoff-40").name }}), which gives
   {{ P["controller-standoff"] }} of free air.
2. Fit the temperature controller and the limit controller through the two front cutouts,
   and the solid-state relay and the contactor on the base. Fit the box's earth stud.
3. Fit the three cable glands ({{ part("m20-gland").name }}) in the base. Fit the door switch where
   the closed door operates it; the electrician sets
   its position and does all the wiring (installation manual).
4. Screw the lid ({{ part("controller-lid").name }}) on with four self-tapping screws.
5. Rivet the rating label ({{ part("rating-label").name }}) to the box front.
