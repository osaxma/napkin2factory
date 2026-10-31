# Decisions log (system build-out)

Decisions beyond `GRAND_PLAN.md` §2, with rationale. `[revisit]` marks ones the owner may
want to reopen; `[verify]` marks engineering numbers taken from published sources that a
human should confirm before relying on them.

## S-001 — Host platform differs from the plan (2026-10-30)
The build runs on an Intel macOS host (Darwin 25.6, x86_64, 16 cores, 32 GB), not the
sandboxed Linux the plan assumed. Nothing in the plan is Linux-specific; CI (`ci.yml`)
runs both `ubuntu-latest` and `macos-latest`.
**Amended 2026-10-31 (owner):** there is no Linux machine. This macOS host (a separate user
acting as the agents' sandbox) is the reference platform, and the definition of done is
verified here. Linux coverage comes only from the CI matrix, which first runs when the
branch is pushed; until then Linux is untested, not failing. No manual Linux run is planned.

## S-002 — OCP wheel and render path pairing (D2 / D12) (2026-10-30)
`uv sync` with `build123d>=0.12,<0.13` on Python 3.13.18 resolves, through build123d's
`cadquery-ocp-proxy`, to **`cadquery-ocp-novtk 7.9.3.1.1`** (no VTK). Therefore the
VTK offscreen render path is unavailable and the render path is the **numpy z-buffer
rasterizer** over the OCCT tessellation (`geometry/render.py`): orthographic front/top/right,
an isometric view, and a crude section (triangles above a Z plane dropped). Flat shading,
one hash-derived colour per part. `tests/smoke/test_toolchain.py` asserts VTK is absent so a
future wheel change forces this entry to be revisited. Python 3.13 pinned; 3.14 not tried.

## S-003 — three.js pinned at r170 (0.170.0), vendored, inlined (D13) (2026-10-30)
One download from jsdelivr of four files into `src/napkin2factory/report/vendor/three/`:

| file | sha256 |
|---|---|
| three.module.js | ce1fa418de16a19495a9f72495580e3015d7745c296d3ce0485897f902ddedfb |
| GLTFLoader.js | 45139faddd5aaf48ed2d62203d976e5cbd703db1a592de40527f9f6cf58abd44 |
| OrbitControls.js | 80efaadea4f8a636a65fb0bd08bfef62f3d93a0bb94e2e7500f23176c5c07f4e |
| BufferGeometryUtils.js | c25b7930e570e9ec56173cd3b866ec8d2e10016630db3937efb439daf1cedbf6 |

`report/inline.py` strips `import`/`export` statements, wraps each addon in a block scope with
its exports re-bound through a holder object, and concatenates core + addons + `viewer.js`
into one inline `<script type="module">`. Proven from `file://` with Playwright Chromium
(`tests/smoke/test_viewer_skeleton.py`): zero console errors, the single cube mesh reports
two instances.

## S-004 — In-house GLB writer; URIs carried in glTF `extras` (2026-10-30)
build123d's `export_gltf` propagates labels into node and mesh names but writes **no
materials** and **duplicates meshes per instance**. D13 requires one mesh per part URI,
instanced per occurrence, with material names equal to URIs, so `geometry/glb.py` writes
GLB directly through pygltflib. three.js's `GLTFLoader` sanitizes node names (strips `/`,
`:`, `.`), so each node and mesh also carries `extras: {n2f_uri, n2f_node, n2f_kind}`, which
the loader exposes untouched as `userData`; the viewer keys on that, not on `name`.

## S-005 — selectolax lexbor backend (2026-10-30)
selectolax 1.0 removed the Modest backend; all HTML parsing in tests uses
`selectolax.lexbor.LexborHTMLParser`.

## S-006 — `rich` and `packaging` added as runtime dependencies (2026-10-30)
`rich` for tables and persona-vocabulary output in the CLI (typer already depends on it);
`packaging` to evaluate the product repo's `system: ">=0.1,<0.2"` pin.

## S-007 — Expression grammar: hyphenated names, spaced minus (2026-10-30)
Parameter slugs contain hyphens, so `a-b` is ambiguous. In `expr:` strings a hyphenated
token is always a parameter name and subtraction must be written with spaces (`a - b`).
`core/expr.py` rewrites slugs to identifiers and evaluates a whitelisted AST (arithmetic,
`min/max/abs/sqrt/ceil/floor/round`) over pint quantities. `check_syntax` runs before
name resolution so `__import__('os')` is reported as disallowed, not as an unknown name.

## S-008 — Lint L1 "measurable" exempts binary verify kinds (2026-10-30)
"All exposed sheet edges deburred" has no number and is a legitimate `manual` requirement.
L1 requires a number-with-unit in the statement unless `verify.kind` is `manual`,
`interference`, or `interface`. Vague words ("adequate", "appropriate") warn.

