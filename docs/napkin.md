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
`modules`, `massing` and `notes` (not its `refs`). A filled card, the one the project manager role (`roles/pm.md`) quotes:

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
modules:                            # what is built, bought or serviced as one unit, and why
  door: {driver: [built-as-unit]}
  controls: {driver: [separate-process-or-supplier]}
massing:                            # rough shapes, one kit call per line, numbers only
  - {kit: enclosure, as: body, material: mild steel, args: {length: 420 mm, width: 440 mm, height: 418 mm, thickness: 1.2 mm}, at: {z: 760 mm}}
  - {kit: plate, as: lid, role: body, material: mild steel, args: {width: 420 mm, depth: 440 mm, thickness: 2 mm}, at: {z: 1178 mm}}
  - {kit: enclosure, as: door, module: door, material: mild steel, process_class: sheet-metal, args: {length: 340 mm, width: 60 mm, height: 340 mm, thickness: 1.2 mm}, at: {y: -250 mm, z: 800 mm}}
  - {kit: block, as: controls, module: controls, material: abs, process_class: cots-controls, args: {length: 300 mm, width: 160 mm, height: 100 mm}, at: {z: 1180 mm}}
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

**Modules** (optional, v0.4, P10): `modules: {<name>: {driver: [...], build: unit|phantom}}`
names the units the product is built from and why, with the assemblies' reasons
(`built-as-unit`, `tested-as-unit`, `serviced-as-unit`, `separate-process-or-supplier`,
`varies`, `agent-context`; `docs/vocabulary.md`), and `module: <name>` on a massing line
says which unit a rough shape belongs to. A line without one belongs to the product as a
whole. Screening ignores modules; the board lists them ("door (put together and fitted as one piece)") and
promotion turns them into the product's first structure (below). Name a module only when a
reason applies: start flat, split for a reason (P11). Lint warns (never fails) about an
unknown reason word, a line naming a module that has no entry (allowed: it promotes with no
reason) and an entry no line belongs to (it gets no size budget).

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
- **Optional fields screening reads**: `envelope.door_swing` (how far a hinged door opens,
  `110 degree`; without it the door counts swung fully back, the widest case),
  `envelope.door_width` (the leaf, when there is no `door` call), `envelope.target_volume`
  (the useful volume the owner asked for, `8 L`), `site.touch_limit` (the hottest outside
  surface allowed, `60 degC`; without it, a burn threshold on file, `[verify]`). Like every
  `envelope` number, `door_swing` and `target_volume` seed parameters at promotion.
- `n2f concept lint` after every edit: schema, ids, refs that exist, known kit names,
  quantities that parse and are the right kind (`power: 3 kg` is an error; screening leaves
  such a number out with a note); unknown `site` keys only warn.

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

## The three labels

Every number carries a label, in the card, in JSON and on screen:

- **`given`** — the card's own inputs echoed back: `power` (from `envelope.power`) and
  `circuit_class` (from `site.circuit`). They are neither measured nor estimated (review
  gate A); a verdict that relies on them, such as whether the power fits the circuit, is
  still an estimate.
- **`computed`** — measured from the massing shapes: `width`, `depth`, `height` (the
  bounding box), `volume`, `mass` (only when every call declares a `material`), and
  `footprint_with_door_swing` and `door_leaf` (only when the card's `layout` names a door:
  no door, no rows).
- **`estimate`** — from the calc kit ([calckit.md](calckit.md)) fed with the card's
  `envelope` numbers: `heat_loss`, `skin_temperature`, `stored_heat`, `heat_up_time`
  (from `envelope.power`) or `required_power` (from `envelope.heat_up_time`),
  `insulation_mass`, `total_mass`, `current`, `circuit_class`, `cost_low`/`cost_high`,
  `lift_class`.

