---
id: assembly
title: Assembly
audience: [owner, engineer, manufacturer]
order: 15
depends_on: [asm://kiln, asm://door, part://outer-shell, part://guard-shell, part://liner-slab, part://liner-side, part://liner-back, part://fiber-slab, part://fiber-side, part://fiber-back]
---

# Assembly

Work on a clean bench. Wear gloves and a dust mask when handling brick and fiber board.

## Insulated body

1. Lay the {{ part("outer-shell").name | lower }} on its back (opening up).
2. Line the shell: a {{ part("fiber-slab").name | lower }} on the bottom, a
   {{ part("fiber-back").name | lower }} against the back, two
   {{ part("fiber-side").name | lower }}s, then the second slab on top. Boards are
   {{ P["fiber-thickness"] }} total per wall; butt the joints tight.
3. Fit the brick: one {{ part("liner-slab").name | lower }} as the floor, the two
   {{ part("liner-side").name | lower }}s with their grooves facing the chamber, the
   {{ part("liner-back").name | lower }}, then the second slab as the roof. Bed joints in
   refractory mortar.
4. Stand the body up and fit the {{ part("guard-shell").name | lower }} on its 25 mm
   standoffs (M6, four per side, by the installer) so the vent slots are low at the sides.

## Door

Build the door as its own unit: skin, fiber board, brick plug (see the door drawing), two
hinges on the left edge, latch on the right. Hang it on the shell's hinge holes.

## Controller box

Mount the box beside the right wall with {{ P["controller-standoff"] }} of free air. Fit the
PID controller through the front cutout and the relay on the base. Wiring is the
electrician's (see installation).
