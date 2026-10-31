# Future improvements — context for whoever picks these up

Five changes to how this repo is worked on, none to the product itself. Each has a backlog row
(B-0053 … B-0057) so it shows up with the rest of the open work; this file carries the reasoning,
the evidence and where to look, so an agent can start without re-deriving it. Measurements are
from the v0.2 build-out on the reference macOS host (16 cores) on 2026-10-31/11-01 unless stated.
Do them in the order below if nothing else decides; the first two are about an hour each, the
third about half a day of change, the fourth is a habit, the fifth a small task of its own.

## 1. Keep review-gate reports in the repo (B-0053)

**What happened.** v0.2 had two fresh-context review gates: gate A (honesty and architecture,
after M4) and gate B (UX in the owner persona, after M6). Their full reports — every finding with
the exact text seen, the text wanted and a file:line — existed only in the orchestrating agent's
scratch folder. Only the *outcomes* were copied into `DECISIONS.md` ("Review gate A — outcome",
"Review gate B — outcome"). The briefs that produced them (the questions the reviewer had to
answer, the persona, the read-only rules) were also scratch files, rewritten for each gate. v0.1
did better on one: the gate-3 shop read-through was kept as `reports/shop-readthrough.md` in the
kiln example because the contract named it a launch artefact.

**Why it matters.** The report is the best record of what a reader with no context actually
tripped over; the outcome entry is a summary by the people being reviewed. The next version's
gates will ask the same questions (can a build rule read `concepts/`? is every number labelled?
does the red card read as information? any git word visible? are refusals plain with a next
step?) and should not start from a blank page.

**Do.** Create `docs/reviews/` with one file per gate (`v0.2-gate-a.md`, `v0.2-gate-b.md` — ask
the maintainer whether the scratch copies still exist; if not, reconstruct the finding list from
the two outcome entries and the backlog rows they opened, and say so at the top). Add
`docs/reviews/TEMPLATE.md`: the reviewer's standing rules (fresh context, read-only, work on
copies, quote exact text, verdict per question, blockers vs concerns with file:line) and the two
question sets (architecture/honesty; UX in the owner persona) as they stand in `NAPKIN_STAGE.md`
§5 ("Review gate A", "Review gate B") and `GRAND_PLAN.md` §8. Add one line to `AGENTS.md` under
"Working style": gate reports live in `docs/reviews/`, outcomes in `DECISIONS.md`.

## 2. Run the demos in parallel in `make check-full` (B-0054)

**What happened.** `make check-full` is `check` + `kiln` + `demos` in series (see `Makefile`).
Measured on a clean clone of eab10b1: 28 min 01 s total, of which `check` is about 7.5 min
(tests are already parallel, S-070), the kiln build with renders plus the kiln napkin build about
6 min, and `demos` — `tests/e2e/test_demos.py`, which runs `demo.sh`, `demo-design.sh` and
`demo-napkin.sh` one after another, each in its own temp copy — about 12 min (the two v0.1
demos ≈ 5 min each with `--no-render`, the napkin demo ≈ 2 min). The nightly CI job runs the
same target.

**Why it matters.** Every milestone close-out and every clean-clone proof waits on it; cutting it
to 12–15 min is free wall-clock.

**Do.** The three demos are independent (separate temp folders, `N2F_OFFLINE=1`, no shared
state), so `tests/e2e/test_demos.py` can run under xdist: change the `demos` target to
`N2F_TIMING=1 $(PY) pytest tests/e2e/test_demos.py -q -n 3 --dist loadfile` (three test
functions, one per demo — check they are separate functions, not one parametrised test, and
that `tests/e2e/test_timing.py` is not pulled in, since timing assertions must stay serial, D30).
The kiln step and the demos could also overlap (`make -j2 kiln demos` from the `check-full`
recipe), but the kiln build with renders is CPU-heavy; measure before keeping that. Record the
before/after in `DECISIONS.md` as an amendment to S-070 and update the ≈ 28 min figure in
`STATUS.md` (Environment).

## 3. Build each example product once per test worker, not per test (B-0055)

**What happens today.** 22 test files call `tests.conftest.copy_product`, and most end-to-end
tests then run `n2f build` (often `--no-render`) on their fresh copy before testing what they
are about to test. The bracket builds in a few seconds, the enclosure in tens of seconds; across
`tests/e2e/*.py` (14 files) and the unit tests that build, the same two products are built many
dozens of times per run. The unit+e2e step is 5 min 33 s in parallel (16 workers); the first
`import build123d` per worker is paid anyway.