Every value also says **where it comes from**, twice: `source` is one sentence in the
owner's words, printed under the number on the board and in `n2f concept show` ("measured
across the rough shapes", "from the walls' stored heat and the element power", "rough cost
of the guard (5 pieces), hinge, controls, stand, brick layer and fiber layer from cost bands
per process; the body and the door are not counted; to be checked"); a `[verify]` default
reads "to be checked" at its end. `ref` is the engineer's reference — the calc-kit function
and the defaults it used (`thermal_enclosure.heat_up_time`, `mass_cost.cost_estimate
(guard-left: sheet-metal; …) [verify]`) — kept in the card and in `--json`, never shown to the
owner (review gate B).

A missing input never becomes an invented number: the estimate is left out and a note says
what would unlock it. When the card is silent, screening states its defaults: room 25 degC,
skin film coefficient 5 W/m²K, emissivity 0.9, hot face 1200 degC; a bare
`insulation: 170 mm` is one ceramic-fiber-board layer (the kiln's values); layers named
`brick`/`K23` or `fiber` take the kiln's K23 and fiber-board values; `shell` layers grow
the box without resistance or stored heat. All of these are `[verify]`.

## The rules (`rulepacks/concept-v0.yaml`)

| rule | fails when |
|---|---|
| `fits-site-width` | width + the open door > `site.alcove_width`. A hinged door (`layout.door: hinged-left/right`) adds what its leaf (the `door` massing call, else `envelope.door_width`) reaches past the hinge: leaf × max(0, −cos `envelope.door_swing`), the whole leaf when the card gives no angle |
| `fits-site-depth`, `fits-site-height` | depth/height exceed `site.alcove_depth`/`alcove_height` |
| `circuit-available` | the current × 1.2 headroom ("a fifth to spare" in the owner's line) exceeds `site.circuit` (e.g. `240V-13A`) or every class on file for `site.region`; an unknown region only warns |
| `mass-vs-lift-class` (warning) | the mass needs more than a two-person lift, or more than `site.lift_class` |
| `blank-vs-stock-sheet` | a sheet-metal call's flat blank (open box: (L + 2H) × (W + 2H)) fits no stock sheet on file |
| `walls-fit-envelope` | chamber + 2 × insulation does not fit inside the `body` call |
| `controls-not-adjacent-hot-face` (warning) | controls sit on top or beside the door, in the hot air path |
| `skin-vs-touch-limit` (warning) | the skin estimate is above `site.touch_limit`, or without one the 1-minute burn threshold in `calckit/data/touch_limits.yaml` (ISO 13732-1, `[verify]`) |
| `chamber-volume-vs-target` (warning) | the chamber holds less than `envelope.target_volume` |

Each rule carries an owner-worded `title` ("Fits the alcove with the door open", "Every sheet
fits a stock size", "The walls fit inside the body"); `n2f concept show` prints the title,
`--json` keeps the id.

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
`given`, `computed` or `estimate` badge, taken from the card's screening data** — the page never
decides a label — and estimates carry their `source` sentence underneath (the two cost rows
share one; a band whose high end is more than 1.5 × its low end adds "a wide band: only the
parts screening can price are counted"). A red card stays in its place with a red header and
"this direction has problems:" followed by the failing rules in plain words; warnings read
"worth a look:". The decision line says which card was chosen (and its `DEC-`) or why one was
set aside ("set aside when C-003 was chosen (DEC-018) — 2026-10-31": the date, never the time).

`n2f concept build --all` builds every card, set-aside ones too, so the board has a picture
of each; their lines end "(set aside)", the promoted card's "(the chosen direction)".

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
     alcove_width − allowance`, the allowance being the room the open door takes beside
     the hinge (screening's door-swing term rounded up to 0.1 mm; 0 for a door that does
     not swing sideways), stated in the rationale. For a hinged door promotion also seeds
     `door-leaf-width` (screening's leaf; `door-width` when the card gives `door_width`)
     and `door-swing-clearance` (an expression on it, `door-leaf-width * 0.34202` at 110°),
     and writes a second row, "The open door keeps to its room beside the hinge":
     `param://door-swing-clearance ≤ allowance`. Rewrite the leaf as an expression over the
     designed door's parameters and a wider door or a wider opening fails instead of passing
     unseen. This is what makes DEC-011 impossible to repeat;
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
   - **Modules** (P10), when the card names any and the product has **no assembly yet**:
     `model/assemblies/<product id>.yaml`, the top assembly, with one `asm://<module>` child
     per module, and one stub `model/assemblies/<module>.yaml` per module (`children: []`,
     `build`/`driver` from the card; an unknown reason word is left out and noted). Each
     module with rough shapes gets three size budgets, "The door module fits the width the
     concept gave it" and its depth and height: `asm://<module>#props.bbox.x|y|z ≤` the
     extent of its massing lines' box, rounded up to 0.1 mm and labelled computed. The site
     and form rows above then go to the new top assembly instead of `unallocated`. Lines
     without a module seed nothing: their parts go into the top assembly. A module named
     like the product, or an assembly file already on disk, refuses the promotion (nothing
     is ever overwritten). An empty stub builds; `n2f check` shows it as worth a look
     (`general-v0` "module has parts") and its budgets as not checked until it has parts.
     When the product **already has assemblies**, nothing is written: the output prints the
     modules as a suggestion, and the decision records them.
6. **The decision**: one `DEC-` ("Design direction: <title>", plus ", despite screening" for
   an overridden red card) whose context lists every other card with its verdict and
   one-line reasons as the alternatives (and the override reason and failing rules),
   whose rationale quotes the screening numbers each tagged computed or estimate, linking
   the new requirements and parameters; `made_by: human` with `--by`, `verify: true` when an
   estimate was used or `--override` was given.
7. **Cards**: the chosen card becomes `promoted` (`decision: {dec, at}`), every exploring
   sibling `rejected` (`decision: {reason: "set aside when C-00x was chosen (DEC-0xx)", at}`).
   Cards are kept forever.
8. **A snapshot**, "Promote C-00x: <title>" — the only napkin verb that takes one; the
   output says "snapshot saved".

It ends in one line, for example: "C-003 is now the design direction (DEC-002). Seeded 5
parameters, 5 requirements (3 about form, 1 about the alcove, 1 about the supply), wrote
style.yaml. C-001, C-002 and C-004 are kept as alternatives. Next: `n2f build && n2f
check`." A card with no sizes or site limits says so instead: "The card had no sizes or site
limits, so no numbers or requirements were added; the look is recorded in style.yaml."
`--json` carries every id. After promotion `n2f status` moves past Napkin: its headline names
the first stage not yet complete ("stage: Design" once Intake is done; "stage: ready to
release" when only the Revision is missing).

## The conversation: the project manager's napkin protocol

The verbs above work the same by hand or agent-driven. In a product folder the
project-manager role (`roles/pm.md`, section "Napkin stage (before
intake)") runs them as a conversation; the designer role (`roles/design.md`, "After the napkin
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
8. **Hand-over**: intake continues (skipping what the cards answered), then the designer role,
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

## The kiln's story: what screening says in minute five

v0.1 built the kiln (`examples/kiln`) with no napkin stage. Three of the four questions it
left for the owner were trade-offs that a napkin stage would have raised at the start:
DEC-011 (the kiln is wider than the alcove), DEC-012 (the cost is above the wish) and DEC-004
(the heat-up is slower than "about four hours"). v0.2 adds the stage after the fact, in
`examples/kiln/concepts/`. Each card was written by hand from the kiln's own parameters and
cites them in its notes. `examples/kiln/demo-napkin.sh` replays the stage unattended.

**C-001, the kiln as built in v0.1, is red.** `n2f concept build` prints its reason word for
word:

```
✗ C-001 — this direction has problems:
    • it needs 1236 mm of width — 995 mm for the body plus 240 mm for the open door (the 702 mm door leaf opened to 110°) — but the alcove is 800 mm
  995 × 667 × 1370 mm (computed), 2.5 kW (on the card) on the 230V-16A circuit — fits with a fifth to spare (estimate), 4.4 h to temperature (estimate), 650–2267 USD (estimate)
  ! worth a look: the outside skin is about 61 degC (estimate), above the 60 degC touch limit (on the card) — more insulation or a guard would bring it down
```

- **DEC-011, the alcove.** The 995 mm is the closed width. It is computed from the rough
  shapes and matches the v0.1 report's bounding box. The 702 mm door leaf, opened to its
  110°, reaches 240 mm past the hinge and brings the width to 1236 mm, and the owner's alcove
  is about 800 mm. The kiln is too wide even with the door shut. v0.1 found this when the
  report was built, at hour forty. Screening finds it in the time a card takes to build.
- **DEC-012, the cost.** The estimate is 650–2267 USD. It counts only the parts screening
  can price: the guard sheets, the stand, the hinge, one control box, and the brick and
  fiber. The inner shell, the door sheets and most bought-in parts are not in it. The band
  is incomplete, and the owner's 1500 USD wish already sits inside it. v0.1's
  per-part estimate came to about 2200 USD.
- **DEC-004, the heat-up.** The estimate is 4.4 h to 1200 degC at 2.5 kW. That is
  screening's number, not the 7 h in DEC-004. The 7 h is the margin planned on top of the
  estimate: 2.5 kW is 1.28 times the 1.95 kW that a 7 h heat-up needs
  (`calc://element.power_margin`). The owner asked for about four hours, and the screening
  estimate is close to that. The planned margin is what goes past it.

The other three cards show the choices that follow. **C-002** was worked back from the alcove
rule and fits it at 773 mm with the door open. To fit, it gives up three things, and its
notes and numbers show each one. Its chamber is 3.4 L, below the 8 L that REQ-001 asks for.
It has no touch guard, so its skin estimate is 91 degC against a 60 degC limit. Its
controller box hangs under the body. Its card states the 8 L target and the 60 degC touch
limit, so screening lists the small chamber and the hot skin as worth a look: the trade-offs
show on the board without a red verdict. **C-003** is the kiln as built in the appliance look
the owner preferred. It assumes an alcove of about 1.75 m, which the owner has not confirmed
(DEC-011). Its card gives the door's 110° opening, so screening asks for 1236 mm with the door
open; with a hand's room beside the hinge, about 1.3 m may be enough in practice. **C-004**
is C-003 in the v0.1 look. It was rejected because the owner did not like that look.

Promoting C-003 shows reconcile mode at work. All eleven of the card's envelope numbers, and
the two door numbers the alcove requirements read (`door-leaf-width`, written in the kiln as
the door guard's width, and `door-swing-clearance`), were already in `parameters.yaml` with
the same values, so nothing was seeded or overwritten.
Five requirements were added. The alcove requirement takes off the 240.3 mm the open door
needs beside the hinge, giving closed width ≤ 1509.7 mm, and the kiln as built measures
995.4 mm. A second alcove requirement holds the door to that room: the door's width is a
parameter (the door guard's outside width), so a wider door or a wider opening fails there
instead of passing unseen. The supply requirement is
element power ≤ 3066.7 W on 230 V / 16 A. The two form requirements are a 1 mm minimum
corner radius and controls on the right. `style.yaml` takes the appliance look. DEC-018
records C-001, C-002 and C-004 as rejected alternatives. The card's corner radius and
fastener choice match what the kiln as built can meet. Its folds are 1 mm, and its door
guard is screwed on through its face. The softer 8 mm corners and hidden front fasteners
that the appliance look suggests would therefore be a change request, not something a
promotion can claim. DEC-018 also notes that the owner has not yet answered DEC-011,
DEC-012 or DEC-004.
