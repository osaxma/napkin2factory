# Napkin2Factory — FOUNDATION.md: plan for v0.5 ("the seams")

**Audience:** the agents who build v0.5: one overseer and the subagents it hands tasks to. None
remembers an earlier session. Work flows as `AGENTS.md` says: one task per worktree, landed with
`make land`. §8 says how the overseer runs the waves.

**Companions:** `GRAND_PLAN.md` (v0.1, D-series), `NAPKIN_STAGE.md` (v0.2, N-series) and
`PRODUCT_STRUCTURE.md` (v0.4, P-series) stay in force except where an F-series decision below
amends them. Also read `DECISIONS.md` (the index) and `BACKLOG.md`.

**Origin:** a review of the project on 2026-11-01, after v0.4 M2 landed. The maintainer's brief,
in their words: build a solid foundation first, one that agents of any model can develop
continuously without breaking what exists; steps such as analysis or electrical are added when a
product needs them and absent otherwise; real-world testing comes later. The review measured
what adding a step costs today (§0) and found that the seams the brief needs do not exist yet.

---

## 0. Why this release (read once; it calibrates every judgment call)

### 0.1 The vision this release serves
- **A step is a folder.** Electrical, analysis, a manufacturer's rule set: each is a domain that
  registers what it brings. The core knows the contract, never the domain. Adding one touches
  no core file.
- **The owner's flexibility is data, not an agent's memory.** Which domains are in scope, which
  are done elsewhere, which come later: recorded once in the product, shown by `n2f status`,
  read by every role. The owner moves forward, back, adds and removes; underneath it is the
  change-request loop they already never see.
- **The system hands the agent the moment and the words.** A trade-off the owner should know
  about ("a standard size costs less; the water line would have to move") is a *choice* a rule
  produces when the facts first exist, queued until the owner next touches that area. No role
  has to remember to ask, so a weaker model asks as well as a strong one.
- **Any model, any client, measured.** A seam is done when a fresh-context agent, given only the
  contract document, adds a domain without touching the core, and a test counts the files.

### 0.2 What adding a step costs today (measured 2026-11-01 on `main` at 1e52083, S-107)
A new rule family, verify kind, check stage, report section and doc helper, which is what any
domain brings, has to edit these:

| seam | today | a new step edits |
|---|---|---|
| build rule families | one function, nine kinds in a fixed order, a fixed `--target` table | `core/graph/rules.py`, `core/graph/runs.py` |
| verify kinds | an if/elif chain over nine kinds | `core/checks/evaluators.py` |
| check stages (interference, interface, count, hardware) | called one by one | `core/checks/engine.py` |
| pipeline stages | a fixed tuple: intake, design, verify, released | `core/checks/stage.py` |
| report sections | a fixed tuple plus a template with 33 branches | `report/builder.py`, `report/templates/report.html.j2` |
| doc helpers | hardcoded names | `docs/engine.py` |
| impact's static read set | per rule kind | `core/graph/impact.py` |
| interface kinds, processes, style roles, finishes, requirement categories, verify kinds | closed `Literal`s | `core/model/*.py` |

That is eight core files and the schema package per step. The v0.4 assembly-sheet rule (M3) is
being added the same way, so the pattern is still being reinforced.

Three more findings:
- **The example became the schema.** The founding handoff said "example used throughout: a
  kiln". 23 of the package's source files mention kiln, door, chamber or alcove. The concept
  card schema has `alcove_width`, `alcove_depth`, `alcove_height` and `chamber` as first-class
  keys (`core/concepts.py`). `concepts/screening.py` (866 lines) hardcodes thermal, supply and
  door-swing logic; six of the ten rules in `rulepacks/concept-v0.yaml` are heated-box rules.
  The style roles are `body`, `door`, `stand`, `controls`, `lining`. A product that is not a
  heated box gets a heated box's screening.
- **The schema version is written and never read.** `n2f.yaml` carries `schema: 1`; every model
  forbids unknown fields (`core/model/base.py`). Strict is right, but it means every new field
  is a breaking change for every product folder, and there is no migration path (B-0042).
- **Five files are where parallel agents will collide:** `concepts/promote.py` (1,299 lines),
  `core/loader.py` (999), `concepts/screening.py` (866), `rulepacks/concept_checks.py` (710),
  `geometry/build.py` (702). The loader holds every family's cross-reference validation, so
  every new family edits it.

What is already right, and what this release builds on: one module per CLI verb, `--json` on
every verb, recorded reads (D5), code hashes per package subtree (S-031), goldens with a
regeneration log, product-local calcs in `model/calcs/`, the stage ladder computed from state
(D10), decisions delegated and never deleted, and the task-worktree landing flow (S-097).

The scope in one sentence: **v0.5 adds no owner-facing feature except scope and choices; it
turns every hardcoded list a domain would edit into a registry behind one contract, and proves
it with a toy domain, a kiln that lives only in `examples/`, and a count of zero.** When unsure
whether something belongs in v0.5, ask whether it makes a future step cheaper to add without
touching the core. If it doesn't, it waits.