## S-009 — Schema failures do not cascade (2026-10-30)
When a file fails schema validation the loader records its id in `product.broken`, so
references to it are not reported as "does not exist" on top of the real error. One
flaw, one finding.

## S-010 — Product-repo common files live in `templates/_common` (2026-10-30)
`CLAUDE.md`, `AGENTS.md`, the two skills, the two agents, the two workflows and
`.gitignore` are maintained once in `templates/_common/`. `make templates` copies them
into every example and then copies `examples/bracket` and `examples/enclosure` into
`templates/`; `tests/unit/test_templates.py` asserts the trees are identical (D19).
`n2f init` overlays `_common` on the chosen template.

## S-011 — Unattended git identity (2026-10-30)
`core/vcs.py` sets `GIT_AUTHOR_NAME/EMAIL` and `GIT_COMMITTER_*` to `napkin2factory
<n2f@localhost>` when the environment has none, disables hooks (`core.hooksPath=/dev/null`)
and the pager, so `n2f init` works in a fresh sandbox. A configured identity wins.
**Amended 2026-10-31 (owner):** owners may not know git exists, so intake never asks for a
git identity. Where git has no `user.name`/`user.email`, snapshots are authored as the
product name from `n2f.yaml` (the folder name if there is none) `<n2f@localhost>`. The
v0.1 code set the variables whenever the environment lacked them, which overrode a
configured identity despite the sentence above; `Vcs._fallback_identity` now checks
`git config` first and fills only what is missing (`tests/unit/test_vcs.py`).

## S-012 — Validate semantics for computed selectors (2026-10-30)
`#props.*` on parts/assemblies and `bom://rollups#*` are computed by the build, so
`n2f validate` checks only that the base URI exists and the selector is syntactically
valid; `n2f check` resolves them against `build/`. Declared-field selectors
(`req://REQ-001#verify.value`) are resolved at validate time.

## S-013 — Interface bolt patterns are applied by the build, not by each generator (2026-10-30)
D16 says both parties' generators consume the interface. Rather than teaching every kit
generator about interfaces, `geometry/build.py:apply_interfaces` cuts every declared
bolt-pattern interface into each party after its generator returns: holes along the frame
normal at `hole_pattern.centers_from_spec`, reaching `spec.depth` (default 10 mm) on each
side of the frame plane, and records a `HolePattern` feature tagged `iface://…` plus
`Hole` entries. Agreement by construction, for kit and module parts alike; the M4
`interface` check then compares the two parties' recorded patterns. Mating-face interfaces
only record the face frame (`features.extra.mating_faces`). A generator that already
emitted a pattern tagged with the interface is left alone.

## S-014 — Per-party interface frames and `param://` in specs (2026-10-30)
One frame cannot serve two parts with different local origins (the lid's holes are at
z = 0 in the lid, z = 80 in the base). `Interface.frames: {part://x: Frame}` holds each
party's copy; `frame_for(uri)` falls back to `frame`. Spec quantities may be `param://`
references (`QuantityOrParam`); `I[...]` returns a resolved copy and records those
parameters, so a spec that depends on a parameter invalidates both parties (D5).

## S-015 — Assembly instance numbering is global per part URI (2026-10-30)
`flatten()` numbers leaf occurrences `part://x#1…#n` across the whole top-level assembly,
nested sub-assemblies included; group nodes are `asm://y#m`. This is what the viewer, the
BOM and `instance_counts` use (D13, D18). An assembly without a geometry module gets an
auto layout in a row along X, flagged in `props.notes`.

## S-016 — Downstream rules depend on upstream *output hashes*, not keys (2026-10-30)
A recorded read of `part://x` resolves to the output hash of `part:x` (props minus reads,
features, flat pattern), not to its post-run key. So a parameter edit that reruns a part but
yields identical geometry does not cascade; and an unused parameter reruns only `validate`
(whose declared input is the model tree hash). `rule:<id>` keys cover rules that produce no
URI (checks → report → site). This is why `make check`'s invalidation tests assert that
touching an assembly module reruns only `asm:enclosure` when its props are unchanged.

## S-017 — `validate` always reruns when any model file changes, never otherwise (2026-10-30)
Its declared inputs are the hashes of `model/`, `n2f.yaml`, `operator.yaml` and `changes/`.
Deleting a build output or interrupting a build does not rerun it. The §6.4 wording
"unused parameter → runs only validate" holds exactly.

## S-018 — Interruption safety by atomic manifest writes after each rule (2026-10-30)
Outputs are written to their final paths; the manifest entry is written last, atomically
(temp file + `os.replace`). A kill between the two leaves outputs without an entry → the
rule reruns; a kill after leaves a consistent entry. `N2F_TEST_EXIT_AFTER=<rule>[:before]`
makes the runner `os._exit(3)` deterministically at either point for the tests.

