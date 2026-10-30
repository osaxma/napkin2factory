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
