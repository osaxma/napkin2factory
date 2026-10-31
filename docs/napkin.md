# The napkin stage: concepts, screening, the board and promotion

Concept cards (`concepts/C-xxx.yaml`, NAPKIN_STAGE §3) are cheap directions for the
product. `n2f concept build C-xxx` (or `--all`) turns one into rough shapes and a
**screening**: a handful of numbers and rule outcomes that say, in seconds, whether the
direction holds up. Screening is not verification — it is a third tier for ideas, and
everything it writes lives outside the build (`build/concepts/`, never in the manifest;
deleting `concepts/` changes no build output).

## Writing a card

`n2f concept new "<title>"` writes `concepts/C-00x.yaml` as a commented skeleton;
`--from C-00x` starts a variant with the other card's `layout`, `envelope`, `site`, `style`,
`massing` and `notes` (not its `refs`). A filled card, the one the PM skill quotes:

```yaml
id: C-001
title: Compact bench kiln, controls on top
status: exploring
refs: [refs/sketch-01.jpg]          # images that informed it (never geometry); [] if none
layout: {load: front, door: hinged-left, controls: top, stand: four-leg}
envelope:                           # rough named sizes; they seed parameters at promotion
  chamber: [180 mm, 200 mm, 180 mm] # width, depth, height
  insulation: 115 mm
  power: 1.8 kW
site: {alcove_width: 800 mm, circuit: 240V-13A, region: SA}
style: {preset: appliance, corner_radius: 8 mm, fastener_visibility: hidden-front}
massing:                            # rough shapes, one kit call per line, numbers only
  - {kit: enclosure, as: body, material: mild steel, args: {length: 420 mm, width: 440 mm, height: 418 mm, thickness: 1.2 mm}, at: {z: 760 mm}}
  - {kit: plate, as: lid, role: body, material: mild steel, args: {width: 420 mm, depth: 440 mm, thickness: 2 mm}, at: {z: 1178 mm}}
  - {kit: block, as: door, material: mild steel, process_class: sheet-metal, args: {length: 340 mm, width: 3 mm, height: 340 mm}, at: {y: -221.5 mm, z: 800 mm}}
  - {kit: block, as: controls, material: abs, process_class: cots-controls, args: {length: 300 mm, width: 160 mm, height: 100 mm}, at: {z: 1180 mm}}
  - {kit: frame, as: stand, material: mild steel, args: {length: 380 mm, width: 400 mm, height: 760 mm, member: {size: 25 mm, wall: 1.5 mm}}}
notes: Budget about 1500 USD. Small chamber so the door can swing inside the alcove.
screening: null                     # written by `n2f concept build`
decision: null                      # written by promote or reject
```

(Without the reference image, `refs: []`; with it, the file must exist under
`concepts/refs/` or lint fails.) This card screens green: 420 × 443 × 1280 mm, 760 mm with
the door open in the 800 mm alcove, 7.5 A on the 13 A circuit, about 2.7 h to temperature
and 888–1741 USD (estimates); it warns that the controls sit above the door and that about
64 kg needs more than a two-person lift.

Conventions for `massing`:

- Each call's **bottom centre** sits at the origin; `at: {x, y, z, rz}` moves it (z up, the
  front is −y, +x is the right-hand side seen from the front, `rz` in degrees).
- **Names carry meaning.** `as: door` is the leaf whose x-extent is the door-swing term;
  `as: body` is the shell the walls check fits the chamber into; `controls` and `stand` are
  what they say. A name that is a role word is also the part's colour role; any other name
  takes `role:` explicitly (the lid above is `role: body`).
- **A closed body** is an `enclosure` (an open-top shell, so its weight reads right) with a
  `plate` lid. A `block` is solid: a steel block weighs as solid steel (hundreds of
  kilograms for a kiln body), so use it for doors, control boxes and bought items.
- **Mass** is computed only when every call has a `material`; `process_class` picks the cost
  band when the generator's own process is wrong (`cots-controls` for a bought control box).
