# napkin2factory v0.6 — handoff report ("the wiring")

**The count (`../stages/v0.6-electrical-stage.md` E10, DoD 1): 0 files** changed under `src/napkin2factory/core/`,
`src/napkin2factory/report/builder.py`, `src/napkin2factory/docs/engine.py`, or
`src/napkin2factory/cli/check.py` across every `domains/electrical/` milestone commit (`M0`–`M7`,
including the gate-fix commits `0a8db00` S-178 and `7521311` S-179). Every core edit in
`7d90121..HEAD` was a v0.5 contract seam defect opened and landed in its own task under E10
(`S-142`–`S-144`, `S-148`–`S-152`, `S-160`–`S-167`, `S-180`; 7 seam commits, 16 decision entries,
listed apart in §1 and §2).

> **Next agent:** v0.6 is closed on `main` with version 0.6.0 and the product pins `>=0.6,<0.7`
> (S-181); it is **not pushed and not tagged**: both are the maintainer's. The maintainer's visual
> judgment of the wiring diagrams and the report's Wiring section (`docs/reviews/v0.6-*.png`, plus
> v0.5's `docs/reviews/v0.5-*.png`) is pending (§10). The outside-model trial brief is
> `docs/reviews/v0.6-independent-trial.md` (§9).

Plan: `../stages/v0.6-electrical-stage.md` (decisions E1–E12, reconciled with the v0.5 contract in S-141). Run by
overseer agents and one subagent per task, each in its own task worktree, landing with `make land`
(§8 of the plan). Every number below is copied from the decision entry named beside it, or was
measured on the macOS host; where neither holds, it says "not measured".

## 1. What v0.6 set out to do, and the E10 count

v0.6 had two goals (`../stages/v0.6-electrical-stage.md` §0):
1. **Prove the v0.5 domain contract (`../stages/v0.5-foundation.md`)** with a real domain (`electrical`, under
   `src/napkin2factory/domains/electrical/`) that nobody built the seams for in advance, counting
   every core edit required along the way (E10).
2. **Complete the kiln's manufacturer package**: wire its 18 devices across power, control, sensing
   and earth circuits, cut its three gland holes through `cable-entry` interfaces, generate its
   wiring diagrams, connection tables, cable schedule, terminal labels and cable-to-buy list into
   the package and installation manual, and run the `later` → `in` change-request story end to end.

### Verification of the count (`git log --stat 7d90121..HEAD`)
- **Domain milestone commits (`M0`–`M7`, including `70a2fa9` S-174, `0a8db00` S-178, and `7521311`
  S-179): 0 files** touched under `src/napkin2factory/core/`,
  `src/napkin2factory/report/builder.py`, `src/napkin2factory/docs/engine.py`, or
  `src/napkin2factory/cli/check.py`.
