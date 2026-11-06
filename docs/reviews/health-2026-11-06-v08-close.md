# Health Review — 2026-11-06 (v0.8 close)

Health review per `docs/reviews/TEMPLATE-health.md` and S-190, at the close of v0.8. Window: 32 commits, `5898aae` (the wave-2
review, S-257) to `45119c8` (HEAD, S-274); `make health` windows from the last touch of `trend.csv`, the same 32. Recorded in
`docs/health/trend.csv` at `45119c8`. Numbers are from commands run here; "not measured" is said where it applies. The coverage
figure is the main folder's `coverage.xml` (written 5 hours before).

## 1. Trend measures

| Measure | 45119c8 | 75100c8 (last row) | Change |
| :--- | :---: | :---: | :--- |
| Modules over 550 lines | 12 | 13 | better |
| Collisions in window | 1 | 1 | same |
| Task conflicts | 0 | 0 | same |
| Unstamped commits | 3 | 0 | worse |
| E10 seam commits since v0.7.0 | 11 | 6 | +5, all with an entry (section 4) |
| Core -> domains / cross-domain imports | 0 / 0 | 0 / 0 | clean |
| TODO/FIXME lines in `src/` | 0 | 5 | better (M2c closed B-0263) |
| Unconfirmed verify rows | 279 | 279 | same, no confirmation work |
| Test functions | 1450 | 1386 | +64 |
| Test skip/xfail marks | 35 | 34 | +1 |
| Coverage line-rate | 0.9391 | 0.9413 | -0.0022 (floor 0.80) |
| Open `BACKLOG.md` rows | 138 | 131 | +7 |

