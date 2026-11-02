# napkin2factory v0.5 — handoff report ("the seams")

> **Next agent:** v0.5 is closed on `main` with version 0.5.0 and the product pins `>=0.5,<0.6`
> (S-140); it is **not pushed and not tagged**: both are the maintainer's. The maintainer's visual
> judgment of the status output with a choice and the report's scope line is pending (§10). Then
> continue with v0.6, `ELECTRICAL_STAGE.md` (§9).

Plan: `FOUNDATION.md` (decisions F1–F17). Run by one overseer agent and one subagent per
milestone, each in its own task worktree, landing with `make land` (§8 of the plan). Every number
below is copied from the decision entry named beside it, or was measured for this report on
2026-11-02 on the macOS host; where neither holds, it says "not measured".

## 1. What v0.5 set out to do

A review on 2026-11-01 (S-111) measured what adding a step (a domain such as electrical or
analysis) cost, and found the seams missing (`FOUNDATION.md` §0.2, re-measured in M0, S-122):
1. **A new step edited 10 files, 7 of them in the core** (the M0 dry run: a no-op rule family,
   verify kind, check stage, report section and doc helper, each reached by a build).
2. **The example had become the schema:** the concept card had `alcove_*` and `chamber` keys,
   screening hardcoded a heated box, and 32 package files (outside the templates) named the
   words kiln, door, chamber or alcove; 13 named "kiln".
3. **`schema: 1` was written and never read**; every new field was a breaking change.
4. **Five files where parallel agents collide:** `concepts/promote.py` 1,647 lines,
   `core/loader.py` 1,060, `concepts/screening.py` 866, `rulepacks/concept_checks.py` 710,
   `geometry/build.py` 728.
