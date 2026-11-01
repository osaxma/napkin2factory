# Napkin2Factory — ELECTRICAL_STAGE.md: plan for v0.6 ("the wiring")

**Audience:** the agents who build v0.6: one overseer and the subagents it hands tasks to. None
remembers an earlier session. Work flows as `AGENTS.md` says. §8 says how the overseer runs
the waves.

**Companions:** `FOUNDATION.md` (v0.5, F-series) is the plan this one proves; `GRAND_PLAN.md`,
`NAPKIN_STAGE.md` and `PRODUCT_STRUCTURE.md` stay in force except where an E-series decision
below amends them. Also read `DECISIONS.md` (the index), `BACKLOG.md` and `docs/domains.md`
(the contract v0.5 wrote; this release is its first real user).

**Origin:** the same review as `FOUNDATION.md` (2026-11-01). The maintainer: electrical design
is a step a product needs or does not; the system must support it; it is the right first proof
that the v0.5 seams hold. The kiln's own installation manual says today: "This package has no
wiring diagram. The electrician wires, to local code" (`examples/kiln/model/docs/installation.md`).

---

## 0. Why this release (read once; it calibrates every judgment call)

Two reasons, in this order:

1. **It is the proof of v0.5.** A domain that nobody built the seams for is the only honest
   test of them. The measure is the one `FOUNDATION.md` set: the electrical domain's own
   commits change nothing under `src/napkin2factory/core/`. Where a core change turns out to be
   needed, it is a v0.5 defect, fixed in its own task with its own backlog row (E10), and the
   count of such tasks is the headline of the handoff report.
2. **The kiln's package is incomplete without it.** Measured 2026-11-01: 22 of the kiln's 39
   parts are BOM-only, and the powered ones (controller, limit controller, contactor, solid-state
   relay, door switch, thermocouple, heating element, three cable glands, five earth studs, a
   rating label) have no connections, no cable schedule and no diagram. The manual hands the
   whole of it to "the electrician, to local code". A manufacturer package that cannot say what
   connects to what is not a package.

What electrical means here, and what it does not:
- **Wiring-level electrical:** a supply, devices with ratings and terminals, connections between
  terminals, conductors with a cross-section from a cited table, protection, earthing, interlocks.
  What an appliance, a panel, a machine or a bench tool needs.
- **Not printed-circuit design.** No boards, no layout, no footprints. A product that needs a
  board treats it as a bought part with terminals, exactly like the kiln's controller.
