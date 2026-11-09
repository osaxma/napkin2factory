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
In the wave 7 trial, for an 1800 mm change the agent computed the sag by hand 14 times before
asking the owner. `ecr quick` and `ecr impact` are in `src/napkin2factory/ecr/live.py` (`impact`
around line 178, `quick` around line 358); the CLI is `src/napkin2factory/cli/ecr.py`; the MCP tool
`n2f_ecr` is in `src/napkin2factory/mcp/combined.py`. Structure requirements are those checked by a
`structure.*` calc (for example `calc://structure.tip_over_factor`) or of kind `structure`; read
how the impact gathers requirement results first.
</this_task>
</context>

<scope>
IN: src/napkin2factory/ecr/* src/napkin2factory/cli/ecr.py src/napkin2factory/mcp/combined.py tests/unit/test_ecr*.py tests/unit/test_w8_* DECISIONS.md BACKLOG.md
OUT: everything else. Do not refactor, rename or reformat anything not asked for.
</scope>

<task>Make a quick change's impact show the structure requirements' new figures first, so after a size change the agent reads the sag from n2f instead of computing it by hand.</task>

<checklist>
1. Find how the impact gathers requirement results before and after the change; write it in your report.
2. Order the impact's requirement lines so structure requirements come first, each as '<title>: <before> → <after> against <limit> (<passes|fails>)', with units, in plain words.
3. In `mcp/combined.py`, make sure `n2f_ecr`'s summary keeps those lines first and whole (cap the list at 10, never cut a line).
4. If the product has no structure requirement, add one line 'No structure requirement: the sag and tipping are not checked.' and a `next` naming the command or tool that adds one (read the guide `docs/agent-guide.md` for it; if none exists, say 'ask the owner for the load and add a structure requirement').
5. New test `tests/unit/test_w8_quick_structure.py` on a prebuilt copy of `examples/table`: a quick change of the top's length; the first requirement lines of the impact are the structure ones with before and after figures. Journal: one decision entry `S-NEW-1`; move B-0327 to Closed with S-NEW-1. Commit with subject `Wave 8: a quick change shows the structure figures first (B-0327)`.
</checklist>

<acceptance>
`uv run pytest tests/unit/test_w8_quick_structure.py tests/unit/test_ecr_quick_failures.py -q --no-header -x` exits 0; `make lint` exits 0.
</acceptance>

<final_reminder>5 checklist items, in order; only the IN files; plain words for the owner; an exact next step on every error; stop every process you started; commit, never land or push.</final_reminder>
