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
`model/geometry/<id>.py` places them: `def build(P, I, parts)` returning `AssemblyResult`.
A part joined to one already placed is placed **by its interface**:
`res.add(place_by(I, res, "<iface-id>", "part://x", parts["x"], label="…"))`. The code does
the arithmetic: the part turns so its frame points the same way as the placed party's and
lands `offset` along the normal. Add `onto="<label>"` when the other party is placed more
than once; place the other party first. Only a part with no interface to anything already
placed (the first one, a loose lining brick) uses
`place("part://x", parts["x"], translate=(…), rotate=(…), label="…")`, or `grid(...)` for
courses of bricks. `n2f check` warns when two joined parts are both placed by coordinates.
The checker verifies placed counts equal quantities.
Set `exploded: {axis, spacing}` to the stacking axis.

A sub-assembly joins the rest only through **ports**. An interface always joins two parts,
never an assembly. When its two parts sit in different assemblies, list it under
`ports: [iface://…]` in every sub-assembly between each part and the assembly holding both;
`n2f validate` names the file when one is missing. The parent then places the whole
sub-assembly by that joint, after the other part:
`res.add(place_by(I, res, "<iface-id>", "asm://door", parts["door"], label="door"))`
(`inner="<label>"` picks the part's occurrence inside it when there are several). A
sub-assembly never reads or places its siblings' parts.

Every sub-assembly says how it is built. A **unit** (`build: unit`, the default) is put
together on its own and fitted whole; give it `driver: [...]`, why: `built-as-unit`,
`tested-as-unit`, `serviced-as-unit`, `separate-process-or-supplier`, `varies` or
`agent-context` (`n2f lint` asks). A grouping with no such reason is `build: phantom`: its
lines fold into the step of the unit around it. The build plan (report, `bom.xlsx`, one
assembly sheet per unit) comes from this; in a manual, `{{ build_step("asm://door") }}` prints
a step's parts, joints and hardware. Count joint hardware on the interface:
`spec.hardware: [{part: part://m6-standoff-25, per_hole: 1}, {part: part://m6x16-bolt,
per_hole: 2}]` (`per_joint:` on a mating face); list those parts in the assembly where the joint
closes (the lowest one holding both parts). Where two joints share holes, list each item once,
on the joint it closes. `n2f check` fails a shortfall and warns a surplus unless the line says
`spare: "<reason>"`; `loose: true` marks a line packed loose for the installer.

## Start flat; split for a reason
A product starts as one assembly. Make a sub-assembly only when one of the reasons above
applies (it is built, tested or serviced as one unit, made by another process or supplier,
or comes in variants), or when the module's working context would be more than one agent
can hold (`agent-context`): split when `n2f context asm://<id>` prints more than 32 kB
(`n2f context asm://<id> | wc -c`). That is the reference kiln's measure (S-114): as one flat
module its context is 50 kB; split into the door (17 kB) and the controls (11 kB), its largest
module, the kiln with its lining, is 31 kB. It is a line drawn on one product, not a measured
limit of any agent: the geometry code the context lists comes on top. Splitting later is cheap, because every joint is already an explicit
interface: move the parts into the new assembly file, list the joints that now cross its
edge under `ports:`, and place it by one of them. A sub-assembly with no reason is handling
overhead: fold it back into its parent, or mark it `build: phantom`.

Each unit keeps its own sizes: give a parameter only that unit uses `scope: asm://<id>`, and
`export: true` to one its parent must read (the door's outside width the hinge post reaches
to). A unit's parts never read a sibling unit's sizes: move such a size up to the parent, or
let a joint carry it. Work on one unit with `n2f context asm://<id>` (its files, its sizes,
its ports), `n2f build --asm <id>` and `n2f check --scope asm://<id>`; then `n2f build && n2f
check` for the joints between units.

## After the napkin stage
When a concept card has been promoted (`n2f concept list` shows it `promoted`; its
decision is in `model/decisions.yaml`), the owner has already chosen the form. Start from it:
- **The promoted card's `massing` is the starting layout.** Use the same kit calls at
  full fidelity: each line becomes a part (`model/parts/<id>.yaml`) and its `at:` becomes
  a `place(...)` in the top assembly. Replace the stand-ins with real parts (a `plate` lid
  over an `enclosure` becomes the real shell panels, a solid `block` of controls becomes
  the control box, the stand a real `frame`), and point the arguments at the parameters
  promotion seeded (`param://chamber-width`, `param://insulation`, …), never at raw numbers.
- **The modules the card named are already there, empty.** When the card had `modules:`
  and the product had no assembly yet, promotion wrote the top assembly
  (`model/assemblies/<product>.yaml`, one `asm://` child per module) and one stub per
  module (`children: []`, its `build`/`driver` from the card). Fill each stub with the
  parts of its massing lines (lines without a module go in the top assembly), give it its
  geometry module, list its `ports:` and place it in the top assembly by one of them.
  `n2f check` shows an empty stub as worth a look ("has no parts yet") until it has parts.
  Each module also got three size budgets (`asm://<module>#props.bbox.x`, `.y`, `.z`, at
  most the size of its rough shapes, computed): design the module within them; changing
  one is a decision (`DEC-xxx`), never a quiet edit. When the product already had its
  assemblies, promotion only printed the modules as a suggestion: split one off only
  where its reason holds (above).
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
(`kind: bolt-pattern | mating-face`, `parties`, per-party `frames`, `offset`, `spec`). List
it on both parts; the build cuts the pattern into both in their own frames and `n2f check`
verifies they agree and that, placed, the frames meet. Never hard-code a mating hole pattern
in two places.
- **One convention.** Write each party's frame (`origin`, `normal`, `x_axis`) in that part's
  own coordinates so that, once placed, both normals and both x axes point the same way.
  `offset` is the signed distance along the normal from the first party's frame to the
  second's (a standoff's length, a sheet's thickness; default 0). List the party placed
  first first, so the offset reads from it.
- **Coordinates are expressions, not helper parameters.** A coordinate or the offset may be
  `{expr: "-shell-outer-width / 2", unit: mm}` (the same grammar as a parameter `expr`).
  Never add a parameter only to write a frame.

## Decisions
Every material, thickness, process or sizing choice is a `DEC-xxx` with `links:` to the
requirements and parameters it affects and `sources:` for any number taken from a
datasheet or standard. Numbers you could not confirm get `verify: true`.
A candidate to combine two parts, from the verifier's review of a joint between units, is
logged the same way when you or the owner take it up: `links:` to the joint (`iface://…`)
and both parts, so the report shows it beside that joint.

## Calcs
`model/calcs/<topic>.py` functions take `P` (and optionally `I`) and return pint
quantities (`from napkin2factory.core.units import Quantity`). Cite the formula and source in
the docstring; add `model/tests/test_calcs.py` with a value you checked by hand.
Requirements reference them as `calc://<topic>.<function>`.

## Done means
`n2f check` shows no `fail`; every custom part has renders you looked at; instance counts
match; every sheet-metal part has a flat pattern DXF under `build/drawings/`; every
decision is logged.