### What got worse
1. **Unstamped 0 -> 3:** `3cb4912` and `a70981f` (handoff edits) and `f74ace9` (S-261's R12 timings and handoff) were committed
   straight on `main`, docs-only, with no `Task-started` trailer. The overseer's way of working, not a lost task. Row B-0287.
2. **Skips +1:** `tests/e2e/test_gate_b.py:209`, `xfail(strict=True)` for B-0285 (`n2f check` shows no failure after the switch to
   C-001). Strict, so it fails loudly when the bug is fixed; tracked by B-0285.
3. **Coverage 0.9413 -> 0.9391:** 61 `src/` files changed (+2871/-1214) with 118 test files; the cause is not measured per file.
4. **Open backlog 131 -> 138:** the Closed table grew too (B-0218, B-0230, B-0265, B-0270 to B-0273, B-0278 and others); new rows are
   gate K and gate B findings (B-0275 to B-0286) and B-0279. B-0264 (stale) closed here.
5. **`test_gate_b_flow` takes 217 s** on the macOS host with a busy machine (S-272, one run); it is `full`-marked, so `make check`
   never runs it, only `check-full` and the nightly. Not a trend column.

### What got better
- Long modules 13 -> 12: `core/concepts.py` 740 -> 364 (S-259, `6db2f10`, move-only into `concept_lint.py` 338 and
  `concept_render.py` 132); no module over 550 was created.
- TODO/FIXME 5 -> 0: M2c (`1c1766e`, S-261) removed the old change-request paths.
- Upward imports into `cli/` from the library 4 -> 1 (section 4): B-0270 done in `f6beb11` (S-262), B-0272 and B-0273 closed.
- Tests +64 functions, 118 test files changed (+2691/-484).

## 2. Collisions and hotspots

One pair: `k-fix-ecr` x `k-fix-labels`, shared file `tests/e2e/test_ecr_live.py` (342 lines, gate K fixes). Not a hotspot: one
file of one family of tests, two fix tasks of the same gate. No row. `docs/agent-guide.md` was edited by M4 (`19a08f4`) alone;
B-0207 (guide as a collision hotspot) stays: M4 is done and the next wave is not planned.

## 3. Long modules

Twelve over 550 lines (`find src -name '*.py' | xargs wc -l`): `domains/electrical/checks/calcs.py` 838, `core/checks/stage.py` 734,
`calckit/thermal_enclosure.py` 686, `core/checks/interface.py` 677, `core/checks/choices.py` 674, `ecr/release.py` 650,
`concepts/screenshot.py` 647, `core/registry.py` 647, `core/checks/engine.py` 599, `core/checks/calcs.py` 579,
`core/graph/rules.py` 560, `domains/electrical/outputs/diagram_layout.py` 553. Unchanged from the last review except `core/concepts.py`
(left). Nearest: `report/builder.py` 549, `geometry/kit/enclosure.py` 547, `geometry/assembly.py` 543, `domains/electrical/model/refs.py` 537.
v0.8 modules: `cli/concept.py` 441, `cli/undo.py` 383, `ecr/live.py` 361, `concepts/switch.py` 326, `concepts/board.py` 519.

Upcoming tasks that touch them: none planned after v0.8 in `docs/stages/`. B-0244 (electrical `calcs.py`, `diagram_layout.py`) and
B-0245 (`report/builder.py`) stay open and unchanged. `concepts/board.py` (519) took the built-card marking in M3a; watch it.

## 4. Modularity and seams

Eleven seam commits since v0.7.0 (E10 paths); the five new ones, each with an entry that names the files:
`6db2f10` S-259 (`core/concepts.py`, `concept_lint.py`, `concept_render.py`), `1c1766e` S-261 (`core/graph/impact*.py`, `lint.py`,
`loader.py`, `model/concepts.py`, `model/ecr.py`, `model/migrate.py`, `vcs.py`), `f6beb11` S-262 (`cli/check.py`, `core/graph/runner.py`),
`dd6b334` S-263 (`concept_lint.py`, `concepts.py`, `loader.py`, `model/__init__.py`, `model/concepts.py`, `vcs_store.py`), `77d94eb`
(`concept_render.py`, covered by S-267). B-0246 (land warns about an unnamed seam file) stays open; the discipline held again.

Layers: `core_domain_imports` 0, `cross_domain_imports` 0. Imports from the library up into `cli/`: 4 -> 1, `core/graph/runner.py:203`
(`cli.common.console`); `mcp/tools.py:213` imports `cli.app` by design. `ecr/live.py`, `ecr/live_impact.py` and `ecr/release.py` now
import `ecr/checkpointing.py` (S-262). B-0274 (a measure for this) stays open; its baseline text is corrected to 1.

## 5. Deterministic tests

- **CI on `main`:** not checked (no `GH_TOKEN` in this task). From history: no commit in the window is a test-stability fix
  (`git log` subjects: none mention flake, retry or rerun).
- **Skips/xfails:** 35 (+1), the strict xfail above. No other change in `git diff 75100c8..HEAD -- tests`.
- **Wall clock / network / randomness:** grep of `tests/` for `datetime.now`, `time.time(`, `import random`, `urlopen`, `httpx`,
  `requests.`, `import socket`: no code hit (one docstring). `time.perf_counter` stays in the five N2F_TIMING-gated files; the new tests
  of the window add none.
- **Gate B:** `tests/e2e/test_gate_b.py` runs in-process on a prebuilt tracked copy; its 217 s is not a determinism problem.

## 6. Rules no test catches

- **README commands:** `README.md` has not changed since v0.7.0 (`git log v0.7.0..HEAD -- README.md`: none); no shell commands in it.
- **Guide against `n2f --help`:** 28 top-level verbs and 11 `ecr` sub-verbs. `tests/unit/test_cli_doc_rows.py` (B-0271, S-268) now
  fails when `docs/cli.md` lacks a row; all 28 and all 11 have one. The guide teaches `ecr start/impact/approve/close/quick/abort`
  (`docs/agent-guide.md:384-393`); `new`, `apply`, `reject`, `list`, `show` are in `docs/cli.md` only, `apply` is gone from the live flow
  ("There is no patch and no apply step", line 393). No mismatch found. The guide itself has no test against `--help`.
- **Owner words:** strings added to `cli/`, `ecr/`, `concepts/`, `mcp/` since the last review: no git vocabulary found
  (`tests/unit/test_vocabulary.py` is in the unit suite; not re-run here).

## 7. Vision alignment (`docs/roadmap/road-to-v1.0.md`)

1. **Accuracy:** nothing landed; 279 verify rows unchanged (B-0208). Gate K found two honesty gaps in the change report, fixed by
   S-274 (every impact figure labelled computed or estimate).
2. **Robustness:** schema 2 with the first real migration (S-261, `core/model/migrate.py`); gate K blockers and later findings
   B-0275, B-0281 to B-0283 (abort and upgrade corners, a clone without `refs/n2f/`) are open.
3. **Reliability:** change-request ids are never reused after a rollback and approval is bound to the approved checkpoint (S-273);
   `concept switch` parks and restores a direction (S-264). Open: B-0284 (the undo property test has no `ecr abort` or `concept
   switch` operation), B-0285, B-0286.
4. **Ease of use:** the guide and roles teach checkpoints, live change requests and directions (S-268); the oracle replays a change
   request (S-269). Gate B ran as a scripted flow (S-272); the cold-agent trial of B-0266 is not run.

## 8. Housekeeping

- **`make tasks`:** `b-fix-seed` (unsaved changes, 0 ahead, gate B fixes), `b0279` (2 commits, clean, minutes old) and this review.
  Nothing stale; the first two are live work of other agents.
- **Backlog rows whose work is done:** B-0264 (promotion one-way) closed here by S-264 and S-265. B-0274's baseline said 4, now 1.
  B-0266 still true (cold agents not run); B-0207 and B-0246 still true.
- **Broken links:** 9 relative targets in `docs/` and root `.md` files that do not exist, the 8 of the last review (untracked
  `OWNER-TODO.md`, six `file://<scratch>` placeholders in closed records, one literal `](path)`) plus the same literal `](path)` in
  `health-2026-11-05.md`'s prose, which the last count missed. Left as they are (closed records).
- **Repository root:** tracked root files are the expected ones (`AGENTS.md`, `BACKLOG.md`, `DECISIONS.md`, `LICENSE`, `Makefile`,
  `README.md`, `STATUS.md`, `pyproject.toml`, `uv.lock`, dot-files); no untracked notes seen in this folder.

## Version close: `core/` files touched since v0.7.0

`git diff --name-only v0.7.0..HEAD -- src/napkin2factory/core | sort -u | wc -l` = **17**: `checkpoints.py`, `concept_lint.py`,
`concept_render.py`, `concepts.py`, `graph/impact.py`, `graph/impact_live.py`, `graph/impact_patch.py`, `graph/runner.py`, `lint.py`,
`loader.py`, `model/__init__.py`, `model/concepts.py`, `model/ecr.py`, `model/migrate.py`, `vcs.py`, `vcs_store.py`, `vitals.py`
(all under `src/napkin2factory/core/`). Wave 2's count was 10 (S-257); waves 3 and 4 added `concept_lint.py`, `concept_render.py`,
`concepts.py`, `loader.py`, `model/concepts.py`, `model/migrate.py`, `impact.py`.

## Findings and actions

| # | Finding | Action | Row |
| ---: | :--- | :--- | :--- |
| 1 | Three docs-only handoff commits on `main` read as unstamped | row | B-0287 |
| 2 | B-0264 was done (S-264, S-265) | closed here | none |
| 3 | B-0274 baseline said 4, now 1 | text corrected | none |
| 4 | Gate B's cold-agent trial and the three open undo/switch gaps (B-0266, B-0284, B-0285) | already tracked | none |

Fixed in this task: BACKLOG rows only (no `src/` or test change). Outcome: `DECISIONS.md` S-276, citing `45119c8`.
