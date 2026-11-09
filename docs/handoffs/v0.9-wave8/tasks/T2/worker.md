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
In the wave 7 trial, `concept switch` failed nine times in a row: once on a model problem
(a parameter with a key the schema refuses), then with `engine_internal`
`FileNotFoundError: model/parameters.yaml` (exit 70) while the agent was rewriting the file. The
switch is `src/napkin2factory/concepts/switch.py` (`_preflight` around line 164, `switch` around
line 204); the CLI verb is `src/napkin2factory/cli/concept_switch.py`. Errors are `N2FError(msg,
next="...")` from `napkin2factory.core.errors`; under `--json` they print `{error, message,
next}`. The undo verb `n2f undo` puts back the last saved state of the model files.
</this_task>
</context>

<scope>
IN: src/napkin2factory/concepts/switch.py src/napkin2factory/cli/concept_switch.py tests/unit/test_concept_switch.py tests/unit/test_w8_* DECISIONS.md BACKLOG.md
OUT: everything else. Do not refactor, rename or reformat anything not asked for.
</scope>

<task>Make `n2f concept switch` refuse a missing or broken `model/parameters.yaml` with a plain error and an exact next step, before it changes anything.</task>

<checklist>
1. In `_preflight` (before anything is moved), if `model/parameters.yaml` is missing raise `N2FError("model/parameters.yaml is missing, so the switch cannot start", next="n2f undo --dir <folder>, then run the switch again")` with the real folder.
2. If it exists but is not valid YAML, raise `N2FError` naming the file and the YAML error's line, `next="fix model/parameters.yaml line <n>, then run the switch again"`.
3. If the product's model does not validate, raise one `N2FError` with the first problem's file, field and message, and `next="n2f validate --json --dir <folder>"`. Reuse the validate function the CLI uses; do not write a new validator.
4. New test `tests/unit/test_w8_switch_missing.py` with the three cases, through the CLI with `--json` (`n2f()` from `tests/conftest.py`): exit code 1, the message names the file, `next` as above, and no file changed in the product folder.
5. Journal: one decision entry `S-NEW-1`; move B-0326 to Closed with S-NEW-1. Commit with subject `Wave 8: concept switch refuses a missing or broken parameters file (B-0326)`.
</checklist>

<acceptance>
`uv run pytest tests/unit/test_w8_switch_missing.py tests/unit/test_concept_switch.py -q --no-header -x` exits 0; `make lint` exits 0.
</acceptance>

<final_reminder>5 checklist items, in order; only the IN files; plain words for the owner; an exact next step on every error; stop every process you started; commit, never land or push.</final_reminder>
