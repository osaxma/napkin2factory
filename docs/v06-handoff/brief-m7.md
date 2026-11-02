# Task: v0.6 M7a — the docs for the wiring (milestone task; commit subjects `M7: …`)

Written by the second overseer (2026-11-02) from ELECTRICAL_STAGE.md §5 "M7", DoD 10, and the
handoff README §5. M7's other parts are the overseer's, not yours: the owner simulation (DoD 7),
gates G and H, their fixes, the close-out (version files, pins, the handoff report).

Hand this to the subagent together with `docs/v06-handoff/brief-common.md` (read it first).
Task folder: `make task NAME=m7-docs GOAL="v0.6 M7a: docs/electrical.md, the agent guide, the three roles, vocabulary, docs/domains.md read against the domain"`
from the main folder, then `.worktrees/m7-docs`. Started (second overseer, 14:16) while M5 was still building: M5 edits no `roles/` file, so `make templates`' copies into the kiln do not collide; read the kiln's wiring and `demo-electrical.sh` from M5's branch (`git show task/m5-kiln:<path>`) or main once M5 lands, and land after M5 if you can.

Read: ELECTRICAL_STAGE.md §1.3 DoD 10, §3 (shapes; **three of its examples are wrong**, see
below), §4 (the CLI surface), §5 "M7"; the decisions S-153..S-168 and the M5/M6 entries (index
rows; open one only when you need it); `docs/domains.md`; the domain as built,
`src/napkin2factory/domains/electrical/` (read it: the docs describe what is there, not the
plan); `tests/fixtures/electrical/minimal/` and `tests/fixtures/scope/external-box/` (the
shapes to show); `examples/kiln/model/electrical/` and `examples/kiln/demo-electrical.sh`.

## Build
1. **`docs/electrical.md`** (new): the agent's reference for the wiring, as `docs/kit.md` or
   `docs/calckit.md` are for theirs. What it is and is not (wiring-level, no boards, advisory,
   never a licence: §0); the files (`model/electrical/supply.yaml`, `devices/`, `circuits/`,
   `conductors/`) with one complete small example taken from the minimal fixture (generic
   words); connection ends `device://<id>#<terminal>` (S-154); the `cable-entry` interface kind
   and its spec as built (`count: 1`, `diameter`, `passes`; no `pattern:`); an external box as
   a module with cable-entry ports; the outputs under `build/electrical/`; the checks and what
   fails versus warns (E6, quote `electrical-v0.yaml`'s rule ids and their plain meaning); the
   `circuit` verify kind and its four figures (`#props.load_current`, `supply_margin`,
   `conductor_margin`, `earth_paths`; values are quantities, never `param://`); the
   supply-headroom choice (E11, S-158); the scope states for the wiring (`in`, `later`,
   `external`); the manual helpers by their exact names (`owner/docs_helpers.py`); where the
   numbers come from (`calckit/data/` wiring tables, `make verify-list`).
2. **`docs/agent-guide.md`**: the command reference gains an electrical paragraph (no new verb:
   what `n2f doctor`, `n2f status`, `n2f build`, `n2f check --scope asm://…` show for the
   wiring, §4); "Show the example (the kiln)" mentions the wiring and `demo-electrical.sh`;
   "What napkin2factory does not do (yet)" is corrected: wiring-level electrical design is
   covered now; printed circuit boards, FEA and hosted services are not.
3. **`README.md`**: only its "does not do" line (around line 93), the owner's version of the
   same correction, plain words, no commands.
4. **The three roles** (`src/napkin2factory/templates/_common/roles/design.md`, `verifier.md`,
   `pm.md`): design — when a product has powered parts, the wiring files and the joint;
   verifier — the wiring checks, that every electrical safety requirement stays a person's
   sign-off, a licensed electrician decides every warn; pm — the scope question for the wiring
   in the owner's words, and the supply-headroom choice raised after the first build with
   wiring, never in the interview (F12, F13). Then `make templates` (it copies `_common` into
   every example, the kiln included) and commit the synced copies.
5. **`docs/vocabulary.md`**: owner words for supply, circuit, wiring, cable entry, earth,
   interlock (the table's existing shape: owner word, meaning, what it is in the files).
6. **`docs/domains.md`**: read it once against the domain as built (the wave-2 seams amended it:
   S-143, S-144, S-161–S-167); the electrical package is the third worked example (after the
   toy and the gadget domains): point to it where a section's example would be clearer with a
   real one; fix any sentence the domain proves wrong. No code change.
7. **ELECTRICAL_STAGE.md §3**: add one dated amendment line under its heading (never rewrite the
   plan's text): "Amended 2026-11-02 by the domain as built: a requirement's `value` is a
   quantity, never `param://`; a cable entry's spec has no `pattern:`; connection ends are
   `device://<id>#<terminal>` (S-154, S-158, S-167); `docs/electrical.md` has the shapes as
   built."
8. Check `tests/unit/test_agent_docs.py` (no model or vendor names, no per-client files) and
   `tests/unit/test_templates.py` pass; the guide's "Adapting to your client" needs nothing new
   unless you add a capability the wiring assumes (it assumes none).

## Owns
`docs/electrical.md`, `docs/agent-guide.md`, `docs/vocabulary.md`, `docs/domains.md`,
`README.md` (the one line), `ELECTRICAL_STAGE.md` (the one amendment line),
`src/napkin2factory/templates/_common/roles/{design,verifier,pm}.md` and the copies
`make templates` writes, `DECISIONS.md`, `BACKLOG.md`.
## Must not touch
`src/napkin2factory/` code (anything `.py`, `.yaml`, `.j2`), `examples/` except what
`make templates` writes, `tests/` except running them, `STATUS.md`.
## DoD
10 (the docs half; the version files and the handoff report are the overseer's). Run:
`make lint`, `tests/unit/test_agent_docs.py`, `tests/unit/test_templates.py`,
`tests/unit/test_journals.py`, then `make land`. Report the words you added to the vocabulary.