- **Source is data, in the model's own YAML.** No desktop tool is required to build, check or
  read it (D3's pip-only rule holds). A schematic file for a desktop tool may be *exported* as
  text, never used as source (E1).
- **Advisory, never a licence.** The checks catch arithmetic and topology (a load above the
  supply, a conductor too thin for its current, a metal part with no path to earth, an
  interlock that does not break the load). Compliance with a wiring code is a person's
  judgment; every safety requirement stays `needs-human`, and the disclaimer says the wiring
  was not reviewed by a licensed electrician.

The scope in one sentence: **a product declares its supply, its devices' terminals and its
connections; the system draws, schedules, counts and checks them, and the mechanical model
gets a port for every cable that crosses the box.** When unsure whether something belongs in
v0.6, ask whether an electrician reading the package would need it to wire the product. If
not, it waits.

## 1. Mission, non-goals, definition of done

### 1.1 Mission
Ship **napkin2factory v0.6**: the `electrical` domain under `src/napkin2factory/domains/electrical/`,
registered through the v0.5 contract and nothing else:
- a model family `model/electrical/` (the supply and the circuits) and an `electrical:` block on
  parts (the devices);
- the `cable-entry` interface kind: the joint between a box and the wiring that crosses it,
  and the port an external electrical module exposes;
- a rule family `elec:` producing a wiring diagram per circuit, a connection table, a cable
  schedule and terminal labels, read by the BOM and the manuals;
- the `circuit` verify kind, the `electrical` check stage with `electrical-v0.yaml`, gate rows,
  the "Wiring" report section, doc helpers, vocabulary, the generic supply screen;
- the kiln wired, its manual's wiring section generated, and its story as the demo: released
  with electrical *later*, then *in* through a change request, with one choice decided on the
  way;
- a fixture product whose electrical box is *external* and declares only ports.

### 1.2 Non-goals for v0.6 (stay in `BACKLOG.md`)
- Printed-circuit design, footprints, layout, design-rule checks against a fab (B-0035 keeps
  the PCB half).
- Running a desktop tool's electrical rule check (`kicad-cli` or similar): tier-1, optional,
  later. v0.6 may export a text schematic (E1, ⤵ droppable).
- Three-phase supplies, motors with starters, variable-speed drives, DC power trees with
  regulators. The schema must not prevent them (a supply has `phases`), but no rule reads them.
- Voltage-drop and short-circuit calculations beyond the conductor table's ampacity.
- Claims of compliance with any wiring code. Rules cite their tables with `[verify]`.
- Anything that changes the core: see E10.

### 1.3 Definition of done (from a clean clone; the macOS host plus the CI matrix, S-001)
1. **The count.** Every v0.6 task's commits change nothing under `src/napkin2factory/core/`,
   `report/builder.py`, `docs/engine.py`, `core/graph/` or `cli/check.py`, verified by
   `git log --stat` over the release's tasks in the handoff report. Core changes made under E10
   are listed there with their backlog rows; the target is zero.
2. **The kiln is wired.** `build/electrical/<circuit>/diagram.svg` for its power, control and
   sensing circuits; `build/electrical/schedule.csv` and `labels.csv`; the BOM carries the
   conductor lines; the installation manual's wiring section is generated from the doc helpers,
   and the sentence "This package has no wiring diagram" is gone. The report has a Wiring
   section. The report stays ≤ 20 MB; record its size.
3. **The checks catch what they claim.** Fixtures under `tests/fixtures/electrical/`: a load
   above the supply rating fails; a conductor below the table's cross-section fails; a custom
   metal part with no path to earth fails; a circuit with no protective device fails; an
   interlock that does not break the load path warns; control and mains conductors sharing one
   cable entry warn. Each failure names the part, the circuit and what to do.
4. **The scope story runs unattended.** `examples/kiln/demo-electrical.sh`, in a temp copy
   (D23): release `v1.0.0` with `electrical: later` (the cover says so) → `ECR-003` adds the
   wiring as a design change request with a patch (D7) → impact → approve → apply → build →
   the supply-headroom choice is raised and decided (`n2f decide`) → check → close → `v1.1.0`
   with `electrical: in` → the diff page shows the Wiring section as added. It runs in
   `make check-full`; record its time.
5. **External works.** `tests/fixtures/scope/external-box/` validates: a small heated product
   whose control box is `build: external` with two `cable-entry` ports; its wiring diagram shows
   the boundary ("to the external box: L, N, PE, two control conductors") and nothing inside it.
   Removing a port fails validation naming the file.
6. **The supply screen moved.** The generic supply screen ships with the domain; the kiln's
   product-local pack no longer carries a copy; `goldens/kiln-board.json` unchanged.
7. **The choice is raised at the right time.** A scripted owner session (M7) shows the supply
   headroom choice raised after the first build with wiring, not in the interview, in the
   owner's words with both options' consequences; transcript under `tests/e2e/intake-transcripts/`.
8. **Every number has a source.** The conductor table, the earthing rule and the supply tables
   cite their sources with `[verify]`; `make verify-list` shows them; the element current and
   power read from the calc kit's existing `power` pack.
9. **Review gates.** Gate G (engineering: role-play a licensed electrician reading only the
   manufacturer package: can they wire it; what is ambiguous; kept in `examples/kiln/reports/`
   like the shop read-through) and gate H (UX in the owner persona: the later → in story, the
   cover line, the choice, no engineering vocabulary) are closed with reports in `docs/reviews/`.
   The maintainer judges one wiring diagram and the report's Wiring section (S-078).
10. **Docs.** `docs/electrical.md`; the agent guide's electrical section; the design, verifier
    and project-manager roles; `docs/vocabulary.md` (supply, circuit, wiring, cable entry,
    earth, interlock); `HANDOFF-REPORT-v0.6.md` with the count as its first line; version files
    and pins `>=0.6,<0.7`.

---

## 2. Locked decisions (E-series)

| # | Decision | Why |
|---|---|---|
| E1 | **Wiring-level, data as source, pip-only.** The electrical model is YAML under `model/electrical/` plus an `electrical:` block on parts. Building, checking and reading need no desktop tool. A text schematic export (`.kicad_sch`, an s-expression file written by the `elec:` rule) is a ⤵ droppable extra and never source; running a desktop tool's rule check is tier-1 and a later version | What the kiln and most tinkerer products need; D3's pip-only rule; a desktop file as source would make the model unreadable to a rule and unmergeable to the change loop |
| E2 | **Devices are parts.** A part gains an optional `electrical:` block: `role` (supply, load, control, protection, sensor, earth, passthrough), `rating` (voltage, and current or power), `terminals` (a list of names: `L`, `N`, `PE`, `A1`, `A2`, `+`, `-`, `1` …), `class` (I, II, III) and `notes`. One part, one BOM line, one URI: the controller the mechanical model places is the controller the wiring connects. The block is additive (F7: no schema bump) | One canonical model; the BOM and the wiring never disagree about what exists |
| E3 | **Circuits are connection lists.** `model/electrical/supply.yaml` declares the supply: voltage, phases, frequency, circuit rating, earthing arrangement, region (the key into the existing circuits table). `model/electrical/circuits/<id>.yaml` declares a circuit: its purpose (power, control, sensing, earth), its protective device, and `connections: [{from: part://x#L, to: part://y#1, conductor: <id>, length: 0.6 m, via: iface://<cable-entry>}]`. Nets are derived from the connections; a terminal named on a part that has no such terminal is a validation error naming both. Conductors come from `calckit/data/conductors.yaml` (cross-section, ampacity, insulation class, cited `[verify]`); a product may add its own rows | A connection list is what an electrician reads and what a rule can walk; nets are a view, never typed twice |
| E4 | **`cable-entry` is an interface kind.** Parties: the box part (it gets the hole, a `circle` pattern of count 1, cut by the existing interface machinery) and the gland or bushing part. Its spec adds `passes: [circuit://<id>, …]`. The mechanical side sees a hole; the electrical side sees which circuits cross there. A sub-assembly that is `build: external` (F11) lists its cable entries under `ports:`; that is the whole contract between the product and the work done elsewhere. The kiln's three M20 glands become three cable entries on the controller box base | The joint between the two domains is one interface, owned by neither; an external box is a module with ports (P4) |
| E5 | **The `elec:` rule family.** One rule per circuit, after `part` (it reads the devices and the cable entries) and before `bom` (the BOM reads its schedule). Outputs under `build/electrical/`: `<circuit>/diagram.svg` (a programmatic ladder-style diagram: devices as labelled boxes, terminals, conductors with their id and cross-section, the cable entries as dashed boundaries; drawn with the same SVG helpers as the drawings), `<circuit>/connections.json`, `schedule.csv` (conductor id, from, to, cross-section, length, colour, via), `labels.csv` (terminal labels for the shop). The BOM's rollups add the conductor lines as consumables from the schedule. The diagram embeds in the report as the drawings do | Derived views of one source; the diagram is what the electrician reads, the schedule is what they buy and cut |
| E6 | **Advisory discipline in `electrical-v0.yaml`.** `fail` only for arithmetic and topology that is certain: load current above the supply rating; a conductor below the table's ampacity for its current; a custom part of conductive material with no connection to the earth net and no `bonded_via: iface://…` note; a circuit with no protective device; a terminal used twice where the device allows one conductor. `warn` for everything a code would judge: an interlock not in series with the load's switching device; a limit device sharing the controller's switching path; mains and control conductors through one cable entry; missing labels; `bonded_via` claims (a bolted joint as an earth path is a claim a person verifies). Every rule's message says what to do and, for warns, that a licensed electrician decides. Safety requirements in the electrical category are `manual` (`needs-human`) always; the disclaimer gains the wiring sentence | Catch what arithmetic can; never let a rule read as a code review |
| E7 | **Gate rows.** Design gate: a part with `electrical.role: load` or `control` and no connection blocks the gate when the scope is `in` ("the fan is not wired yet"). Verify gate: the electrical check stage's rows. Both rows exist only when the domain has content or the scope says `in` (F4, F11) | A product cannot leave Design with a device nobody wired |
| E8 | **The supply screen is the domain's.** `supply-fits` (the card's power against the site's circuit, by region) moves from the kiln's product-local pack into the domain's screens; the kiln pack keeps only its thermal screens. A screen migrating from a product to a domain is exactly the path a third party's screen would take | Screens follow their physics: supply is electrical, not kiln |
| E9 | **The kiln is the demo and the scope story.** The kiln ships wired on `main` (its pre-change-request state, D23, with `scope.electrical: in`), and `demo-electrical.sh` replays the story from a copy whose wiring is removed: `later` at v1.0.0, a design change request with a patch that adds `model/electrical/` and the `electrical:` blocks, the choice, `in` at v1.1.0, the diff. `demo.sh` and `demo-design.sh` are unchanged; B-0063's patch is re-created in the same task because the manual moves | The story the owner will live: design the thing, wire it later, see what changed |
| E10 | **A core change is a v0.5 defect.** When a v0.6 task cannot proceed without editing the core, it stops, commits `WIP:` naming the file and the reason, and the overseer opens a separate task with a `B-NEW` row and a decision entry naming the seam that failed. The electrical task resumes after that lands. The handoff report lists every such task; the target is zero | The count is the point of the release; a silent core edit would hide the one thing v0.6 exists to measure |
| E11 | **Choices in the domain.** `supply-headroom`: when the load uses more than a cited fraction of the supply rating but still fits, the check returns a `choice` with `blocks: none` ("2.5 kW on the 16 A circuit leaves 5 A spare; a bigger element later would need a 20 A circuit, which is the electrician's job"); the project manager decides conservatively and logs it (F13). The kiln's demo decides it with `n2f decide` so the path is exercised end to end | A real choice from real numbers, low consequence, raised after the facts exist |
| E12 | **Backward compatible.** Every new field is optional (F7's additive rule; schema stays 1); products without `model/electrical/` show no electrical row anywhere; the bracket and enclosure goldens are unchanged; pins `>=0.6,<0.7` at release | The two flat examples must not move; a product with no wiring must not see the word |

## 3. Schema additions (all optional; shapes only, not kiln data)

```yaml
# model/parts/pid-controller.yaml — a device (E2)
electrical:
  role: control
  rating: {voltage: 230 V, power: 5 W}
  terminals: [L, N, "1", "2", TC+, TC-]
  class: II

# model/electrical/supply.yaml (E3)
voltage: 230 V
phases: 1
frequency: 50 Hz
rating: param://circuit-rating          # 16 A
earthing: TN-S                          # [verify] the owner's installation
region: EU
protection: part://mcb-16a              # the protective device, a part

# model/electrical/circuits/power.yaml (E3)
id: power
purpose: power
protection: part://mcb-16a
connections:
  - {from: part://mcb-16a#2, to: part://contactor#L1, conductor: cu-2p5-pvc, length: 0.3 m}
  - {from: part://contactor#T1, to: part://ssr#1, conductor: cu-2p5-pvc, length: 0.2 m}
  - {from: part://ssr#2, to: part://heating-element#A, conductor: cu-2p5-silicone, length: 0.8 m, via: iface://cable-entry-element}
  - {from: part://supply-terminal#PE, to: part://earth-stud#1, conductor: cu-2p5-gy, length: 0.5 m}
notes: the limit controller and the door switch are in the contactor's coil circuit (control)

# model/interfaces/cable-entry-element.yaml (E4)
kind: cable-entry
parties: [part://controller-box, part://m20-gland]
frames: {...}                           # as any interface; the box gets a 20.5 mm hole
spec: {pattern: circle, count: 1, diameter: 20.5 mm, passes: [circuit://power]}

# model/assemblies/control-box.yaml — the external case (E4, F11)
build: external
ports: [iface://cable-entry-mains, iface://cable-entry-control]

# model/requirements.yaml — the circuit verify kind
- id: REQ-030
  statement: The power circuit's load stays under the supply rating
  verify: {kind: circuit, target: "circuit://power#load_current", op: "<", value: param://circuit-rating}

# calckit/data/conductors.yaml (E3) — every row cited, [verify]
- {id: cu-2p5-pvc, material: copper, csa: 2.5 mm², ampacity: 20 A, insulation: PVC 70C, source: "...", verify: true}
```

## 4. CLI surface added or changed
No new verb. Through the registries: `n2f doctor` lists `electrical` with its verify kind, check
stage and screen; `n2f status` shows the electrical rows and the scope row; `n2f build --target`
gains nothing (the family joins the existing targets by its `after:` declaration); `n2f check
--scope asm://<id>` includes the circuits whose devices all sit in that module. The agent guide's
command reference gains an electrical paragraph, not a command.

## 5. Milestones

Budgets are guesses; record the actual times. Every task owns files under
`src/napkin2factory/domains/electrical/` and the kiln's or fixtures' folders named below, and
nothing else. **Waves (§8):** M0 → M1 alone → wave 2 = {M2, M3, M4} → wave 3 = {M5, M6} → M7.

### M0 — Baseline and tables (budget 3 h)
**Build:** land this plan, its entry (`S-111`), the STATUS line. Survey the kiln's electrical
content by hand into `docs/v06-baseline.md`: every powered part, its terminals from the vendor
page (`[verify]`), the intended connections from `installation.md` and `decisions.yaml`, the
three glands' circuits, the earth studs' parts. Draft `calckit/data/conductors.yaml` and the
earthing arrangements table with sources. Record `make check-full`'s time.
**Owns:** `ELECTRICAL_STAGE.md`, the journals, `docs/v06-baseline.md`, `calckit/data/conductors.yaml`.

### M1 — The family and the joint (budget 6 h; serial)
**Build:** `domains/electrical/__init__.py` (the `DOMAIN` object; every registry entry stubbed
so later tasks fill functions, not registrations); `domains/electrical/model.py` (the schemas:
`Electrical` block, `Supply`, `Circuit`, `Connection`; the `validate_refs` for terminals,
conductors, protection, `via` entries); the `electrical:` field on `Part` (additive) registered
as the family's extension; the `cable-entry` interface kind with `passes:` (its hole cut by the
existing `circle` pattern); the external stub's port check for cable entries; the toy-level
fixture `tests/fixtures/electrical/minimal/` (one supply, one load, one circuit, one entry).
**Tests:** load and validate the minimal fixture; every validation error names its file and the
fix; an `electrical:` block on a part in a product with no `model/electrical/` is a lint warn
("a device with no wiring; add a circuit or set scope: later").
**Owns:** `domains/electrical/__init__.py`, `domains/electrical/model.py`,
`domains/electrical/interfaces.py`, `tests/fixtures/electrical/minimal/`,
`tests/unit/test_electrical_model.py`.

### M2 — The rule family and its outputs (budget 7 h)
**Build:** `domains/electrical/rules.py` (`elec:<circuit>` after `part`, before `bom`; recorded
reads through the accessors: `P[...]`, parts' blocks, the entries); `diagram.py` (the ladder
SVG with the drawings' helpers; the external boundary dashed); `schedule.py` (`schedule.csv`,
`labels.csv`, `connections.json`); the BOM consumable lines read from the schedule through the
`bom` family's hook; the `.kicad_sch` text export (⤵ droppable; a test parses the s-expression,
nothing runs it).
**Tests:** outputs for the minimal fixture; a golden diagram; the BOM line count; a changed
conductor length rebuilds the circuit and the BOM and nothing else (`test_invalidation` gains
a case); the report size.
**Owns:** `domains/electrical/rules.py`, `diagram.py`, `schedule.py`, `export_kicad.py`,
`tests/unit/test_electrical_outputs.py`, `tests/golden/goldens/electrical-*`.

