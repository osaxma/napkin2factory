---
name: n2f-design
description: Designer role for a napkin2factory product — compose kit generators, run the render inner loop, use interfaces, log decisions, write calcs. Use when parts, assemblies or geometry need to be created or changed.
---

# n2f-design: the designer

## Compose the kit first
Every part starts as a kit generator call in `model/parts/<id>.yaml`:
`geometry: {kit: plate|panel|block|tube|hole_pattern|bracket_l|enclosure|frame, args: {...}}`.
Arguments reference parameters (`param://wall-thickness`), never raw numbers, so a change
request can move them. Drop to a module (`geometry: {module: geometry/<id>.py}` exposing
`build(P, I, kit) -> PartResult`) only for what no generator covers, and still build from
`kit.*` inside it. Sibling helpers in `model/geometry/` may be imported.

Every custom part declares `process`, `material: {name, spec}`, `finish`,
`tolerance_class` (ISO2768-f/m/c/v) and a `cost: {unit, basis: estimate}`; every bought
part declares `kind: cots`, `source: {vendor, mpn, url, verified: false}` and a cost. Parts
without 3D (`geometry: none`) are BOM-only and show as a warning.

## Assemblies
`model/assemblies/<id>.yaml` declares children with quantities (that is the BOM);
`model/geometry/<id>.py` places them: `def build(P, I, parts)` returning
`AssemblyResult` with `place("part://x", parts["x"], translate=(…), rotate=(…), label="…")`
or `grid(...)` for courses of bricks. The checker verifies placed counts equal quantities.
Set `exploded: {axis, spacing}` to the stacking axis.

## Inner loop: look before you claim
After every geometry edit:
```
n2f validate
n2f build --target geometry --part <id>
```
Open `build/parts/<id>/renders/iso.png`, `front.png`, `top.png`, `right.png`,
`section.png` and read `build/parts/<id>/props.json` (bbox, volume, mass). Compare with
the requirement envelope. Use `docs/render-checklist.md` in the system repo as the list.
If the render does not look like the part, it is not the part.

## Interfaces
Two parts that bolt or sit together share an `iface://` file
(`kind: bolt-pattern | mating-face`, `parties`, `frame`, per-party `frames`, `spec`). List
it on both parts; the build cuts the pattern into both in their own frames and `n2f check`
verifies they agree. Never hard-code a mating hole pattern in two places.

## Decisions
Every material, thickness, process or sizing choice is a `DEC-xxx` with `links:` to the
requirements and parameters it affects and `sources:` for any number taken from a
datasheet or standard. Numbers you could not confirm get `verify: true`.

## Calcs
`model/calcs/<topic>.py` functions take `P` (and optionally `I`) and return pint
quantities (`from napkin2factory.core.units import Quantity`). Cite the formula and source in
the docstring; add `model/tests/test_calcs.py` with a value you checked by hand.
Requirements reference them as `calc://<topic>.<function>`.

## Done means
`n2f check` shows no `fail`; every custom part has renders you looked at; instance counts
match; every sheet-metal part has a flat pattern DXF under `build/drawings/`; every
decision is logged.
