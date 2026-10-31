# STATUS — napkin2factory

**Version:** 0.2.0, released 2026-11-01 (`v0.2.0` on 42f0672; `main` at the same commit) ·
**Release branch:** `v0.2-build` (next work continues here until a v0.3 branch is cut) ·
**Open work:** `BACKLOG.md` · **Why things are the way they are:** `DECISIONS.md` (index at the top) ·
**What shipped:** `HANDOFF-REPORT-v0.2.md` (v0.2), `HANDOFF-REPORT.md` (v0.1)

## Where we are
v0.2 (the napkin stage) is complete and published: M0–M7 done, review gates A and B closed with
their blockers fixed, `make check-full` green from a clean clone. Uncommitted or pending on this
branch: journal consolidation (this layout), brand integration (`brand/`, in progress separately).

## Environment (host facts a cold reader needs)
- Reference platform: the macOS host (S-001); Linux is covered by the CI matrix. Python 3.13 via
  `uv`; OCP novtk wheel, renders through the built-in rasterizer; Playwright Chromium installed.
- `export PATH=$HOME/.local/bin:$PATH` before `uv`. No GNU `timeout`; `sed -i ''`.
- `make check` ≈ 8 min (tests in parallel, S-070); `make check-full` ≈ 28 min; the first
  `import build123d` on a machine takes one to two minutes (S-057).
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
