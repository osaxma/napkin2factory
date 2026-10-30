# STATUS

**Branch:** `v0.1-build` · **Current milestone:** gate 1 fixed → M5 in progress (drawings + docs/BOM agents running; report next)
**Resume order:** `GRAND_PLAN.md` → this file → `DECISIONS.md` → `git log --oneline -30` → `make check`

## Environment (host facts a cold reader needs)
- Intel macOS host (not Linux; see DECISIONS S-001). `uv` installed at `~/.local/bin/uv`
  (add to PATH). Python 3.13.18 managed by uv. Playwright Chromium installed and working.
- OCP wheel: `cadquery-ocp-novtk 7.9.3.1.1` → render path is the numpy z-buffer (S-002).

## Done
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

## Next (M5)
Fold in review gate 1 findings (blockers fixed, rest to BACKLOG). Then M5: drawings (D11:
three views + iso, hidden lines, dims, hole table, title block in `<g id="titleblock">`,
flat-pattern view + DXF), BOM CSV/XLSX, docs HTML (markdown-it-py) + PDF (Typst emitter),
the real self-contained report (D13/D17) with viewer, galleries, matrix, persona toggle,
`n2f serve`, Playwright smoke, `validate_outputs.py` extended.

## Open risks
- Plan's Linux DoD is exercised only in CI (S-001).
