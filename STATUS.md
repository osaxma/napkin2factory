# STATUS

**Branch:** `v0.1-build` · **Current milestone:** M0 done → starting M1
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

## Next (M1)
Schemas in `core/model/`, `core/uris.py`, `core/units.py` (degC/USD/d), `core/loader.py`,
`core/vcs.py`, `n2f validate|lint|init`, `examples/bracket`, templates sync + equality test.

## Open risks
- Per-triangle Python rasterizer may be slow on the kiln (B-0002).
- Plan's Linux DoD is exercised only in CI (S-001).
