---
id: maintenance
title: Maintenance
audience: [owner, engineer]
order: 30
depends_on: [part://heating-element, part://liner-side, part://liner-back, part://thermocouple, param://element-wire-diameter]
---

# Maintenance

## Element replacement

The {{ part("heating-element").name }} is a consumable. Expect to replace it after a few
hundred firings, or when it reads open on the controller.

1. Isolate the kiln at the circuit isolator and lock it off. Let it cool.
2. Open the door; remove the thermocouple (it passes through the back wall).
3. Lift the old coil out of the grooves in the two {{ part("liner-side").name | lower }}s
   and the {{ part("liner-back").name | lower }}. The brick is soft: do not pry.
4. Wind the new coil from {{ P["element-wire-diameter"] }} wire to the length in the
   report (calc://element.wire_length) and lay it in the grooves, pinning it with
   ceramic staples every 100 mm.
5. Have the electrician reconnect the element tails. Run a 200 degC conditioning firing.

## Bricks and fiber

Inspect the grooves and the door brick for cracks after every ten firings. Hairline cracks
are normal in K23; replace a liner when a piece can move.

## Thermocouple

Replace the {{ part("thermocouple").name }} when readings drift or the sheath flakes.
