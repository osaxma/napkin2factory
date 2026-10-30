---
id: manufacturer-notes
title: Manufacturer package notes
audience: [manufacturer, engineer]
order: 40
depends_on: [part://outer-shell, part://guard-shell, part://door-tray, part://door-guard, part://controller-box, part://controller-lid, part://hinge-post, part://latch-keeper, part://stand, part://liner-side, part://liner-back, part://liner-slab, part://door-brick, part://door-fiber, part://fiber-side, part://fiber-back, part://fiber-slab, part://rating-label]
---

# Manufacturer package notes

This package is a Revision of a complete technical data package: STEP models of every custom
part, drawings, flat-pattern DXFs, a bill of materials and these notes. Quote per part;
quantities are in the BOM. The STEP models ship with the package and govern the shape; the
drawings and DXFs carry every hole.

## Sheet-metal shop

General: every box may be built as a multi-piece weldment (a wrap plus two end panels, or
panels on corner angles) joined by spot welds or rivets, with closed corners. The one-piece
flat patterns are reference developments only; the inside dimensions are what matter. All
holes are in the DXFs. Deburr every edge before coating.

- {{ part("outer-shell").name }}: {{ part("outer-shell").material.spec }},
  {{ part("outer-shell").tolerance_class }}. Critical inside dimensions
  {{ P["shell-inner-width"] }} wide × {{ P["shell-inner-height"] }} high ×
  {{ P["shell-inner-depth"] }} deep (the fiber box must fit). Sixteen
  Ø{{ P["mount-bolt-clearance"] }} standoff holes (four per wall), two
  Ø{{ P["tail-hole-shell"] }} element tail holes and two Ø{{ P["thermocouple-hole-shell"] }}
  thermocouple holes in the back. Finish: {{ part("outer-shell").finish }}, outside only;
  inside bare.
- {{ part("guard-shell").name }}: {{ part("guard-shell").material.spec }},
  {{ part("guard-shell").tolerance_class }}. Critical inside opening: the shell plus
  {{ P["guard-gap"] }} each side. Holes: four stand mounting holes, sixteen standoff holes,
  four for the hinge post, two for the latch keeper, four for the controller mount, the rear
  tail openings (Ø{{ P["tail-hole-guard"] }}) and thermocouple holes. The vent slots must stay
  open. Finish: {{ part("guard-shell").finish }}.
- {{ part("door-tray").name }}: {{ part("door-tray").material.spec }}, four standoff holes.
  Fiber-anchor holes are drilled on assembly. Finish: {{ part("door-tray").finish }}.
- {{ part("door-guard").name }}: {{ part("door-guard").material.spec }}, vent slots top and
  bottom, four standoff holes. The two hinge parts on the left wall and the latch body on the
  right wall are welded on before coating. Finish: {{ part("door-guard").finish }}.
- {{ part("controller-box").name }}: {{ part("controller-box").material.spec }}. Two
  instrument cutouts {{ P["controller-cutout"] }} +0.6/0 (48 × 48 DIN), three
  Ø{{ P["gland-hole"] }} gland holes in the base, four mounting holes in the left wall.
  {{ part("controller-lid").name }}: {{ part("controller-lid").material.spec }}, flat.
  Finish for both: {{ part("controller-box").finish }}.

## Powder coat

Two systems (DEC-007):

- Inner shell and door tray, outside only: {{ part("outer-shell").finish }}.
- Every other steel part: standard polyester, {{ part("guard-shell").finish }}.

Mask threads and the bare-metal spots under the earth studs.

## Fabrication and welding

- {{ part("hinge-post").name }}: {{ part("hinge-post").material.spec }}, four M6 clearance
  holes; the hinge parts are welded to the outward leg before coating. Do not substitute a
  thinner angle: it carries the door.
- {{ part("latch-keeper").name }}: {{ part("latch-keeper").material.spec }}, two M6 clearance
  holes.
- {{ part("stand").name }}: {{ part("stand").material.spec }}; cut list on the drawing; weld
  all joints. Drill the four Ø{{ P["mount-bolt-clearance"] }} holes in the top rails and set
  M6 rivet nuts in them before coating (the rails are hollow).

## Refractory supplier

- Insulating firebrick K23 ({{ part("liner-side").material.spec }}): cut to the drawings for
  {{ part("liner-slab").name }}, {{ part("liner-side").name }}, {{ part("liner-back").name }}
  and {{ part("door-brick").name }}. Pieces larger than a standard brick come from
  large-format K23 if available; otherwise make them from two pieces with a vertical mortar
  joint kept away from the grooves. Saw-cut faces.
- Grooves: {{ P["element-grooves-per-wall"] }} per wall,
  {{ P["element-groove-width"] }} × {{ P["element-groove-depth"] }}, on the chamber face of
  the side liners and the back liner. On the side liners they run from the front face over the
  chamber depth and end blind at the back, where the back liner butts against them. The back
  liner also carries the element tail holes (Ø{{ P["tail-hole-brick"] }}) and the thermocouple
  holes (Ø{{ P["thermocouple-hole"] }}).
- {{ part("door-brick").name }} and {{ part("door-fiber").name }}: sides taper
  {{ P["door-plug-taper"] }} towards the chamber (see the drawings).
- Ceramic fiber board 1260 class: boards to the panel drawings, {{ P["fiber-thickness"] }}
  per wall from 50 + 50 + 25 mm boards. The door plug is bonded from boards
  ({{ part("door-fiber").material.spec }}). Brush rigidizer on every fiber face left exposed
  (the plug's sides and inner face, the front edge of the fiber box at the opening).

## Open points for quotation

- Standoffs, fasteners, rivet nuts, earth studs, glands, bushes and fiber anchors are stock
  parts; supply from stock to the BOM.
- Refractory mortar, the gasket strip, ceramic staples and the element wire are consumables;
  supply from stock.