## S-019 — `--jobs N` builds parts in a spawn pool; assemblies reload from STEP (2026-10-30)
Workers return props/reads/output hashes only (OCCT shapes do not pickle); the parent
records manifest entries and later assembly rules reconstruct `BuiltPart` from
`build/parts/<id>/model.step` + `props.json` (`load_built_part`). Default stays 1 (D2 risk).

## S-020 — Impact before the first build is the conservative static read set (2026-10-30)
Without a manifest, `compute_impact` uses a static over-approximation (every `param://` a
part's YAML mentions, every parameter for assemblies/docs) and says so (`firm: false`).
After one build the recorded reads make it exact and equal to the rebuild set, which the
invalidation suite asserts for the enclosure.

## S-021 — Manual pages record `depends_on` plus every templated read (2026-10-30)
`docs/engine.py` renders Jinja2 over the Markdown body with proxies that record
`part://x#name`, `req://R#statement`, `param://x`, `bom://rollups#total_cost`;
`depends_on` entries are added as bare URIs so a geometry change to a listed part marks the
page for rebuild even when the body reads only declared fields. StrictUndefined: a typo
fails the build rather than rendering blank.

## S-022 — Rule packs are YAML rules bound to named Python checks (2026-10-30)
A rule pack lists rules `{id, title, severity, check, params, message}`; `check` names a
function in `rulepacks/checks.py` that evaluates `features.json` and returns violation
dicts the message template formats. No expression language: every rule is a tested,
deterministic function; packs only carry thresholds and wording. Product-local packs may
live in `model/rulepacks/*.yaml`. Thresholds in `sheet-metal-v0` (r ≥ 1 t, hole ≥ 1 t,
hole-to-bend ≥ 2 t + r, flange ≥ 4 t) are common shop rules of thumb `[verify]` — confirm
with the fabricator; they are cited as nominal in the pack header.

## S-023 — BOM link checks default to offline in `make check` (2026-10-30)
`validate_bom` runs the URL tier only when `N2F_OFFLINE` is unset/0; the Makefile exports
`N2F_OFFLINE=1` so the gate never touches the network, and results are cached seven days in
`build/bom/url-cache.json` for interactive runs. Unverified sources stay visible as
`warn` rows (`bom://validation@<part>`), never hidden (D15).

## S-024 — Evidence keys (D25) per scheme (2026-10-30)
`part://`, `asm://`, `doc://`, `drawing://` → that rule's output hash from the manifest;
`bom://` → the bom rule's output hash; `calc://m.f` → sha256 of (module source, recorded
input values, formatted result); `param://`, `req://`, `dec://`, `iface://` → hash of the
declared value/object. `n2f signoff` binds the sign-off to the keys of the requirement's
verify target and allocation (or `--evidence`); `n2f check` compares and reverts to
`needs-human` with the list of changed URIs in the message.

