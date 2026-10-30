---
id: manufacturer-notes
title: Manufacturer package notes
audience: [manufacturer, engineer]
order: 40
depends_on: [part://outer-shell, part://guard-shell, part://controller-box, part://door-skin, part://stand, part://liner-side, part://liner-back, part://liner-slab, part://door-brick]
---

# Manufacturer package notes

This package is a Revision of a complete technical data package: STEP models, drawings,
flat-pattern DXFs, a bill of materials and these notes. Quote per part; quantities are in
the BOM.

## Sheet-metal shop

- {{ part("outer-shell").name }}: {{ part("outer-shell").material.spec }},
  {{ part("outer-shell").finish }}, {{ part("outer-shell").tolerance_class }}. Open corners
  with reliefs; do not weld the corners. Four Ø{{ P["mount-bolt-clearance"] }} holes in the
  bottom wall and the hinge holes on the front lip are in the flat pattern.
- {{ part("guard-shell").name }}: {{ part("guard-shell").material.spec }},
  {{ part("guard-shell").finish }}. Vent slots per the DXF must stay open.
- {{ part("controller-box").name }}: {{ part("controller-box").material.spec }}, with the
  48 × 48 mm controller cutout and the cable entry.
- {{ part("door-skin").name }}: flat, {{ part("door-skin").material.spec }}, hinge holes
  per DXF.
- Deburr every edge before coating. Mask the hinge and mount holes.

## Fabrication / welding

- {{ part("stand").name }}: {{ part("stand").material.spec }}; cut list in the BOM sheet
  "Manufacturer"; weld all joints; powder coat after drilling the four Ø{{ P["mount-bolt-clearance"] }}
  mounting holes in the top rails.

## Refractory supplier

- Insulating firebrick K23: cut to the sizes in the drawings for {{ part("liner-slab").name }},
  {{ part("liner-side").name }} (with {{ P["element-grooves-per-wall"] }} grooves
  {{ P["element-groove-width"] }} × {{ P["element-groove-depth"] }}), {{ part("liner-back").name }}
  and {{ part("door-brick").name }}. Saw-cut faces, ±2 mm.
- Ceramic fiber board 1260 class: boards to the panel drawings, {{ P["fiber-thickness"] }}
  total thickness per wall from 50 + 50 + 25 mm boards.

## Open points for quotation

- Standoffs for the guard (M6 × 25 mm spacers, 16 off) are not drawn; supply from stock.
- Refractory mortar, ceramic staples and the element tails are consumables; supply from stock.
