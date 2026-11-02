# Task: v0.6 M2 — the rule family and its outputs (milestone task; commit subjects `M2: …`)
Task folder: /Users/wakeel/napkin2factory/.worktrees/m2-outputs (branch task/m2-outputs).
Read ELECTRICAL_STAGE.md §5 "M2" and E5 (as decided in S-145: no parts-list seam, the
domain's own schedule plus `cables.csv`), DoD 2 and 5, and the wave-2 common brief
(docs/v06-handoff/brief-wave2-common.md:
the file contract you write).

## Build (fill `src/napkin2factory/domains/electrical/outputs/`)
- `rules.py`: `elec_rules(b)` → one `elec:<circuit>` per circuit plus `elec:_schedule`
  (wave-2 brief), `depends_on` the parts each circuit's devices name and the parts of each
  entry; `elec_static_reads(product, rule)`. Every model value through `ctx.proxy` (supply,
  devices, circuits, conductors, parts' names, the entries' interfaces); any other key with
  `ctx.log.add`. Parameter values a supply names (`param://…`) are read through the proxy of
  the parameter or `ctx.log.add("param://<id>")`. Output hash = `sha256_json(record)`.
- `diagram.py`: a programmatic ladder-style SVG per circuit (E5): devices as labelled boxes
  (part name, instance words), terminals as marked pins with their markings, each wire a line
  labelled with its id, conductor cross-section and colour; the cable entries as dashed
  boundaries crossed by the wires that pass them; an external module's boundary dashed and
  labelled ("to the external box: L, N, PE, two control conductors", DoD 5) with nothing
  drawn inside it. Readable at the kiln's size (a dozen devices, three circuits: one diagram
  each; if crowded, a device index table beside it, risk table §7). Reuse the drawings'
  SVG text/line style if there is a helper under `src/napkin2factory/drawings/` (read only;
  import it, never edit it); deterministic output (no timestamps, stable ordering) so a golden
  can hold it. Self-contained SVG (no external refs: it is embedded in the `file://` report).
- `schedule.py`: `schedule.csv`, `labels.csv`, `cables.csv`, `connections.json` per the
  contract; colours from `calckit.wiring.colour(region, role)` when a wire names none (role
  from the terminals: `L`/`N`/`PE` …; else the connection's own colour, else "not given").
- `export_kicad.py` (⤵ droppable, E1): a text `.kicad_sch` s-expression per circuit, written
  under `build/electrical/<circuit>/`, never source; a test parses it (balanced
  s-expressions, the symbols and wires present); nothing runs a desktop tool. Drop it if it
  costs more than an hour; record the decision either way.
- `RELEASE_FILES` in `outputs/__init__.py` already names the shipped files; keep them in step.
## Tests (`tests/unit/test_electrical_outputs.py`, plus goldens)
- The minimal fixture builds: every file of the contract exists and parses; `connections.json`
  matches the model; the CSV headers exactly as the contract; `cables.csv` totals.
- A golden diagram for the minimal fixture: `tests/golden/goldens/electrical-minimal-*.svg`
  (and its JSON), compared byte-for-byte; generated through the repo's goldens mechanism
  (read `tests/golden/conftest.py`; `make goldens REASON=...` regenerates all goldens and logs
  it — prefer regenerating only yours if the mechanism allows; never change another golden).
- Invalidation: a changed conductor length reruns `elec:<that circuit>`, `elec:_schedule`
  and what reads them (`doc:*` pages that use the helpers, `checks`, `report`), and no part,
  assembly, drawing or `bom` rule; an edit of another circuit leaves this circuit's rule
  skipped; `n2f impact --set circuit://<id>#…` names `elec:<id>` (impact ⊇ rebuild, like the
  toy's table test; one case per Circuit and Connection field you read).
- An external-boundary variant of the fixture (your own copy) shows the dashed boundary with
  its words and draws nothing inside the external module.
- The release package of the built minimal fixture holds `electrical/<circuit>/diagram.svg`,
  `schedule.csv`, `labels.csv`, `cables.csv` (S-142) — `make_bundle` into a tmp folder.
- The report's size for the minimal fixture, recorded in your decision entry (measured).
## Owns
`src/napkin2factory/domains/electrical/outputs/` (all), `tests/unit/test_electrical_outputs.py`,
`tests/golden/goldens/electrical-*`, your own fixture folders under
`tests/fixtures/electrical/outputs-*/`, `tests/golden/REGENERATION_LOG.md` (one line),
`DECISIONS.md`, `BACKLOG.md`.
## Must not touch
`core/`, `report/builder.py`, `docs/engine.py`, `cli/check.py` (E10), `domains/electrical/`
outside `outputs/`, `tests/fixtures/electrical/minimal/`, `examples/`, `STATUS.md`,
`docs/domains.md` (if you find the contract short, say where in your report).
## DoD
2 (the diagrams, schedule, labels; the release ships them), 5 (the boundary drawn).
Run: `make lint`, `make types`, your tests, the goldens, `tests/unit/test_electrical_model.py`,
then `make land`.