## S-025 — `count` verify kind semantics (2026-10-30)
`verify: {kind: count, target: part://x, op, value}` compares the total number of
occurrences of the part across the top-level assemblies (geometry instance counts, or the
BOM's rolled-up quantity for BOM-only parts). `count://<asm>` rows additionally assert
geometry counts == YAML quantities per assembly (D18) and auto-layout or BOM-only parts
produce `warn` rows.

## S-026 — Safety verdict ladder (2026-10-30)
computed `fail` → `fail`; `skip` → `skip`; safety requirement → `needs-human` (message
notes when the computation already passes) until a valid sign-off → `signed`; non-safety
`manual` → `needs-human` → `pass` with a valid sign-off; everything else `pass`. Stage
`verify` requires no `fail` and no `needs-human`; `warn` is ignored everywhere (D10).

## Review gate 1 (architecture) — outcome (2026-10-30)
A fresh-context reviewer found six blockers in the M3 graph; all six are fixed and each has
a regression test in `tests/e2e/test_invalidation.py`. Concerns C1–C8 were fixed where
cheap (kit-name validation, corrupt-JSON handling, doc error line numbers, per-read values
in the manifest for the "why" column, key precision, product proxy in docs, ruamel width,
`n2f build --explain`, parallel results recorded as they arrive, validate-first ordering);
the rest are in `BACKLOG.md` (B-0004…B-0006).

## S-027 — Membership keys `set://…` (gate-1 B1)
Rules that enumerate a collection (BOM, checks, report) read `set://parts`, `set://asms`,
`set://reqs`, `set://docs`, `set://decs`, `set://ecrs`, `set://signoffs`, `set://ifaces`,
`set://params`, whose value is the hash of the sorted id list (parts: id + has_geometry +
kind). Adding or removing an object therefore reruns exactly the rules that enumerate it.
Rules whose object disappeared are pruned from the manifest with their output directories
at the start of every build; a consumer that read the pruned URI sees "unbuilt" ≠ the old
hash and reruns.

## S-028 — Parts and assemblies record the fields they read (gate-1 B3)
`build_part` records `part://x#geometry|material|mass|process|kind|interfaces|rev`;
`build_assembly` records `asm://y#children|geometry|rev|exploded`; the part/asm YAML file
hash is no longer a declared input. A cost or notes edit no longer rebuilds geometry, and
`n2f impact` (which no longer adds the bare base URI for selector edits) agrees with the
build by construction. Impact remains a superset: a rerun with identical output stops the
cascade (S-016), which impact cannot predict.

## S-029 — Outputs are verified, never trusted (gate-1 B2/B4)
`needs_run` compares every recorded output's sha256 with the file on disk; a tampered or
half-written output reruns the rule. Part and assembly rules clear their output directory
before exporting, so stale renders or flat patterns cannot survive a change. `render` is a
declared input of part/asm rules (`--no-render` then a default build rebuilds). `load_built_part`
refuses a STEP whose volume disagrees with `props.json` and points at `n2f build --clean`.
`--clean` also removes the artifact directories.

## S-030 — Stable instance numbering and placements in the assembly hash (gate-1 B5)
Leaf instances are numbered per URI by (label, rounded world translation, rotation, parent),
so reordering placement code does not renumber occurrences; a label, when given, is the
occurrence's identity. The assembly output hash includes `instances.json`, so moving a part
reruns checks, report and (M6) diff even when bbox/mass are unchanged.

## S-031 — Package-tree code hashes (gate-1 B6)
Rules hash the system package trees their code lives in (`geometry`, `drawings`, `bom` +
`catalog`, `docs`, `core/checks` + `rulepacks`, `report`) rather than hand-bumped version
constants; module-based parts and assemblies also hash the product's whole
`model/geometry` tree, and the loader purges cached product-local modules before each
import so helper edits are seen in-process. Part tessellations are persisted as `mesh.npz`
and reused when a part is reloaded, so `--jobs N` produces byte-identical assembly GLBs.

## S-032 — Report layout and persona toggle (D13, D17) (2026-10-30)
One Jinja2 template (`report/templates/report.html.j2`), one page. Sections are flex items
whose CSS `order` differs per persona (`html[data-persona=owner|engineer]`), so the owner
view leads with Safety → status → 3D → cost/manufacturer → drawings, and the engineer view
with Safety → status → check matrix → requirements → parameters. Safety has order 0 in both
and is never inside a persona-only block. Vocabulary is rendered twice (`vv()` macro emits
an owner span and an engineer span) and switched by CSS, so the toggle needs no re-render;
the chosen persona persists in `localStorage`. The viewer is one inline module script
(S-003); the top assembly's GLB (or every part's GLB when there is no assembly), the iso
and section renders, and every drawing SVG are embedded. `report.json` records the byte
size against the 20 MB budget; `tests/validate_outputs_full.py` asserts it. Manual pages
are embedded as HTML fragments with their own `<h1>` dropped (the report titles them).
The footer timestamp is excluded from the output hash.

## S-033 — `n2f serve` is a plain `http.server` (2026-10-30)
Convenience only (D13): it serves `build/report` (or `build/site` with `--site`) on
127.0.0.1. The page works from `file://`; the server exists for people who prefer a URL.

## S-034 — Interface holes reach the flat pattern through `PartResult.flat_map` (2026-10-30)
The build cuts interface bolt patterns into the solid after the generator returns (S-013),
so the generator's flat pattern did not contain them and the DXF would have been wrong.
Generators that know their unfold now set `result.flat_map`, a function from a 3D point on
the part to its 2D flat position (None when not mappable, e.g. in a bend zone); the build
appends each interface hole to `flat_pattern.holes` and adjusts the area, and records a
note on the part when holes could not be mapped (the checks surface it as a warn). plate
and panel map identity XY; bracket_l and enclosure map legs, base, walls and lips. Every
part with a flat pattern gets a DXF (cut-sheet included), not only `process: sheet-metal`.

## S-035 — Parameter edits are line-targeted; other YAML edits round-trip (2026-10-30)
ruamel cannot preserve the column alignment used in `parameters.yaml` (`slug:   {value: …}`),
so `n2f ecr apply` changes a parameter's `value:` on its own line with a regex and touches
nothing else: a one-value change is a one-line diff. Block-style files (requirements,
parts, assemblies, interfaces, decisions) go through the ruamel round-trip, which keeps
comments and order. If a parameter is written in block style the edit falls back to ruamel.

