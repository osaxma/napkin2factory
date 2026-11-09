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
In the wave 7 rerun, 28 minutes in, the trial agent ran `pip install napkin2factory==0.8.0`
inside its sandbox (the sandbox allows the network, since the client needs it) and read that copy's
source 121 times. The trial set-up is outside the repository, in `/Users/wakeel/n2f-trial/rerun/`:
`run.sh` starts the client under `sandbox-exec -f sandbox.sb` (line 18), and `smoke.sh` checks the
sandbox before a run. Do not change `sandbox.sb`'s network rules (the client needs the network).
Do not start dsh or a browser. Never print the contents of any `.env` or credentials file.
</this_task>
</context>

<scope>
IN: the files named in the checklist, outside the repository
OUT: everything else. Do not refactor, rename or reformat anything not asked for.
</scope>

<task>Make the persona trial's sandbox refuse package installs, so the agent cannot install n2f from a package index and read its source.</task>

<checklist>
1. Read `run.sh` and `smoke.sh` (not the key files). In `run.sh`, just before the `sandbox-exec` line, export: `PIP_NO_INDEX=1`, `PIP_INDEX_URL=http://127.0.0.1:9/simple`, `PIP_FIND_LINKS=`, `UV_OFFLINE=1`, `UV_INDEX_URL=http://127.0.0.1:9/simple`, `UV_DEFAULT_INDEX=http://127.0.0.1:9/simple`, `PIP_CONFIG_FILE=/dev/null`.
2. In `smoke.sh`, add a step that runs, inside the same sandbox with the same variables, `python3 -m pip download --no-deps -d /tmp/w8-pip napkin2factory==0.8.0` and `uv pip install --target /tmp/w8-uv napkin2factory==0.8.0`, and fails the smoke if either succeeds.
3. Run `bash smoke.sh`; it must pass, with the new step showing both installs refused.
4. Write what you changed (files and lines) in your report. Do not commit anything in the napkin2factory repository.
</checklist>

<acceptance>
`bash /Users/wakeel/n2f-trial/rerun/smoke.sh` exits 0.
</acceptance>

<final_reminder>4 checklist items, in order; only the IN files; plain words for the owner; an exact next step on every error; stop every process you started; commit, never land or push.</final_reminder>
