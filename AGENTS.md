# napkin2factory — rules for developing napkin2factory

> **Here to use napkin2factory, not to change it?** If a person asked you to design or change
> a product with it, this is the wrong file: read `docs/agent-guide.md`. Inside a product
> folder, that folder's own `AGENTS.md` is your file.

This file is for **developing** napkin2factory: this repository's code, tests, docs and
templates (the `napkin2factory` package and its CLI `n2f`). It is maintained by AI agents of
different models and providers, working in parallel and one after another; none of them
remembers an earlier session. So every project rule and fact lives in this repository, never
in a model's memory or a client's settings: if you learn something about the project the next
agent needs, write it here, in `STATUS.md`, or in a decision entry. `AGENTS.md` is the only instructions file (no
`CLAUDE.md` or other per-client copy, S-076).

## Start here (in this order, and no more)
1. This file, then `STATUS.md` (one screen: where things stand, host facts).
2. `make tasks`: unfinished tasks left by earlier agents, each with its goal and last commit.
   Resume one if it is yours to finish; never start a duplicate.
3. For your task only: the `BACKLOG.md` rows and `DECISIONS.md` entries it touches (the index
   table at the top of `DECISIONS.md` names them; open an entry only when you change what it
   decides). `GRAND_PLAN.md` (v0.1, D-series), `NAPKIN_STAGE.md` (v0.2, N-series) and
   `PRODUCT_STRUCTURE.md` (v0.4, P-series) are the plans those entries amend.
Do not run `make check` to "see where things stand": CI's result for `main` says that.

## How work flows (S-097)
One trunk, `main`; every task in its own branch and folder; a release is a tag.
```
make task NAME=<slug> GOAL="<one line>"   # in the main folder: .worktrees/<slug> on task/<slug>
cd .worktrees/<slug>                      # work and commit here, as often as you like
make land                                 # rebase on main, assign journal ids, gate, fast-forward main
make check                                # in the main folder, before anything is pushed
```
- **The main folder stays on `main` with no unsaved changes**: tasks land there. Several
  agents at once each take their own task, so nobody edits files another is editing.
- **Commit freely on your task branch** and tidy it (amend, reset, rebase) as you like: it is
  never pushed. Never rewrite `main` or anything pushed (other agents build on it).
- **Stopping before you are done?** Commit the work on the task branch with a subject starting
  `WIP: ` and a body saying what is done, what is left and how to check it. The next agent
  finds it with `make tasks`. `make land` refuses `WIP` commits: fold them first
  (`git reset --soft main && git commit`).
- **Journal ids are placeholders until landing**: write `S-NEW<n>` (1, 2 …) and `B-NEW<n>`
  everywhere you reference them, commit messages included; `make land` gives them the next
  free numbers in every task commit, so parallel tasks never collide and no landed commit
  holds a placeholder. `DECISIONS.md` and `BACKLOG.md` merge line by line (`merge=union`);
  `tests/unit/test_journals.py` catches a duplicated row.
- **The gate**: `make land` runs lint, types and the journal checks (about a minute);
  `LAND_GATE=check make land` runs the full `make check` instead. Before a push, run
  `make check` once on `main` for everything landed since the last push; if it fails,
  `git bisect run make check` finds the task (history is linear).
- **Push only when the maintainer asks** (another agent may still be landing).
- **Commits**: `M<n>: <what>` while a milestone is open, plain imperative otherwise. Stage
  explicit paths, never `git add -A`. Never commit `build/` or `examples/*/build/`.
- Your client may have its own worktree feature: fine, as long as it starts from `main`; land
  it with `make land` from inside it.

## Non-negotiables
Every rule carries its reason. If a reason no longer holds, propose deleting the rule to the
maintainer instead of obeying it.
- **Generic, for any model and any client**, on both sides, because either side breaks the
  moment someone arrives with a different model (S-076, S-077). Developing: no model or vendor
  names in instructions, no per-client files or folders (`CLAUDE.md`, `.claude/` and the like),
  no step only one client can do. Using: nothing `n2f init` writes, nor the README nor the agent
  guide, depends on one client; the guide's "Adapting to your client" carries the fallbacks for
  every assumed capability (images, subagents, a browser). `tests/unit/test_agent_docs.py`
  checks the names and the absence of per-client files.
- **Run only the checks a change can break.** Docs, journals, brand assets, workflow files:
  nothing. Tests, scripts or the Makefile: `make lint` and the touched tests. `src/`,
  `examples/` or the templates: the tests covering the change, then the gate. CI runs
  `make check` on every push to `main` and skips a commit it has already tested.
- Do not edit `LICENSE`: the licence is the maintainer's call.
- No `TODO`/`FIXME` in `src/` without a `BACKLOG.md` id: open work lives in one table, and an
  unlisted TODO gets lost (`make todo-grep`).
- **The why sits where the thing happens.** Where code, config, a script or a test does
  something for a reason a reader could not guess (a workaround, a measured choice, a rule), a
  short comment there names the decision holding the full reason (`S-098`), so whoever changes
  that line sees why first. Cite the decision, not a closed backlog row: backlog ids mark open
  work (`TODO(B-0042)`).