## S-036 — Revision bump rule (D7/M6) (2026-10-30)
`n2f ecr apply` stores the part/assembly output hashes of the last build in
`applied.before`; `n2f ecr close` rebuilds the checks, requires zero `fail`, and bumps the
rev of every part whose output hash changed or whose YAML changed in the applied snapshot,
then of every assembly that contains a bumped child or whose own output changed. The
checks rebuild once more so the new revs reach title blocks and the report, and the
closing snapshot records everything. `CHANGELOG.md` gets one section per closed request.

## S-037 — "Unused parameter → nothing rebuilds" holds for artifacts, not for the report (2026-10-30)
The report prints every parameter's value in its Parameters section and therefore records
`param://*` reads; changing a parameter nobody else reads reruns `validate`, `report` and
`site` and nothing else (no geometry, drawing, BOM, doc or check rule). The invalidation
suite asserts exactly that set. Showing a stale value in the report would be the real bug.

## S-038 — Release bundle and frozen site data (2026-10-30)
`n2f release` builds `build/release/<product>-vX.Y.Z.zip` with STEP per part (rev in the
file name), drawing SVGs plus `drawings.pdf` (Typst embeds the SVGs, one A3 page each),
flat-pattern DXFs, BOM files, manual PDFs/HTML, the report, `checks.json`, the changelog and a
README with the disclaimer. `build/site/vX.Y.Z/` holds the report, the ZIP and `data/`
(drawings, props, instances, GLBs, rollups, checks, a `model.json` snapshot of declared
values) so `n2f diff` never has to rebuild a released Revision. Order of operations:
build → gates → write `released_in` and the changelog header → rebuild (report shows the
Revision) → bundle → snapshot → tag → site index. `--dry-run` stops before the model edits.

## S-039 — Diff overlays rescale to the newer drawing (2026-10-30)
Both drawings are A3 sheets at their own scale (`data-scale`); the overlay strips the title
blocks (D14), draws the new drawing in green and the old in red inside a `scale(new/old)`
group so both sit at one shared scale. Changed parts are those whose tessellation hash or
declared fields differ; added/removed come from the part sets; the two 3D viewers
highlight changed parts in amber, added in green (new side) and removed in red (old side).
`working` as the second ref compares a released Revision with the current model.

## S-040 — Sign-off evidence for parts is geometry, not the manifest hash (2026-10-30)
`n2f ecr close` bumps part revisions, and `rev` is in `props.json`, so a sign-off keyed on
the part rule's output hash was voided by the bump itself — right after the re-sign the
ECO loop requires. Evidence keys for `part://x` are now sha256(tessellation hash + features);
for `asm://x` sha256(instances + instance counts). A label change never invalidates a
sign-off; any change of shape, placement or feature still does (D25).

## S-041 — `n2f check` never changes render state (2026-10-30)
Renders are outputs of the part rules and `render` is in their key (S-029), so a check that
built with `--no-render` would rebuild parts and wipe their renders. `n2f check`,
`n2f signoff` and `n2f ecr close` build with renders on; `--no-render` is only for
`n2f build` and `n2f release`.

## Review gate 2 (UX) — outcome (2026-10-30)
A fresh-context reviewer played a non-technical owner. Five blockers, all fixed: `n2f snapshot`
and `n2f discard` are the owner-level save/undo and the release refusal names them (B1);
`n2f init .` sets up change tracking on an existing product folder (B2); EXAMPLE sign-offs
show as such in `n2f check` and `n2f release` refuses them unless
`--allow-example-signoffs` is passed for a demonstration (B3); the report says
"draft — changed since Revision vX" instead of "Revision vX" once the model is edited (B4);
`n2f signoff` refreshes the checks and saves, and `n2f status` says when the checks are out
of date (B5). Concerns fixed: owner vocabulary throughout `n2f check`, owner-friendly table
headers and hidden `verify` column, clickable drawings, honest `ecr close` next step, diff
rev label, versions hint, changelog order, impact legend, disclaimer in drawings and CSV,
manual wording in the enclosure example, the test-only parameter removed from the template.
Left for later: C13 (terminal wrapping), C14/C15 (URI prefixes in owner tables), C4
(design-time wording for inspection sign-offs) → BACKLOG B-0007…B-0009.

## S-042 — EXAMPLE sign-offs are visible everywhere and gate releases (2026-10-30)
A sign-off with `example: true` makes a safety requirement `signed`, but the check message
starts with "EXAMPLE SIGN-OFF, NOT A REVIEW", the CLI prints "signed off (EXAMPLE, not a
review)", the report labels it, and `n2f release` refuses unless
`--allow-example-signoffs` is given (the demos pass it and print a warning). Example products
ship with example sign-offs so their matrices are green and the demos run unattended (D9).

## S-043 — Drawings read features and flat patterns from the part's files (2026-10-30)
The assembly rule reloads already-built parts from STEP; those objects carry no features or
flat pattern in memory, and the drawing rule used to trust them, producing a drawing without
a flat view. Drawings now read `features.json` and `flat_pattern.json` from
`build/parts/<id>/` and take only the shape from memory. Regression test in
`tests/unit/test_drawings.py`.

