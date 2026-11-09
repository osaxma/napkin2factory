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
In the wave 7 trial, after a `concept switch` to another card the earlier (hand-edited) parts
and layout stayed, because promotion seeds only an empty model and the switch seeds nothing. The
switch is `src/napkin2factory/concepts/switch.py` (`switch`, `_restore`, `_parked_source`); the
seeding is `src/napkin2factory/concepts/promote/seeding.py` and the other files in that folder;
checkpoints and undo are in `src/napkin2factory/core/checkpoints.py` and `src/napkin2factory/cli/undo.py`.
The note is reviewed by a person before anything is built.
</this_task>
</context>

<scope>
IN: docs/handoffs/v0.9-b0329-design.md
OUT: everything else. Do not refactor, rename or reformat anything not asked for.
</scope>

<task>Write a design note for B-0329: on `concept switch` to another card, seed that card's model as promotion does, setting the earlier model aside. No code.</task>

<checklist>
1. Read the switch and promotion code. Answer, each with file and function names: (1) What does a switch do today to the model files, step by step? (2) What does promotion's seeding write, and what does it require to be empty? (3) Where would the switch call the seeding, and what must be set aside first so `undo` and a switch back both restore the earlier model exactly?
2. (4) What happens to hand edits the owner made to the earlier model: kept with that card, and how are they restored? (5) Which change requests or sign-offs would the switch invalidate, and how is the owner told?
3. Propose the change in at most 10 numbered steps, with the files each step touches, and list the risks.
4. End with the tests the change would need (one line each). Write it all to `docs/handoffs/v0.9-b0329-design.md`, at most 120 lines, plain words.
5. Commit with subject `Wave 8: design note for re-seeding on a concept switch (B-0329)`. Do not touch `BACKLOG.md` or `DECISIONS.md`.
</checklist>

<acceptance>
`test -s docs/handoffs/v0.9-b0329-design.md` exits 0; `make lint` exits 0.
</acceptance>

<final_reminder>5 checklist items, in order; only the IN files; plain words for the owner; an exact next step on every error; stop every process you started; commit, never land or push.</final_reminder>
