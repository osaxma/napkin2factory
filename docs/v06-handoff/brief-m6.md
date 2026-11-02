# Task: v0.6 M6 — external, scope and the simulation fixture (milestone task; commit subjects `M6: …`)

Hand this to the subagent together with `docs/v06-handoff/brief-common.md` (read it first).
Task folder: `make task NAME=m6-external GOAL="v0.6 M6: the external-box fixture, the diff page's added section, the owner-session script"`
from the main folder, then `.worktrees/m6-external`. Runs beside M5 (start M5 first).

Read: ELECTRICAL_STAGE.md §5 "M6", DoD 4, 5, 7; S-124, S-127, S-148..S-152 (scope, stand-ins,
the scope words), S-153..S-159 (the domain), `docs/domains.md` §5; the electrical domain's
`model/`, `interfaces/` (the external stub's port check), `outputs/diagram.py` (the dashed
boundary), and `tests/fixtures/electrical/minimal/` (copy its shape).

## Build
1. **`tests/fixtures/scope/external-box/`** (DoD 5): a small heated product (generic words:
   a box, a heater, a probe) whose control box is a sub-assembly with `build: external`,
   `ports:` listing two `cable-entry` interfaces (mains: L, N, PE; control: two control
   conductors), no children; `scope.electrical: in`; one power circuit and one control
   circuit crossing those entries to devices inside the external module only through its
   ports. It validates; its wiring diagram shows the boundary ("to the external box: L, N,
   PE, two control conductors" — the words come from M2's diagram, assert what it draws) and
   nothing inside it; removing a port fails validation naming the assembly file and the port.
2. **`tests/unit/test_scope_external.py`**: DoD 5's three facts; `n2f status` and the
   report's cover/scope lines for `external` and for `later` read the core's words (S-148:
   "done elsewhere (supplied, not built here)", "left for later (not designed here yet)");
   the release cover for a `later` product says what is not included (S-148); a stub joint
   reads "supplied, not built here" (S-152).
3. **`ecr/diff.py`, the "added section" case only**: the diff page between two releases shows
   a report section that is new in the later Revision as "<section label>: added" (generic:
   any domain's section, not a wiring special case), and one that disappeared as
   "<label>: removed". This is the phrase M5's demo asserts ("Wiring: added"). The diff page
   golden (find it: grep tests for the diff page) gains the case; regenerate only that golden,
   logged in `tests/golden/REGENERATION_LOG.md`.
4. **The owner-session script for M7** (DoD 7): `tests/e2e/intake-transcripts/wiring-session.md`
   — the script, not the transcript: the product (a copy of the kiln at the state where its
   wiring is first added, or the external-box fixture if better), the owner persona, the lines
   the owner says turn by turn, what the simulated project manager must do, and the pass
   criteria: the supply-headroom choice is raised after the first build with wiring, not in
   the interview; it is put in the owner's words with both options' consequences; the PM
   decides only with the owner's answer and logs it (F13; see B-0102 for the pick-and-ECR
   question). Copy the shape of the v0.5 protocols (find them via S-132 and S-136).

## Owns
`tests/fixtures/scope/external-box/`, `tests/unit/test_scope_external.py`, `src/napkin2factory/ecr/diff.py`
(the added/removed-section case only), the diff page golden and one log line,
`tests/e2e/intake-transcripts/wiring-session.md`, `DECISIONS.md`, `BACKLOG.md`.
## Must not touch
`src/napkin2factory/core/`, `report/builder.py`, `docs/engine.py`, `cli/check.py` (E10),
`src/napkin2factory/domains/` (finished; a defect is a WIP naming it), `examples/` (M5's),
`STATUS.md`.
## DoD
5, the diff half of 4, the script for 7. Run: `make lint`, `make types`, your tests, the
release/diff tests, the goldens, then `make land`.
