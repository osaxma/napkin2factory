# Task: v0.6 M1 — the family and the joint (milestone task; commit subjects `M1: …`)

Task folder: /Users/wakeel/napkin2factory/.worktrees/m1-family (branch task/m1-family).
Read ELECTRICAL_STAGE.md §3 and §5 "M1" (lines 162–251), `docs/v06-baseline.md` (the kiln
survey; §4 and §5 especially), and the overseer's decisions file
docs/v06-handoff/overseer-decisions-m1.md
(binding; it amends E2/E3/E6 where it says so; you record it as a DECISIONS.md entry).

## What landed in M0 that you build on (read their entries)
- S-142: `Domain.release_files` / `ReleaseFiles` (a domain's build files in the release package).
- S-143: `RuleFamily.before=` (the `elec` family declares `after=("part",), before=("doc",)` so
  the manual's wiring helpers read this build's files). Not `before=("bom",)`: E5 is decided.
- S-144: an interface kind whose spec subclasses `BoltPatternSpec` gets the core's hole cut,
  hole match and alignment, then the kind's own `check` (worse status wins). `BoltPatternSpec`
  is public (`docs/domains.md` §1, §3.9). A party with no geometry (a bought gland) is skipped
  with a plain sentence.
- S-145: E5 — no parts-list seam; the conductors stay in the domain's schedule (+ a per-conductor
  "cable to buy" total, M2's).
- S-146: `calckit/wiring.py` (`conductor(id)`, `conductors(region)`, `earthing(code)`,
  `colour(region, role)`) and its three tables. Use it; do not copy numbers.
- The scope words (B-0115–B-0119) landed just before you: read their entries; `later` and
  `external` words come from the core now.

## Build
The package `src/napkin2factory/domains/electrical/`, laid out so the three wave-2 tasks never
share a file. **You write every file below; afterwards you own only the top-level ones.**
- `__init__.py` — `DOMAIN = Domain(name="electrical", title=..., root=..., ...)` composed from
  the subpackages' tuples (below) plus `model.py`'s families and `interfaces.py`'s kind;
  `categories=("electrical",)`; `release_files=` from `outputs`. Nothing else lives here.
- `model.py` — the schemas and `validate_refs` (D5-safe, strict `Model`s, docstrings):
  families `supply` (`model/electrical/supply.yaml`; decide the folder/id shape so the
  plan's path holds and a product may later add conductors: e.g. supply family over
  `model/electrical/` with `id: supply`, and product conductor rows as their own family
  `conductor` in `model/electrical/conductors/`; write the decision), `device`
  (`model/electrical/devices/*.yaml`, `device://`), `circuit`
  (`model/electrical/circuits/*.yaml`, `circuit://`), `conductor` (product rows, optional).
  Schemas per ELECTRICAL_STAGE §3 as amended by the decisions file: `Device` (part, role,
  rating, terminals, class, instance, contact, notes), `Supply` (voltage, phases, frequency,
  rating — a quantity or `param://`, earthing — an `earthing.yaml` code, region, protection),
  `Circuit` (purpose: power/control/sensing/earth, protection, connections, earth/bonded_via,
  notes), `Connection` (from, to, conductor, length, via, colour optional). Every field the
  wave-2 tasks will need is declared now (they add none: a schema field added later is a
  registration change). `validate_refs`: a device's part exists; device count per part (the
  decisions file, point 1); a connection end names an existing device and one of its
  terminals (error naming both, and listing the device's terminals); `part://x#T` shorthand
  rules; conductor ids exist in `calckit.wiring` or the product's rows; protection resolves;
  `via` names a `cable-entry` interface whose `passes` lists the circuit; the supply exists
  when any circuit does; a device with `terminals: []` is a warn ("its terminals are not
  sourced yet; read them from the datasheet named on the part") never an error. Every
  problem names its file, the thing, and the fix.
- `interfaces.py` — `CableEntrySpec(BoltPatternSpec)` (`pattern: circle`, `count: 1`,
  `diameter`, `passes: [circuit://…]`), `InterfaceKind("cable-entry", "Cable entry",
  spec=CableEntrySpec, check=check_cable_entry)`; the check: the circuits named exist and have
  a connection `via` this entry, and the entry joins the box to the gland (owner words). The
  external stub's port check (F11, E4, DoD 5): a circuit whose connection goes `via` an entry
  that is a port of a `build: external` assembly is fine; a circuit whose device sits inside
  an external assembly and whose entry is not one of its `ports:` is a validation error naming
  the assembly file and the missing port.
- Subpackages, each exporting its registration tuples; you write them as **stubs that run**
  (return no rows / no outputs / `None`) with the exact names and signatures the contract
  gives, so wave 2 fills function bodies and may add private helpers in its own subfolder only:
  - `outputs/` (M2's): `RULE_FAMILIES = (RuleFamily("elec", ..., after=("part",),
    before=("doc",), produces="circuit://", output_dir="electrical", static_reads=...),)`,
    `RELEASE_FILES = (ReleaseFiles("electrical", ("*/diagram.svg", "schedule.csv",
    "labels.csv", "cables.csv"), "wiring diagrams, cable schedule, terminal labels"),)`;
    module files `rules.py`, `diagram.py`, `schedule.py`, `export_kicad.py` (stubs).
  - `checks/` (M3's): `VERIFY_KINDS = (VerifyKind("circuit", ..., target_schemes=("circuit",),
    compares=True, ...),)`, `CHECK_STAGES = (CheckStage("electrical", ...,
    after=("interface",), reads=...),)`; `stage.py`, `verify.py`, `calcs.py`,
    `electrical-v0.yaml` (stub rule list).
  - `owner/` (M4's): `GATE_ROWS` (Design: "Wiring" with the E7 blocker — you implement THIS
    row fully, it is M1's test; Verify: "Wiring checks" via `check_rows_state`, stubbed),
    `REPORT_SECTIONS = (ReportSection("wiring", "Wiring", group="Product",
    fragment="owner/wiring.html.j2", data=..., reads=..., show=...),)` (a stub fragment that
    renders an empty card; `show` false without content), `DOC_HELPERS` (`circuit`,
    `cable_schedule`, `terminal_labels`), `VOCABULARY` (`{"owner": {"device": "electrical
    device", "circuit": "circuit", "supply": "supply", "electrical": "wiring", ...}}`, M4
    refines), `SCREENS` (stub; M4 moves the supply screen in), `CONTEXT` (stub).
  Code hashing: decide `Domain.code` / `RuleFamily.code` so an edit of `owner/` does not rerun
  the `elec:` rules (e.g. `code=("outputs", "model.py", "interfaces.py")` on the family if the
  contract allows files; else restructure), and write why.
- Install it: add `"napkin2factory.domains.electrical"` to `INSTALLED` in
  `src/napkin2factory/domains/__init__.py`. Then fix every test that asserts an exact domain
  list or position (docs/domains.md §1 lists them: `test_domain_contract.py`'s exact lists,
  `reg.screens()[0]`, `STYLE_ROLES[-1]`, `ctx["domains"][0]`, the toy row being last …) to the
  membership form §1 shows. That is the only edit you make to the toy's test file.
- Fixture `tests/fixtures/electrical/minimal/`: one supply (upstream protection), one device
  on a part, one circuit, one cable entry on a box part with geometry and a bought gland, a
  requirement or two (`category: electrical`). Generic names (box, gland, heater, switch).
- Tests `tests/unit/test_electrical_model.py`: the fixture loads and validates; each
  validation error (bad part, too many devices per part, unknown terminal with the list,
  ambiguous `part://` shorthand, unknown conductor, `via` not passing, missing supply,
  missing port on an external stub) names its file and the fix; `terminals: []` is a warn; a
  device with no connection in a product whose scope is `in` is a Design-gate blocker (E7)
  and the gate row is absent for a product with no `model/electrical/`; a `later` product's
  devices give the core's lint warn ("content exists; set scope to in or remove it"); the
  entry's hole is cut in the box and matched (S-144), the gland skipped with its sentence;
  `n2f doctor` lists `electrical`. The contract tests of docs/domains.md §8 for what M1
  brings (families, interface kind, categories, gate row): copy the toy's pattern.
- E12: prove a product without `model/electrical/` sees no electrical word: run the
  bracket and enclosure goldens (`uv run pytest tests/golden -q`) and `n2f status`,
  `n2f check --all` and the report on a temp copy of the bracket, grepping for "electrical",
  "wiring", "circuit"; record what you ran.

## Owns
`src/napkin2factory/domains/electrical/` (all of it, now; after landing the top-level files
`__init__.py`, `model.py`, `interfaces.py` stay yours, the subfolders pass to wave 2),
`src/napkin2factory/domains/__init__.py` (`INSTALLED` only), `tests/fixtures/electrical/minimal/`,
`tests/unit/test_electrical_model.py`, the exact-list assertions in
`tests/unit/test_domain_contract.py` and any other test that asserts the installed domain list,
`DECISIONS.md`, `BACKLOG.md`, `STATUS.md` (the M1 line under v0.6).

## Must not touch
Anything under `src/napkin2factory/core/`, `report/builder.py`, `docs/engine.py`,
`cli/check.py` (E10: stop and WIP), `examples/` (read only; the kiln is M5's), `docs/domains.md`
(if you find it wrong or short, list where in your report: the overseer fixes it).

## DoD items
Feeds DoD 1 (the count: M1 must change no core file), 3, 5 (the port check), 12 (E12).
Run: `make lint`, `make types`, your tests, `tests/unit/test_domain_contract.py`, the goldens,
the E12 greps, then `make land`.
