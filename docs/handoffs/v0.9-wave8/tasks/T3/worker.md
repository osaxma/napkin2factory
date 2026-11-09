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
In the wave 7 trial a card's cross member ran through a frame kit's member. The screen
`src/napkin2factory/concepts/screens/overlap.py` compares only exact silhouettes
(`EXACT_KITS = ("block", "plate", "tube")`, line 29): a frame is drawn as one solid in the massing,
so it is skipped, the card screened green, and the built model failed "parts do not overlap"
(50,388 mm³). The frame kit is `src/napkin2factory/geometry/kit/frame.py`: `pieces(a, bottom_height)`
(line 215) lists its members, and `_solid_span` / `_box` (lines 299 to 316) give each member's
extent. Read the module docstring of `overlap.py` first: it explains why hollow shapes are
skipped. Keep that for tubes and enclosures; only add frames, member by member.
</this_task>
</context>

<scope>
IN: src/napkin2factory/concepts/screens/overlap.py tests/unit/test_screening*.py tests/unit/test_w8_* DECISIONS.md BACKLOG.md
OUT: everything else. Do not refactor, rename or reformat anything not asked for.
</scope>

<task>Make the `rough-shapes-overlap` napkin screen test a piece against each member of a `frame` kit, so a cross member through a frame member is caught at the napkin.</task>

<checklist>
1. In `overlap.py`, for a piece whose kit is `frame`, build the list of its members' axis-aligned boxes in the card's coordinates from the frame kit's `pieces()` (reuse its functions; do not copy the geometry maths).
2. Compare each other exact piece (block, plate, tube) with each member box; report an overlap when the common volume is above the screen's existing threshold, naming the frame and the member (for example 'the cross member passes through the frame's front leg').
3. Two frames: compare member boxes with member boxes.
4. New test `tests/unit/test_w8_overlap_frame.py`: a card with a frame and a plate through one member (fails), the same plate moved into the open space between members (passes), and a block resting on top of the frame (passes: touching is not overlapping).
5. Journal: one decision entry `S-NEW-1`; move B-0323 to Closed with S-NEW-1. Commit with subject `Wave 8: the overlap screen tests a frame's members (B-0323)`.
</checklist>

<acceptance>
`uv run pytest tests/unit/test_w8_overlap_frame.py tests/unit/test_screening.py tests/unit/test_screening_door_touch.py -q --no-header -x` exits 0; `make lint` exits 0.
</acceptance>

<final_reminder>5 checklist items, in order; only the IN files; plain words for the owner; an exact next step on every error; stop every process you started; commit, never land or push.</final_reminder>
