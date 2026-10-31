# STATUS

**Branch:** `v0.2-build` (cut from `53bd7bc`, the v0.1 close-out) · **Current milestone:** M3 (styled imagery, style.yaml, kit aesthetics), in progress
**Contract:** `NAPKIN_STAGE.md` (v0.2, the napkin stage); `GRAND_PLAN.md` §0/§8/§9 and its D-series still apply.
**Resume note (2026-10-31):** M0–M2 committed. M3 (styled viewer screenshots via Playwright,
`style.yaml` presets, six opt-in kit aesthetic parameters) is running as one subagent from a brief in the
orchestrator's scratchpad; then M4 (board + promotion + `rule` verify kind), gate A, M5 (skills), M6 (kiln
retrofit + `demo-napkin.sh`), gate B, M7. If you find the tree uncommitted: run `make check`, then commit.
**Resume order:** `NAPKIN_STAGE.md` → this file → `DECISIONS.md` (S-055 onward) → `git log --oneline -30` → `make check`

## Environment (host facts a cold reader needs)
- Intel macOS host (reference platform, S-001). `uv` at `~/.local/bin/uv` (add to PATH; no `timeout`
  command on this host). Python 3.13.18 managed by uv. Playwright Chromium installed and working.
- OCP wheel: `cadquery-ocp-novtk 7.9.3.1.1` → z-buffer render path (S-002); viewer screenshots via
  Playwright are v0.2's appearance path (N6).
- `make check` ≈ 11 min; `make check-full` adds the kiln (≈ 1 min build) and both demos (≈ 13 min).
- Published: `napkin2factory 0.1.0` and alias `n2f 0.1.0` on PyPI (S-054); CI green on Linux and macOS.

## v0.2 — done
- **M0 (done 2026-10-31)** — branch `v0.2-build`; version 0.2.0, every pin `>=0.2,<0.3`; S-055
  (N2 ratification); S-056 (pin policy: warn, never refuse; schema 1 unchanged; `n2f doctor` row);
  README installs from PyPI first; `docs/concepts.md` → `docs/how-it-works.md`; CI triggers on the
  branch. Folds, each with regression tests: B-0015 `ecr close` refuses on missing sign-offs
  (S-060); B-0008 owner tables drop URI prefixes via `core.uris.display_uri` (S-061); B-0016
  `n2f init` warms the kernel in a detached process (S-057); B-0018 validate reports expression
  and reference errors together (S-058); B-0017 true plane section (S-059). **Section judgment
  (M0 exit):** the kiln section now shows a flat cut plane with straight rims — thin red shell
  band, wide hatched fiber bands, a narrower hatched brick-liner band around the chamber, the
  chamber floor and element grooves lit below the plane; v0.1's sawtooth slivers are gone. Kiln
  assembly section renders in 0.8 s. `make check-full`: 387 passed, 1 skipped, 7 deselected
  (12 min 25 s), kiln + both demos + timing green.

- **M1 (done 2026-10-31)** — concept cards outside the build (N1): schema, loader, lint C1–C6
  (C5 warns), `n2f concept new|list|show|reject|lint`; optional Napkin gate first in `n2f status`
  (N11, report excluded); `n2f init` seeds `style.yaml` (N7); S-062. `make check`: 429 passed,
  1 skipped, coverage 88.7 %.
- **M2 (done 2026-10-31)** — massing fidelity in every kit generator (S-063), the calc kit with the
  kiln's numbers reproduced bit-for-bit (S-064), and concept screening: `n2f concept build [C-xxx|--all]`
  composes cards into `build/concepts/` outside the build graph, labels every number computed or
  estimate, runs `concept-v0` and screens the DEC-011 kiln red on an 800 mm alcove with the door swing
  counted — and on a one-piece blank larger than any stock sheet (S-065). Warm `concept build --all` on
  the two-card fixture: 1.2 s. `make check`: 482 passed, coverage 90 %.

## Next
M3: `style.yaml` presets and roles, six opt-in kit aesthetic parameters, the Playwright screenshot rig
with the z-buffer fallback logged, the "product image" checklist and a judged exit. Then M4.

## Open risks
- Linux is covered only by CI (`ci.yml` ubuntu job); the reference platform is this macOS host (S-001).
- Playwright screenshot loop speed (N6/M3) and massing-mode feature leakage (N3/M2): see
  `NAPKIN_STAGE.md` §7 for the fallbacks.

## v0.1 — closed 2026-10-31
Released as `v0.1.0` on `main`, published to PyPI, CI green on Linux and macOS; `HANDOFF-REPORT.md`
has the definition-of-done evidence, the dropped items, the `[verify]` numbers and the demo script.
Milestone notes kept for the record:

