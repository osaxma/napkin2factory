# Task: gate G blockers 1 and 2 — the protection and Class II checks (commit subjects `M7: …`)

Opened by the third overseer (2026-11-03) from gate G's report, `docs/reviews/v0.6-gate-g.md`
(read its §9 and its "Blockers" 1 and 2; quote its test cases). A domain fix, not a seam: both live
in `src/napkin2factory/domains/electrical/checks/`. Hand this with `brief-common.md`.
Task folder: `.worktrees/gate-g-checks` on `task/gate-g-checks` (created by the overseer).

## What is wrong (measured by the reviewer at f67dc06)
1. **A conductor below its protective device passes.** The minimal fixture with every conductor
   0.75 mm² PVC (8.5 A) on a 32 A supply and breaker reads "conductor-current@heater | pass |
   … every conductor is rated for it". Conductors are judged only against the load
   (`checks/calcs.py:612-630`), never against the device that protects them
   (`checks/stage.py:395-430`). The kiln's 0.75 mm² control wiring under a fuse with no rating
   passes too.
2. **The Class II shortcut passes a metal box.** The unearthed fixture (mild-steel box) with the
   heater Class II and its PE removed reads "earth-path@product | pass | Every device is Class
   II or III …, so no part needs a path to earth." (`checks/stage.py:550-558`): the product's own
   single-insulated mains conductors still run inside that steel box.

## Build (generic words only, F9; E6: `fail` only for arithmetic and topology)
1. Each conductor's rating (the table's, as the load check reads it) against the rating of the
   protective device upstream of it on its circuit (`protective_rating()` or its equivalent):
   below it → `fail`, naming the conductor (connection), the circuit, both ratings with their
   labels (given / from the table), and what to do (a thicker conductor, or a device rated for
   it; a licensed electrician decides). A protective device with no rating → `warn`: "its rating
   is not given, so whether it protects its conductors is not checked; a licensed electrician
   decides". A circuit that needs no protective device (the checks' own set) is skipped. Decide
   whether this is a new check row or part of the conductor row; say which in your entry.
2. Class II: the shortcut may pass only when no conductor of a mains circuit is in or passes
   through a conductive custom part. If the model cannot tell where conductors run, then any
   conductive custom part plus any mains circuit → `warn` (not `pass`, not `fail`): "every device
   is Class II or III, but the product's own wiring runs in <part>, which conducts: whether the
   product as a whole is Class II is a licensed electrician's call; or run an earth conductor to
   it". Name the part.
3. Fixtures under `tests/fixtures/electrical/` for both (the reviewer's two cases), with tests;
   the existing six DoD 3 fixtures keep their results.
4. The kiln: expect its control circuit's fuse (no rating) to raise the new `warn`; that is the
   honest result. Run `tests/e2e/test_kiln.py`; if a kiln test pins the count of warns, update
   only that count, and say so. No kiln model edit.
5. DECISIONS.md: one entry (a placeholder id, as brief-common.md says) citing gate G blockers 1–2; BACKLOG.md rows only if you
   leave something.

## Owns
`src/napkin2factory/domains/electrical/checks/`, the domain's rule pack
(`domains/electrical/checks/*.yaml`) if a message or param needs it, `tests/fixtures/electrical/`,
the domain's unit tests, kiln test counts in `tests/e2e/test_kiln.py` only if moved, goldens of
electrical checks only (`make goldens REASON="…"`), `DECISIONS.md`, `BACKLOG.md`.
## Must not touch
`src/napkin2factory/core/`, `report/builder.py`, `docs/engine.py`, `cli/check.py` (E10: if you
need one, stop with a `WIP:` naming it), `domains/electrical/outputs/` and `owner/` (another task
fixes the disclaimer there), `examples/`, `STATUS.md`, `docs/v06-handoff/`, the untracked
`FIX_CI_NIGHTLY.md` in the main folder.
## DoD
Both blockers fixed with fixtures; run `make lint`, `make types`, the domain's tests,
`uv run pytest tests/golden -q`, `tests/e2e/test_kiln.py`; then `make land` from the worktree.
Report: landed commit, decision id, the messages your new rows print (quoted), the kiln's new
row(s), test numbers, gate time, 0 core files (`git show --stat`).
