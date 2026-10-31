# napkin2factory — rules for agents working on this (system) repository

This is the **system** repo: the `napkin2factory` package and its CLI `n2f`. Product repos
(what `n2f init` writes; see `examples/`) have their own `AGENTS.md`. `CLAUDE.md` here is an
identical copy of this file for clients that look for that name; edit `AGENTS.md` and copy
(`make agents-doc`, or `cp AGENTS.md CLAUDE.md`). Nothing in this repo assumes a particular
model or client: any coding agent, or a person, works from these files.

## Read first, in this order
1. This file.
2. `STATUS.md` — where the project stands (one screen).
3. `BACKLOG.md` — every piece of open work, including what the plans left out.
4. `DECISIONS.md` — start with the index table at the top; open an entry only when you touch
   what it decides. `GRAND_PLAN.md` (v0.1 contract, D-series) and `NAPKIN_STAGE.md` (v0.2
   contract, N-series) are the plans those entries amend; the latest handoff report
   (`HANDOFF-REPORT-v0.2.md`) is the fastest tour of what shipped.
5. `git log --oneline -30`, then `make check`.

## Non-negotiables
- Never run checks a change cannot break. Docs, journals, brand assets, workflow files → nothing
  to run; tests, scripts or the Makefile → `make lint` and the touched tests; anything under
  `src/`, `examples/` or the templates → `make check`. CI runs the full check on every push and
  skips commits it has already tested. Never commit `build/` or `examples/*/build/`.
- Work on the release branch named in `STATUS.md` (`v0.2-build` today; v0.1 is closed on `main`).
  Commit messages `M<n>: <what>` while a milestone is open; plain imperative otherwise.
  Stage explicit paths, never `git add -A` (unrelated work may sit in the tree).
  Never force-push, never rewrite history. Push only when the maintainer asks.
- Do not edit `LICENSE`.
- No `TODO`/`FIXME` in `src/` without a `BACKLOG.md` id (`B-0001`).
- Public functions have docstrings (ruff `D`); `mypy --strict` on `napkin2factory.core` and
  `napkin2factory.calckit`; coverage ≥ 80 %.
- No invented engineering numbers: cite the source in the calc file or data table, mark the row
  `verify: true` or the entry `[verify]`; `make verify-list` prints everything still unconfirmed.
- No git vocabulary in user-facing strings or schema fields (`docs/vocabulary.md`): draft,
  snapshot, change request, released, Revision. All git calls go through `core/vcs.py` (D31).
- Every model read inside a build rule goes through the recording accessors (`P[...]`, `I[...]`,
  `part()`, `req()`, `bom`), never raw YAML (D5).
- The report and the board are fully self-contained (`file://` safe, inline module script,
  embedded GLBs, ≤ 20 MB) (D13, N10).
- Owner-facing text is plain words: numbers carry their label (given / computed / estimate),
  identifiers and rule ids stay in `--json` and files (N5, D17).
- Measured, not claimed: a number in a journal entry or report is one you ran; otherwise write
  "not measured".

## Releases and CI
- CI (`.github/workflows/ci.yml`) runs `make check` on Linux and macOS for every push to `main`
  and the release branches, and `make check-full` nightly. A commit that already passed is not
  tested again: the `gate` job skips the matrix when an earlier green run of the same commit
  exists, so fast-forwarding a green branch tip onto `main` costs one tiny job.
- A release is a `v<version>` tag on a commit that is green on its branch (S-072); the tag runs
  `publish.yml`, which checks that `pyproject.toml`, `packaging/n2f/pyproject.toml` and
  `src/napkin2factory/__init__.py` agree and publishes both packages (S-054). Tagging is the
  maintainer's call.

## Talking to a person
- An id never travels alone: pair it with its short title every time — "S-064, the calc kit",
  "B-0022, wide cost bands", "review gate B, the owner-persona UX review". The reader may be on a
  phone with no repo at hand. Milestones likewise: say what they delivered.
- A question gets its answer first, from what you already know. Run commands afterwards, and
  only if the answer needs them.

## The three journals (what goes where)
- `STATUS.md` — state only: branch, version, current milestone, environment facts, one line per
  milestone pointing at its decision entries. No prose that repeats `DECISIONS.md`.
- `DECISIONS.md` — why. One entry per decision, ≤ 10 lines, dated, with its id in the index table
  at the top and a status there (in force / amended by … / superseded by …). An entry that changes
  an earlier one names it; the earlier one's index row is updated, its text is never rewritten.
  Review-gate outcomes are entries too (`Gate <n> — outcome`).
- `BACKLOG.md` — all open work in one table: bugs, deferred items, plan leftovers, non-goals
  that may return, risks worth watching. One line per row; detail goes in the decision entry
  that opened or closed it. Closed rows move to the "Closed" table with the closing entry's id.

## Working style that has paid off
- Fresh-context review gates between milestones (architecture/honesty, then UX in the owner
  persona) found the bugs the builders could not see; keep them, and fix blockers before the next
  milestone.
- Big implementation chunks go to a subagent with a written brief and disjoint file ownership;
  run `make check` only when no agent is editing `src/`; judge every visual artifact yourself
  before calling a milestone done.
- Templates are synced, never hand-edited in `examples/`: edit `src/napkin2factory/templates/`
  and `examples/{bracket,enclosure}`, then `make templates`.

## Commands
```
uv sync                      # environment
uv run n2f --help            # CLI
make check                   # lint + types + tests (parallel) + goldens + fast examples
make check XDIST=            # the same, tests run serially
make check-full              # + kiln + demos + timing (N2F_TIMING=1)
make templates               # sync examples/{bracket,enclosure} + _common → templates/
make goldens REASON="..."    # regenerate golden props, logged
make verify-list             # every number a human still has to confirm
make agents-doc              # copy AGENTS.md → CLAUDE.md
```

## Layout
See `GRAND_PLAN.md` §3.1. One kit generator per file under `geometry/kit/`; one CLI verb per
module under `cli/`; schemas under `core/model/`; the napkin stage under `concepts/`, the
calc kit under `calckit/` with its data tables in `calckit/data/`.
