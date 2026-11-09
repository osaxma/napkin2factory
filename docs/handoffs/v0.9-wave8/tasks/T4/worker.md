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
In the wave 7 trial, promotion seeded REQ-008 "mass at most 33 kg" (the card's one-person
lift limit) although the card's own screening put the bench at 76.5 kg; nothing at the napkin said
so, and the seeded model failed its own requirement. Promotion lives in
`src/napkin2factory/concepts/promote/` (`seeding.py`, `loads.py`, `result.py`, `verb.py`). Find
where requirements are created from the card's fields and where the card's screening figures are
read (the card's recorded screening results). The decided design: do not seed a requirement the
card's screening already fails; list it in the promotion result under `conflicts`.
</this_task>
</context>

<scope>
IN: src/napkin2factory/concepts/promote/* tests/unit/test_promote*.py tests/unit/test_w8_* DECISIONS.md BACKLOG.md
OUT: everything else. Do not refactor, rename or reformat anything not asked for.
</scope>

<task>When promotion seeds requirements from a card, skip any whose limit the card's own screening already fails, and report it as a conflict for the owner.</task>

<checklist>
1. Find where promotion turns card fields into requirements and where the card's screening figures (mass, cost, structure) are available; write both locations in your report.
2. Before seeding each requirement that has a numeric limit with a matching screening figure, compare them. If the figure breaks the limit, do not seed it; add `{title, limit, figure, say}` to a `conflicts` list in the result, where `say` reads like 'The design weighs 76.5 kg on the napkin, over the 33 kg one-person lift limit. Ask the owner: drop the limit, or change the design.'
3. When `conflicts` is not empty, the result's `next` says to ask the owner about each conflict before building. Show the conflicts in the CLI's plain output too (one line each).
4. New test `tests/unit/test_w8_seed_conflict.py`: a card with a 33 kg lift limit screened at 76.5 kg is promoted; the requirement is absent from the model, `conflicts` has it with both figures, and a passing limit is still seeded.
5. Journal: one decision entry `S-NEW-1`; move B-0324 to Closed with S-NEW-1. Commit with subject `Wave 8: promotion reports a limit the card already breaks instead of seeding it (B-0324)`.
</checklist>

<acceptance>
`uv run pytest tests/unit/test_w8_seed_conflict.py tests/unit/test_promote_seed.py tests/unit/test_promote_loads.py tests/unit/test_promote.py -q --no-header -x` exits 0; `make lint` exits 0.
</acceptance>

<final_reminder>5 checklist items, in order; only the IN files; plain words for the owner; an exact next step on every error; stop every process you started; commit, never land or push.</final_reminder>
