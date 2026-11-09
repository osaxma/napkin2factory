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
In the wave 7 trial the final bench's legs stopped at 735 mm, under top rails at 735 to 824 mm
that sat between the leg lines, so the top rested on nothing, and the screens and `n2f check`
passed it. The interference check is the model to follow: `src/napkin2factory/core/checks/interference.py`
(`check_interference` reads `build/assemblies/<id>/instances.json` and each part's
`build/parts/<id>/model.step`, placing each instance with its translation and rotation), staged by
`interference_stage` in `core/checks/engine.py` (line 435) and registered in
`src/napkin2factory/domains/mechanical/__init__.py` (line 198) as
`CheckStage("interference", lazy(...), after=("interface",))`. Put the new code in a new file
`src/napkin2factory/domains/mechanical/support.py` and register
`CheckStage("support", lazy(...), after=("interference",))` beside it. The build's Z axis is up;
check it on `examples/table` (the legs are along Z) before relying on it.

Decided design (do not change it):
1. For each assembly, take each placed instance's world bounding box (from the moved STEP shape).
2. Ground = instances whose box bottom (min Z) is within 0.5 mm of the lowest min Z in the
   assembly.
3. Two instances are connected when (a) their boxes touch: a gap of at most 0.5 mm along one
   axis, and on the other two axes an overlap whose area is at least 1 mm² (a face patch, not an
   edge or a corner); or (b) a declared interface (`product.interfaces`) names both parts and the
   gap between their boxes is more than 0.5 mm and at most 30 mm (drawn-less hardware such as
   standoffs bridges it).
4. Walk the connections from the ground. Every instance not reached is unsupported.
5. The check result: `id=f"support://{aid}"`, `kind="support"`, `title="every part is held up"`,
   `status` `pass` or `fail`, the message naming each unsupported part in words ('<part title> is
   not held up: it touches nothing that leads to the floor'), `skip` when the assembly has not been
   built.
</this_task>
</context>

<scope>
IN: src/napkin2factory/domains/mechanical/* tests/unit/test_w8_* DECISIONS.md BACKLOG.md docs/cli.md docs/agent-guide.md
OUT: everything else. Do not refactor, rename or reformat anything not asked for.
</scope>

<task>Add a check that every part of an assembly is held up: connected, through face contacts or declared interfaces, to a part standing on the floor.</task>

<checklist>
1. Check on a prebuilt copy of `examples/table` that Z is up and that `instances.json` gives what the design needs; write it in your report.
2. Write `src/napkin2factory/domains/mechanical/support.py` with the decided design (a public function `check_support(product, asm_id, build_dir)` returning a small report, and `support_stage(sctx)` returning `CheckResult`s as `interference_stage` does), with docstrings.
3. Register the stage in `domains/mechanical/__init__.py` after `interference`. Run it on prebuilt copies of `examples/bracket`, `examples/enclosure`, `examples/table` and `examples/test-stand`: each must pass. If one fails, do not loosen the design: report which parts and why, and stop there.
4. New test `tests/unit/test_w8_support_check.py`: (1) the table passes; (2) the table with its legs shortened so the rails sit on the legs' top edges only fails and names the top and the rails; (3) a unit test of the connection rule on hand-made boxes: face touch connects, edge touch does not, an interface across a 10 mm gap connects.
5. Docs: one row for the new check where `docs/cli.md` lists check kinds (if it does), and one sentence in `docs/agent-guide.md` where checks are explained. Journal: one decision entry `S-NEW-1` (the design in 4 lines; no core files touched); move B-0328 to Closed with S-NEW-1. Commit with subject `Wave 8: a check that every part is held up (B-0328)`.
</checklist>

<acceptance>
`uv run pytest tests/unit/test_w8_support_check.py -q --no-header -x` exits 0; `make lint` exits 0.
</acceptance>

<final_reminder>5 checklist items, in order; only the IN files; plain words for the owner; an exact next step on every error; stop every process you started; commit, never land or push.</final_reminder>