## S-044 — `kind: reference` parts (2026-10-30)
Owner-supplied or existing items (a wall stud, screws the owner already has) are neither
bought nor made: `kind: reference` parts carry no cost, need no source, are excluded from the
custom ratio and interference (unless the other part is custom), and the manufacturer column
says they are not quoted. Requested by the intake simulation.

## S-045 — Interface frames may reference parameters (2026-10-30)
Frame coordinates accept numbers (mm), quantity strings and `param://` references, resolved
with the spec when the interface is read (S-014). The kiln's hinge and mount frames follow
the guard dimensions, so ECR-001 moves the holes with the box.

## S-046 — Interference volume by inclusion–exclusion (2026-10-30)
`n2f check` measures overlap as V_a + V_b − V(a ∪ b) instead of V(a ∩ b). OCCT's direct
boolean common reported a spurious 15 cm³ for the kiln peephole plug sitting coaxially in its
slightly larger hole (demo-design.sh, ECR-002); the fuse is robust there. The direct common
remains the fallback when a fuse fails. `[verify]` with a stress corpus of coaxial fits.

## S-047 — Example sign-offs never read as verification (2026-10-30)
`checks.json` summaries count example sign-offs under their own key (`example`), the verify
stage stays open with a caveat naming them, `n2f check`/`n2f status` and the report header say
"N example sign-offs (not reviews)" instead of "signed off", and the ladder shows verify as not
done. The release gate's `--allow-example-signoffs` path is unchanged (demos). Gate-3 B9.

## S-048 — First-run notice and `n2f build --offline` (2026-10-30)
The first `import build123d` on a machine takes one to two minutes with no output (OCP native
library load); `n2f build` prints a notice to stderr before importing, and `n2f init`'s hint
says so. `--offline` sets `N2F_OFFLINE=1` so the README can show one switch. Gate-4 B2/C1.

## Review gate 3 (engineering) — outcome (2026-10-30)
Verdict NOT READY on the kiln as built at M8: nine blockers. B1 door skin ~97 degC uncomputed;
B2 guard model double-counted the film coefficient, used a flat-slab loss for walls as thick as
the chamber, and the vent slots were vertical at mid-height; B3 24 m of 1.6 mm wire at 3 kW did
not fit three grooves (pitch 1.2 d) and ran 2.4 W/cm²; B4 stored heat omitted 41 kg of fiber and
double-counted a slab; B5 zero-clearance plug cannot swing; B6 contradictory mounting (notes vs
DXF, hinges on a 1 mm lip, nuts inside hollow tube, no standoff or penetration holes, open
controller tray); B7 stainless-sheathed thermocouple; B8 no over-temperature protection; B9 the
tool counted example sign-offs as verification. All nine are addressed: B9 in the tool (S-047),
B1–B8 by the kiln rework (mean-area two-node thermal model, 2.5 kW / 7 h, five 14 mm grooves,
tray-and-guard plug door with a 6° taper and a bolted hinge post, modelled standoffs and
penetrations, ceramic-sheathed probes, independent limit controller + contactor + door switch;
DEC-012…DEC-017). Concerns logged: B-0011…B-0014; C1/C9 flagged to the owner in the decisions.
The shop read-through (`examples/kiln/reports/shop-readthrough.md`) is kept as written, with a
preface stating which findings the rework answered. `[verify]`: the mean-area conduction model
and the 50 degC gap-air assumption; measure the guard, guard top, door guard and latch.

## Review gate 4 (onboarding) — outcome (2026-10-30)
Every README command ran in order; the report and diff pages load from disk with no errors; no
account needed. Blockers: dead clone URL (the repository is private until launch) and the silent
first-import stall (S-048). Concerns fixed: `N2F_OFFLINE`/`--offline` documented, `uv run` only
inside the checkout, `n2f diff` shown, sign-offs explained, `uv sync --no-dev`, `xdg-open`/
`n2f serve`, `docs/cli.md` regenerated from `--help`. Logged: B-0015, B-0016.

## S-049 — Parents reload up-to-date sub-assemblies from disk (2026-10-30)
When a change invalidates a parent assembly but not a sub-assembly, the parent's run used to
fail ("sub-assembly was not built first"). `load_built_assembly` now rebuilds the in-memory
sub-assembly from its `instances.json` (leaf placements in its own frame; nested groups
flattened one level), reusing parts already loaded. Regression: `tests/e2e/test_nested_assembly.py`.
Found by the kiln rework (changing a stand parameter with the door up to date).