- **Numbers only**: a card cannot refer into the model (`param://…`).
- `n2f concept lint` after every edit: schema, ids, refs that exist, known kit names,
  quantities that parse; unknown `site` keys only warn.

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
   - `circuit` with an `envelope.power` → `param://element-power ≤ V × I / headroom`, the
     `headroom` (1.2) read from rule `circuit-available` — the same margin screening used,
     so a green circuit row never becomes a failing requirement (NEC 210.20's continuous-load
     factor 1.25 is stricter, `[verify]`);
   - `mass_limit` (or a `lift_class` with a weight on file) → `props.mass <` the limit.
4. **Form requirements** (taste becomes checkable), from the combined style and the layout:
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

## The conversation: the PM skill's napkin protocol

The verbs above work the same by hand or agent-driven. In a product folder the
project-manager role (`.claude/skills/n2f-pm/SKILL.md`, section "Napkin stage (before
intake)") runs them as a conversation; the designer role (`n2f-design`, "After the napkin
stage") picks up after promotion. The protocol, in short:

1. **When.** A new idea, a dropped sketch or photo, or "I'm not sure what I want yet". A
   product born as a spec skips the stage (N11); `n2f status` says `stage: Napkin` while
   cards exist and none is promoted.
2. **Diverge first.** Ask only the two or three facts that split directions (where it sits →
   `site`; what goes in it → `envelope`; the look they like → `style.preset`), then propose
   **3–5 directions** that differ in layout, size class or use, each a card. Show, don't
   ask the owner to design.
3. **Screen, then talk limitations from the data.** `n2f concept build --all`,
   `n2f concept board`, the styled iso pictures in chat. Every limitation the PM states
   comes from `screening` — the rule rows and the estimate strip — and every number is said
   to be computed or an estimate. **A red card is information, not rejection**: the PM
   explains what it would take to make it work and never hides it.
4. **Iterate cheaply.** "Like C-002 but taller" is `n2f concept new … --from C-002`, one
   envelope line, `n2f concept build C-004`. Rejecting is `n2f concept reject C-00x
   --reason "…"`, on the owner's word only.
5. **Interpretation cards** (N9), below.
6. **Promotion in the owner's register**: "Lock this in as the design direction? Changing
   the basic form later is a bigger change than tuning sizes." Then
   `n2f concept promote C-00x --by "<owner>"` and a read-back of what it wrote. A red card
   needs `--override --reason "<the owner's reason>"`, and the PM says that the reason is
   recorded in the decision.
7. **Safety floor** at the napkin stage too: mains power, hot surfaces, lifting, sharp
   edges, pinch points are named in one plain sentence when a direction implies them.
8. **Hand-over**: intake continues (skipping what the cards answered), then `n2f-design`,
   whose starting layout is the promoted card's massing at full fidelity, which respects
   `style.yaml` and the form requirements, and which never edits `concepts/` after
   promotion except the status fields.

### Interpretation cards: images never become geometry

When the owner drops a sketch, photo or drawing, the PM copies it into `concepts/refs/` and,
before any card exists, replies with an **interpretation card**: a structured playback in
words of what it read —

```
Interpretation card — refs/photo-01.jpg
Proportions:  about twice as wide as it is deep; height about 1.5 × the width (ratios, estimated)
Layout:       two doors on the front, hinged at the outer edges; a handle on top; four castors
Style cues:   sharp corners; folded-steel look; hinges and screws on show
Dimensions:   "600" written along the top edge — 600 mm wide? [verify]
Not shown:    the back and the inside; I assumed one shelf
Did I read it right? Tell me in words what is wrong, missing or more important than it looks.
```

Proportions are ratios; any dimension read off the image is tagged `[verify]` and put to
the owner. The PM then **waits for the owner's correction in words**, plays back what
changed, and only then writes cards, each with `refs: [refs/<file>]` when the image
informed it. The image is provenance (the board shows it as a thumbnail); the numbers on
the card come from the corrected words. A sketch described in words gets the same
treatment without a `refs` entry. Automated tests use textual stand-ins
(`tests/e2e/intake-transcripts/napkin-bench-kiln.md`); runs with a real image in the
agent's context are the owner's to do by hand (NAPKIN_STAGE §1.2).
