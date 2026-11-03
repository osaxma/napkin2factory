# Task: the wiring outputs carry the disclaimer (gate G blocker 3, gate H blocker B2; commit subjects `M7: …`)

Opened by the third overseer (2026-11-03). Read `docs/reviews/v0.6-gate-g.md` (Q5, Q10, Blocker 3)
and `docs/reviews/v0.6-gate-h.md` (B2, C3, C4). A domain fix (`outputs/`, `owner/`), not a seam.
Hand with `brief-common.md`. Task folder: `.worktrees/wiring-disclaimer` on `task/wiring-disclaimer`.

## What is wrong (measured by the reviewers at f67dc06)
1. The four `electrical/<circuit>/diagram.svg` files in the package carry no disclaimer, no product
   name and no Revision (grep "licensed" → 0), unlike every mechanical drawing; a printed diagram
   travels without one. The diagram is the page an owner hands an electrician.
2. "not reviewed by a licensed electrician" exists only in the report's Wiring section
   (`owner/wiring.html.j2:6`); the installation manual's wiring pages and the schedule/labels/cables
   CSVs do not say it.
3. (gate H C3, B-0157) The report's heading above each diagram reads "Control control circuit" and
   "protected by not given" for earth and sensing; sensing shows "51 mV DC".
4. (gate H C4) The section's lead says "Lengths are given in the wiring model" while every circuit
   note calls them estimates.

## Build (generic words, F9)
1. A footer band on every diagram, like the mechanical sheets' title block (`drawings/sheet.py`
   shows how they word and place it; read it, do not import private helpers): the product's name,
   the circuit, the Revision when the build is a release's (else "draft"), and "Produced with an AI
   system; not reviewed by a licensed electrician: a licensed electrician wires the product to local
   code." Goldens: only electrical SVG goldens may move (`make goldens REASON="…"`).
2. The installation manual's wiring section (the doc helpers in `owner/docs_helpers.py`) states the
   same sentence once at its head.
3. The CSVs: do not put a comment row into a CSV (parsers choke). Instead the domain writes
   `build/electrical/README.txt` (the disclaimer, what each file is, and that lengths are
   estimates) and the package's `electrical/` folder carries it. If the release copies only listed
   files, use the domain's release-files declaration (S-142); if that needs a core edit, stop with a
   `WIP:` naming it (E10).
4. C3/C4: the heading line says the circuit once, the voltage and "protected by" only where the
   diagram title does (S-174's rule: by purpose); lengths "estimated" where they are.
5. DECISIONS.md: one entry (a placeholder id, as `brief-common.md` says) citing gate G blocker 3
   and gate H B2/C3/C4; close B-0157 in BACKLOG.md.

## Owns
`src/napkin2factory/domains/electrical/outputs/`, `src/napkin2factory/domains/electrical/owner/`,
the domain's `__init__.py` only for a release-files declaration, electrical goldens, the domain's
output/owner tests, `docs/reviews/v0.6-kiln-diagram-*.png` (re-render one, power, and look at it),
`DECISIONS.md`, `BACKLOG.md`.
## Must not touch
`src/napkin2factory/core/`, `report/builder.py`, `docs/engine.py`, `cli/check.py`, `ecr/` (the
package README's sentence is a separate seam task), `domains/electrical/checks/` (another task),
`examples/`, `STATUS.md`, `docs/v06-handoff/`, the untracked `FIX_CI_NIGHTLY.md`.
## DoD
Run `make lint`, `make types`, the domain's tests, `uv run pytest tests/golden -q`,
`tests/e2e/test_kiln.py`; then `make land`. Report: landed commit, decision id, the footer's text
as printed, which goldens moved, test numbers, gate time, 0 core files.