- **v0.5 contract seam tasks (E10, listed apart from the domain commits):**
  1. *Known before M1 and opened in M0:* `d50d0ab` (`S-142`, closes B-0099: `Domain.release_files`
     so a domain's outputs under `build/<output_dir>` ship in the release package); `eada869`
     (`S-148`–`S-152`, closes B-0115–B-0119: gate F's scope words, the `later` check status, a
     domain's own owner word, `n2f status` with a missing stand-in, and "supplied, not built here"
     for stand-ins).
  2. *Found by the overseer reading the core before M1:* `9f6860b` (`S-143`, closes B-0125:
     `RuleFamily.before` so `elec` runs before `doc` and manuals read the current build's outputs);
     `8229d0d` (`S-144`, closes B-0126: `check_interface`, the report and fastener checks treat an
     interface by its spec's type `BoltPatternSpec` rather than the kind name).
  3. *Found by the domain tasks during wave 2 (the E10 stop-and-open path):* `f4a25ec`
     (`S-160`–`S-164`, closes B-0142–B-0146, B-0129: a card field's `param` from any declaration,
     `concepts/screens/base.py` import order, `check_rows_state` wording every status it counts,
     public `scope_entry`, `HelperContext.build_dir`); `d7dbf2f` (`S-165`–`S-167`, closes B-0135,
     B-0136, B-0139, B-0140, B-0147: `set://<family>` membership keys recorded on `product.families`
     access, interface field reads valued by field, `rule:<x>` keys and `#props.<figure>` selectors
     in the contract, `ctx.build_dir` passed by the docs rule).
  4. *Found by gates G and H:* `df35938` (`S-180`, closes B-0184, B-0160: dry-run patch impact in
     `compute_impact`, `Domain.disclaimer` in the package `README.txt` and report `#disclaimer`,
     the `later` → `in` cover transition line, and `"an agent may decide it"` restricted to
     delegated areas).
  - *Decided not to open in v0.6:* the parts-list consumable seam (E5, `S-145`, B-0128: conductors
    stay in the domain's own schedule and `cables.csv`).

## 2. What shipped, per milestone

| milestone | what | entry |
|---|---|---|
| Plan & M0 | v0.6 plan reconciled with v0.5 (`../stages/v0.6-electrical-stage.md`); kiln electrical baseline survey (`docs/v06-baseline.md`); `calckit/data/{conductors,earthing,wire_colours}.yaml` and `calckit.wiring`; E5 decided (no parts-list seam in v0.6) | S-141, S-145, S-146, S-147 |
| M0 seams | `Domain.release_files` (B-0099); `RuleFamily.before` (B-0125); interfaces checked by spec type `BoltPatternSpec` (B-0126); scope words table, `later` check status, domain owner word, missing stand-in in status, stand-in joint words (B-0115–B-0119) | S-142, S-143, S-144, S-148–S-152 |
| M1 | `domains/electrical/` installed: `supply`, `device`, `circuit` and product `conductor` model families; connection-end parser; `cable-entry` interface kind (one-hole `BoltPatternSpec` + `passes:`); Design gate row "Wiring" and Verify gate row "Wiring checks"; minimal fixture (`tests/fixtures/electrical/minimal/`) | S-153, S-154, S-155 |
| M2 | `elec:<circuit>` and `elec-schedule` rules: per-circuit `connections.json`, ladder `diagram.svg` and `.kicad_sch` text schematic; `schedule.csv`, `labels.csv`, `cables.csv` | S-156, S-157 |
| M3 | `electrical` check stage and `electrical-v0.yaml` rules (load vs supply, conductor ampacity, earth paths over conductive custom parts, circuit protection, interlock series path, limit independence, contact-on-coil rating, ELV vs mains entry sharing); `circuit` verify kind (`#props.load_current`, `supply_margin`, `conductor_margin`, `earth_paths`); `supply-headroom` choice; six fault fixtures | S-158 |
| Wave-2 seams | Card field `param` merge; screen import order; gate row status words; public `scope_entry`; `HelperContext.build_dir`; `set://<family>` membership keys; interface field-read valuation; contract docs (`rule:<x>`, `#props.<figure>`) | S-160–S-167 |
| M4 & M4b | "Wiring" report section (`owner/report.py`, `wiring.html.j2`, page-safe SVG scoping `owner/svg.py`), manual helpers (`circuit`, `cable_schedule`, `terminal_labels`, `cables_to_buy`), vocabulary, module context (`n2f context`); generic `circuit-available` supply screen moved from the kiln's pack to the domain (E8) | S-159, S-168 |
| M6 | `tests/fixtures/scope/external-box/` (external control box with two `cable-entry` ports); diff page section delta (`"<label>: added"` / `"removed"`); owner-session script (`tests/e2e/intake-transcripts/wiring-session.md`) | S-169, S-170 |
| M5 & follow-ups | Cited EU 20 A and 32 A dedicated circuit classes and `Supply.dedicated` (`S-171`); the kiln wired (18 devices, power/control/sensing/earth circuits, three cable entries, five bought parts, `scope.electrical: in` DEC-025, headroom decided `dedicated` DEC-026, generated manual section, `demo-electrical.sh` + `ECR-003`); kiln diagram layout readability (`S-174`) | S-171, S-172, S-174 |
| M7 & close-out | `docs/electrical.md`, agent guide, roles (`pm.md`, `design.md`, `verifier.md`), vocabulary, `docs/domains.md` (`S-173`); portable `mktemp` for Linux nightly (`S-175`); DoD 7 owner simulation passed (`S-176`); publish tests bare-repo `--git-dir` (`S-177`); gates G and H and their blocker fixes (`S-178`, `S-179`, `S-180`, Gate G, Gate H); version 0.6.0, pins `>=0.6,<0.7`, this report (`S-181`) | S-173, S-175–S-180, Gate G, Gate H, S-181 |

## 3. Definition of done, item by item (`../stages/v0.6-electrical-stage.md` §1.3)

1. **The count.** Verified in §1 above: **0 files** under `src/napkin2factory/core/`,
   `report/builder.py`, `docs/engine.py`, or `cli/check.py` in the electrical domain's milestone
   commits (`M0`–`M7`, including `S-174`, `S-178`, `S-179`). All core edits are v0.5 contract seam
   tasks listed apart (`S-142`–`S-144`, `S-148`–`S-152`, `S-160`–`S-167`, `S-180`).
2. **The kiln is wired.** `examples/kiln/model/electrical/` defines the supply, 18 devices, 1
   product conductor (`type-k-extension`), and 4 circuits (`power`, `control`, `sensing`, `earth`;
   earth separated into its own circuit so the power diagram stays readable, S-172). Building the
   kiln produces `build/electrical/{power,control,sensing,earth}/diagram.svg`, `schedule.csv` (30
   wires), `labels.csv` (60 labels), `cables.csv` (4 cable lines) and `README.txt` (S-179).
   Conductors stay in the domain's schedule per M0's E5 decision (`S-145`). The installation
   manual's wiring section is generated from the doc helpers and the sentence "This package has no
   wiring diagram" is gone. The report has a Wiring section; report size is **3,916,749 bytes** (≈
   3.92 MB, well under the 20 MB cap; S-174).
3. **The checks catch what they claim.** Eight fault fixtures under `tests/fixtures/electrical/`:
   `over-supply` (fail), `thin-conductor` (fail), `unearthed` (fail), `unprotected` (fail),
   `interlock` (warn), `shared-entry` (warn: ELV beside mains, S-154), plus Gate G's two new
   fixtures `thin-under-breaker` (fail: conductor ampacity below its protective device's rating,
   S-178) and `class-two-metal` (warn: Class II devices inside a conductive custom part with mains
   wiring, S-178). Each names the part, the circuit and what to do (`tests/unit/test_electrical_checks.py`).
4. **The scope story runs unattended.** `examples/kiln/demo-electrical.sh` runs in a temp copy:
   releases `v1.0.0` with `electrical: later` (cover says "Not included in this package: Wiring") →
   `ECR-003` adds the wiring via a patch → `n2f ecr impact ECR-003` dry-runs the patch and lists the
   scope transition, parts and circuits added (S-180) → approve → apply → build → `supply-headroom`
   choice raised and decided (`n2f decide`) → pick applied → check → close → releases `v1.1.0` with
   `electrical: in` (cover says "Wiring: included in this Revision; left for later in v1.0.0",
   S-180) → diff page shows `"Wiring: added"` (S-169). Runs in `make check-full`; standalone wall
   time **492 s** (8 min 12 s, S-172).
5. **External works.** `tests/fixtures/scope/external-box/` validates: its control box is
   `build: external` with two `cable-entry` ports; the power and control diagrams draw the dashed
   boundary (`"to the external control box, supplied, not built here: L, N, PE"` and `": C1, C2"`,
   S-170, S-174) and nothing inside it. Removing a port fails validation naming the stub file, the
   port and the circuit (`tests/unit/test_scope_external.py`).
6. **The supply screen moved.** `circuit-available` ships in
   `src/napkin2factory/domains/electrical/owner/screens.py` (phase `check`); `examples/kiln/model/screens/heated_enclosure.py`
   no longer carries a copy; `tests/golden/goldens/kiln-board.json` is unchanged (S-168).
7. **The choice is raised at the right time.** A fresh PM subagent ran the scripted session
   (`tests/e2e/intake-transcripts/wiring-session.md`) across six owner turns: the supply-headroom
   choice was not asked in the interview, was raised after the first build with wiring in owner
   words with both options' consequences, and was recorded with `n2f decide … --by "Dana Whitfield"`
   only after the owner chose (S-176; transcript at
   `tests/e2e/intake-transcripts/wiring-session-2026-11-03.md`).
8. **Every number has a source.** `calckit/data/conductors.yaml` (25 rows), `earthing.yaml` (4
   rows), `wire_colours.yaml` (15 rows) and the two new EU dedicated rows in `circuits.yaml` cite
   their standards with `verify: true` (S-146, S-171) and appear in `make verify-list` (86
   data-table rows, 17 product decisions, 67 tagged lines in `DECISIONS.md`). Element current reads
   from `calckit.power.element_current`.
9. **Review gates.** Gate G (electrician read-through + engineering, `docs/reviews/v0.6-gate-g.md`;
   Part 1 kept at `examples/kiln/reports/electrician-readthrough.md`) and Gate H (UX in the owner
   persona, `docs/reviews/v0.6-gate-h.md`) were run by fresh-context subagents at `dbe46e0`, and
   every blocker was fixed in `S-178`, `S-179` and `S-180` (§5). Visual exits are captured in
   `docs/reviews/v0.6-*.png`; the maintainer's visual judgment is pending (§10).
10. **Docs, report and pins.** `docs/electrical.md`, `docs/agent-guide.md`, the three roles
    (`roles/{pm,design,verifier}.md`, synced with `make templates`), `docs/vocabulary.md` (10 wiring
    terms), `docs/domains.md` updated with the electrical domain as its third example (S-173);
    `docs/handoffs/HANDOFF-REPORT-v0.6.md` with the count first; version `0.6.0` and product pins `>=0.6,<0.7`
    (S-181).

## 4. Measured numbers

| measure | before (v0.5 close-out, S-140 / S-147) | after (v0.6 close-out) |
|---|---|---|
| core files edited by domain commits | 0 (v0.5 toy & gadget, S-123, S-134) | **0** across all M0–M7 domain commits; 7 E10 seam commits listed apart (§1) |
| `make check` on `main` (idle host) | 10 min 4 s, 1,088 passed, 4 skipped; 141 goldens (S-140) | **8 min 19 s** at `6135323` (1,323 passed, 4 skipped; 141 goldens), and close-out gate run in `STATUS.md` |
| `make check-fast` (land gate) | 2 min 1 s (S-131) | 2 min 8 s – 3 min 58 s across wave 3 and M7 landings |
| kiln cold build time | 69.1 s (S-147) | **60.0 s** with 4 circuits and 3 cable entries (S-172) |
| kiln report size (`build/report/index.html`) | 3,796,445 bytes (S-147) | **3,916,749 bytes** (≈ 3.92 MB, ≤ 20 MB cap; S-174) |
| minimal electrical fixture report size | did not exist | 1,722,207 bytes with renders and Wiring section (S-159) |
| `demo-electrical.sh` standalone | did not exist | **492 s** (8 min 12 s, S-172) |

Wave wall-clock times on the host (2026-11-02 – 2026-11-03): M0 + 4 seam tasks 55 min; M1 30 min;
wave 2 (M2, M3, M4, 2 seam tasks, M4b) 76 min; wave 3 (M6, headroom follow-up, M5) 76 min; M7
(M7a docs, diagram follow-up, Linux nightly fix, DoD 7 simulation, gates G and H, and 3 blocker-fix
tasks).

## 5. What the gates found and how it was fixed

**Gate G (licensed-electrician read-through + engineering), at `dbe46e0` (`docs/reviews/v0.6-gate-g.md`,
Part 1 at `examples/kiln/reports/electrician-readthrough.md`): NOT READY, 3 blockers.** Topology,
hand-recomputed currents and margins, cited tables, generic vocabulary and recording accessors all
passed; an electrician could wire the kiln from the package with about a dozen calls to the maker.
- **Blocker 1:** a conductor rated below its protective device (`0.75 mm²` at 8.5 A under a 32 A
  breaker) passed because conductors were checked only against the load, never `I_n <= I_z`, and an
  unrated protective device (the kiln's control fuse) passed silently — fixed in **S-178**
  (`conductor-protection` rule and row per power/control circuit; `fail` when below rating, `warn`
  when protective rating is unknown; fixture `thin-under-breaker`).
- **Blocker 2:** the Class II shortcut (`earth-path@product`) passed a mild-steel box carrying
  single-insulated mains conductors when its devices were declared Class II — fixed in **S-178**
  (shortcut passes only when no conductive custom part exists or no circuit exceeds ELV; otherwise
  warns naming the mains circuits; fixture `class-two-metal`).
- **Blocker 3:** "not reviewed by a licensed electrician" was only in the report's Wiring banner,
  not in the package `README.txt`, the manual helpers or the four diagram SVGs — fixed in **S-179**
  (every `diagram.svg` gets a `<g id="footer">` band with product, circuit, Revision/draft and the
  licensed-electrician disclaimer; `build/electrical/README.txt` ships in the package; manual
  `circuit(id).table` prepends the disclaimer once per page) and **S-180** (`Domain.disclaimer`
  appends each in-scope domain's disclaimer to the package `README.txt` and report `#disclaimer`).
- **Concerns:** 1–14 recorded in `BACKLOG.md` as B-0161–B-0173 (6 is B-0137; 15 is closed by the
  0.6.0 version bump in S-181).

**Gate H (UX in the owner persona), at `dbe46e0` (`docs/reviews/v0.6-gate-h.md`): NOT READY, 2
blockers.** The `later` status/report/cover wording, `"Wiring: added"` on the diff page, the
licensed-electrician warnings, zero wiring words on the bracket, and plain validation errors all
read well.
- **Blocker B1:** `n2f ecr impact ECR-003` on the patch-based design change request that adds the
  wiring printed `"# Impact of 0 change(s)"` and `"nothing is rebuilt"` — fixed in **S-180**
  (`compute_impact` dry-runs a `kind: design` patch in a scratch copy, maps its diff to touched
  keys and `manifest://scope`, and reports added/changed/removed files and entities, scope
  transitions in owner words, and rebuilt artifacts; closes B-0184).
- **Blocker B2:** the wiring diagrams in the release package carried no disclaimer, product name or
  Revision (= Gate G blocker 3) — fixed in **S-179**.
- **Concerns:** C3 and C4 (duplicate purpose word and `"protected by not given"` in report circuit
  headings, and `"Lengths are given"` vs `"estimates"`, B-0157) fixed in **S-179**; C7 (`later` →
  `in` cover line and electrician disclaimer in `README.txt`) and B-0160 (`"an agent may decide it"`
  shown to an owner who asked to be asked) fixed in **S-180**; C1, C2, C5, C6, C8–C11 recorded in
  `BACKLOG.md` as B-0174–B-0181.

## 6. Departures from the plan, decided on the way

- **Plan §3 examples amended (`../stages/v0.6-electrical-stage.md` §3):** a requirement's `value` is a quantity
  (`0 A` against `#props.supply_margin`), never `param://`; a `cable-entry` spec is a one-hole
  `BoltPatternSpec` (`count: 1`, `diameter`, `passes`, no `pattern: circle`); connection ends name
  `device://<id>#<terminal>` so multiple instances of one part have distinct devices (S-154, S-158,
  S-167).
- **Four kiln circuits instead of three:** protective-earth bonding leads were split out of `power`
  into their own `earth` circuit so the power diagram stays clean (S-172).
- **The schedule rule id is `elec-schedule`:** named to match `rule:elec-schedule`, which the core
  values as the output hash of rule `<x>` (S-156, S-167).
- **Owner simulation fixture:** the M6/M7 owner-session simulation (`wiring-session.md`) runs on a
  dedicated warming-box fixture (`tests/fixtures/scope/external-box`) rather than the full kiln so
  each build in the interactive session takes ~5 s instead of ~60 s (S-170, S-176).

## 7. `[revisit]` decisions and `[verify]` numbers added in v0.6

- **`[revisit]` (in `DECISIONS.md`):** S-141/E2 (devices as a separate family vs a schema-extension
  seam on `Part`); S-144 (domain interface kinds with a mating-face spec, B-0127); S-145/E5 (no
  parts-list consumable seam in v0.6, B-0128); S-146 (EU silicone ampacity floor at PVC values,
  B-0162); S-148 (kiln REQ-007, -016, -021 left untagged); S-153 (extra fields on `Device`,
  `Circuit`, `Supply`); S-156 (`elec-schedule` rule id); S-157/S-174 (diagram column layout and
  wire-label threshold); S-158 (how a limit device's controller is identified; AC-3 accepted for
  inductive loads); S-165 (no removal edit form in `n2f impact`, B-0148); S-168 (supply screen
  fields `hint=False`); S-169 (diff section block placement before 3D, B-0150); S-172 (earth devices
  naming the metal part rather than `part://earth-stud`, B-0153); S-173 (PM role rule that an owner
  who asked to be asked decides every choice in that area); S-178 (`conductor-protection` leaves out
  secondary-fed leads, zero-source loops and earth conductors, B-0182).
- **`[verify]` (`make verify-list`):** 25 conductor ampacity rows in `calckit/data/conductors.yaml`
  (IEC 60204-1 Table 6 col B2 / IEC 60364-5-52; NFPA 79 / NEC 310.16 / 402.5 / 400.5), 4 earthing
  rows in `earthing.yaml` (IEC 60364-1), 15 colour rows in `wire_colours.yaml` (IEC 60445 / NFPA 79 /
  IEC 60584-3), 2 EU dedicated circuit rows in `circuits.yaml` (IEC 60898-1 / IEC 60309-2, S-171),
  ELV bands and switching categories in `electrical-v0.yaml` and `conduction.yaml` (S-154, S-158,
  S-178; B-0141/B-0161 tracks adding domain YAML tables to `make verify-list`), and the kiln's
  sourced terminal markings, wire lengths and Type K extension row (`docs/v06-baseline.md`, S-172).

## 8. Open after v0.6

- Gate G concerns B-0161–B-0173 and S-178 follow-ups B-0182, B-0183 (§5).
- Gate H concerns B-0174–B-0181 (§5).
- Earlier v0.6 backlog rows: B-0127 (mating-face spec subclassing), B-0128 (`bom_lines` hook),
  B-0130 (`Domain.code` file hashing), B-0131 (keyword field aliases `#class`/`#from`), B-0132
  (package folder collision), B-0133 (impact on scope note), B-0134 (`later` rows in report header
  filter), B-0137 (per-terminal conductor count limit), B-0138 (`conducts:` column in
  `materials.yaml`), B-0141 (`verify-list` scanning domain tables), B-0148 (`--remove` in impact),
  B-0150 (diff section block in template and CLI), B-0153 (`bonds:` on earth devices), B-0155
  (`docs/calckit.md` row count), B-0156 (domain import-order guard in `registry.ensure`), B-0158
  (kiln control/earth diagram crowding).
- **Linux nightly:** the two red runs on `7d90121` (2026-11-02, 2026-11-03) failed only on BSD
  `mktemp -d -t` in `demo-napkin.sh` (all 1,092 + 141 tests and the kiln sign-off evidence keys
  passed on Linux, proving S-121 / B-0073). Fixed in S-175 and verified in a Debian container
  (GNU coreutils 9.7); the next scheduled run after `main` is pushed will confirm `check-full` end
  to end on GitHub's runner.

## 9. What follows v0.6

`docs/reviews/v0.6-independent-trial.md` briefs an outside model to build a third domain cold from
`docs/domains.md`, with `domains/mechanical/` and `domains/electrical/` as the two shipped proofs
of the contract.

## 10. Waiting on the maintainer

1. **Visual judgment (S-078):**
   - v0.6 wiring diagrams and report section: `docs/reviews/v0.6-diagram-power.png`,
     `docs/reviews/v0.6-diagram-external.png`, `docs/reviews/v0.6-kiln-diagram-{power,control,earth,sensing}.png`,
     and `docs/reviews/v0.6-report-wiring.png`. Question: does the ladder layout (after S-174's
     column/entry split and S-179's footer band) read clearly enough for the kiln, or should control
     returns and earth-7's loop (B-0158) be reworked first? Recorded as "judged by the agent; the
     maintainer's visual judgment pending" in "Review gate H — outcome".
   - v0.5 visual exits (`docs/reviews/v0.5-status-choice.png`, `docs/reviews/v0.5-report-scope.png`),
     still pending from `docs/handoffs/HANDOFF-REPORT-v0.5.md` §10.
2. **Push** `main` (unpushed since `7d90121`), then check the next scheduled Linux nightly run.
3. **Tag** `v0.6.0` (and `v0.4.0` / `v0.5.0` if desired) on the green CI commit (S-072);
   `publish.yml` checks `pyproject.toml`, `packaging/n2f/pyproject.toml` and
   `src/napkin2factory/__init__.py`.
4. **`[revisit]` calls** in §7, notably E2 (whether to add a schema-extension seam on `Part` so a
   device need not be a separate file) and E5/B-0128 (whether a domain's consumables should join
   the parts list).

## 11. Where things are

- Plan: `../stages/v0.6-electrical-stage.md`; baseline: `docs/v06-baseline.md`; domain guide: `docs/electrical.md`;
  contract: `docs/domains.md`.
- Decisions: `DECISIONS.md` `S-141`–`S-181`, "Review gate G — outcome", "Review gate H — outcome";
  open work: `BACKLOG.md`.
- Domain package: `src/napkin2factory/domains/electrical/` (`model/`, `interfaces/`, `outputs/`,
  `checks/`, `owner/`); calc-kit tables: `src/napkin2factory/calckit/data/{conductors,earthing,wire_colours}.yaml`,
  `src/napkin2factory/calckit/wiring.py`.
- Kiln wiring & demo: `examples/kiln/model/electrical/`, `examples/kiln/changes/ECR-003.{yaml,patch}`,
  `examples/kiln/demo-electrical.sh`, `examples/kiln/reports/electrician-readthrough.md`.
- Fixtures & transcripts: `tests/fixtures/electrical/`, `tests/fixtures/scope/external-box/`,
  `tests/e2e/intake-transcripts/wiring-session-2026-11-03.md`.
- Gate reports & visual captures: `docs/reviews/v0.6-gate-g.md`, `docs/reviews/v0.6-gate-h.md`,
  `docs/reviews/v0.6-*.png`.
