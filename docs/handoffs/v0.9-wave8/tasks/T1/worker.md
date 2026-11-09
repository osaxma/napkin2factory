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
In the wave 7 trial, `n2f_sync` summarised a failed validate as a JSON fragment
(`"assemblies": 1, "interfaces": 0, … } }`) three times, so the agent could not see which field was
wrong and went to read n2f's source. The tool code is `src/napkin2factory/mcp/combined.py`: the
sync tool runs `("validate",)` first (around line 620 to 650), and `compact()` (around line 190)
shortens nested values for every tool. S-333 already fixed the same problem for screening reasons
(`_capped(out, "reasons", ...)` around line 387): follow that pattern. Run
`n2f validate --json` on a broken copy of an example to see the exact shape of its problems.
</this_task>
</context>

<scope>
IN: src/napkin2factory/mcp/* tests/unit/test_mcp*.py tests/unit/test_w8_* DECISIONS.md BACKLOG.md
OUT: everything else. Do not refactor, rename or reformat anything not asked for.
</scope>

<task>Make `n2f_sync` return a failed `n2f validate`'s problems whole, so a small model sees which file and field to fix.</task>

<checklist>
1. Run `n2f validate --json` on a copy of `examples/table` with one parameter key misspelt and one part field removed, and note the JSON shape of each problem (write it in your report).
2. In `mcp/combined.py`, when the validate step fails, put `problems` in the tool's result: a list of `{file, field, message, fix}` built from validate's JSON, with messages whole. Cap at 20; add `more: <n>` when there are more. Do not pass them through `compact()`.
3. Set the result's `next` to `{"say": "Fix <field> in <file> (<message, first 120 characters>), then call n2f_sync again."}` for the first problem.
4. New test `tests/unit/test_w8_sync_validate.py`: calls the sync tool's function (as `tests/unit/test_mcp.py` does) on a broken copy with two problems; asserts both problems come back whole with file and field, and that `next.say` names the first one's file.
5. Journal: one decision entry `S-NEW-1` (what changed, why: the wave 7 trial, B-0325); move B-0325 to Closed with S-NEW-1. Commit with subject `Wave 8: n2f_sync gives a failed validate's problems whole (B-0325)`.
</checklist>

<acceptance>
`uv run pytest tests/unit/test_w8_sync_validate.py tests/unit/test_mcp.py -q --no-header -x` exits 0; `make lint` exits 0.
</acceptance>

<final_reminder>5 checklist items, in order; only the IN files; plain words for the owner; an exact next step on every error; stop every process you started; commit, never land or push.</final_reminder>
