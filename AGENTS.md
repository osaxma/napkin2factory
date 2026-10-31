# napkin2factory — rules for developing napkin2factory

> **Here to use napkin2factory, not to change it?** If a person asked you to design or change
> a product with it, this is the wrong file: read `docs/agent-guide.md`. Inside a product
> folder, that folder's own `AGENTS.md` is your file.

This file is for **developing** napkin2factory: changing this repository's code, tests, docs
or templates. This is the **system** repo: the `napkin2factory` package and its CLI `n2f`. Product repos
(what `n2f init` writes; see `examples/`) have their own `AGENTS.md`. `AGENTS.md` is the only
instructions file, here and in product folders: no `CLAUDE.md` or other per-client copy (S-076).
Nothing in this repo assumes a particular model or client: any coding agent, or a person, works
from these files.

## Read first, in this order
1. This file.
2. `STATUS.md` — where the project stands (one screen).
3. `BACKLOG.md` — every piece of open work, including what the plans left out.
4. `DECISIONS.md` — start with the index table at the top; open an entry only when you touch
   what it decides. `GRAND_PLAN.md` (v0.1 contract, D-series) and `NAPKIN_STAGE.md` (v0.2
   contract, N-series) are the plans those entries amend; the latest handoff report
   (`HANDOFF-REPORT-v0.2.md`) is the fastest tour of what shipped.
5. `git log --oneline -30`, then `make check`.

## Who reads what
Two kinds of agent come here; never mix their documents up.
- **Using** napkin2factory (an agent making a product for its owner):
  - `README.md` is for the owner, a person. It covers what the tool is, the prompt they paste
    into their agent, and the other ways in. It has no commands, no Python setup and no
    internals. A hidden comment at its top sends agents to the guide.
  - `docs/agent-guide.md` is for that agent: setup, making the product folder, handing over
    to the folder's own instructions, and the command reference. When an install step, a CLI
    verb or a template changes, update the guide. Touch the README only when what the owner
    sees changes.
  - A product folder's `AGENTS.md` (from `templates/_common/`) governs one product; its roles
    are plain Markdown under `roles/`.
- **Developing** napkin2factory (a contributor, person or agent): this file and the journals.

## Non-negotiables
Every rule here carries its reason (a clause or a decision id). If a rule's reason no longer
holds, propose deleting it to the maintainer instead of obeying it.
- **Generic, for any model and any client**, on both sides, because either side breaks the
  moment someone arrives with a different model (S-076, S-077):
  - Developing: the project is open source, so any model, agent or person must be able to
    work on it from `AGENTS.md` alone. No model or vendor names in the instructions, no
    per-client files or folders (`CLAUDE.md`, `.claude/` and the like), no step only one
    client can do.
  - Using: owners bring whatever agent they have. Nothing `n2f init` writes, and nothing in
    the README or the agent guide, may depend on one client. The guide tells an agent
    everything it needs to adapt ("Adapting to your client"). When a new capability is
    assumed (images, subagents, a browser), add its fallback there.
  - `tests/unit/test_agent_docs.py` checks the names and that no per-client files exist.
- Never run checks a change cannot break. Docs, journals, brand assets, workflow files → nothing
  to run; tests, scripts or the Makefile → `make lint` and the touched tests; anything under
  `src/`, `examples/` or the templates → `make check`. CI runs the full check on every push and
  skips commits it has already tested. Never commit `build/` or `examples/*/build/`: they are
  generated from the model and rebuilt anywhere.
- Work on the release branch named in `STATUS.md` (`v0.3-build` today; earlier versions are
  closed), so every release has one branch whose tip CI has tested.
  Commit messages `M<n>: <what>` while a milestone is open (the milestone's work then reads
  straight from the log); plain imperative otherwise.
  Stage explicit paths, never `git add -A` (unrelated work may sit in the tree).
  Never force-push, never rewrite history (other sessions build on the branch). Push only when
  the maintainer asks (another agent may still be finishing work on the branch).
- Do not edit `LICENSE`: the licence is the maintainer's call.
- No `TODO`/`FIXME` in `src/` without a `BACKLOG.md` id (`B-0001`): open work lives in one
  table, and an unlisted TODO gets lost.
- Public functions have docstrings (ruff `D`), because the next agent reads the code cold.
  `mypy --strict` on `napkin2factory.core` and `napkin2factory.calckit`, where a type slip
  becomes a wrong part or a wrong number. Coverage ≥ 80 %, the floor CI enforces.
- No invented engineering numbers: cite the source in the calc file or data table, mark the row
  `verify: true` or the entry `[verify]`; `make verify-list` prints everything still unconfirmed.
- No git vocabulary in user-facing strings or schema fields (`docs/vocabulary.md`): draft,
  snapshot, change request, released, Revision. Owners are not developers (D17). All git
  calls go through `core/vcs.py` (D31).
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
  milestone. Write the brief from `docs/reviews/TEMPLATE.md`; keep the full report in
  `docs/reviews/` and the outcome in `DECISIONS.md`, so the next gate starts from the last one's
  questions and findings instead of a blank page (S-078).
- Big implementation chunks go to a subagent with a written brief and disjoint file ownership;
  run `make check` only when no agent is editing `src/`; judge every visual artifact yourself
  before calling a milestone done.
- When a milestone's exit is judged by eye (renders, the board, a report page), send the
  maintainer the board screenshot and one or two renders with a one-line question before calling
  it done, and record the answer in the decision entry ("judged by the maintainer: …"): an
  agent's taste is not the maintainer's (S-078). Screenshots: `napkin2factory.concepts.screenshot`,
  or the full-page capture in `tests/unit/test_board.py`.
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
```

## Layout
See `GRAND_PLAN.md` §3.1. `brand/` holds the logo package (generated by `brand/build.py`, which
also writes the icon copy in `src/napkin2factory/report/brand/`). One kit generator per file under `geometry/kit/`; one CLI verb per
module under `cli/`; schemas under `core/model/`; the napkin stage under `concepts/`, the
calc kit under `calckit/` with its data tables in `calckit/data/`.
