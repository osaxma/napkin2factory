# Task: v0.6 M3 — checks, the verify kind and the choice (milestone task; commit subjects `M3: …`)
Task folder: /Users/wakeel/napkin2factory/.worktrees/m3-checks (branch task/m3-checks).
Read ELECTRICAL_STAGE.md §5 "M3", E6, E11, DoD 3 and 8; DECISIONS S-154 (the overseer's
decisions: devices address instances, upstream protection, entries by voltage band, earth paths
through joints, contact ratings — they refine E6); the wave-2 common brief
(docs/v06-handoff/brief-wave2-common.md);
`docs/domains.md` §3.3, §3.4, §3.13; `calckit/wiring.py` and `calckit/power.py`.

## Build (fill `src/napkin2factory/domains/electrical/checks/`)
- `calcs.py`: the figures, unit-safe (`core.units`), every number from the calc kit:
  a load device's current from its rating (power and voltage → `calckit.power`'s element
  current; or its rated current); a power circuit's load current (the sum of its loads);
  the supply's rating (a quantity, a `param://` value, or the upstream protection's rating);
  the supply margin (rating − the sum of the power circuits' loads on it); each conductor's
  current (the circuit's load current for a power circuit; a control or sensing conductor's
  current is "not known" unless a device declares it — never a fail on an unknown);
  the conductor margin (ampacity − current, from `calckit.wiring.conductor` or a product row);
  earth paths (each custom part of conductive material — read its material's class from the
  calc kit's materials table — has a PE connection, or a `bonded_via` earth entry).
- `electrical-v0.yaml`: the rule list with owner words per rule, in the shipped rule packs'
  style (id, title, severity, message, params with `source` and `verify: true` for any
  number). E6 as refined by S-154:
  **fail** (arithmetic and topology, certain): the load current above the supply's rating;
  a conductor below its table ampacity for its current; a conductive custom part with no
  path to earth and no `bonded_via`; a circuit with no protective device (`supply` passes when
  the supply declares a rating); a terminal used by more conductors than the device allows
  (only when the device or its datasheet row declares a limit; else no row).
  **warn** (a code would judge it; every message ends "a licensed electrician decides" or
  similar): an interlock (`safety: interlock`) not in series with the coil of the device that
  switches the load (walk the control path through the devices' `through` pairs); a limit
  device (`safety: limit`) switching the same device the controller switches (it must break
  an independent one); extra-low-voltage and mains conductors through one cable entry (S-154
  point 4; the 50 V AC / 120 V DC band cited `[verify]`); a contact switching a coil or an
  inductive load whose category is not AC-15/DC-13 or unknown (S-154 point 6); `bonded_via`
  claims; upstream protection to confirm (S-154 point 2); a device with `terminals: []`.
  Each failure names the part (by its name), the circuit and what to do (DoD 3).
- `stage.py`: `electrical_checks(sctx)` → `CheckResult` rows of kind `electrical`, ids
  `elec-rule://<rule>@<circuit or part>` or similar (unique, stable), reading the model
  through `sctx.proxy` and `sctx.log`; `sctx.keep(<the assembly id the circuit's devices
  share, else None>)` so `n2f check --scope asm://<id>` includes the circuits whose devices all
  sit in that module (§4); `electrical_check_reads(product)` returns the `circuit://<id>` keys.
  No rows at all for a product without `model/electrical/` (E12).
- **The choice (E11):** `supply-headroom` — when the power circuits' load is above a cited
  fraction of the supply's rating but fits, the row is a choice through `offer(..., blocks="none")`.
  The fraction: 50 %, NEC 210.23(A)(2) (fixed equipment above half a branch circuit's rating
  must not share the circuit with other loads) `[verify]`, a param of the rule. Options in the
  owner's words, both valid: keep the rating on a circuit that serves this product alone
  ("a dedicated <rating> circuit; nothing else may be plugged into it"), or a larger circuit
  that leaves room ("a <next size> circuit: room for a bigger heater later; the electrician
  fits thicker cable", `cost_delta` only if cited, else omitted). `detail["evidence"]` = the
  supply and the power circuits' keys, so a change reopens it. `problem`: one owner sentence
  with the numbers ("10.9 A of the 16 A circuit: more than half of it").
- `verify.py`: `evaluate_circuit` for `circuit://<id>#load_current`, `#supply_margin`,
  `#conductor_margin`, `#earth_paths` (a count): compares, `res.message` with the numbers,
  `evidence["circuit://<id>"]` = the `elec:<id>` rule's output hash as the core recomputes it
  (read docs/domains.md §3.3 on evidence keys; use `napkin2factory.core.checks.evidence.evidence_key`
  only in tests). A selector you do not know is a `check(verify)` error listing the four.
  Note: a requirement's `value` is a quantity, never a `param://` (ELECTRICAL_STAGE §3's
  example is wrong there): compare `#supply_margin` with `0 A` instead.
  Safety requirements in the `electrical` category stay `manual` (needs-human) always: the
  verify kind refuses `safety: true` requirements with a message saying to use `manual`.
## Tests (`tests/unit/test_electrical_checks.py`)
DoD 3's six fixtures under `tests/fixtures/electrical/{over-supply,thin-conductor,unearthed,unprotected,interlock,shared-entry}/`
(each a copy of the minimal fixture with one change): the first four fail, the last two warn,
each message names the part, the circuit and what to do. Plus: the minimal fixture's rows all
pass or warn as expected; the choice raised (minimal fixture above 50 %), `n2f decide` it
in-process, the row reads `pass` with the decision, then an edit of a power connection reopens
it; the verify kind passes/fails on each selector and its evidence key changes when a
connection changes (and not when an unrelated part changes); `--scope asm://` keeps only that
module's circuits; a product without wiring has no `electrical` row; owner words: no row text
contains a URI scheme or an example id.
## Owns
`src/napkin2factory/domains/electrical/checks/` (all), the six fixture folders,
`tests/unit/test_electrical_checks.py`, `DECISIONS.md`, `BACKLOG.md`.
## Must not touch
`core/` (E10), `domains/electrical/` outside `checks/`, `tests/fixtures/electrical/minimal/`,
`examples/`, `STATUS.md`, `docs/domains.md`.
## DoD
3, 8 (the current read from the calc kit's `power` pack; every threshold cited), feeds 4 and 7
(the choice). Run: `make lint`, `make types`, your tests, `tests/unit/test_electrical_model.py`,
then `make land`.