**Why it is not an hour.** The tests *mutate* their copies (change requests, releases,
sign-offs, promotions), so a built product cannot be shared — it has to be built once per worker
and then copied, `build/` included, to each test. Two things make that uncertain: (a) the build
graph may not be relocatable — `validate.json` is known to embed absolute paths (B-0006) and
`core/graph/rules.py` and `runs.py` resolve paths; if the manifest treats a copied build as stale,
everything rebuilds and the saving is zero; (b) tests start from different states (unbuilt,
tracking off via `copy_product(..., git=False)`, a specific first snapshot), so each file has to
be read to see which fixture it can take, and some may be passing only because the build was
cold.

**Do.** (1) Measure first: `uv run pytest tests/e2e tests/unit -q --durations=30 -n auto` and
sum the time spent inside `n2f build`; if it is under a minute, stop and close the row. (2) Check
relocatability: build a bracket copy, `cp -R` it to another path, run `n2f build` there and read
the manifest's rebuilt list (`build/manifest.json` or `n2f build --json`); if anything rebuilds,
fix the manifest to store paths relative to the product root (this also closes B-0006) — that is
a `core/graph` change and needs the invalidation tests (`tests/e2e/test_invalidation.py`) green.
(3) Add session-scoped fixtures in `tests/conftest.py` (`built_bracket`, `built_enclosure`) that
build once into `tmp_path_factory.getbasetemp()` under a file lock (xdist workers share the
base temp's parent; use `FileLock` or an atomic rename), and a `fresh_built_bracket` that copies
the built folder per test. (4) Migrate tests file by file, only where the test does not depend
on a cold build. (5) Measure again and record the numbers.

## 4. Send the maintainer the pictures at visual milestones (B-0056)

**What happened.** The napkin stage's exit criteria are partly visual: "judged by eye" for the
styled renders (M3), the board (M4), the kiln retrofit (M6). In v0.2 the orchestrating agent
judged them alone and wrote the judgment into `DECISIONS.md` (S-066, S-067, S-069) and
`STATUS.md`. The maintainer follows from a phone; the files (`build/concepts/board.html`
screenshots, `build/concepts/C-00x/renders/styled-iso.png`) existed the whole time.

**Why it matters.** The contract's own premise (NAPKIN_STAGE §0) is that taste only shows up when
you see something, and an agent's taste is not the maintainer's.

**Do.** This is a working-style rule, not code: when a milestone's exit is a visual judgment, the
agent posts the board screenshot and one or two renders to the maintainer with a one-line
question before calling the milestone done, and records the maintainer's answer in the decision
entry ("judged by the maintainer: …"). Add it to `AGENTS.md` "Working style" and to the
milestone exit text in the next plan. The screenshots are produced by
`napkin2factory.concepts.screenshot` and the board test's Playwright path (see
`tests/unit/test_board.py` for a full-page capture).

## 5. A client-neutral home for the role skills (B-0057)

**What is there.** The product templates (`src/napkin2factory/templates/_common/`) ship the PM
and designer roles as `.claude/skills/n2f-pm/SKILL.md` and `.claude/skills/n2f-design/SKILL.md`,
plus two agents under `.claude/agents/`. `AGENTS.md` (= `CLAUDE.md`) in a product describes the
roles and points at those paths. The sync (`python -m napkin2factory.templates.sync`) copies the
tree into every example; `tests/e2e/test_napkin_protocol.py` and `tests/unit/test_templates.py`
compare the copies byte for byte.

**Why it matters.** `.claude/` is one client's convention. The project is open source and its
own rules say nothing assumes a particular model or client; a product opened with another agent
should find the roles without knowing that path.

**Do.** Keep the skill text where it is written once, in a neutral place — for example
`agents/skills/n2f-pm/SKILL.md` and `agents/skills/n2f-design/SKILL.md` at the product root —
and make `.claude/skills/...` point at it (a symlink, or a copy maintained by the sync, which is
safer across filesystems and zip packaging). `AGENTS.md` lists the neutral path first. Touch:
`templates/_common/`, `templates/sync.py`, `cli/init.py` (what `n2f init` writes), the three
examples, `docs/agent-layer.md`, `docs/product-model.md`, and the two tests above (they hard-code
`COMMON / ".claude" / "skills"`). Check how other clients discover skills before choosing the
neutral path name, so it is not just a second private convention.
