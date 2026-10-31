# Designer (roles/design.md)

**What and when:** Designer role for a napkin2factory product — compose kit generators (starting from the promoted concept and style.yaml), run the render inner loop, use interfaces, log decisions, write calcs. Use when parts, assemblies or geometry need to be created or changed.

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

## After the napkin stage
When a concept card has been promoted (`n2f concept list` shows it `promoted`; its
decision is in `model/decisions.yaml`), the owner has already chosen the form. Start from it:
- **The promoted card's `massing` is the starting layout.** Use the same kit calls at
  full fidelity: each line becomes a part (`model/parts/<id>.yaml`) and its `at:` becomes
  a `place(...)` in the top assembly. Replace the stand-ins with real parts (a `plate` lid
  over an `enclosure` becomes the real shell panels, a solid `block` of controls becomes
  the control box, the stand a real `frame`), and point the arguments at the parameters
  promotion seeded (`param://chamber-width`, `param://insulation`, …), never at raw numbers.
- **Read `style.yaml` and respect it.** Give every visible part its `role:` (`body`,
  `door`, `stand`, `controls`, `trim`; `lining`, `fastener` for the rest): the role picks
  its colour and finish, and only `body`/`door`/`stand`/`controls`/`trim` parts take the
  style's shape defaults — corner radius, chamfer, panel reveal, frame overhang, vent
  pattern, radius scale. Leave those arguments unset so the style decides. Override one on
  a part only with a logged `DEC-xxx` that says why.
- **Form requirements are checked like any other.** Before composing, read the rows in
  `model/requirements.yaml` with `verify: {kind: rule, target: rule://form-v0/…}` (rounded
  exposed corners, no visible fasteners on the front, where the controls sit) and the
  site rows (alcove width with the door swing, the supply); `n2f check` runs them with
  everything else. If promotion ran before any assembly existed, those rows are
  `unallocated` (the alcove one `kind: manual`): once the top assembly exists, point them
  at it (`asm://<top>#props.bbox.x`, the limit from the requirement's rationale) and log
  the change as a decision. Form rows stay `needs your sign-off` (and `n2f lint` warns
  L12) until the body, door, stand, controls and trim parts carry `role:` — set the roles
  so the rows are checked, rather than asking the owner to sign them off.
- **Never edit `concepts/` after promotion** except the status fields that `n2f concept
  reject` and `promote` write; the cards are the record of what was chosen and why. Never
  make a card an input to geometry, a calc or a build rule: everything the factory needs
  was copied into the model at promotion. A new direction is a new card and, once the
  product exists, a change request.

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