## S-050 — Evidence for parts without geometry (2026-10-30)
A sign-off that cites a bought part with `geometry: none` (a thermocouple, a label, a
standoff) could not bind: parts keyed on geometry only. Such parts now key on their record
(everything but the revision label), so changing the source, cost or notes of a cited part
voids the sign-off and a revision bump does not. Found when re-signing the kiln.

## S-051 — A bolt shared by two interfaces is one hole (2026-10-30)
Interfaces are part-to-part (B-0005), so a bolt that passes through three parts (kiln: shell
→ standoff → guard → stand rail) is written as two interfaces whose patterns coincide on the
middle part. `apply_interfaces` skips a centre already cut at the same spot with the same
diameter, so the middle part's hole table lists each hole once; the pattern record keeps
all centres. The three-party interface stays in the backlog (B-0005).

## S-052 — One report layout, no persona toggle (amends D17) (2026-10-31)
The owner/engineer toggle is gone: reordering the same cards did not make the page
navigable. The report has one layout with a sticky section index grouped Overview / Safety /
Product (3D, parts & cost, drawings, interfaces) / Verification (requirements, rule checks,
sign-offs) / Design record (parameters, decisions, change requests) / Manuals. Requirement
status and trace are one table. Every model URI on the page is a hyperlink to its row (the
`ref` filter over `anchor_for`). The rules × parts matrix is compact dots in a scrollable
area with a sticky rule column. `operator.persona` now only picks the status words. Safety is
always the second section and never collapsed.

## S-053 — The viewer renders on demand (2026-10-31)
The report felt heavy after a few scrolls and switching tabs stalled: the viewer's
`requestAnimationFrame` loop drew ~60 frames a second for the life of the page, at full
device pixel ratio with `preserveDrawingBuffer`, whether or not the model was on screen.
Headless profiling attributed ~97% of the page's scroll cost to it; the 23 inline drawings
cost ~0.5 CPU-s per pass and the base64 GLB and scroll-spy nothing measurable.
`viewer.js` now queues at most one frame, only when something changed (orbit, an API call,
resize, model load) and only while the container intersects the viewport and the tab is
visible; damping keeps queueing frames until the motion settles. `preserveDrawingBuffer`
is gone (`snapshot()` renders before reading back), the pixel ratio is capped at 2, and
`render()` joins the API for callers that mutate the scene directly. The wheel scrolls the
page until the viewer is clicked, so scrolling past the model no longer zooms it.

## S-054 — PyPI publishing through trusted publishers (2026-10-31)
Pushing a `v*` tag runs `.github/workflows/publish.yml`: it checks that the tag, both
package versions and the alias pin agree, builds both, then publishes `napkin2factory`
from the `pypi` GitHub environment and `n2f` from `pypi-alias`. `n2f` is an empty alias
package (`packaging/n2f/`) that depends on `napkin2factory==<same version>`; bump all three
together. PyPI holds both as pending trusted publishers (owner `osaxma`, repo
`napkin2factory`, workflow `publish.yml`); it refuses two projects on one (repo, workflow,
environment), hence two environments. A pending publisher does not reserve a name, so the
names stay unclaimed until the first tag is pushed. Both GitHub environments must exist
in the repository settings before that tag (GitHub creates a missing one on first use,
without protection rules).

## Kiln engineering decisions (2026-10-30)
See `examples/kiln/model/decisions.yaml` DEC-001…DEC-011. The notable one: the owner's
60 degC touch limit cannot be met by a single skin at 1200 degC with any sensible wall
(the inner shell computes to ~109 degC with 64 mm brick + 125 mm fiber), so the kiln has
a ventilated touch guard whose radiation-balance temperature computes to ~53 degC
(`calc://thermal.guard_temperature`). `[verify]`: K23 k = 0.25 W/m·K, fiber board
k = 0.12 W/m·K and ρ = 260 kg/m³, film coefficient 10 W/m²·K, emissivities 0.9, Kanthal A1
ρ = 1.45 Ω·mm²/m, K-factor table, sheet-metal rule thresholds. Element 3 kW / 5 h heat-up
(DEC-004) after 2.5 kW / 4 h gave a margin of 1.0.

## S-055 — Owner ratifies S-052 (NAPKIN_STAGE N2): one layout, persona in dialogue (2026-10-31)
`NAPKIN_STAGE.md` N2 records the owner's ratification of S-052's amendment of D17: the
report — and, in v0.2, the concept board — has one layout for everyone; persona lives in
dialogue, status words and which artifacts lead in conversation, never in CSS reshuffling.
This closes the one D-override v0.1 made on its own authority. v0.2 starts here: branch
`v0.2-build` cut from `53bd7bc` (v0.1 closed; `v0.1.0` tagged on `main`, HANDOFF-REPORT §9).

