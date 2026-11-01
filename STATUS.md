# STATUS — napkin2factory

**Version:** 0.3.0, released 2026-11-01 (tag `v0.3.0`) · **Trunk:** `main`; work happens in task
worktrees (`make task`, `make land`; S-097); the old `v*-build` branches are closed ·
**Open work:** `BACKLOG.md` · **Why things are the way they are:** `DECISIONS.md` (index at the top) ·
**What shipped:** `HANDOFF-REPORT-v0.2.md` (v0.2), `HANDOFF-REPORT.md` (v0.1)

## Where we are
v0.2 (the napkin stage) is complete and published: M0–M7 done, review gates A and B closed with
their blockers fixed, `make check-full` green from a clean clone.
v0.3 is released: journal consolidation (S-073), README for people and the agent guide (S-074),
the icon and the wordmark on generated pages (S-075, S-081), `AGENTS.md` only (S-076), generic
roles in `roles/` (S-077), gate reports kept and visual exits judged by the maintainer (S-078),
faster checks (S-079, S-080, S-084), relative paths in `validate.json` (S-082), product pin
`>=0.3,<0.4` (S-083). Since 0.3.0, unreleased on `main`: the v0.2 leftovers (S-085–S-096),
including share mode `n2f publish` (S-094) and the product release workflow's dry-run fix (S-095);
B-0022 (cost bands), B-0036 (MCP server) and B-0047–B-0049 left open by the maintainer; one trunk
and a worktree per task (S-097). Releasing a version: bump the three version files and the pins
(S-054, S-083), `make check` on `main`, push, wait for CI, tag `v<version>` on that green commit
(S-072).

## Environment (host facts a cold reader needs)
- Reference platform: the macOS host (S-001); Linux is covered by the CI matrix. Python 3.13 via
  `uv`; OCP novtk wheel, renders through the built-in rasterizer; Playwright Chromium installed.
- `export PATH=$HOME/.local/bin:$PATH` before `uv`. No GNU `timeout`; `sed -i ''`.
- Tasks (S-097), measured 2026-11-01: `make task` takes ≈ 2 s (worktree + `uv sync` from the shared
  cache). macOS scans each newly written native library on first load (`syspolicyd`): 117–190 s
  for the first `import build123d` in a cloned environment. `make task` installs with hardlinks,
  so later task folders reuse the scanned files: 10 s (S-NEW1); the import is also warmed detached.
- `make check` ≈ 7 min (tests in parallel, S-070; long files split, S-080, S-084);
  `make check-full` ≈ 21 min (2026-11-01: `check` 7 min 27 s, then kiln, demos side by side
  and timing 13 min 27 s; was ≈ 28 min, S-079); the first `import build123d` on a machine takes
  one to two minutes (S-057).
- Never run `n2f build` inside `examples/`; copy a product to a temp folder first
  (`tests.conftest.copy_product`). Templates are synced with `make templates`, never hand-edited.

## Milestones (one line each; detail in the entries named)
v0.2 — `NAPKIN_STAGE.md`:
- M0 folds and ratifications — S-055–S-061.
- M1 concept cards, loader, lint, optional Napkin gate — S-062.
- M2 massing fidelity, calc kit, screening — S-063, S-064, S-065.
- M3 styled screenshots, `style.yaml`, kit aesthetics — S-066.
- M4 board, promotion, form requirements, `rule` verify kind — S-067.
- Gate A (honesty + architecture) — "Review gate A — outcome".
- M5 PM-skill napkin protocol, DoD 7 simulation — S-068.
- M6 kiln retrofit, `demo-napkin.sh` — S-069.
- Parallel `make check` — S-070. Gate B (UX, owner persona) — "Review gate B — outcome".
- M7 close-out, release, CI gate — S-071, S-072.

v0.1 — `GRAND_PLAN.md`, closed 2026-10-31: M0–M9 and gates 1–4 — S-001–S-054 and the four gate
entries; `HANDOFF-REPORT.md`. The former milestone paragraphs are kept verbatim in
`docs/history/STATUS-through-v0.2.md`.
