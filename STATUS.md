# STATUS

**Branch:** `v0.1-build` · **Current milestone:** M2 done → starting M3
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

## Next (M3)
`core/graph/` (rules, keys, manifest, needs-run, impact), `n2f build` through the DAG for
all targets (placeholders for docs/checks/report until M4/M5), `n2f graph`, `n2f impact
--set`, `--jobs N` spawn pool. Invalidation suite on enclosure (§6.4): `lid-thickness` →
part:lid, asm:enclosure, drawing:lid, bom, doc:assembly, checks, report, site; unused param
→ validate only; generator source change; interface spec change → both parties.
Then review gate 1 (fresh-context reviewer, §8.3 architecture checklist).

## Open risks
- Plan's Linux DoD is exercised only in CI (S-001).