- Public functions have docstrings (ruff `D`): the next agent reads the code cold. `mypy
  --strict` on `napkin2factory.core` and `napkin2factory.calckit`, where a type slip becomes a
  wrong part or a wrong number. Coverage ≥ 80 %, the floor CI enforces.
- No invented engineering numbers: cite the source in the calc file or data table, mark the row
  `verify: true` or the entry `[verify]`; `make verify-list` prints what is still unconfirmed.
- No git vocabulary in user-facing strings or schema fields (`docs/vocabulary.md`): owners are
  not developers (D17). All git calls in the package go through `core/vcs.py` (D31).
- Every model read inside a build rule goes through the recording accessors (`P[...]`, `I[...]`,
  `part()`, `req()`, `bom`), never raw YAML (D5).
- The report and the board are self-contained (`file://` safe, inline module script, embedded
  GLBs, ≤ 20 MB) (D13, N10).
- Owner-facing text is plain words: numbers carry their label (given / computed / estimate);
  identifiers and rule ids stay in `--json` and files (N5, D17).
- Measured, not claimed: a number in a journal entry or report is one you ran; otherwise write
  "not measured". The next agent cannot ask you what you meant.
- Templates are synced, never hand-edited in `examples/`: edit `src/napkin2factory/templates/`
  and `examples/{bracket,enclosure}`, then `make templates`.

## Who reads what
Two kinds of agent come here; never mix their documents up.
- **Using** napkin2factory for an owner: `README.md` is for the owner, a person (no commands,
  no setup, no internals; a hidden comment at its top sends agents to the guide).
  `docs/agent-guide.md` is that agent's: setup, the product folder, the command reference.
  When an install step, a CLI verb or a template changes, update the guide; touch the README
  only when what the owner sees changes. A product folder's `AGENTS.md` (from
  `templates/_common/`) governs one product; its roles are plain Markdown under `roles/`.
- **Developing** napkin2factory: this file and the journals.

## The journals (what goes where)
- `STATUS.md`: state only (version, current milestone, host facts, one line per milestone
  pointing at its decisions). No prose that repeats `DECISIONS.md`.
- `DECISIONS.md`: why. One entry per decision, ≤ 10 lines, dated, its id in the index table at
  the top with a status (in force / amended by … / superseded by …). An entry that changes an
  earlier one names it; the earlier one's index row is updated, its text never rewritten.
  Review-gate outcomes are entries too.
- `BACKLOG.md`: all open work in one table, one line per row; closed rows move to "Closed" with
  the closing entry's id.

## Releases and CI
- CI (`.github/workflows/ci.yml`) runs `make check` on Linux and macOS for every push to `main`
  and `make check-full` nightly; a commit that already passed is not tested again.
- A release is a `v<version>` tag on a `main` commit that is green in CI (S-072). The tag runs
  `publish.yml`, which checks that `pyproject.toml`, `packaging/n2f/pyproject.toml` and
  `src/napkin2factory/__init__.py` agree and publishes both packages (S-054). Bump those three
  and the product pins (S-083) first. Tagging is the maintainer's call.

## Working style that has paid off
- Fresh-context review gates between milestones (architecture and honesty, then UX in the owner
  persona) found the bugs the builders could not see. Write the brief from
  `docs/reviews/TEMPLATE.md`, keep the report in `docs/reviews/` and the outcome in
  `DECISIONS.md`, so the next gate starts from the last one's findings (S-078).
- Large work: split it into tasks with disjoint files, one task per agent or subagent, each in
  its own worktree; decide the design yourself and hand each a written brief.
- Judge every visual artifact yourself, then send the maintainer the board screenshot and one or
  two renders with a one-line question before calling a visual exit done; record
  the answer in the decision entry ("judged by the maintainer: …"). An agent's taste is not the
  maintainer's (S-078). Screenshots: `napkin2factory.concepts.screenshot`, or the full-page
  capture in `tests/unit/test_board.py`.

## Talking to a person
- An id never travels alone: pair it with its short title every time ("S-064, the calc kit",
  "B-0022, wide cost bands"). The reader may be on a phone with no repo at hand. Milestones
  likewise: say what they delivered.
- A question gets its answer first, from what you already know. Run commands afterwards, and
  only if the answer needs them.

## Commands
```
uv sync                      # environment (export PATH=$HOME/.local/bin:$PATH first on the host)
uv run n2f --help            # CLI
make task NAME=x GOAL="…"    # start a task in .worktrees/x;  make tasks  lists open ones
make land                    # from inside a task: rebase, ids, gate, fast-forward main
make check                   # lint + types + tests (parallel) + goldens + fast examples
make check-full              # + kiln + demos + timing (N2F_TIMING=1)
make templates               # sync examples/{bracket,enclosure} + _common → templates/
make goldens REASON="..."    # regenerate golden props, logged
make verify-list             # every number a human still has to confirm
```
Layout: `GRAND_PLAN.md` §3.1. One kit generator per file under `geometry/kit/`, one CLI verb per
module under `cli/`, schemas under `core/model/`, the napkin stage under `concepts/`, the calc
kit under `calckit/` (data tables in `calckit/data/`), the logo package in `brand/`.