### M3 — Checks, the verify kind and the choice (budget 7 h)
**Build:** `domains/electrical/checks.py` (the `electrical` stage: nets walked, the earth path,
the interlock topology, the entry sharing); `domains/electrical/electrical-v0.yaml` (E6) with
owner words per rule; the `circuit` verify kind (`circuit://<id>#load_current`, `#supply_margin`,
`#earth_paths`, `#conductor_margin`) with evidence keys; the `supply-headroom` choice (E11);
`domains/electrical/calcs.py` binding the calc kit's `power` pack and the conductor table.
**Tests:** DoD 3's six fixtures; the choice raised, decided, reopened on evidence; the verify
kind's evidence keys change when a connection changes.
**Owns:** `domains/electrical/checks.py`, `electrical-v0.yaml`, `verify.py`, `calcs.py`,
`tests/fixtures/electrical/{over-supply,thin-conductor,unearthed,unprotected,interlock,shared-entry}/`,
`tests/unit/test_electrical_checks.py`.

### M4 — The owner's view (budget 5 h)
**Build:** `domains/electrical/report.py` and `report/wiring.html.j2` (the Wiring section:
diagrams, the schedule, the circuit rows, the scope line when `later` or `external`); the doc
helpers `circuit("id")`, `cable_schedule()`, `terminal_labels()` (recorded reads); the gate
rows (E7); the vocabulary (owner and engineer words); `screens.py` with `supply-fits` moved from
the kiln's pack (E8; the kiln pack edit is M5's, so M4 ships the screen and M5 removes the copy).
**Tests:** the section renders for the minimal fixture and is absent for the bracket; the
helpers record reads and go stale (`doc_staleness`); the gate rows appear only with content or
`scope: in`; the screen on a card with a `circuit` site field.
**Owns:** `domains/electrical/report.py`, `report/wiring.html.j2`, `docs_helpers.py`,
`gates.py`, `vocabulary.py`, `screens.py`, `tests/unit/test_electrical_report.py`.

