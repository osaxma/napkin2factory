# Task: v0.6 M4 — the owner's view (milestone task; commit subjects `M4: …`)
Task folder: /Users/wakeel/napkin2factory/.worktrees/m4-owner (branch task/m4-owner).
Read ELECTRICAL_STAGE.md §5 "M4", E7, E8, E12, DoD 2, 6, 10; DECISIONS S-148..S-155 (the scope
words and the domain's word, S-150; the M1 package); the wave-2 common brief
(docs/v06-handoff/brief-wave2-common.md);
`docs/domains.md` §3.5–3.8, §3.11, §3.12, §6.

## Build (fill `src/napkin2factory/domains/electrical/owner/`)
- `report.py` + `wiring.html.j2`: the "Wiring" section (group Product): per circuit its
  diagram embedded inline (the SVG text from `build/electrical/<c>/diagram.svg`, sanitised to
  stay `file://`-safe: no external refs, D13), its wires as a table, then the cable schedule,
  "cable to buy" totals and the check rows of kind `electrical` with `badge`/`w` words; the
  scope line when the domain is `later` or `external` (the core's words, S-148/S-150: read
  them, do not restate them); `show(product)` false with no content and no scope entry (E12);
  `data(sctx)` reads the model through `sctx.proxy`, `reads(product)` = the `circuit://<id>`
  keys and `rule:elec-schedule`. Plain owner words throughout; ids only with their titles.
  The report stays ≤ 20 MB.
- `docs_helpers.py`: `circuit("id")` (the circuit's owner words, devices, wires as an object a
  page can print), `cable_schedule()` (rows), `terminal_labels()` (rows); each records what it
  reads (`h.proxy`, `h.log.add` of the build keys); a page using them is stale until rebuilt
  (`doc_staleness`) and fresh after ONE build (S-143's `before=("doc",)`). Build files: read
  from `h.product.paths.build` (a `HelperContext` has no `build_dir`, B-NEW: the S-143 task
  noted it; record a backlog row for it).
- `gates.py`: the Design row M1 wrote (keep it); fill the Verify row "Wiring checks"
  (`check_rows_state(build_dir, "electrical", …)`); both absent without content unless the
  scope names the domain (E7, F4, F11).
- `vocabulary.py`: owner words for every scheme and term (`device`, `circuit`, `supply`,
  `conductor`, the domain itself "wiring", `cable-entry` "cable entry"), so `n2f check --all`
  says "circuit power" not `circuit://power`; engineer words where the contract has them.
- `screens.py`: E8 — the supply screen moves from the kiln's pack into the domain, as one
  atomic change (you also own the kiln pack's edit, so main is never left with two copies or
  none): the screen, its rule `circuit-available` (its row id, params, words) and the helpers
  it needs, generic (no kiln words; "the heater", "the product"). Domain screens run before a
  product's own within a phase (docs/domains.md §3.11), and the kiln's supply screen today
  reads `values.shared["power"]` that the kiln's thermal screen writes in the same phase:
  choose the phase so the kiln's heat-up-derived power is still seen, and the card's own
  `envelope.power` too. In `examples/kiln/model/screens/heated_enclosure.py` remove the supply
  screen and its rule, keep `PROMOTE_REQUIREMENTS`/`PROMOTE_RATIONALE`/`SUMMARY_PHRASES`
  working (the promotion hook reads `RULES["circuit-available"]["params"]["headroom"]` and the
  screening row `circuit-available`: read the domain's value instead, through a public name).
  **DoD 6: `tests/golden/goldens/kiln-board.json` must not change.** If keeping it unchanged
  needs a core edit (screen order, a field another screen declares), stop and commit `WIP:`
  saying exactly what; do not regenerate that golden.
- `context.py`: `n2f context asm://<id>` lists the circuits whose devices sit in that module
  (each with its connections in owner words) and the cable entries that are its ports; nothing
  of another module's circuits (F1, so a one-module simulation can make a wiring change).
## Tests (`tests/unit/test_electrical_report.py`)
The section renders for the minimal fixture (diagram inline, schedule, rows) and is absent for
the bracket (no "Wiring" in its report or side index); a `later` product shows the scope line;
the helpers record reads, a page goes stale on a wire edit and is fresh after one build; the
gate rows appear only with content or a scope entry; the screen on a card with
`site.circuit`/`site.region` and `envelope.power` gives the row and estimates it gave in the
kiln pack (same words, same numbers); the kiln board golden test passes unchanged
(`uv run pytest tests/golden -q -k kiln`, and the kiln's napkin tests: grep `tests/` for
`kiln-board` and `concept`); the context lists a module's circuits and not another's.
`docs/domains.md` §8's contract tests for what M4 brings (gate rows, section, helpers,
vocabulary, screen, context): copy the toy's pattern.
## Owns
`src/napkin2factory/domains/electrical/owner/` (all), `tests/unit/test_electrical_report.py`,
`examples/kiln/model/screens/heated_enclosure.py` (the supply move only), your own fixture
folders `tests/fixtures/electrical/owner-*/`, `DECISIONS.md`, `BACKLOG.md`.
## Must not touch
`core/`, `report/builder.py`, `docs/engine.py`, `cli/check.py` (E10), `domains/electrical/`
outside `owner/`, `tests/fixtures/electrical/minimal/`, every other kiln file (M5's),
`tests/golden/goldens/kiln-board.json`, `STATUS.md`, `docs/domains.md`.
## DoD
2 (the report's Wiring section; a visual exit the overseer sends the maintainer — make it
look right in a browser: run the repo's screenshot helper on the minimal fixture's report and
look), 6, 12. Run: `make lint`, `make types`, your tests, the kiln board/napkin tests, the
goldens, then `make land`.