- **M0** — skeleton, `pyproject.toml`, `Makefile`, `ci.yml`, `CLAUDE.md`, journals,
  handoff/review moved to `docs/history/`, three.js r170 vendored with hashes (S-003),
  `report/inline.py` + `viewer.js` inliner, `geometry/glb.py` in-house GLB writer (S-004),
  `geometry/render.py` z-buffer renderer, `tests/smoke/test_toolchain.py` (9 capabilities),
  `tests/smoke/test_viewer_skeleton.py` (file:// proof via Playwright: no console errors,
  one mesh / two instances). Looked at the viewer screenshot: two shaded brown cubes, correct.

- **M1** — `core/model/*` (all §4.2 schemas, strict, quantities as pint via `Quantity`),
  `core/uris.py` (+ selectors, instances), `core/units.py` (USD defined; d/degC pinned),
  `core/expr.py` (safe AST, S-007), `core/loader.py` (Product, cross-refs, S-009/S-012),
  `core/lint.py` (L1–L11), `core/vcs.py` (D31 wrapper, S-011), `cli/{validate,init}.py`,
  `templates/{_common,blank}` + `templates/sync.py` (S-010), `examples/bracket`.
  Tests: 29 invalid fixtures (`tests/fixtures/invalid/*/EXPECT`), units/uris/expr/schemas,
  vcs persona wording, vocabulary grep, template equality, init→validate→lint e2e.

- **M2** — `geometry/accessors.py` (P/I + ReadLog, `resolve_interface`), `features.py`
  (Features/Dim/FlatPattern/CutItem/PartResult), `kit/` (plate, block, tube, panel,
  hole_pattern, bracket_l, enclosure, frame; `_sheet.py` K-factor/bend allowance/bend solid;
  `_common.py` Length/Angle/Count validators), `exporters.py` (STEP, GLB, props with mass
  from `materials.py`, features JSON, renders), `assembly.py` (place/grid/flatten, GLB with
  groups, props), `build.py` (build_part/build_assembly/build_geometry, S-013 interface
  application), `n2f build --target geometry [--part]`, `examples/enclosure` (base, lid,
  2 brackets, 4 screws, bolt-pattern interface with per-party frames S-014),
  `tests/validate_outputs.py` (geometry stage), `docs/render-checklist.md`, goldens per
  generator (`tests/golden/goldens/*.json`), hypothesis property tests, build tests.
  **Render judgment (M2 exit):** `examples/bracket` iso shows an L with a rounded bend and
  two holes per leg; `examples/enclosure` iso shows a tray with a lid whose four corner
  holes sit over the lip pattern, two brackets behind the back wall; section shows the open
  tray with uniform walls. Both match the YAML. Flat area × t vs volume: 0.996 (bends).
  `make check` ≈ 1.5 min.

- **M3** — `core/graph/` (hashing, manifest with atomic writes, rules list, values,
  runs, runner with needs-run/`--jobs`/interruption hook, impact, export), `bom/rollups.py`
  (quantity/cost/mass/lead rollups with recorded selector reads), `docs/engine.py` (Jinja2
  with recording proxies, S-021), placeholder drawing/checks/report/site runs that record
  their true read sets, `n2f build` through the DAG (all targets), `n2f graph`, `n2f impact`.
  Invalidation suite `tests/e2e/test_invalidation.py` (exact sets, no-op, interruption both
  sides of the manifest write, impact == rebuild, hypothetical param_bound and cost
  verdicts, `--jobs 2` ≡ `--jobs 1`, clean, missing output). `make check` runs the full
  `n2f build` for both examples (~2.5 min).

- **M4** — `core/checks/` (results, evidence keys S-024, calc runner, evaluators per verify
  kind with the safety ladder S-026, interference with D29 allowed contact, interface
  conformance, stage computation, engine writing `checks.json` with matrix + summary),
  `rulepacks/` (sheet-metal-v0, general-v0; named checks S-022), `catalog/common.yaml`,
  `bom/validation.py` (D15 tiers, offline default S-023), `n2f check|status|signoff`.
  Tests `tests/e2e/test_checks.py`: overlapping/touching blocks, mating-face allowed
  contact, interface mismatch, tight bend radius fails, sign-off ladder incl. evidence
  change, refuse signing a failing requirement, exit code 2, stage progression incl. warn
  never moving the stage, doc staleness, calc requirement with recorded reads.

- **Review gate 1** — six blockers fixed (S-027…S-031) with regression tests; cheap concerns
  fixed; rest in BACKLOG B-0004…B-0006.