## 1. Mission, non-goals, definition of done

### 1.1 Mission
Ship **napkin2factory v0.5**:
1. the domain contract and the registries behind it (rule families, verify kinds, check stages,
   gate rows, report sections, doc helpers, vocabulary, interface kinds, processes, screens);
2. a toy domain and a toy product in the tests that exercise every registry in seconds;
3. the open sets (processes, finishes, style roles, interface kinds, categories) as data tables;
4. a schema policy and a migration hook;
5. the kiln out of the system: free-form card fields, screens as packs, product-local packs,
   the kiln's own screens in the kiln's folder;
6. scope as data: a domain is *in*, *external* or *later*; stub modules with ports; scope read
   at release and printed on the package cover;
7. choices: a fourth check outcome with a queue, `n2f decide`, and the project-manager rule for
   when to raise one;
8. the conflict magnets split along the seams;
9. `docs/domains.md`, the contract written for a fresh agent, and the roles, guide and
   vocabulary updated;
10. calcs that prove themselves: reference cases on every calc, run by `n2f check`, with one
    external case per calc-kit pack.

The bracket, the enclosure and the kiln must build to the same outputs, plus the new files.

### 1.2 Non-goals for v0.5 (stay in `BACKLOG.md`)
- Everything the earlier plans exclude, except what is named above.
- Any electrical content: v0.6 (`ELECTRICAL_STAGE.md`) is the first real domain and the proof.
- Analysis solvers of any kind; v0.5 only reserves the load-case slot (F11).
- A plugin mechanism for packages outside this repository (entry points, plugin discovery).
  Domains are in-tree packages; products carry packs. A solo maintainer does not need more.
- Moving the mechanical code into a domain package. It registers in place (F2). Moving files
  for their own sake would move goldens and gain nothing.
- A schema version 2. v0.5 ships the policy and the hook, exercised by a test migration only.
- New kit generators, the MCP server, the second product, kinematics (unchanged non-goals).

### 1.3 Definition of done (from a clean clone; the macOS host plus the CI matrix, S-001)
1. **Nothing moved.** `make check` and `make check-full` green. The bracket, enclosure and kiln
   goldens unchanged; `tests/validate_outputs.py` passes on all three with the new files added
   to its expected set. `goldens/kiln-board.json` unchanged.
2. **A step is a folder: the count.** `tests/unit/test_domain_contract.py` registers the toy
   domain (`tests/fixtures/domains/toy/`) and proves every registry sees it: its rule family
   runs in the build in the right place, its verify kind evaluates, its check stage reports,
   its gate row shows in `n2f status`, its report section renders, its doc helper records a
   read, its vocabulary word appears in the owner view, its interface kind validates, its
   process passes the general rule pack, its screen runs on a card. Then the M7 simulation: a
   fresh-context agent given only `docs/domains.md` adds a second toy domain; the transcript is
   saved under `tests/e2e/domain-transcripts/` and the number of files it changed under
   `src/napkin2factory/core/` is zero.
3. **The kiln lives in `examples/`.** `tests/unit/test_no_example_identifiers.py` (F9) finds no
   example identifier and no example product name in the package. `AGENTS.md` carries the rule
   and `docs/reviews/TEMPLATE.md` the reviewer's question. The kiln's thermal, supply, skin,
   chamber and hot-face screens live in `examples/kiln/model/screens/`; the kiln's board and
   screening outputs are unchanged.
4. **Schema policy.** `docs/schema-policy.md` exists. `core/model/migrate.py` holds the
   migration registry; `n2f init .` (the upgrade path, S-057) applies pending migrations after a
   snapshot and says so in owner words. `tests/fixtures/schema/` holds one product per schema
   version that has existed (today: 1) and a test migration `1 → 1+test` round-trips in a test
   without touching any shipped product.
