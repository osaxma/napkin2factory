# Common brief for every napkin2factory v0.6 subagent (part of your brief; read all of it)

You are a subagent building one task of napkin2factory v0.6 ("the wiring": the `electrical`
domain added through the v0.5 domain contract). Nobody will answer questions: where the brief is
silent, decide like a senior engineer, write the decision in a DECISIONS.md entry with its reason
(tag it `[revisit]` if the maintainer might want to reopen it), and continue.

## Read first, in this order and no more
1. `/Users/wakeel/napkin2factory/AGENTS.md` (the developer rules; all of them apply to you).
2. `ELECTRICAL_STAGE.md` **§0 (lines 19–66) and §2 (lines 145–160) in full**: they are part of
   this brief. Then your milestone's section (named in your brief).
3. `docs/domains.md` (the contract; the domain's only sanctioned way into the system).
4. Only then the code your task touches.

## Where you work
- Your task folder is given in your brief (`.worktrees/<slug>`, branch `task/<slug>`, already
  created from `main`). Work and commit only there. Never touch the main folder
  `/Users/wakeel/napkin2factory` except to read it.
- Environment: `export PATH=$HOME/.local/bin:$PATH` before `uv`. macOS host: no GNU `timeout`;
  `sed -i ''`. Never run `n2f build` inside `examples/`; copy a product to a temp folder first
  (`tests.conftest.copy_product`).
- Commit freely on your branch; stage explicit paths, never `git add -A`. Never commit `build/`.
- **Commit often: this run may be cut off at any moment without warning.** After each
  meaningful piece of work (a file family written, a test passing, a fix found), commit it on
  your branch with a subject starting `WIP: ` and a body saying what is done, what is left and
  how to check it, so a cut-off loses minutes, not hours. Before `make land`, fold them
  (`git reset --soft main && git commit` with the real `M<n>: …` subject; land refuses `WIP`).
- Journal ids are placeholders until landing: write `S-NEW` plus a number (`S-NEW1`,
  `S-NEW2` …) and `B-NEW` plus a number in DECISIONS.md, BACKLOG.md, comments and commit
  messages; `make land` gives them the next free numbers. Never write a literal next number
  yourself: a parallel task may take it first.
- Commit subjects: `M<n>: <what>` for a milestone task (your brief names `<n>`); plain imperative
  for a seam task.
- When done: `make land` from inside your task folder (it rebases on main, assigns ids, runs
  `make check-fast`, fast-forwards main). If it fails because main moved or a git lock was held,
  run it again. If the gate fails, fix and land again. Never push. Never rewrite main.
- Checks: run only what your change can break (AGENTS.md), then the land gate. Do not run
  `make check` or `make check-full` unless your brief says so.

## The rule this release exists to measure (E10) — read twice
The electrical domain's own commits change **nothing** under `src/napkin2factory/core/`,
`src/napkin2factory/report/builder.py`, `src/napkin2factory/docs/engine.py` or
`src/napkin2factory/cli/check.py`. If you cannot proceed without editing one of those (or any
file your brief does not list as yours): **stop**, commit what you have on your branch with a
subject starting `WIP: ` and a body naming the file you need, the reason, and what the contract
(`docs/domains.md`) would have to offer instead; do not land; end your run and report it. The
overseer opens a separate seam task and restarts you after it lands. A workaround that smuggles
core behaviour into the domain is worse than a WIP: the count must be honest.
(Seam tasks are the exception: their brief names the core files they own.)

**If you need a file you do not own, stop and commit `WIP:` saying what you need.**

## Domain-wide rules
- The domain is named `electrical` (the kiln's `scope.electrical` key); its owner word is
  "wiring". It lives in `src/napkin2factory/domains/electrical/`.
- Generic words only in the domain's code, messages, fixtures and docs: the F9 guard
  (`tests/unit/test_no_example_identifiers.py`) forbids every example's part, parameter,
  requirement and decision ids anywhere in the package. Say "the switching device", "the limit
  device", "the interlock", "the sensor", "the box", "the gland"; never a kiln part id.
- Wiring-level, data as source, no desktop tool (E1). Rules `fail` only on arithmetic and
  topology; everything a wiring code would judge is a `warn` whose message says a licensed
  electrician decides (E6).
- No invented engineering numbers: every table row cites its source and carries `verify: true`
  (`make verify-list` prints them); a DECISIONS.md line about a number carries `[verify]`.
- Every model read inside a rule, check stage, report section or doc helper goes through the
  recording accessor (`ctx.proxy`, `sctx.proxy`, `h.proxy`) or `log.add` (D5, gate E B2).
- Owner-facing text is plain words; ids pair with their titles; no git vocabulary
  (`docs/vocabulary.md`). Public functions have docstrings. `mypy --strict` covers `core` and
  `calckit`. Coverage floor 80 %.
- Backward compatible (E12): every new field optional, schema stays 1; a product without
  `model/electrical/` shows no electrical row or word anywhere; the bracket and enclosure goldens
  do not change.
- Measured, not claimed: a number you write in a journal or report is one you ran; otherwise
  "not measured".

## Your report back (your final message)
Under 40 lines: landed or WIP (the commit hash on main, or the WIP commit and the file you need);
files changed (`git diff --stat main~N..main` over your commits); any file under
`src/napkin2factory/core/`, `report/builder.py`, `docs/engine.py` or `cli/check.py` you changed
(milestone tasks: this must be none); the tests you added and their pass count; the decisions
you took (ids as landed); what you left open (backlog ids as landed); measured times.