5. `make check` took 10 min 14 s (S-122; v0.4's close-out figure was 10 min 8 s, S-119).

The scope in one sentence (the plan's): no owner-facing feature except scope and choices; every
hardcoded list a domain would edit becomes a registry behind one contract, proved with a toy
domain, a kiln that lives only in `examples/`, and a count of zero.

## 2. What shipped, per milestone

| milestone | what | entry |
|---|---|---|
| M0 | the before numbers (dry run, word counts, file sizes, check time) | S-122 |
| M1 | the domain contract (`core/domain.py`), 15 registries (`core/registry.py`), the mechanical code registered in place (`domains/mechanical/`), the toy domain and its contract test, `docs/domains.md` | S-123 |
| M2 | schema policy (`docs/schema-policy.md`), migrations (`core/model/migrate.py`, `n2f init .` snapshots first), calc reference cases (`calc-case` rows, lint L16); the checks rule hashes the calc kit | S-125, S-126 |
| M3 | the kiln out of the package: screens declare their fields, the heated-box screens are the kiln's own `model/screens/`, product rule packs, `site.width`, neutral style roles, the example-identifier guard | S-128 |
| M4 | scope as data (`scope:` in `n2f.yaml`: in / done elsewhere / later), `build: external` stubs, the reserved `model/loads/` family; scope a recorded read; stubs "supplied, not built here" in the build plan | S-124, S-127 |
| gaps | eight backlog rows waves 1–2 left (targets and prose URIs from the registries, density in part keys, no example ids, screen fields and domain style roles in the contract, …) | S-129 |
| M5 | choices: the `choice` status, `build/checks/choices.json`, "Waiting on you" in `n2f status`, `n2f decide` writing a `DEC-`, reopened on evidence; the kiln's bolts choice | S-130 |
| M5b | an open choice holds the release; the report's "waiting on you"; decided-not-applied caveat; the generic concept summary | S-133, S-135 |
| M6 | the splits (`validate_refs` beside each schema, `concepts/promote/` one seeder per family, `build_part`/`build_asm`) and `make check-fast`, the land gate | S-131 |
| M7 | docs, `n2f doctor` lists the domains, the two simulation protocols; the two simulations; gates E and F and their fixes; 0.5.0 | S-132, S-134, S-136, S-137–S-140 |

## 3. Definition of done, item by item (`FOUNDATION.md` §1.3)

1. **Nothing moved.** Goldens unchanged since v0.4 (gate E: `git diff --stat a9bea31 HEAD --
   tests/golden/goldens` empty; one regeneration-log line, the promote golden's `door → opening`,
   `stand → support` style keys, F9's rename); `tests/validate_outputs.py` passes on all three
   products; the kiln board golden unchanged. `make check` green on `main` (§4). `make
   check-full` from a clean clone of 29951e2 on the host: green, 29 min 14 s (lint, types, 1,088 tests, 141 goldens, the examples, the kiln, the demos side by side, timing). Not done: `validate_outputs.py`'s expected set was not extended to
   the new check files (B-0108).
2. **A step is a folder: the count is 0.** `tests/unit/test_domain_contract.py` proves every
   registry sees the toy domain. The M7 simulation: a fresh agent given only `docs/domains.md`
   added a second domain (`gadget`, eleven registrations, 15 tests) in 224 s; files changed under
   `src/napkin2factory/core/`: **0**; under `src/`: 0; core files opened: none (S-134,
   `tests/e2e/domain-transcripts/gadget-2026-11-02.md`). The seven places the contract fell short
   were fixed in `docs/domains.md` (S-135).
3. **The kiln lives in `examples/`.** `tests/unit/test_no_example_identifiers.py` green with an
   empty allow-list; the `AGENTS.md` non-negotiable and the review template's question; the five
   heated-box screens in `examples/kiln/model/screens/heated_enclosure.py`; the kiln's board and
   screening unchanged (S-128). After gate F, a shelf's napkin stage says "the space" and no door
   unless the card names one (S-137).
4. **Schema policy.** `docs/schema-policy.md`, `core/model/migrate.py`, `n2f init .` snapshots
   then migrates and says so in owner words, `tests/fixtures/schema/v1/`, a throwaway 1→2→3
   migration round-trips; a newer format stops plainly (S-125; gate E §8 OK).
5. **Scope.** The kiln declares `electrical: later` (DEC-024); `n2f status`, the report overview,
   `release.json` and the package cover say it in the same words; `external` without a stub fails
   naming the file; `later` excludes requirements with a visible note and never a safety one
   (S-124, S-127; gate E §5 OK).
6. **Choices.** The kiln's real choice (the M6 bolts meeting inside the 25 mm spacers: shorter
   bolts, or one through-bolt with a nut; the plan's "tapped blind deeper" option was found not
   to be a valid design, S-130); listed under "Waiting on you"; `n2f decide` writes a `DEC-`; the
   row reads OK with the decision and reopens when its evidence changes; a decided pick not yet
   in the model holds the release (S-139). The simulation: not raised in the interview, raised
   when the owner asked about the guards, decided by the owner (S-136,
   `tests/e2e/intake-transcripts/choice-kiln-2026-11-02.md`).
7. **Verify methods are discoverable.** `n2f doctor` lists the installed domains with their verify
   kinds, check stages and screens (S-132); an unknown verify kind is a validation error listing
   the installed ones (S-123; its wording, B-0112).
8. **Splits.** Before → after (lines): `concepts/promote.py` 1,647 → `concepts/promote/` (12
   modules, largest `verb.py` 365); `core/loader.py` 1,060 → 386; `concepts/screening.py` 866 →
   167; `rulepacks/concept_checks.py` 710 → 451; `geometry/build.py` 728 → 57 (`build_part.py`
   344, `build_asm.py` 416). None over 500 (measured 2026-11-02).
9. **Check time.** `make check` on `main` at 29951e2 (the close-out, idle host): **10 min 4 s**, green, 1,088 passed and 4 skipped, then 141 goldens — 4 s under v0.4's 10 min 8 s (S-119), with 212 more tests. The margin is thin: the plan's fallback (§7, move the slowest end-to-end files behind `-m full`) was not needed and was not used. `make check-fast`: 2 min 1 s (S-131), 2 min 9 s (gate E); the
   default land gate.
10. **Review gates.** Gate E and gate F closed, reports in `docs/reviews/v0.5-gate-e.md` and
    `v0.5-gate-f.md` (§5). The maintainer's visual judgment pending (§10).
11. **Docs.** `docs/domains.md`, `docs/schema-policy.md`, the agent guide, the four roles,
    `docs/vocabulary.md` (domain, scope, in / done elsewhere / later, choice, waiting on you),
    this report; version files and pins at 0.5.0 / `>=0.5,<0.6` (S-132, S-140).
12. **Calcs prove themselves.** Cases: `thermal_enclosure` 11 (1 external: Incropera 6th ed.
    Example 3.1, `[verify]`), `power` 10 (2 external: Kanthal "Design of wire elements", p. 51),
    `mass_cost` 5 (1 external: EN 1993-1-1 §3.2.6 steel density, `[verify]`); every one of the
    23 kit functions covered; the kiln 21 calcs, 21 cases; `n2f check` on the kiln shows 23
    `calc-case` rows, all pass; a wrong case fails naming calc, expected and actual; a calc with
    no case warns (S-125). The Kanthal cases are not marked `verify` (B-0111).

## 4. Measured numbers

| | before (v0.4 / M0) | after (v0.5) |
|---|---|---|
| files a new step edits | 10, 7 in `core/` (S-122) | 0 in `core/` (S-123 toy test; S-134 fresh agent) |
| package files naming kiln / door / chamber / alcove, outside templates and vendor | 32 (kiln 13) (S-122) | 35 (kiln 0, chamber 1, alcove 0, door 34) — door is a generic word F9 allows (a swing term, the roles' prose); every example identifier is gone (the guard) |
| largest of the five collision files | 1,647 lines | 451 lines |
| `make check` on `main` | 10 min 14 s, 876 passed (S-122) | 10 min 4 s, 1,088 passed (29951e2, idle host) |
| `make check-fast` | did not exist | 2 min 1 s (S-131) |
| tests | 876 passed, 5 skipped (S-122) | 1,088 passed, 4 skipped; 141 goldens |

`make check` on `main` at each wave boundary (the overseer's runs): 9 min 7 s at 29e7d4b (after
M1, 908 passed); 9 min 14 s at 895df01 (after wave 2, 998 passed); 9 min 10 s at 5e1a100 (after
wave 3, 1,029 passed, idle host). Wave times: M0 14 min; M1 65 min; wave 2 79 min; wave 3 73
min; M7 about 4 h 30 min including the simulations, the gates and three fix tasks (STATUS.md).

## 5. What the gates found and how it was fixed

**Gate E (architecture and honesty), at baecb90: NOT READY, four blockers.** The seams held: the
core imports no domain, goldens unchanged, scope never hides safety, an open choice stops the
release, `n2f check` never decides.
- B1 `n2f impact` missed every rule that reads an object whole when one of its fields is edited
  (a kiln interface depth: impact said `validate`, the build reran 16 rules; older than v0.5 for
  interfaces) — fixed, S-138.
- B2 the contract gave a domain's rule no recording accessor, and the toy example went stale on
  a field edit — fixed with `ctx.proxy()`/`ctx.log` for rules, stages and report data (the
  section `data(sctx)` signature changed), S-138.
- B3 a decided pick not yet in the model could be released (the package bought the colliding
  bolts) — fixed, S-139.
- B4 the core's open-set tables were hashed into no rule — fixed, S-138.
- Concerns: C7, C8, C13, C14 fixed (S-137, S-138); C1–C6, C9–C12 open, B-0105–B-0114.

**Gate F (UX, owner persona), at baecb90: NOT READY, four blockers.** The scope block, "waiting on
you" with costs and the plain refusals read well.
- 1 the decided-unapplied release (= E B3), S-139. 2 the package's report was the pre-release
  draft, S-139. 3 a shelf's board and promoted requirement spoke of an open door and an alcove,
  S-137. 4 a failing product screen printed an 87-line traceback, S-137.
- Concerns 5, 11–14, 17 fixed (S-137, S-139); 6–10, 15, 16, 18, 20, 21 open, B-0115–B-0124
  (19 joins B-0112).

## 6. Departures from the plan, decided on the way

- **The kiln's choice:** the plan named "a standoff tapped right through" as DEC-022's second
  option; M5 found both bolt ends still meet in a 25 mm spacer, so the options are shorter bolts
  or one through-bolt with a nut (S-130).
- **Extra tasks:** wave 2 and 3 each gained a follow-up task for the gaps the milestones left in
  files they did not own (S-126, S-127, S-129, S-133, S-135), rather than widening a milestone's
  ownership mid-wave.
- **`Product`, `Paths`, `Doc` moved to `core/product.py`** so the loader fits under 400 lines
  (S-131) [revisit].
- **The choice simulation's criterion e** assumed an unapplied pick; the PM applied it (allowed
  before a release), so the criterion was amended to accept both forms (S-136) [revisit].
- **The report section contract** changed to `data(sctx)` at gate E (S-138); the contract is
  unreleased, so no domain outside the repo is affected.

## 7. `[revisit]` decisions and `[verify]` numbers added in v0.5

[revisit] (in the entries): S-123 (checks, report and site run after every producing family; a
later domain's section at the end of its group); S-124 (the loader guards for stubs; the `stub:`
field; which requirements belong to a domain); S-125 (L16's number); S-127/S-133 (the scope
always read); S-128 (rule-row order by id); S-129 (B-0081, B-0087 then); S-131 (`core/product.py`;
the kiln's promotion hooks); S-132 (the roles synced into the kiln); S-133 (decided-not-applied as
a caveat — superseded for the release by S-139); S-136 (criterion e; B-0102); S-137 (the pack
wrapper's import); S-139 (the ECR-002 patch line the demo updates).
[verify]: Incropera Example 3.1 and the EN 1993-1-1 density (calc cases, S-125); the ISO bolt and
nut sizes behind the kiln's choice (S-130); the kiln's new M6 x 12 bolt's catalogue line (none
chosen; the demo borrows the M6 x 16's price). `make verify-list` prints them.

## 8. Open after v0.5

- Gate concerns B-0105–B-0124 (§5).
- v0.5's own rows: B-0088 (remove the `alcove_*`, `door`, `stand` aliases at the next schema
  bump), B-0099 (a domain cannot put files in the release package — v0.6's wiring diagrams need
  it), B-0100 (no calc-pack field on `Domain`), B-0101 (the bolts choice reopens on any edit of
  its joints), B-0102 (whether a decided pick goes through a change request before release),
  B-0103 (the kiln still writes `door`/`stand` roles: six L17 warnings), B-0104 (impact cannot
  be asked about a product rule-pack edit).
- **No Linux nightly has run on a commit after S-121** (the platform-stable evidence keys): the
  push run of `make check` on 4c8d66c was green on ubuntu and macOS, and `main` was not pushed
  during v0.5, so the proof the plan's §5 asks for comes with the next push.

## 9. What v0.6 inherits

`ELECTRICAL_STAGE.md` (E1–E12) builds the electrical domain through this contract; the count of
core edits is its headline. It starts from `docs/domains.md`, the toy and gadget examples
(`tests/fixtures/domains/toy/`; the gadget lives in its transcript), the recording accessor
(S-138), scope (the kiln's `electrical: later` becomes `in`), the `model/loads/` slot, and
B-0099/B-0100 above. `docs/reviews/v0.6-independent-trial.md` briefs an outside model afterwards.

## 10. Waiting on the maintainer

1. **Visual judgment (S-078):** the status output with the kiln's open choice and the report's
   scope line — `docs/reviews/v0.5-status-choice.png` and `docs/reviews/v0.5-report-scope.png`
   (sent 2026-11-02). Question: would a hobby potter follow the choice as written, or should its
   title drop the catalogue part name? Recorded as "judged by the agent; the maintainer's judgment
   pending" in "Review gate F — outcome".
2. **Push** `main` (it is 0.5.0 at the commit that adds this report, unpushed), then the first Linux nightly after
   S-121 is the evidence-key proof (§8).
3. **Tag** `v0.5.0` on the green CI commit (S-072); `publish.yml` checks the three version files.
4. **[revisit] calls** in §7, notably B-0102 (a decided pick and change requests before release)
   and the section-data contract change (S-138).
5. `make check-full` took 29 min 14 s from a clean clone (v0.4: about 21 min, S-079); nothing in the plan budgets it, but it grew by about 8 min (the demos now decide and apply the kiln's choice; more tests). Not investigated further.

## 11. Where things are

- Plan: `FOUNDATION.md`; decisions: `DECISIONS.md` S-122–S-140, "Review gate E — outcome",
  "Review gate F — outcome"; open work: `BACKLOG.md`.
- The contract: `docs/domains.md`; `src/napkin2factory/core/domain.py`, `core/registry.py`,
  `domains/`; the toy: `tests/fixtures/domains/toy/`, `tests/unit/test_domain_contract.py`.
- Simulations: `tests/e2e/domain-transcripts/`, `tests/e2e/intake-transcripts/choice-kiln*.md`.
- Gate reports and the visual exits: `docs/reviews/v0.5-*`.