5. **Scope.** The kiln's `n2f.yaml` declares `scope: {electrical: {state: later, decision:
   DEC-xxx}}`. `n2f status` shows the row; the report overview and the release package cover
   say it. A fixture product with `state: external` validates only when a stub module with
   ports exists, and the error names the file. Requirements allocated to a `later` domain are
   excluded from the Verify gate with a visible note, never silently.
6. **Choices.** A rule-pack check can return `choice`. The kiln has at least one real choice
   produced by a rule (the bottom-corner fastening found by S-105: a through bolt or a threaded
   standoff, each with its hardware count), `n2f status` lists it under "waiting on you",
   `n2f decide` resolves it into a `DEC-` entry, and the row reads `pass` with the decision
   afterwards. A changed evidence key reopens it, exactly like a sign-off (D25). The
   project-manager role names when to raise one. A scripted simulation (M7) shows the choice
   raised after the first build, not in the interview.
7. **Verify methods are discoverable.** `n2f doctor` lists the installed domains with their
   verify kinds, check stages and screens. A requirement naming an uninstalled verify kind is a
   validation error that lists the installed ones.
8. **Splits.** Each model family's cross-reference validation lives beside its schema
   (`core/model/<family>.py::validate_refs(product, problems)`); `core/loader.py` orchestrates
   and is under 400 lines. `concepts/promote.py` is split into one seeder per family and
   `concepts/screening.py` into the screen runner plus the generic screens; none of the five
   files named in §0.2 exceeds 500 lines. Record the before and after in the decision entry.
9. **Check time.** `make check` ≤ 10 min on the host; `make check-fast` (lint, types, the unit
   and smoke tests, no end-to-end, no examples) exists, runs in ≤ 3 min, and is the default
   `make land` gate. Record both times.
10. **Review gates.** Gate E (architecture and honesty: can a domain reach core state it should
    not; is every registry hashed into the rules that depend on it; is impact still a superset
    of invalidation with registered families) and gate F (UX in the owner persona: scope rows,
    the package cover, a choice raised and decided, no git or engineering vocabulary) are
    closed with their reports in `docs/reviews/`. The maintainer judges a screenshot of the
    status output with a choice and the report's scope line (S-078).
11. **Docs.** `docs/domains.md` (the contract), `docs/schema-policy.md`, the agent guide, the
    four roles, `docs/vocabulary.md` (domain, scope, in / done elsewhere / later, choice,
    waiting on you), `HANDOFF-REPORT-v0.5.md`. The three version files and the product pins
    bumped to `>=0.5,<0.6`.
12. **Calcs prove themselves.** Every calc-kit function and every kiln calc has at least one
    reference case; each calc-kit pack has one external case with its source; `n2f check` on
    the kiln shows the `calc-case` rows, all `pass`; a fixture calc with a wrong case fails
    naming the calc, the expected and the actual; a calc with no case warns. The number of
    cases and the external sources are listed in the decision entry.

---

## 2. Locked decisions (F-series)

| # | Decision | Why |
|---|---|---|
| F1 | **One domain contract.** A domain is a package under `src/napkin2factory/domains/<name>/` exposing one object, `DOMAIN = Domain(...)`, that declares everything it brings: model families (`model/<name>/*.yaml`, their schemas and their `validate_refs`), build rule families (each with the families it runs after and the URI scheme it produces), verify kinds, check stages, gate rows, report sections, doc helpers, vocabulary words, interface kinds, processes, screens and calc packs. `core/registry.py` holds one registry per kind and `domains/__init__.py` lists the installed domains in order. The core never imports a domain by name. The contract is documented once, in `docs/domains.md`, with the toy domain as its worked example | A step is a folder. The core knows the contract, never the domain |
| F2 | **The mechanical code registers in place.** `geometry/`, `drawings/`, `bom/`, `docs/`, `report/` and `rulepacks/` stay where they are and register through the same contract from a thin `domains/mechanical/__init__.py`. No file moves in v0.5. The toy domain, not a rearranged mechanical package, is the proof | Moving files moves goldens and buys nothing; the registries are the seam |
| F3 | **Registries replace lists.** `build_rules` walks the rule-family registry in dependency order instead of nine hardcoded blocks; `TARGET_KINDS` is derived from the families (the existing target names are kept as aliases). Verify kinds, check stages, gate rows, report sections, doc helpers and vocabulary are each a registry with a stable iteration order (installation order, then name). A family's code hash (S-031) comes from the package that registered it, so a domain's rules rebuild when the domain's code changes and nothing else does | Each registry removes one of the eight edits in §0.2 |
| F4 | **The stage ladder is the core's; domains add rows, not rungs.** `intake → design → verify → released` stays (D10, S-090). A domain registers *gate rows*: contributions to the Design or Verify gate (blockers, caveats) that exist only when the domain has content in the product or scope says `in`. `n2f status` shows a domain as a row under its gate ("Wiring: 3 checks OK, 1 needs attention"). An empty domain shows nothing | The owner sees one ladder; a domain is a row on it, present only when it applies (the founding "auto-pass only when empty" rule, made explicit) |
| F5 | **Report sections and doc helpers register.** `report/builder.py::SECTIONS` becomes the registry's view; the template becomes a page shell plus one fragment per section under `report/sections/`. A domain contributes a fragment and the data it renders. Doc helpers (`part()`, `req()`, `bom`, `build_step()`, …) are looked up in a registry; every helper call is still a recorded read (D5). The page stays self-contained and ≤ 20 MB (D13) | The report is the owner's one page; a domain must be able to add to it without editing it |
| F6 | **Open sets are tables; closed sets stay `Literal`.** Processes, finishes, style roles, interface kinds, requirement categories and verify kinds move to `core/data/*.yaml` plus domain additions, validated against the registry at load time with an error that lists the known values. Statuses, severities, labels (`given` / `computed` / `estimate`), concept statuses and ECR states stay `Literal`: they are the system's own words, not a product's | A product that is 3D-printed or anodised must not need a schema change; a status must |
| F7 | **Schema policy.** Additive optional fields with defaults that reproduce the old behaviour do not bump `schema`. A rename, a removal or a changed meaning bumps it, ships a migration function registered in `core/model/migrate.py` by (from, to), and a fixture product of the old version under `tests/fixtures/schema/v<n>/`. `n2f init .` applies pending migrations after a snapshot, prints what changed in owner words, and refuses nothing. Reading a product of a newer schema than the installed system says so plainly and stops. The policy is written once in `docs/schema-policy.md` and `AGENTS.md` points at it | Before the maintainer's own products exist, breaking the schema is free; afterwards it costs real folders (B-0042) |
| F8 | **Card fields are free-form; screens declare what they read.** A concept card's `envelope` and `site` accept any named quantity (the N-series said so; the code did not). The table of known fields with their units and examples (`core/concepts.py`) moves to the screens: each screen declares the fields it reads, their unit kind and an example, and `n2f concept new` writes the skeleton from the installed screens. The generic site fields are renamed `site.width`, `site.depth`, `site.height` ("the space it must fit"); `alcove_*` is read as an alias for one version and the lint says so. Generic screens stay in the system: fits-the-space (with the door-swing term when a massing call is named `door`), mass-vs-lift, blank-vs-stock-sheet, cost band, walls-fit-envelope. The thermal, supply, skin-vs-touch, chamber-volume and controls-vs-hot-face screens move to `examples/kiln/model/screens/` as a product-local pack (F10) | The example stops being the schema; the calc kit stays reusable |
| F9 | **The package never names an example.** Three guards, none of them an English word list (a word like "element" or "door" is generic; a grep for it would be noise). (1) `tests/unit/test_no_example_identifiers.py` derives the forbidden set from the examples themselves: every part id, parameter slug, interface id, assembly id, requirement id, decision id, doc id, calc name and card field name that exists in `examples/*` and not in the templates, and fails on any of them appearing as a literal in `src/napkin2factory/` (docstrings and comments included; `templates/` and `report/vendor/` excluded), plus the example products' names (`kiln`). (2) `AGENTS.md` gains a non-negotiable with its reason: the examples are users of the package, never its vocabulary; a screen, rule, field or default that only an example needs lives in that example's folder (F10). (3) `docs/reviews/TEMPLATE.md`'s architecture set gains a standing question: does any change in this diff teach the package a product's noun, field or default? The style roles become a table (F6) seeded with neutral words (`body`, `opening`, `support`, `controls`, `trim`, `lining`, `fastener`); `door` and `stand` are read as aliases for one version | A folder boundary forbids nothing; a word list cries wolf; identifiers are exact, a rule says why, and a reviewer catches what a grep cannot |
| F10 | **Products carry packs.** A product may hold `model/screens/*.py` (screens for the napkin stage) and `model/rulepacks/*.yaml` with their checks in `model/rulepacks/*.py`, loaded exactly like `model/calcs/` (fresh import per product root, hashed into the `checks` rule's inputs and into the concept build). A pack uses the same contract as an in-tree domain's screens and rule packs; it cannot register rule families, verify kinds, report sections or gate rows (those are the system's). `n2f init --template` may ship packs | The kiln's screens need a home that is the kiln's; a third party's product needs the same seam |
| F11 | **Scope is data.** `n2f.yaml` gains `scope: {<domain>: {state: in \| external \| later, decision: DEC-xxx, note: "…"}}`. Default: a domain with content is `in`; one without content is absent (no row). `external`: the work is done elsewhere; the product must hold a stub module for it — a sub-assembly with `build: external` (extends P7), its `ports:` declared and no children — or validation fails naming the file; the stub's ports are checked like any port. `later`: the domain's requirements and gate rows are excluded from the Design and Verify gates with a visible note ("electrical: later, DEC-021"), never silently; a `later` domain with content is a lint warning ("content exists; set scope to in or remove it"). The release records the scope in the Revision's `release.json` and prints it on the package cover and the report overview. Changing a state is a decision. Also reserved here: a requirement may cite a `load://<id>` (a load case: where, how much, on which faces) under `model/loads/`; v0.5 defines the family and its validation, no solver reads it | The founding "auto-pass only when empty" rule made explicit; the owner's flexibility recorded once and read by every role; the release is the one place scope must not be fudged |
| F12 | **Choices.** `CheckResult.status` gains `choice` (never blocking by itself). A check returning a choice carries `detail.options: [{id, summary, what_it_takes, cost_delta?}]` and `detail.blocks: design \| verify \| release \| none`, the gate it blocks until decided. Choices are written to `build/checks/choices.json` and listed by `n2f status` under "waiting on you", after sign-offs. `n2f decide <check-id> --pick <option> --by "<name>" [--note "…"]` writes a `DEC-` entry naming the check, the option and the evidence keys at that moment, and the row reads `pass` with the decision from then on; when an evidence key changes the choice reopens (D25). `n2f check` never decides. Owner text calls it "a choice" and "waiting on you"; `choice` stays in `--json` and files | The system hands the agent the moment and the words; a weaker model asks as well as a strong one |
| F13 | **When to raise a choice is a rule, not a trait.** The project-manager role gets one rule: never in the interview (the facts do not exist yet); raise an open choice when the owner next touches that area, or before the gate it blocks, one at a time, in the owner's words, with each option's cost and what it takes. Low-consequence choices (`blocks: none`) follow the existing delegation rule: decide conservatively, log, say so in a line. The verifier role classes a choice as inside a module or at a joint, like a failure (P12) | Proactive without bombarding; timing from when the facts first exist |
| F14 | **Verify methods are discoverable and offered by consequence.** `n2f doctor` lists installed domains with their verify kinds, check stages and screens (`--json` too). A requirement's verify kind must be installed. The roles say: offer the stronger method when the consequence is high or the owner's expertise in `operator.yaml` for that domain is `expert`; the method is the requirement's `verify.kind`, chosen once and logged | The tinkerer and the engineer share the requirement; the method is the requirement's, not the persona's |
| F15 | **Splits along the seams.** Each model family's cross-reference validation lives beside its schema as `validate_refs(product, problems)`, called by the loader in a fixed order. Promotion becomes one seeder per family under `concepts/promote/`. Screening becomes `concepts/screens/` (the runner, the generic screens). `geometry/build.py` keeps parts and assemblies apart (`build_part.py`, `build_asm.py`). A new family brings its own validation and its own seeder, so nobody edits a shared file to add one | The five files in §0.2 are where parallel agents collide |
| F16 | **Backward compatible.** Every new field is optional with a default that reproduces v0.4 behaviour; schema stays 1 (F7's additive rule); the product pin moves to `>=0.5,<0.6` at release (S-083). Aliases (`alcove_*`, `door`, `stand`) are read for v0.5 and removed with a migration in a later version | Existing products and the three examples must not move |
| F17 | **Every calc carries its reference cases, and the build runs them.** Today a calc is deterministic and hand-checked only where its author wrote a test: the calc kit has one by-hand test per function (`tests/unit/test_calckit.py`, closed-form arithmetic at 1e-8 or better) and the kiln has its own (`examples/kiln/model/tests/test_calcs.py`); a product calc with no test is accepted silently, and no calc anywhere is checked against a source outside its author's head. Two additions. (1) A calc function may declare `cases` (a module-level list, or a `cases:` block beside it in the product's `model/calcs/`): inputs, the expected result with its unit, a tolerance, and a `source` ("Kanthal handbook worked example 3.2", "hand computation in the docstring"). `n2f check` runs every case of every calc the product uses and reports them as rows (`calc-case` kind); a case that misses is `fail`, a calc with no case is `warn` ("no reference case; add one so a change to this formula is caught"). (2) Each calc-kit pack ships at least one *external* reference case: a worked example from the cited handbook or datasheet, not the author's own arithmetic, so the formula is checked against a source, not against itself. Property tests (monotonic in insulation thickness, bounded by the hot face, exact identities such as S-091's) stay in the test suite with `hypothesis`, one file per pack | The agent that writes a formula must also write the case that would catch its own mistake; a reviewer with no domain knowledge can run it; an external case is the deterministic stand-in for validation until real testing comes |

## 3. Schema additions (all optional; shapes only)

```yaml
# n2f.yaml
scope:                                                     # F11
  electrical: {state: later, decision: DEC-021, note: "the electrician wires it; the box keeps three cable entries"}
  analysis:   {state: external, decision: DEC-022}        # needs a stub module with ports

# model/assemblies/control-box.yaml — a stub for work done elsewhere (F11, extends P7)
build: external
ports: [iface://cable-entry-mains, iface://cable-entry-element]
children: []

# model/loads/shelf-load.yaml — reserved slot (F11); no solver reads it in v0.5
id: shelf-load
on: part://shelf
faces: top
force: 120 N
direction: [0, 0, -1]
case: "four batteries, worst case"

# model/requirements.yaml — a requirement may cite a load case
- id: REQ-012
  statement: The shelf deflects less than 1 mm under the shelf load
  verify: {kind: calc, target: "calc://shelf.deflection", op: "<", value: 1 mm, load: load://shelf-load}

# concepts/C-00x.yaml — free-form envelope and site (F8)
site: {width: 800 mm, depth: 600 mm, circuit: 230V-16A}
envelope: {chamber: [200 mm, 200 mm, 200 mm], target_volume: 8 L}

# build/checks/choices.json — written by n2f check (F12)
- id: rule://hardware-v0/shared-hole-fastening#guard-standoff-bottom
  subject: iface://guard-standoff-bottom
  status: choice
  blocks: release
  options:
    - {id: through-bolt, summary: "one M6 x 50 through bolt per corner", what_it_takes: "4 M6 x 50 bolts replace 12 M6 x 16; the manual's order changes", cost_delta: "-2 USD"}
    - {id: threaded-standoff, summary: "a standoff tapped right through", what_it_takes: "a different standoff part; thread depth to verify"}
  evidence_keys: {...}
  decision: null                                           # DEC-xxx once decided

# core/data/processes.yaml — an open set as a table (F6)
- {id: sheet-metal, title: Sheet metal, flat_pattern: true}
- {id: 3d-print, title: 3D printing, flat_pattern: false}
```

The toy domain's shape (the contract's worked example, under `tests/fixtures/domains/toy/`):

```python
DOMAIN = Domain(
    name="toy",
    families=[ModelFamily("toy", schema=ToyThing, folder="model/toy", validate_refs=validate_toy)],
    rule_families=[RuleFamily("toy", after=["part"], produces="toy://", make_rules=toy_rules)],
    verify_kinds={"toy_prop": evaluate_toy_prop},
    check_stages=[CheckStage("toy", run=toy_checks, after=["interface"])],
    gate_rows=[GateRow(gate="verify", title="Toy", blockers=toy_blockers)],
    report_sections=[ReportSection("toy", "Toy things", group="Product", fragment="toy.html.j2", data=toy_report_data)],
    doc_helpers={"toy": toy_helper},
    vocabulary={"owner": {"toy": "toy thing"}},
    interface_kinds=["toy-joint"],
    processes=[Process("toy-cast", "Toy casting")],
    screens=[toy_screen],
)
```

## 4. CLI surface added or changed
```
n2f doctor                      # lists installed domains: verify kinds, check stages, screens (F14)
n2f status                      # domain rows under their gate (F4); scope rows (F11); "waiting on you" lists choices (F12)
n2f decide <check-id> --pick <option> --by "<name>" [--note "…"]   # F12, in cli/decide.py
n2f init .                      # also applies pending schema migrations after a snapshot (F7)
n2f release                     # records scope; the package cover and the report say it (F11)
make check-fast                 # lint, types, unit and smoke tests; the default land gate
```
Each verb or option lives in its own module under `cli/`. The task that adds it updates the agent
guide's command reference.

## 5. Milestones

Budgets are guesses; record the actual times in the decision entries. Every milestone names the
files it owns. A task edits only its owned files plus the three journals and the docs it names;
if it must touch another milestone's file, it stops and says so in its WIP commit.

**Waves (see §8):** M0 alone → M1 alone → wave 2 = {M2, M3, M4} in parallel → wave 3 = {M5, M6}
in parallel → M7 alone.

### M0 — Baseline (budget 2 h, one agent)
**Build:** land this plan, its decision entry (`S-111`) and the STATUS line. Measure and record
in the entry:
- the files a new step must edit today: do a dry run by adding a no-op rule family, verify kind,
  check stage, report section and doc helper on a scratch branch, count the files, discard it;
- `grep -rlw` counts for the product-word list over `src/napkin2factory/`;
- the line counts of the five files in §0.2;
- `make check` wall time on the host.
**Owns:** `FOUNDATION.md`, `DECISIONS.md`, `STATUS.md`, `BACKLOG.md` only.

### M1 — The contract and the registries (budget 12 h, one agent; the one serial milestone)
**Build:**
- `core/registry.py`: one registry per kind, stable order, `register(domain)`, lookups that
  raise with the known values.
- `core/domain.py`: the `Domain`, `ModelFamily`, `RuleFamily`, `CheckStage`, `GateRow`,
  `ReportSection` dataclasses (the contract's types).
- `domains/__init__.py` (installed list) and `domains/mechanical/__init__.py` (F2: registers
  what exists, in place).
- `core/graph/rules.py`: walk the rule-family registry; derive the targets; the family's package
  hash. `core/graph/impact.py::_static_reads` per registered family.
- `core/checks/evaluators.py`, `engine.py`, `stage.py`: the verify-kind, check-stage and
  gate-row registries (F3, F4).
- `report/builder.py` and the template: sections as fragments (F5). `docs/engine.py`: helpers
  from the registry.
- `core/model/`: the `Literal`s of F6 become table-validated strings (`core/data/*.yaml`).
- The toy domain and the toy product (`tests/fixtures/domains/toy/`,
  `tests/fixtures/products/toy/`), and `tests/unit/test_domain_contract.py` (DoD 2).
- `docs/domains.md`, first version: the contract, each registry, the toy domain walked through.
**Tests:** DoD 2; every existing test green; goldens unchanged (the proof that registering in
place changed nothing); a registry lookup error names the known values.
**Owns:** `core/registry.py`, `core/domain.py`, `domains/`, `core/graph/`, `core/checks/`,
`core/model/` (the `Literal` → table change only), `core/data/`, `report/`, `docs/engine.py`,
`tests/fixtures/domains/`, `tests/fixtures/products/toy/`, `docs/domains.md`.

### M2 — Schema policy, the migration hook, and calc reference cases (budget 7 h)
**Build:** `core/model/migrate.py` (registry by (from, to); `pending(product)`, `apply`); the
upgrade path in `cli/init.py` (snapshot, apply, owner-word summary; a newer schema stops with a
plain message); `tests/fixtures/schema/v1/` (a copy of the bracket as of v0.4); a test
migration to a throwaway version that round-trips; `docs/schema-policy.md`; the `AGENTS.md`
pointer; the fixture products under `tests/fixtures/` gain the fields the policy needs.
Then F17: `cases` on calc functions and the `cases:` block in `model/calcs/`; the `calc-case`
rows in `core/checks/calcs.py` (run by the `checks` rule, hashed with the calc source); the
"no reference case" lint; the calc kit's packs each gain one external case with its source
(`thermal_enclosure`: a layered-wall worked example from a handbook; `power`: the element
sizing example from the wire maker's handbook; `mass_cost`: a density row), marked `[verify]`
where the source is a datasheet; the kiln's calcs gain cases from its existing by-hand tests;
a `hypothesis` property file per pack (`tests/unit/test_calckit_properties.py`).
**Tests:** pending detection, apply with snapshot, refusal wording for a newer schema, the
round-trip; DoD 12.
**Owns:** `core/model/migrate.py`, `cli/init.py`, `tests/fixtures/schema/`,
`docs/schema-policy.md`, `tests/unit/test_migrate.py`, `core/checks/calcs.py`, `core/lint.py`
(the one rule), `calckit/` (cases only), `examples/kiln/model/calcs/`,
`tests/unit/test_calckit*.py`, `tests/fixtures/calcs/`.

### M3 — The kiln out of the system (budget 9 h)
**Build:**
- `core/concepts.py`: free-form `envelope` and `site` (F8); the field table removed; the
  skeleton written from the installed screens' declarations; the `alcove_*` alias with its lint
  note.
- `concepts/screens/`: the runner and the generic screens (fits-the-space with the door term,
  mass-vs-lift, blank-vs-stock-sheet, cost band, walls-fit-envelope), each declaring the fields
  it reads; `concepts/screening.py` reduced to the runner's entry point (F15).
- Product-local packs (F10): `model/screens/*.py` and `model/rulepacks/` loaded like calcs,
  hashed into the concept build and the `checks` rule.
- `examples/kiln/model/screens/heated_enclosure.py`: the thermal, supply, skin-vs-touch,
  chamber-volume and controls-vs-hot-face screens, moved verbatim, reading the kiln's card
  fields by name; the kiln cards use `site.width`; the kiln's board golden must not change.
- The style roles table (F6/F9) with neutral words and the two aliases.
- `tests/unit/test_no_example_identifiers.py` (F9), green; the `AGENTS.md` non-negotiable and
  the `docs/reviews/TEMPLATE.md` question.
**Tests:** DoD 3; the generic screens on the bracket and enclosure cards unchanged; a
product-local screen runs and its hash invalidates the concept build; a product-local rule
pack runs in `n2f check`.
**Owns:** `core/concepts.py`, `core/model/concepts.py`, `core/model/style.py`, `concepts/`
(not `promote.py`), `rulepacks/concept-v0.yaml`, `rulepacks/concept_checks.py`,
`examples/kiln/concepts/`, `examples/kiln/model/screens/`,
`tests/unit/test_no_example_identifiers.py`, `tests/unit/test_screening*.py`,
`goldens/kiln-board.json` (must not change), `AGENTS.md` (the one rule),
`docs/reviews/TEMPLATE.md` (the one question).

### M4 — Scope as data (budget 7 h)
**Build:** `scope:` in `core/model/manifest.py` (F11); `build: external` stubs and their
validation beside `core/model/assemblies.py`; `model/loads/` family and its validation (the
reserved slot); gate rows read scope (`later` excluded with the note; the lint for content
under `later`); `n2f status` scope rows; `release.json` scope, the package cover line and the
report overview line; the kiln's `scope: {electrical: later}` with its `DEC-`; a fixture with
an external stub and one without.
**Tests:** DoD 5; the release cover text; the report overview text; impact unchanged by scope.
**Owns:** `core/model/manifest.py`, `core/model/assemblies.py` (the `external` value and its
`validate_refs`), `core/model/loads.py`, `core/checks/stage.py` (scope reads only; M1 lands
first), `ecr/release.py`, `cli/check.py` (status rows), the report overview fragment,
`examples/kiln/n2f.yaml`, `examples/kiln/model/decisions.yaml`, `tests/fixtures/scope/`.

### M5 — Choices (budget 7 h)
**Build:** `choice` in `core/checks/results.py` (F12) and the engine's handling (never blocks;
`blocks` honoured by the gate it names); `build/checks/choices.json`; `n2f status` "waiting on
you"; `cli/decide.py`; the `DEC-` entry it writes and the reopen-on-evidence rule; the
hardware-stage rule for the kiln's shared-hole fastening (DoD 6), with its two options and
hardware counts; the project-manager and verifier role text (F13); the owner words.
**Tests:** DoD 6; a decided choice reads `pass` with its decision; an evidence change reopens
it; `n2f check` never writes a decision; the status wording.
**Owns:** `core/checks/results.py`, `core/checks/engine.py` (the status handling only; M1
lands first), `core/checks/hardware.py` (the one rule), `cli/decide.py`, `cli/check.py`
(the "waiting on you" block; M4 owns the scope rows, so the two tasks each add one
function and rebase), `templates/_common/roles/pm.md`, `templates/_common/roles/verifier.md`,
`examples/kiln/model/interfaces/guard-standoff-bottom.yaml`, `tests/unit/test_choices.py`.

### M6 — Splits and the fast gate (budget 6 h)
**Build:** `validate_refs` beside each schema and the loader as orchestrator (F15; the loader
under 400 lines); `concepts/promote/` one seeder per family; `geometry/build_part.py` and
`build_asm.py`; `make check-fast` and `make land` using it; the `-m "not full"` markers
checked; record the line counts and the two check times.
**Tests:** every existing test green, goldens unchanged (this milestone moves code and must
change no behaviour); `tests/unit/test_task_script.py` with the new gate.
**Owns:** `core/loader.py`, `core/model/*.py` (the `validate_refs` functions only),
`concepts/promote.py` → `concepts/promote/`, `geometry/build.py` → the two files, `Makefile`,
`scripts/land.sh` (or wherever `make land` lives), `tests/unit/test_promote*.py`.

### M7 — Docs, simulations, gates, close-out (budget 7 h)
- `docs/domains.md` final; the agent guide; `docs/vocabulary.md`; the four roles synced with
  `make templates`; `n2f doctor` listing (F14).
- The two simulations: a fresh-context agent adds a second toy domain from `docs/domains.md`
  alone (DoD 2, the count); a scripted owner session where a choice is raised after the first
  build (DoD 6). Transcripts under `tests/e2e/domain-transcripts/` and
  `tests/e2e/intake-transcripts/`.
- Gates E and F from `docs/reviews/TEMPLATE.md`; blockers fixed.
- The maintainer judges the status screenshot and the scope line (S-078).
- `HANDOFF-REPORT-v0.5.md`; version files and pins; `make check-full` from a clean clone.
- Tagging is the maintainer's call.

## 6. `make check` / `make check-full` growth
- `make check-fast` is new and is the land gate; `make check` keeps the end-to-end tests and
  the two small examples; `make check-full` is unchanged in shape.
- The toy product builds in the unit tests in seconds; nothing new runs the kiln.
- The two simulations are run by the M7 agent, not by CI; CI checks the transcripts exist.
- Budget: `make check` must not pass 10 min on the host. Record the number.

## 7. Risks
| Risk | Watch | Fallback |
|---|---|---|
| Registering in place changes a hash and every golden moves | M1's first full run | The family's package hash must equal today's subtree hash for the mechanical families; fix the hash, never regenerate goldens for this |
| The registries become a second place to forget: a domain registers a rule family but not its report section | The toy domain test asserts every registry sees the domain; the contract doc's checklist | Make `Domain` fields required where a domain cannot be useful without them |
| Free-form card fields lose the lint that caught unit mistakes | The screens declare units; the lint reads them | Keep the unit check on every declared field; undeclared fields lint as "no screen reads this" |
| Moving the kiln's screens changes a screening number | The kiln board golden | Move verbatim first, refactor after; the golden must not move inside M3 |
| `later` lets safety requirements vanish from the gate | Safety requirements are never excluded by scope: a `later` domain's safety rows stay `needs-human` | Test it: a safety requirement allocated to a `later` domain still blocks release |
| Choices become a way to defer failures | A check returns `choice` only when every option is a valid design; a failure stays a failure | Gate E asks the question with a fixture |
| Three tasks in wave 2 all touch `core/loader.py` | Each adds one `validate_refs` call; rebase before landing | If the conflicts bite, M6's loader split moves to the start of wave 3 and the others land after it |
| The check time budget | Measured at M6 | Move the slowest end-to-end files behind `-m full` |

## 8. How the overseer runs this plan
One agent oversees; subagents build. The overseer never edits code in a wave it is supervising:
it writes briefs, reads transcripts and landed diffs, runs `make check` on `main` between waves,
and keeps the journals.

1. **Brief per task.** Each subagent gets: this file's §0 and §2, its milestone section, the
   files it owns, the files it must not touch, the DoD items it closes, and the commit rules
   (`S-NEW<n>`, `B-NEW<n>`). It starts with `make task NAME=v05-m<n>-<slug>` and lands with
   `make land`; on landing, placeholders become ids, so two tasks never collide on a number.
2. **Waves.** M0, then M1 alone (everything else registers through it). Wave 2 is M2, M3 and M4
   at once: their owned files are disjoint except `core/loader.py` (one call each) and
   `core/checks/stage.py` (M4 reads scope in gate rows M1 defined). Wave 3 is M5 and M6 at once:
   M5 adds to the checks engine and status, M6 moves the loader, promotion and build code; they
   share `cli/check.py` by one function each. M7 alone.
3. **Between waves:** `make check` on `main`; if red, `git bisect run make check` names the task
   (history is linear, S-097). The overseer records the wave's measured times in `STATUS.md`.
4. **A subagent that needs another task's file stops**, commits `WIP:` with what it needs, and
   the overseer resolves it (reassign the file, or serialise the two tasks). No subagent edits a
   file it does not own.
5. **Review gates** are fresh-context subagents briefed from `docs/reviews/TEMPLATE.md` with
   the questions in DoD 10; they see the repo and the brief, never this conversation.
6. **Push only when the maintainer asks.**
