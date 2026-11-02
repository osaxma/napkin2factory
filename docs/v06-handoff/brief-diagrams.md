# Task: v0.6 follow-up — the wiring diagrams readable at kiln size (commit subjects `M5: …`)

Opened by the second overseer (2026-11-02, after wave 3) from B-0154 (M5's findings), B-0152
(M6's) and the overseer's own read of `docs/reviews/v0.6-kiln-diagram-*.png`. A domain
follow-up, not a seam: the diagram code is the domain's (`outputs/`), never the core. Gate G (a
licensed electrician reading the package) and gate H (the owner) come next and read these
diagrams; the maintainer judges one of them (S-078).

Hand this to the subagent together with `docs/v06-handoff/brief-common.md` (read it first).
Task folder: created by the overseer, `.worktrees/wiring-diagrams` on `task/wiring-diagrams`.

Read: S-157 (the diagram as built), S-170, S-172; the BACKLOG rows B-0152 and B-0154;
`src/napkin2factory/domains/electrical/outputs/diagram.py` and `rules.py`; the four kiln PNGs
named above (look at them); `tests/golden/goldens/electrical-minimal-heater.svg`;
`tests/unit/test_scope_external.py` (asserts the boundary words).

## What is wrong (measured on the kiln, main at b864778)
1. **Earth:** seven conductor labels stack at the earth bar's one terminal and one prints over
   another (`earth-8`); a conductor's label also repeats at each boundary it crosses.
2. **Sensing:** the limit probe is drawn on the box's side of its cable entry, beside the
   controllers, as if it were inside the box; its partner probe is correctly outside.
3. **Titles:** a sensing circuit's title says "0.051 V DC"; an earth circuit's title says the
   supply's "230 V AC"; both say "Protected by: not given" where no protective device applies.
4. **Control:** readable but busy: long return runs under the boxes are hard to follow; a wire's
   label is only at its start.
5. **B-0152:** the boundary of a module supplied from elsewhere says "supplied from elsewhere"
   where every core surface says "supplied, not built here" (S-152).

## Build (generic: no kiln identifier, F9)
1. Never overprint: where one terminal holds several conductors, place their labels so none
   overlaps (fan them, or label at the far end); a label states a wire once per segment that
   needs it, and a long wire is labelled at both ends (so a reader can match the ends).
2. Sides of a cable entry: a device that the circuit reaches through a cable entry from the box
   is drawn on the far side of that entry (outside), whatever the circuit's purpose; the
   box's devices on the near side. Sources on the left for a circuit with no supply terminal.
3. Titles: the supply's voltage only for a circuit the supply feeds (power, control); a sensing
   circuit says what it carries in words ("extra-low-voltage signal", the figure only if the
   model gives it as a rating), an earth circuit says none; "Protected by" only for circuits
   whose purpose needs a protective device (the checks' own set), never "not given" otherwise.
4. Control: reduce crossings where cheap (order devices by the path; route returns on their own
   lane); do not rewrite the layout engine. If something stays crowded, say so in your entry.
5. B-0152: the boundary and the report's line under it use the core's words for a module
   supplied from elsewhere ("supplied, not built here", S-152); update
   `tests/unit/test_scope_external.py`'s assertion.
6. Goldens: `electrical-minimal-heater.svg` (and any other electrical golden) may move: regenerate
   only those, with `make goldens REASON="…"` logged; the bracket, enclosure and kiln board
   goldens must not move.
7. Pictures: re-render the kiln's four diagrams and the report's Wiring section (on a copy of the
   kiln; the screenshot helper `napkin2factory.concepts.screenshot` or the full-page capture in
   `tests/unit/test_board.py`) over `docs/reviews/v0.6-kiln-diagram-{power,control,sensing,earth}.png`
   and `v0.6-kiln-report-wiring.png`, and look at each yourself; say in your entry which still
   reads poorly.

## Owns
`src/napkin2factory/domains/electrical/outputs/diagram.py`, `outputs/rules.py` (the boundary
words and titles only), `src/napkin2factory/domains/electrical/owner/` (only the line under a
diagram, if it repeats the boundary words), the electrical goldens and their log line,
`tests/unit/test_scope_external.py` (the boundary-words assertion only), the domain's diagram
tests, `docs/reviews/v0.6-kiln-*.png`, `DECISIONS.md`, `BACKLOG.md` (close B-0152, B-0154).
## Must not touch
`src/napkin2factory/core/`, `report/builder.py`, `docs/engine.py`, `cli/check.py` (E10: if you
need one, stop with a `WIP:` naming it), `examples/`, `docs/` other than the PNGs, `STATUS.md`.
## DoD
B-0152 and B-0154 closed (or B-0154 narrowed to what is left, said plainly). Run: `make lint`,
`make types`, the domain's tests, `tests/unit/test_scope_external.py`, `uv run pytest tests/golden -q`,
`tests/e2e/test_kiln.py`, then `make land`.
