# STATUS

**Branch:** `v0.1-build` · **Current milestone:** M1 done → starting M2
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

## Next (M2)
`geometry/accessors.py` (P, I recording), part protocol + `PartResult`, kit generators
(plate, bracket_l, enclosure, frame, panel, block, tube, hole_pattern), `geometry/build.py`,
exporters (STEP, GLB via `glb.py`, props/features JSON), renders, `geometry/assembly.py`,
`n2f build --target geometry [--part]`, `examples/enclosure`, `tests/validate_outputs.py`,
`docs/render-checklist.md`, golden + hypothesis tests. Exit: open iso renders and judge.

## Open risks
- Per-triangle Python rasterizer may be slow on the kiln (B-0002).
- Plan's Linux DoD is exercised only in CI (S-001).
