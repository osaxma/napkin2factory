# Decisions log (system build-out)

Decisions beyond `GRAND_PLAN.md` §2, with rationale. `[revisit]` marks ones the owner may
want to reopen; `[verify]` marks engineering numbers taken from published sources that a
human should confirm before relying on them.

## S-001 — Host platform differs from the plan (2026-10-30)
The build runs on an Intel macOS host (Darwin 25.6, x86_64, 16 cores, 32 GB), not the
sandboxed Linux the plan assumed. Nothing in the plan is Linux-specific; CI (`ci.yml`)
runs both `ubuntu-latest` and `macos-latest` so the Linux definition of done is exercised
there. `[revisit]` The owner should run `make check-full` once on Linux before relying on
the DoD timing numbers.

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
`[revisit]` Whether the owner's own name should be prompted for during intake.

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
