---
id: build-and-care
title: Building and caring for the table
audience: [owner, engineer, manufacturer]
safety: true
order: 1
depends_on: [param://centre-load, param://edge-load, param://humidity-low, param://humidity-high, param://glide-height, param://frame-inset, param://slot-length, param://insert-hole, part://top-board, part://apron-frame, part://wood-insert-m8, part://mounting-bolt-m8, part://leveling-foot, req://REQ-009]
---

# Building and caring for the table

The {{ part("top-board").name }} sits on the {{ part("apron-frame").name }}. This page is the safety
notes, the build order and the care of the oak, in one place because the table is an everyday
product.

## Safety

- **Tipping.** The table is built to stay up under {{ P["edge-load"] }} (50 kg) pressed down at the middle of any edge when it is empty ({{ req("REQ-009").statement }}). Do not stand or climb on it, and do not load one edge heavily while the other is empty. A person has to check and sign this requirement: the calculation alone does not close it.
- **Rated load.** It is built to take {{ P["centre-load"] }} (150 kg) at the middle of the top, and a vise and tools (50 kg) may stay on it.
- **Moving it.** The table weighs about {{ bom.total_mass }} in all. Two people lift it, one at each end, by the top; carry it level and do not drag it on its glides.
- **Edges.** Break (lightly round) the sharp edges of the steel before the powder coat. The oak edges are eased by the woodworker.

## Building it

1. **Top.** Fit the {{ part("wood-insert-m8").name }} in each of the eight bores under the top (screwed in by hand with the insert driver, flush with the bore). Wipe off dust, oil the underside as well as the top, and let it cure.
2. **Frame.** Lay the top face down on a soft blanket. Place the frame on it, {{ P["frame-inset"] }} in from every edge, tabs against the top.
3. **Fixings.** Screw the eight {{ part("mounting-bolt-m8").name }} through the tabs into the inserts. The six long-rail tabs have slots across the width: tighten these only until the washer touches, so the top can slide. The two short-rail tabs have round holes and hold the top's centreline: tighten these snug.
4. **Glides.** Thread the four {{ part("leveling-foot").name }} into the leg ends, each set to about {{ P["glide-height"] }}; stand the table up with two people and adjust the glides until it is level and all four are loaded.

## Care of the oak

The solid oak top is not a fixed size: it swells and shrinks across its grain with the room's humidity, by a couple of centimetres across its width between {{ P["humidity-low"] }} and {{ P["humidity-high"] }} relative humidity. The slots ({{ P["slot-length"] }} long, {{ P["insert-hole"] }} wide) let it do that.

- Never fix the top rigidly to the frame along both long edges; keep the slotted fixings loose enough to slide.
- Keep it away from radiators and open windows in winter, and wipe spills quickly.
- Clean with a damp cloth. Renew the hardwax oil when water stops beading.
- If a screw is found tight on a slotted tab, loosen it a quarter turn.
