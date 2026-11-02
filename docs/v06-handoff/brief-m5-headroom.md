# Task: v0.6 M5 follow-up — the supply-headroom choice on a European 16 A supply, and the dedicated pick made (commit subjects `M5: …`)

Opened by the second overseer (2026-11-02, during wave 3) from M6's findings B-0149 and B-0151.
A domain follow-up, not a seam: it touches the domain and a calc-kit data table, never the
core, so the count stays honest. M5 (the kiln's data, `.worktrees/m5-kiln`) runs beside you and
needs this landed to raise and settle the kiln's choice.

Hand this to the subagent together with `docs/v06-handoff/brief-common.md` (read it first).
Task folder: created by the overseer, `.worktrees/wiring-headroom` on `task/wiring-headroom`.

Read: ELECTRICAL_STAGE.md E11; S-158 (the choice as built), S-170 (M6's measurement); the
BACKLOG rows B-0149 and B-0151; `src/napkin2factory/domains/electrical/checks/stage.py`
(`_next_circuit`, `_headroom_row`), `.../model/__init__.py` (`Supply`),
`src/napkin2factory/calckit/data/circuits.yaml` and `calckit/power.py` (`circuit_class`, which
the board's screening also uses); `docs/schema-policy.md` (an additive optional field).

## The two defects
1. **B-0151:** on the supply region `EU` at 230 V the table's largest class is 16 A, so a load
   above half of a 16 A supply finds no larger circuit and the check only warns; E11's choice is
   never raised for a European 16 A product (the kiln's case; DoD 4's demo needs the choice).
2. **B-0149:** the pick `dedicated` ("a dedicated 16 A circuit; nothing else may be plugged into
   it") is never in the design: the rule still finds the load above half, so the Design gate
   says "decided …, not yet in the design" for good.

## Build
1. **A cited larger European class.** Add EU rows above 16 A to `calckit/data/circuits.yaml`,
   each with a real source and `verify: true`, e.g. "20 A dedicated circuit" (IEC 60898-1
   preferred MCB ratings; HD 60364) and/or "32 A dedicated circuit (IEC 60309 32 A outlet)".
   No invented numbers: only ratings the cited standards list. **Then confirm the board's
   screening does not move:** `tests/golden/goldens/kiln-board.json` and every other golden
   unchanged, the screening tests green. If a new row changes a screen's result (a card that
   found no EU class now finds one), do not touch the golden: instead keep the table as it
   was and give the headroom check a generic second option when no larger class is on file
   ("a larger circuit, sized by a licensed electrician", which sets no number), and say which
   way you went and why in your entry.
2. **The dedicated pick is something the model can say.** An optional `Supply` field (name it
   plainly, e.g. `dedicated: true`, "the circuit serves this product alone"; additive, schema
   stays 1, no migration) that the headroom rule reads: with it, the row passes and says the
   circuit serves the product alone and nothing else may be plugged into it (the electrician
   confirms). The option `dedicated`'s "what it takes" text names that field change, so the
   project manager knows what applying the pick means. Picking `larger` keeps meaning "the
   supply's rating becomes N A". Check through the core's choice reading that after
   `n2f decide … --pick dedicated` plus the field set, `n2f status` reads the choice as decided
   and in the design (no "not yet in the design" line).
3. **Tests** (in `tests/unit/`, beside the domain's existing check tests): the European 16 A
   case raises the choice with both options (or the generic second option); `dedicated: true`
   passes the row; the existing headroom tests still pass; `tests/fixtures/scope/external-box`
   and `tests/fixtures/electrical/` unchanged in behaviour.
4. **Journals:** one DECISIONS entry (placeholder id); close B-0149 and B-0151 (move them to
   "Closed" with that entry's id); `docs/electrical.md` does not exist yet (M7 writes it): no
   doc edit beyond the field's docstring.

## Owns
`src/napkin2factory/domains/electrical/checks/stage.py` (the headroom row only),
`src/napkin2factory/domains/electrical/model/__init__.py` (the one `Supply` field),
`src/napkin2factory/calckit/data/circuits.yaml` (EU rows only), the tests you add,
`DECISIONS.md`, `BACKLOG.md`.
## Must not touch
`src/napkin2factory/core/`, `report/builder.py`, `docs/engine.py`, `cli/check.py` (E10: if you
need one, stop with a `WIP:` naming it), `examples/` (M5's), `tests/fixtures/`, goldens.
## DoD
B-0149 and B-0151 closed. Run: `make lint`, `make types`, the domain's unit tests, the screening
and board tests, `make goldens`-free golden run (`uv run pytest tests/golden -q`, all pass), then
`make land`.
