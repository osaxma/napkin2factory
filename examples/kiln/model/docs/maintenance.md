---
id: maintenance
title: Maintenance
audience: [owner, engineer]
order: 30
depends_on: [req://REQ-009, req://REQ-018, req://REQ-019, part://heating-element, part://liner-side, part://liner-back, part://thermocouple, part://ceramic-bush, part://fiber-gasket, part://door-fiber, param://element-wire-diameter, param://element-coil-diameter, param://element-grooves-per-wall]
---

# Maintenance

Before any work: switch off and lock off the kiln at the circuit isolator, and let it cool to
room temperature.

## Element replacement

The {{ part("heating-element").name }} is a consumable. Expect to replace it after a few
hundred firings, or when the kiln can no longer reach temperature or the controller shows an
open circuit.

1. Isolate the kiln at the circuit isolator and lock it off. Let it cool.
2. Have the electrician disconnect the element tails at the back.
3. Open the door and lift the old coil out of the grooves: {{ P["element-grooves-per-wall"] }}
   in each of the two side liners and {{ P["element-grooves-per-wall"] }} in the back liner.
   Old wire is
   brittle and the brick is soft: do not pry.
4. Wind the new coil from {{ P["element-wire-diameter"] }} wire to
   {{ P["element-coil-diameter"] }} outside diameter. The wire length is in the report
   (calc://element.wire_length); stretch the coil evenly so it fills every groove without
   turns touching (calc://element.pitch_factor).
5. Lay it in the grooves, pinning it with ceramic staples every 100 mm, and pass the tails
   out through the two ceramic bushes in the back wall ({{ part("ceramic-bush").name }}).
6. Have the electrician reconnect the tails and re-check the earth bonding.
   {{ req("REQ-019").statement }}
7. Run a slow conditioning firing to 200 degC before the next full firing.

## Thermocouples

There are two thermocouples in the back wall ({{ part("thermocouple").name }}): one for the controller and
one for the over-temperature cut-out. Replace a probe when its reading drifts, when the two
readings disagree noticeably at a steady hold, or when the ceramic sheath cracks or flakes.
Replace it with the same type and sheath. After changing either probe, have the cut-out tested
again: {{ req("REQ-018").verify.note }}

## Door gasket

The fiber gasket strip seals the door's brick slab against the chamber
front. Renew it when it is flattened, torn or crumbling, or when heat marks or light show at
the door edge. Fit a new strip in the same place and close the door to bed it.

## Bricks and fiber

Inspect the grooves, the door plug and the door brick for cracks after every ten firings.
Hairline cracks are normal in insulating brick; replace a liner when a piece can move. The
exposed faces of the {{ part("door-fiber").name | lower }} are hardened with rigidizer;
re-coat them if they start to dust.

## Door switch

At the same ten-firing inspection, check the door switch: with the controller calling for
heat, opening the door must stop the element. If it does not, stop using the kiln and call the
electrician. {{ req("REQ-009").statement }}
