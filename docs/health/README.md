# Project Health Measures

Deterministic measures of codebase health, team coordination, and architectural layering,
tracked across landing windows and releases to prevent drift, collision, and hidden debt.
Periodic reviews use the health review brief at `docs/reviews/TEMPLATE-health.md`.

## What each measure means and why it is tracked

1. **Modules over 550 lines** (`long_modules`)
   - *Meaning:* Count of Python source files under `src/` exceeding 550 lines.
   - *Why tracked:* Large files increase cognitive load and form the primary bottleneck where parallel agents collide (S-080, S-184, B-0185).

2. **Collisions in the window** (`collisions`)
   - *Meaning:* Pairs of stamped tasks active simultaneously whose changed files intersect outside journals (`DECISIONS.md`, `BACKLOG.md`, `STATUS.md`).
   - *Why tracked:* Detects concurrent development collisions across worktrees without relying on manual coordination (S-194, S-080).

3. **Task conflicts** (`task_conflicts`)
   - *Meaning:* Sum of `Task-conflicts` recorded in stamped commit trailers across the window.
   - *Why tracked:* Measures landing and rebasing friction encountered by agents before landing on `main` (S-194).

4. **Unstamped commits** (`unstamped_commits`)
   - *Meaning:* Commits in the window lacking task provenance trailers (`Task`, `Task-started`, `Task-conflicts`).
   - *Why tracked:* Ensures all task work is attributed and tracked through the landing gate (S-194).

5. **E10 seam commits** (`e10_seam_commits`)
   - *Meaning:* Commits since the latest `v*` tag touching core and contract seam files (`core/`, `report/builder.py`, `docs/engine.py`, `cli/check.py`).
   - *Why tracked:* Seam edits represent v0.5 contract defects and must be audited and minimized as domain features land (E10).

6. **Core -> domains static imports** (`core_domain_imports`)
   - *Meaning:* AST imports of specific domain implementations (`napkin2factory.domains.<name>...`) from modules under `src/napkin2factory/core/` (importing the package root `INSTALLED` list is the designed seam, E10).
   - *Why tracked:* Core contracts must remain domain-agnostic and never directly depend on domain implementations (F9, S-128).

7. **Cross-domain imports** (`cross_domain_imports`)
   - *Meaning:* AST imports from one `domains/<a>/` package into another `domains/<b>/` package ($a \ne b$).
   - *Why tracked:* Domain packages must remain independent and communicate only through shared core contracts (F9, S-128).

8. **TODO/FIXME lines in src** (`todo_fixme_lines`)
   - *Meaning:* Occurrences of `TODO` or `FIXME` in `src/` outside vendor dependencies.
   - *Why tracked:* Enforces the rule that all deferred work in source code must carry a tracked backlog identifier (AGENTS.md, S-097).

9. **Unconfirmed verify rows** (`verify_rows`)
   - *Meaning:* Total engineering numbers requiring human confirmation reported by `scripts/verify_list.py` (calc data tables, product decisions, and decision tags).
   - *Why tracked:* Enforces the non-negotiable rule that unverified engineering values are explicit and tracked until verified (AGENTS.md, S-064).

10. **Test functions** (`test_functions`)
    - *Meaning:* Count of test functions (`def test_`) under `tests/` discovered via AST.
    - *Why tracked:* Measures growth of the automated test suite safeguarding system behavior (S-070, S-080).

11. **Test skip/xfail marks** (`test_skips`)
    - *Meaning:* Count of `skip`, `skipif`, and `xfail` decorators and calls across the test suite.
    - *Why tracked:* Prevents silent regressions by ensuring test skips are known, justified, and monitored (S-070, S-080).

12. **Coverage line-rate** (`coverage`)
    - *Meaning:* Line coverage rate from `coverage.xml` at repo root if newer than HEAD commit, else `not measured`.
    - *Why tracked:* Guarantees test coverage remains above the 80 % floor enforced by CI (AGENTS.md).

13. **Open BACKLOG.md rows** (`open_backlog`)
    - *Meaning:* Table rows in `BACKLOG.md` under `## Open` before `## Closed`.
    - *Why tracked:* Tracks open backlog inventory and prevents abandoned work (AGENTS.md, S-097).

## How to record a row

Run `make health ARGS=--record` (or `uv run python scripts/health.py --record`).
This measures all metrics at HEAD and appends a single row to `docs/health/trend.csv`
with the current UTC date, HEAD commit SHA, and all numeric measures.
