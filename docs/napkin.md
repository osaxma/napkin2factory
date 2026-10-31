# The napkin stage: concept screening

Concept cards (`concepts/C-xxx.yaml`, NAPKIN_STAGE §3) are cheap directions for the
product. `n2f concept build C-xxx` (or `--all`) turns one into rough shapes and a
**screening**: a handful of numbers and rule outcomes that say, in seconds, whether the
direction holds up. Screening is not verification — it is a third tier for ideas, and
everything it writes lives outside the build (`build/concepts/`, never in the manifest;
deleting `concepts/` changes no build output).

## What a build does

1. **Massing.** Each `massing:` line is a kit call run at massing fidelity (silhouettes:
   no holes, bends or fillets, but the same argument checks as a full build, so an
   impossible shape fails for real). `at: {x, y, z, rz}` places it; `material:` gives it
   a mass; `process_class:` picks its cost band (default: the generator's own process).
   Cards cannot refer into the model (`param://…`): write the number itself.
2. **Artifacts** under `build/concepts/C-xxx/`: `massing.glb` (one node per call,
   `concept://C-xxx/<as>`), `props.json`, `features.json`, `screening.json` and
   `renders/` (plain z-buffer pictures for checking shape, not for judging looks).
3. **Screening**, written back into the card's `screening:` block.
4. **Styled screenshots** (`renders/styled-iso.png`, `styled-front.png`, 1200 × 900): the
   product image to show and judge (see "Styling" below).

## The two labels

Every number carries a label, in the card, in JSON and on screen:

- **`computed`** — measured from the massing shapes: `width`, `depth`, `height` (the
  bounding box), `volume`, `mass` (only when every call declares a `material`), and
  `footprint_with_door_swing`.
- **`estimate`** — from the calc kit ([calckit.md](calckit.md)) fed with the card's
  `envelope` numbers: `heat_loss`, `skin_temperature`, `stored_heat`, `heat_up_time`
  (from `envelope.power`) or `required_power` (from `envelope.heat_up_time`),
  `insulation_mass`, `total_mass`, `current`, `circuit_class`, `cost_low`/`cost_high`,
  `lift_class`. Each names the calc-kit function it came from.

A missing input never becomes an invented number: the estimate is left out and a note says
what would unlock it. When the card is silent, screening states its defaults: room 25 degC,
skin film coefficient 5 W/m²K, emissivity 0.9, hot face 1200 degC; a bare
`insulation: 170 mm` is one ceramic-fiber-board layer (the kiln's values); layers named
`brick`/`K23` or `fiber` take the kiln's K23 and fiber-board values; `shell` layers grow
the box without resistance or stored heat. All of these are `[verify]`.

## The rules (`rulepacks/concept-v0.yaml`)

| rule | fails when |
|---|---|
| `fits-site-width` | width + the open door > `site.alcove_width`. A hinged door (`layout.door: hinged-left/right`) adds its own width beside the hinge (the `door` massing call, else `envelope.door_width`) |
| `fits-site-depth`, `fits-site-height` | depth/height exceed `site.alcove_depth`/`alcove_height` |
| `circuit-available` | the current × 1.2 headroom exceeds `site.circuit` (e.g. `240V-13A`) or every class on file for `site.region`; an unknown region only warns |
| `mass-vs-lift-class` (warning) | the mass needs more than a two-person lift, or more than `site.lift_class` |
| `blank-vs-stock-sheet` | a sheet-metal call's flat blank (open box: (L + 2H) × (W + 2H)) fits no stock sheet on file |
| `walls-fit-envelope` | chamber + 2 × insulation does not fit inside the `body` call |
| `controls-not-adjacent-hot-face` (warning) | controls sit on top or beside the door, in the hot air path |

A failing rule makes the card **red**; warnings never do. Red is information: the card
keeps its reasons, `n2f concept build` prints them under "this direction has problems:"
and still exits 0.

## Styling: `style.yaml` and the styled screenshots

`style.yaml` (seeded by `n2f init --style industrial|appliance|lab`; `industrial` when the
file is missing) holds the product's look: a `preset`, a `palette` and a `finish` per **part
role** (`body, door, stand, controls, trim, lining, fastener, default`), a `background`, an
`accent`, and shape cues (`radius_scale`, `corner_radius`, `chamfer`, `reveal`, `overhang`,
`vent_pattern`, `fastener_visibility`). Anything the file leaves out comes from its preset.
Finishes are rendering factors (`powder-coat`, `brushed-steel`, `painted`, `ceramic`,
`anodized`, `plastic`), not engineering numbers. A card's `style:` sketch lays over the
product's style for that card's pictures (a different `preset` starts from that preset);
keys the schema does not know are noted and skipped.

Each massing call has a role: its `role:` if given, else its `as` name when that is a role
word (`as: door` is a door), else `default`. `n2f concept build` renders every card through
the same inline viewer the report uses — one self-contained page per card
(`renders/styled.html`), the role's colour and finish on each node, a fixed studio rig (key,
fill and rim lights, a soft environment, a contact shadow), an iso and a front camera — in
one headless browser page reused across cards, and saves the two PNGs. The output line names
the styled iso; `--json` carries `screenshots: {method, paths, notes}`.

When Playwright or its Chromium is missing (or `N2F_NO_PLAYWRIGHT=1`), the z-buffer renders
are copied to the styled names, `method` is `zbuffer-fallback`, and the card's screening
notes say "styled screenshots unavailable (…): showing correctness renders [revisit]" (also
printed once, dim, on stderr). Z-buffer renders are for correctness, viewer screenshots for
appearance (D12 as amended, N6). Judge the pictures with `docs/render-checklist.md`,
"Product image".

## The board: `n2f concept board`

`build/concepts/board.html` puts every card side by side, in id order, for one decision.
It is read-only — choosing happens in conversation or with `n2f concept promote C-00x` —
and self-contained exactly like the report: one inline module script, each card's massing
GLB embedded and shown in its own 3D viewer (the style's materials by role, the studio
lighting), the styled iso picture as the card's image and the front picture beside it, the
card's reference images as thumbnails. It opens from `file://` with nothing fetched.

Each card shows its id, title, status (`exploring`, `rejected`, `promoted`, or "not built
yet"), what it was based on, its sizes and weights, the estimate strip (cost band, heat-up or
power needed, current, supply, lifting), and "more numbers". **Every number carries its
`computed` or `estimate` badge, taken from the card's screening data** — the page never
decides a label. A red card stays in its place with a red header and "this direction has
problems:" followed by the failing rules in plain words; warnings read "worth a look:". The
decision line says which card was chosen (and its `DEC-`) or why one was set aside.

The page stays under the report's 20 MB budget: when it would not, reference images are
left out first, then the front pictures (then, only if still needed, the 3D viewers and the
iso pictures), and a note at the top says what was left out. The board is written by this
verb only; no build rule reads `concepts/` or the board (N1).

## Promotion: `n2f concept promote C-00x`

Promotion turns the chosen card into ordinary model content, all or nothing (every edit is
computed and validated first; a refusal writes nothing):

1. **Gates.** The card must be built (it has a screening). A red card is refused —
   "C-001 — this direction has problems: … Promote anyway with --override --reason "…";
   the reason is recorded as a decision." — unless `--override --reason` is given. Only
   one card can be the design direction; changing it later is a change request. Refusals
   exit 3.
2. **Parameters** from `envelope`, `owner: napkin`, `description: from concept C-00x`: a
   quantity is one parameter (`insulation: 170 mm` → `insulation`), a three-value list
   becomes `<key>-width/-depth/-height`, other lists `<key>-1…n`, named layers
   `<layer>-thickness` and `<layer>-clearance`; `power` seeds `element-power`. A parameter
   that already exists with the same value is left alone ("already declared"); a different
   value refuses the promotion, naming both values, unless `--override` (then it is
   overwritten in place and listed in the decision).
3. **Site constraints become requirements**, allocated to the top assembly
   (`unallocated` and checked by a person when there is no assembly yet):
   - `alcove_width` → "Fits the alcove with the door open": `asm://<top>#props.bbox.x ≤
     alcove_width − door-swing term`, the term being screening's computed one
     (`footprint_with_door_swing − width`, 0 for a door that does not swing sideways),
     stated in the rationale. This is what makes DEC-011 impossible to repeat;
   - `alcove_depth` / `alcove_height` → `bbox.y` / `bbox.z` bounds;
   - `circuit` with an `envelope.power` → `param://element-power ≤ 0.8 × V × I` (a
     continuous load uses at most 80 % of the rating, `[verify]`);
   - `mass_limit` (or a `lift_class` with a weight on file) → `props.mass <` the limit.
4. **Form requirements** (taste becomes checkable), from the merged style and the layout:
   corner radius when `style.corner_radius` > 0, no visible front fasteners when
   `fastener_visibility: hidden-front`, controls placement when the layout names
   `controls`; each `verify: {kind: rule, target: rule://form-v0/<rule>}` (see
   [checks.md](checks.md)). Fewer than two apply? The ones that do are written and the
   output says so.
5. **`style.yaml`**: the card's `style` keys override the product's, and its `layout` is
   recorded (the controls rule reads it). When the card names another preset, values that
   still equal the old preset's take the new one's (the product then looks like the board);
   hand-edited values are kept and listed.
6. **The decision**: one `DEC-` ("Design direction: <title>", plus ", despite screening" for
   an overridden red card) whose context lists every other card with its verdict and
   one-line reasons as rejected alternatives (and the override reason and failing rules),
   whose rationale quotes the screening numbers each tagged computed or estimate, linking
   the new requirements and parameters; `made_by: human` with `--by`, `verify: true` when an
   estimate was used or `--override` was given.
7. **Cards**: the chosen card becomes `promoted` (`decision: {dec, at}`), every exploring
   sibling `rejected` (`decision: {reason: "not chosen: C-00x promoted (DEC-0xx)", at}`).
   Cards are kept forever.
8. **A snapshot**, "Promote C-00x: <title>" — the only napkin verb that takes one.

It ends in one line, for example: "C-003 is now the design direction (DEC-002). Seeded 5
parameters, 5 requirements (3 about form, 1 about the alcove, 1 about the supply), wrote
style.yaml; C-001, C-002 and C-004 are kept as rejected alternatives. Next: `n2f build &&
n2f check`." `--json` carries every id. After promotion `n2f status` moves past Napkin.