- **M5 (in progress)** — report (`report/builder.py`, template, viewer explode/section/
  select, `n2f serve`, Playwright smoke) done and judged; since S-052 one layout for everyone:
  sticky section index, Safety second, every model URI a link to its row; viewer frames the
  enclosure, explode lifts the lid, clicking a part highlights its BOM row; no console errors
  from `file://`; 1.8 MB. Drawings engine (subagent) judged on `examples/enclosure` base:
  third-angle views, dashed hidden lines, legible dims outside the views, flat pattern with
  bend labels, hole table, title block — reads as a drawing a shop could quote from. Two
  defects it found are fixed: lid-mount holes moved onto the lips (model), and interface
  holes now carried into flat patterns via `PartResult.flat_map` (S-034). Docs: HTML via
  markdown-it-py, PDF via the in-house Typst emitter (`docs/typst.py`, 7 goldens; bundled
  Libertinus Serif), safety banner; judged the assembly page PNG: title, templated values,
  disclaimer. BOM: `bom.csv` + `bom.xlsx` (BOM/Rollups/Parts/Manufacturer sheets).
  `tests/validate_outputs_full.py` covers drawings, DXF, BOM files, docs, report.
  `make check` ≈ 6 min. **M6 part 1 (ECR lifecycle)** also landed: `ecr/lifecycle.py` +
  `n2f ecr new|impact|approve|apply|close|reject|list|show`, line-targeted parameter edits
  (one-line diffs), revision bumps at close, CHANGELOG append; `tests/e2e/test_ecr.py`.

- **M6** — `ecr/release.py` (gates via stage, Revision tag, ZIP with STEP/drawings
  SVG+PDF/DXF/BOM/manuals/report, frozen `build/site/vX.Y.Z/` with diff data, S-038),
  `ecr/diff.py` + `report/templates/diff.html.j2` (overlays red/green at one scale, BOM
  delta with cost/mass, parameter and verdict deltas, side-by-side 3D with highlighting,
  S-039), `n2f release|diff`, site index/versions page. Evidence keys for parts are now
  geometry-based (S-040); `n2f check` keeps renders (S-041). Tests
  `tests/e2e/test_release_diff.py`: refusals (unsigned safety, unsaved changes, evidence
  changed, failing check, not a project root, duplicate Revision), package contents, site,
  ECR → release → diff, diff page loads from file:// with two viewers. Docs pages written:
  concepts, vocabulary, product-model, kit, checks, ecr-loop, cli.

- **Review gate 2** — five blockers fixed (S-042 and snapshot/discard/init/status changes),
  most concerns fixed; rest in BACKLOG B-0007…B-0009.
- **M7** — skills/agents/CLAUDE.md expanded (schema cheat sheet, verify target forms, assembly
  API, rotation convention), `docs/agent-layer.md`, weak-intake lint fixture, scripted intake
  simulation passed (fresh-context subagent → validate + lint clean, silhouette built);
  transcript in `tests/e2e/intake-transcripts/monitor-bracket.md`. Its feedback produced
  `kind: reference` (S-044) and the skill additions.
- **M8 (in progress)** — `examples/kiln`: 21 parts, 2 assemblies, 3 interfaces, 17
  requirements, 11 decisions, 6 manuals, 2 calcs with hand-checked tests, 4 example
  sign-offs, ECR-001 (parametric) and ECR-002 (design, with `changes/ECR-002.patch`),
  `demo.sh`, `demo-design.sh`. Check matrix: 0 fail, 4 signed (EXAMPLE), 133 pass, 20 warn;
  no interferences; mass 108 kg; 907 mm wide. **Render judgment:** iso reads as a kiln (boxed
  body on a four-leg stand, hinged door with latch, controller box beside); section through
  the centroid shows the fiber and brick layers around the chamber. Shell and side-liner
  drawings legible (1:15 shell flat pattern 1770 mm blank; liner grooves dimensioned).
  `tests/validate_outputs.py` passes on the kiln. `demo.sh` passes end to end (v1.0.0 →
  ECR-001 → v1.1.0 → diff). **Diff page judged:** nine parts changed with revs A → B, mass
  +6.9 kg, cost unchanged; shell overlay shows the taller green box over the red original at
  one scale; side-by-side 3D highlights changed parts (fixed to show the top assembly rather
  than the door sub-assembly). Remaining: `demo-design.sh` as a test, kiln golden,
  `make check-full`, gate 3 (engineering + shop read-through).

- **Review gate 3 (engineering)** — nine blockers on the kiln (DECISIONS "Review gate 3");
  the tool fix S-047 (example sign-offs never read as verification) and the kiln rework
  (DEC-012…DEC-017: plug door with tray and guard, bolted hinge post, modelled standoffs and
  penetrations, mean-area two-node thermal model with both guards computed, 2.5 kW / 7 h
  element in five grooves, independent over-temperature limit, earth bonding, ceramic-sheathed
  probes). Shop read-through kept with a preface. Core fixes found on the way: S-049 (parents
  reload cached sub-assemblies), S-050 (evidence for parts without geometry), S-051 (shared
  bolts are one hole), each with a regression test.
- **Review gate 4 (onboarding)** — README/docs/cli.md rewritten, `n2f build --offline`, the
  first-run kernel notice (S-048), `n2f init` hint.
- **M9** — README, docs, `n2f doctor`, `uv build` + `twine check`, PyPI names checked, gate
  outcomes journaled, `HANDOFF-REPORT.md`, `make check` excludes kiln/demos (`-m "not full"`,
  D27) and `make check-full` runs them.