### M5 — The kiln, wired (budget 9 h)
**Build:** the kiln's `supply.yaml`, three circuits (power, control, sensing), the `electrical:`
blocks on its powered parts from `docs/v06-baseline.md`, the three cable entries replacing the
glands' hand-placed cutouts, the protective device as a part, `scope.electrical: in` with its
`DEC-`; the kiln pack drops its supply screen; `installation.md` rewritten around the helpers;
`demo-electrical.sh` (E9) and its `ECR-003` patch; B-0063's `ECR-002` patch re-created;
`make check-full` runs the new demo.
**Tests:** `tests/e2e/test_demos.py` gains the demo; the kiln board golden unchanged; the kiln's
report size recorded; `tests/validate_outputs_full.py` expects the electrical files.
**Owns:** `examples/kiln/` (all), `tests/e2e/test_demos.py`, `tests/validate_outputs_full.py`,
`Makefile` (the demos target only).

### M6 — External, scope and the simulation fixture (budget 4 h)
**Build:** `tests/fixtures/scope/external-box/` (DoD 5) and its tests; the diff page's handling
of a section that is new in the later Revision ("Wiring: added"); the owner-session script for
M7 (the product and the lines the owner says, so M7 only runs it).
**Tests:** DoD 5; the diff page golden; the cover text for `later` and `external`.
**Owns:** `tests/fixtures/scope/external-box/`, `tests/unit/test_scope_external.py`,
`ecr/diff.py` (the "added section" case only), `tests/e2e/intake-transcripts/wiring-session.md`
(the script, not the transcript).

