# Task: v0.6 M5 — the kiln, wired (milestone task; commit subjects `M5: …`)

Hand this to the subagent together with `docs/v06-handoff/brief-common.md` (read it first).
Task folder: create it with `make task NAME=m5-kiln GOAL="v0.6 M5: the kiln wired, its manual's wiring section, demo-electrical.sh"`
from the main folder, then `.worktrees/m5-kiln`.

Read: ELECTRICAL_STAGE.md §5 "M5", E8, E9, E11, DoD 2, 4, 6; `docs/v06-baseline.md` (the kiln
survey: §2 parts, §3 intended connections, §4 the proposed devices and circuits, §5 the open
points); `docs/v06-handoff/terminals.md` (terminal markings sourced after the survey: copy the
facts with their sources into `docs/v06-baseline.md` §2 first, `[verify]` each); the decisions
S-153..S-164 (index rows; open S-154, S-157, S-158, S-159 in full); `docs/domains.md` only as
needed. The domain is complete (M1–M4, M4b): you WRITE KILN DATA, you do not change the domain.

## Build (all under `examples/kiln/` unless named)
1. **The model** (`model/electrical/`): `supply.yaml` (230 V, 1 phase, 50 Hz, rating
   `param://circuit-rating`, earthing from the earthing table, region, `protection: {upstream:
   "<the site's 16 A device>", rating: 16 A}` — S-154 point 2), devices for every powered part
   in the survey (connection ends are `device://<id>#<terminal>`, S-154 point 1: two probe
   devices on the one thermocouple part, earth-stud devices per placed stud, each with
   `instance:` words), `terminals:` from the sourced markings (controllers: supply 11–12,
   output 1 on 1(+)/2(−) or the relay 1–2, TC 6(+)/5(−), aux 9–10 and 7–8; door switch NO
   13–14, NC 31–32 (the direct-opening pair: the interlock uses 31–32); SSR control 3(+)/4(−),
   load 1–2; contactor A1/A2, 1/L1…6/T3, 13–14, 21–22), `safety:` (interlock, limit),
   `coil:`, `through:` pairs, `contact:` ratings where sourced (the limit controller's relay is
   resistive-only: the contact-on-coil warn is the honest result, keep it), circuits `power`,
   `control`, `sensing` (and the earth list), conductors from `calckit.wiring` plus a product
   row for type K extension cable (`model/electrical/conductors/`).
2. **Missing parts** (S-154 point 3): bought, BOM-only parts with a source and
   `verified: false`: the box's earth terminal, a supply terminal block, the element tails'
   termination, the SSR heat sink, a control-circuit fuse. No invented ratings: unknown
   ones are `[verify]` notes. Opening parts (lid, door tray) get flexible bonding leads;
   bolted parts may use `bonded_via` (a warn, S-154 point 5).
3. **Cable entries** (E4, S-154 point 4): the three M20 glands become three `cable-entry`
   interfaces on the box (mains in; element + interlock + bonding leads out; sensing out),
   and the box's three `cutouts` leave its kit arguments (no hole cut twice). The joint's
   spec: `count: 1`, `diameter: 20.5 mm`, NO `pattern:` (M1 refuses `pattern: circle` without a
   pitch circle; ELECTRICAL_STAGE §3's example is wrong there), `passes: [circuit://…]`.
   Check the box's built holes and props are unchanged (same positions).
4. **Requirements**: the circuit verify kind's targets are `circuit://<id>#props.<figure>`
   (S-158, B-0139: `load_current`, `supply_margin`, `conductor_margin`, `earth_paths`); compare
   `#props.supply_margin` with `0 A`, never a `param://` value. Electrical safety requirements
   stay `manual` (needs-human); keep the `tags: [electrical]` (S-148). Tag REQ-007/-016/-021
   only if they are electrical (S-148 left them [revisit]).
5. **Scope and the choice**: `scope.electrical: in` with its `DEC-`; build, and the
   supply-headroom choice (E11, S-158: 10.9 A is more than half of 16 A) is raised: decide it
   on main with `n2f decide` as the project manager would (conservative: the dedicated 16 A
   circuit the rating label already states) so main's kiln has no open wiring choice.
6. **The manual**: `model/docs/installation.md` rewritten around the helpers (`circuit("…")`,
   `cable_schedule()`, `terminal_labels()`, `cables_to_buy()`; read `owner/docs_helpers.py`
   for their exact names); the sentence "This package has no wiring diagram" is gone; the
   electrician is still told they wire to local code and decide every marked point.
7. **E8's other half is done** (M4b moved the supply screen); confirm
   `tests/golden/goldens/kiln-board.json` is unchanged after your edits.
8. **Sign-offs**: if a kiln sign-off's evidence changes because the box changed, re-key it
   with `scripts/rekey_signoffs.py` only where the change is the cutout→entry swap with
   identical geometry, and say so in your decision entry; never re-key a real change.
9. **The demo** (E9, DoD 4): `examples/kiln/demo-electrical.sh`, run in a temp copy (D23),
   starts from a copy whose wiring is removed (the script removes `model/electrical/`, the
   cable-entry interfaces, the wiring parts and their decision, and sets `electrical: later`)
   → release `v1.0.0` (the cover says the wiring is left for later) → `ECR-003`, a design
   change request with a patch that adds it all back → impact → approve → apply → build →
   the supply-headroom choice raised and decided with `n2f decide` → check → close →
   `v1.1.0` with `electrical: in` → the diff page shows the Wiring section as added (M6
   writes that case in `ecr/diff.py`: the agreed words are "<section label>: added"; if M6 has
   not landed when you test, assert it in a test M6's landing will satisfy, or land after M6).
   Generate the patch from the wired and unwired trees; store it like the other demos' ECR
   patches. Re-create B-0063's `ECR-002` patch if the manual's change breaks it
   (`demo.sh` and `demo-design.sh` otherwise unchanged).
10. **Tests and Makefile**: `tests/e2e/test_demos.py` gains the demo; the `demos` target in
    `Makefile` runs four side by side (`-n 4`); `tests/validate_outputs_full.py` expects
    `build/electrical/<circuit>/diagram.svg`, `schedule.csv`, `labels.csv`, `cables.csv` for
    the kiln; the kiln's report size recorded (≤ 20 MB) in your entry.
11. **Pictures for the maintainer**: PNG renders of the kiln's three diagrams and the report's
    Wiring section (the repo's screenshot helper) saved under `docs/reviews/v0.6-*.png`
    (the overseer sends them; judge readability yourself first: if a kiln diagram is
    unreadable, say so — the diagram code is M2's `outputs/`, a follow-up the overseer opens).

## Owns
`examples/kiln/` (all), `tests/e2e/test_demos.py`, `tests/validate_outputs_full.py`, `Makefile`
(the `demos` target only), `docs/v06-baseline.md` (the sourced terminals), `docs/reviews/v0.6-*.png`,
`DECISIONS.md`, `BACKLOG.md`, `STATUS.md` (the M5 line).
## Must not touch
`src/` entirely (E10 for the core; the domain is finished — a domain defect found here is a
WIP naming it, the overseer opens a follow-up), `ecr/diff.py` (M6), `tests/fixtures/`.
## DoD
2, 4, 6 (golden unchanged), feeds 7 and 9. Run: `make lint`, `tests/e2e/test_kiln.py`, the new
demo test, `make kiln` (the kiln step of check-full), then `make land` with `LAND_GATE=check`
(the full `make check`, since the kiln and examples change). Measure: the demo's own time, the
kiln build time, the report size.
