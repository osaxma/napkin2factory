<context>
<common>
Repository: napkin2factory (CLI `n2f`), a Python package. You are in a task folder (a separate
checkout on its own branch); `main` is the trunk.
- Environment: `export PATH=$HOME/.local/bin:$PATH N2F_NO_ENGINE=1` before any `uv` or test command.
- Tests: `uv run pytest <files> -q --no-header -x`. Tests that build an example start from a
  prebuilt copy: `copy_product(..., prebuilt=True)` and `n2f()` from `tests/conftest.py`.
- Journals: a decision entry goes at the END of `DECISIONS.md` (at most 10 lines, dated
  2026-11-09), with its index row after the last row of the index table at the top. Its id is
  the placeholder `S-NEW-1`. A closed backlog row moves from "Open" to "Closed" in `BACKLOG.md`
  with `S-NEW-1` as its closing entry. Never type a real S- or B- number for new entries.
- Code rules (AGENTS.md): public functions keep docstrings; no git words in user-facing text
  (`docs/vocabulary.md`); owner-facing text in plain words, ids only in `--json`; every error an
  agent sees states the outcome and names the exact next step (S-308), short enough for a small
  model (S-328).
- Commit on the current branch with explicit paths (never `git add -A`). Subject as the task
  says. Never run `make land`, `make check` or `git push`. Never put artificial load on the
  machine. Before you report, stop every process you started:
  `pkill -f 'from napkin2factory.cli.engine import serve_main'`.
</common>

<this_task>
The run's state is `/Users/wakeel/n2f-wave8/state.md`; the overseer ran `make check` on main
before starting you and wrote its last lines to `/Users/wakeel/n2f-wave8/check.txt`. The handoff
`docs/handoffs/v0.9-overseer.md` has the sections "Where it stands", "In flight" and "Next, in
order"; keep their style (short lines, ids with their short titles). The `core/` count: the number
of distinct files under `src/napkin2factory/core/` changed in v0.9, which was 12 at the end of wave
7; add any wave 8 changed (`git diff --name-only abd544b..HEAD -- src/napkin2factory/core`).
</this_task>
</context>

<scope>
IN: docs/handoffs/v0.9-overseer.md STATUS.md DECISIONS.md
OUT: everything else. Do not refactor, rename or reformat anything not asked for.
</scope>

<task>Close wave 8 in the journals from the run's state file and the make check result.</task>

<checklist>
1. Read the state file, `check.txt` and `make tasks`' output.
2. Update the handoff's three sections as the review points in your brief describe (add a wave 8 line at the top of 'Where it stands'; do not delete older lines).
3. Add one line to `STATUS.md`'s v0.9 milestone line: 'wave 8 (the trial's open rows, S-NEW-1)'.
4. Add the decision entry `S-NEW-1` (at most 10 lines) with the make check numbers, the core count and the commits (`git log --oneline abd544b..HEAD`).
5. Commit with subject `Wave 8 boundary: the tasks, make check, the handoff (S-NEW-1)`.
</checklist>

<acceptance>
`test -s /Users/wakeel/n2f-wave8/check.txt` exits 0; `make lint` exits 0.
</acceptance>

<final_reminder>5 checklist items, in order; only the IN files; plain words for the owner; an exact next step on every error; stop every process you started; commit, never land or push.</final_reminder>