### M7 — Docs, simulations, gates, close-out (budget 6 h)
- `docs/electrical.md`; the agent guide; the three roles synced with `make templates`;
  `docs/vocabulary.md`.
- The owner simulation (DoD 7) from M6's script; the transcript saved.
- Gates G and H from `docs/reviews/TEMPLATE.md`; blockers fixed; the electrician read-through
  kept in `examples/kiln/reports/`.
- The maintainer judges a diagram and the Wiring section (S-078).
- `HANDOFF-REPORT-v0.6.md` with the count first; version files and pins; `make check-full`
  from a clean clone. Tagging is the maintainer's call.

## 6. `make check` / `make check-full` growth
- The electrical unit tests and the minimal fixture run in `make check-fast` and `make check`.
- The kiln's wiring builds inside the existing kiln step of `make check-full`; the new demo
  runs beside the three others (S-079, `-n 4`). Record the times; `make check-full` must stay
  under 25 min on the host.

## 7. Risks
| Risk | Watch | Fallback |
|---|---|---|
| A seam is missing and a task edits the core "just this once" | E10; `git log --stat` over the release's tasks in the handoff | Stop, `WIP:`, a separate task with a `B-NEW` row; the count is reported, not hidden |
| The rules read as a code review | E6: `fail` only for arithmetic and topology; owner words say "a licensed electrician decides" | Gate G's electrician persona reads every message |
| The kiln's terminal names and ratings are guessed | M0 takes them from the vendor pages with `[verify]`; `make verify-list` | A device whose terminals cannot be sourced gets `terminals: []` and a lint warn, never invented names |
| The diagram is unreadable at kiln size (three circuits, a dozen devices) | M2's golden; the maintainer judges it (S-078) | One diagram per circuit (already the design); if still crowded, a device index table beside it |
| The conductor table is regional | Keyed by region like `circuits.yaml`; the supply names its region | Rows for EU and US at v0.6; others `[verify]` as added |
| The text schematic export eats the budget | ⤵ droppable | Drop it; the diagram is the deliverable |
| `bom` must read `elec:` output and the family order fights the registry | M1 declares `after: [part]` and the `bom` family declares `after: [elec]` through the registry's optional-dependency rule (a family may run after another *if installed*) | If the contract lacks optional dependencies, that is a v0.5 defect under E10 |

## 8. How the overseer runs this plan
As `FOUNDATION.md` §8, with these differences:
- **The count is the overseer's first job.** Before each wave, the overseer tells every
  subagent the E10 rule in its brief. After each wave it runs `git log --stat` over the landed
  tasks and records any core edit as a backlog row then and there.
- **Wave 2 (M2, M3, M4) is three subagents on three subfolders** of the domain. They share
  `domains/electrical/__init__.py` only through the stubs M1 left: each fills a function body,
  none adds a registration. If one must, it stops and the overseer serialises.
- **Wave 3 (M5, M6)** is two subagents: the kiln and the fixtures. M5 is the long one; start it
  first.
- **Gate G needs an electrician persona**, which is a fresh-context subagent reading only the
  manufacturer package and the wiring outputs, never the model files.
- **Push only when the maintainer asks.**
