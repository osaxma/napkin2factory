---
name: n2f-design
description: Designer role for a napkin2factory product — compose kit generators, run the render inner loop, use interfaces, log decisions, write calcs.
---

# n2f-design: the designer

## Compose the kit first
Every part starts as a kit generator call in `model/parts/<id>.yaml`
(`geometry: {kit: plate|bracket_l|enclosure|frame|panel|block|tube|hole_pattern, args: {...}}`).
Arguments reference parameters (`param://wall-thickness`) rather than numbers. Drop to a
custom module (`geometry: {module: geometry/<id>.py}` exposing `build(P, I, kit)`) only for
what no generator covers, and still build from `kit.*` inside it.

## Inner loop: look before you claim
After every geometry edit:
```
n2f validate
n2f build --target geometry --part <id>
```
Then open `build/parts/<id>/renders/iso.png`, `front.png`, `top.png`, `right.png` and
read `build/parts/<id>/props.json` (bbox, volume, mass). Compare against the requirement
envelope. If the render does not look like the part, it is not the part.

## Interfaces
Two parts that bolt or sit together share an `iface://` file. Both generators read it
through `I["<iface-id>"]` and place the same pattern; `n2f check` verifies they agree.
Never hard-code a mating hole pattern in two places.

## Decisions
Every material, thickness, process, or sizing choice becomes a `DEC-xxx` with
`links:` to the requirement and parameters it affects and `sources:` for any number
taken from a datasheet or standard. Mark uncertain numbers `verify: true`.

## Calcs
`model/calcs/<topic>.py` functions take pint quantities and return pint quantities.
Each cites its formula and source in the docstring and has a test in
`model/tests/test_calcs.py` pinned to a hand-checked value. Requirements reference
them as `calc://<topic>.<function>`.

## Done means
`n2f check` shows no `fail`; every custom part has renders you have looked at; the
assembly instance counts match the YAML quantities; every sheet-metal part has a flat
pattern in `build/drawings/`.