## S-056 — Version pin across 0.1 → 0.2 (D20): warn, never refuse `[revisit]` (2026-10-31)
`n2f build`, `n2f check`, `n2f status` and `n2f validate` compare the running version with
the product's `system` pin; a mismatch prints one dim line on stderr and **never refuses**
(D10's spirit: upgrading the tool must not lock a person out of their own product; the pin
says what the product was written for). `n2f doctor` shows the pin inside a product.
`schema: 1` is unchanged: v0.2 adds optional files only (`concepts/`, `style.yaml`, a
concept rule pack), so a v0.1 product loads untouched and needs no migration step; upgrade
migrations stay a non-goal until a schema change forces one. Templates and examples now pin
`>=0.2,<0.3`; `__version__` is `0.2.0` on `v0.2-build` from M0 (publishing happens only on
the `v0.2.0` tag, S-054). `[revisit]` if CI builds ever want a strict mode that refuses.

## S-057 — `n2f init` warms the CAD kernel in the background (2026-10-31)
The first `import build123d` on a machine takes one to two minutes with no output (B-0016).
`n2f init` now starts `python -c "import build123d"` as a detached process (own session,
no inherited streams) and exits at once, so the cost is paid while the owner reads the hint;
`n2f build` still prints its kernel note before its own import if it has to wait. Skipped
when build123d is already loaded in-process or `N2F_NO_WARMUP=1` (the test suite sets it in
`conftest.py`). `--json` reports `kernel_warmup`; the next-step line says the kernel is
warming only when a warm-up started. Code: `cli/kernel.py` (`load_cad_kernel` moved from
`build.py`, still re-exported there); the concept verbs reuse it from M1 on (N12).

## S-058 — `validate` reports expression errors alongside reference errors (2026-10-31)
Expression evaluation (cycles, unit mismatches) was skipped whenever any other error existed,
so the gate-3 kiln rework found thirteen bad expressions only after fixing references (B-0018).
Evaluation now runs whenever `parameters.yaml` parsed. Cascade suppression (S-012) narrows to
what it is for: a parameter that is, or transitively reads, one already reported (unsafe
syntax, unknown name, bad unit) is not re-evaluated, so each fault is reported once.
Fixture `tests/fixtures/invalid/expr-and-ref-together`; `EXPECT` lines after the second are
further substrings that must all appear in one run.

## S-059 — True plane section render (amends D12) (2026-10-31)
`section.png` is now a true plane section (B-0017): `render.clip_below` clips every triangle
exactly at Z = section_z (nothing above is drawn), and the cut faces are capped in image
space by back-face capping (viewer above the plane: nearest surface back-facing ⇒ the pixel is
inside a closed solid). Caps are drawn as part colour × 0.65, flat, with 1 px 45° hatch every
8 px at × 0.35 — flat shading alone collides with lit side faces; the hatch is the drafting
convention for cut material. Winding is normalised per mesh by signed volume; open meshes are
clipped but not capped and noted in `Scene.notes` (not yet surfaced: B-0019). Chosen over loop
chaining + triangulation (welding fragility) and OCCT half-space booleans (needs shapes at
render time, per-instance cost). Cost: the kiln assembly section renders in 0.8 s, less than
the full iso. **Judged:** the kiln section shows the shell as a thin red rim, the fiber as
wide hatched bands, the brick liner as a narrower hatched band and the chamber floor below,
with straight edges at the plane — against v0.1's sawtooth slivers. D12 now reads "an
isometric view and a true plane section (clipped, hatched caps)" in place of "a crude section".

## S-060 — Closing a change request waits for human sign-offs (2026-10-31)
`n2f ecr close` now refuses (exit 3) while any check result is `needs-human`, as `n2f release`
already did (B-0015). The wording matches the stage blockers in `core/checks/stage.py`:
"<ECR> cannot close: REQ-004 needs a human sign-off (<why>) — `n2f signoff REQ-004 --by <name>
--statement "…"`; sign it off, then close again". Failing checks are listed first; the
fail-only wording is unchanged. Example sign-offs do not block closing (the release gate and
`--allow-example-signoffs` weigh them), so `examples/kiln/demo.sh` still runs: re-sign with
`--example`, then close. Two e2e tests that closed over an unsigned REQ-004 now sign first.

## S-061 — Owners read model URIs without the scheme prefix (2026-10-31)
`core.uris.display_uri(uri, persona)` is the single display rule (B-0008): for persona
`owner`, human-readable table cells and captions drop a leading model `scheme://` (part, req,
asm, param, dec, ecr, iface, doc, calc, rule, bom) and keep any `#selector`; `engineer` sees
the full URI, byte-identical to before. It applies to the report (ref links, BOM, parameters,
drawing and render captions), the `n2f check` check/subject columns, and the impact summary's
edit lines. JSON, `data-uri`/`data-show3d` attributes, hrefs, GLB node names, the viewer, files
on disk and free-text messages always keep the full URI (copy-paste hints such as
`--set param://…` must stay whole).
