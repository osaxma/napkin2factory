# Domains: the contract (v0.5, FOUNDATION F1)

A **domain** is a step of making a product — mechanical, electrical, analysis, a
manufacturer's rule set — packaged as a folder that registers what it brings. The core knows
this contract, never a domain: adding a domain edits **no file under
`src/napkin2factory/core/`**, and you should not need to open one either. This page is the
whole contract: what you can register, the exact signatures you fill in, the objects you are
handed, how a domain is installed, and the test that proves it. If you had to open a core file
to finish, this page is missing something: say which file and why in your report.

## 0. What to copy

| file | what it is |
|---|---|
| `tests/fixtures/domains/toy/__init__.py` | the **toy domain**: one of everything, each as small as it can be (one file) |
| `tests/fixtures/domains/toy/toy.html.j2` | its report fragment |
| `tests/fixtures/domains/__init__.py` | makes `tests.fixtures.domains` a package (one docstring line) |
| `tests/fixtures/products/toy/` | the product that uses every piece of the toy (11 small files) |
| `tests/unit/test_domain_contract.py` | the test that proves every registry sees the toy: copy its fixture and the tests marked in §8 |
| `tests/conftest.py` | `copy_product`, `FIXTURES`, `EXAMPLES` (test helpers; not core) |
| `src/napkin2factory/domains/__init__.py` | `INSTALLED`, the list of shipped domains (not core) |
| `src/napkin2factory/domains/mechanical/__init__.py` | everything v0.4 did, registered in place (F2): the second, bigger example |

A second domain is a copy of the toy with every name changed (§1, "names are unique").

## 1. What a domain is, where it lives, how it is installed

A Python package exposing one object, `DOMAIN`:

```python
# my_domain/__init__.py
from pathlib import Path
from napkin2factory.core.domain import Domain   # and the types of §3 it uses

DOMAIN = Domain(
    name="wiring",                         # unique; also the key of its code hash
    title="Wiring: circuits, cables, connectors",
    root=Path(__file__).resolve().parent,  # every relative path below is relative to it
    families=(...), rule_families=(...), verify_kinds=(...), check_stages=(...),
    gate_rows=(...), report_sections=(...), doc_helpers={...}, vocabulary={...},
    interface_kinds=(...), processes=(...), finishes=(...), categories=(...),
    drivers={...}, style_roles=(...), screens=(...), context=(...),
)
```

Every field except `name` is optional; declare only what the domain brings. The full field
list, with types and defaults, is §4.1.

**Installed for good (a shipped domain).** The package lives at
`src/napkin2factory/domains/<name>/` and is installed by adding its module path to `INSTALLED`
in `src/napkin2factory/domains/__init__.py`:

```python
INSTALLED: tuple[str, ...] = ("napkin2factory.domains.mechanical", "napkin2factory.domains.wiring")
```
Installation order is the order every registry iterates in. The first registry lookup
imports each module and registers its `DOMAIN`. That file is not part of the core.

**Installed for a test (or a simulation).** The package lives anywhere importable, e.g.
`tests/fixtures/domains/<name>/__init__.py`, and is registered for a block of code:

```python
from napkin2factory.core.registry import installed
from tests.fixtures.domains import toy

with installed(toy.DOMAIN):
    ...  # load, build, check, status, report, context: everything sees the domain
```
`register(domain)` and `unregister(name)` (same module) do the same without a block.
`installed`, `register` and `unregister` change one process-wide registry, so:
- **Load the product inside the block.** A requirement naming your verify kind, a URI of
  your scheme or your interface kind only validates while the domain is registered.
- **Run the CLI in-process** (`typer.testing.CliRunner().invoke(app, [...])` with
  `from napkin2factory.cli.app import app`). `tests.conftest.n2f` starts a new Python
  process, which sees only `INSTALLED`.
- **Names are unique across domains.** A rule family, verify kind, check stage, report
  section id, doc helper, model family or screen named like another domain's is refused at
  `register` ("domain 'b' registers verify kind 'x', which domain 'a' already registers").
  Also give your model family a URI scheme nobody uses: the system's are `req`, `dec`, `ecr`,
  `param`, `part`, `asm`, `iface`, `doc`, `calc`, `rule`, `bom`, `manifest`, `drawing`,
  `load`, `set`, plus every other domain's. Interface kinds, processes, finishes, categories,
  drivers, style roles and vocabulary terms do not error: the first one registered wins, so
  pick new words.
- **Do not assert the whole domain list.** The toy test asserts
  `[d.name for d in registry().domains] == ["mechanical", "toy"]`; yours should assert
  `"<name>" in [d.name for d in registry().domains]`, so both pass in any order.

**What a domain may import** (the public API; anything else is the core's business and may
change). Each name is described in §3 and §4.
- `napkin2factory.core.domain`: the contract's types (§4.1).
- `napkin2factory.core.registry`: `registry()`, `installed`, `register`, `unregister`,
  `UnknownName`.
- `napkin2factory.core.model.base`: `Model`, `Slug`, `PartUri`, `AsmUri`, `ReqUri`,
  `ParamUri`, `IfaceUri`, `DocUri`, `CalcUri`, `UriField`, `Quantity`, `uri_of`.
- `napkin2factory.core.model`: `RuleRow` (a napkin screen's row), `ConceptCard`, `Part`, `Verify`.
- `napkin2factory.core.model.interfaces.InterfaceSpec`.
- `napkin2factory.core.graph.rules`: `Rule`, `RuleBuild`, `RunContext`, `RunResult`.
- `napkin2factory.core.graph.hashing`: `sha256_json(obj)`, `sha256_file(path)`, `sha256_text(s)`.
- `napkin2factory.core.checks.results.CheckResult`.
- `napkin2factory.core.checks.stage.check_rows_state`.
- `napkin2factory.core.checks.choices`: `offer`, `Option` (a check that hands the owner a choice).
- `napkin2factory.core.units`: `parse_quantity`, `compare`, `format_quantity`, `is_quantity`,
  `magnitude_in`.
- `napkin2factory.concepts.screens`: `CardField`, `reads`, `ScreenValues`.
- For tests: `napkin2factory.core.loader` (`load_product`, `validate`),
  `napkin2factory.core.graph.runner` (`run_build`, `explain_build`),
  `napkin2factory.core.graph.rules.build_rules`, `napkin2factory.core.graph.impact`
  (`compute_impact`, `parse_set`), `napkin2factory.core.checks.evidence.evidence_key`,
  `napkin2factory.core.context` (`module_context`, `render_text`),
  `napkin2factory.concepts.screening.screen`, `napkin2factory.core.concepts.render_card`,
  `napkin2factory.core.model.style` (`STYLE_ROLES`, `STYLED_ROLES`, `ROLE_ALIASES`,
  `canonical_role`, `StyleFile`), `napkin2factory.cli.app.app`. Signatures in §8.

## 2. The toy, end to end

What happens to the toy domain and its product, in the order a build meets it. Each step
names the registry (§3) and the assertion in `tests/unit/test_domain_contract.py` that proves it.

1. **The product holds a toy thing.** `tests/fixtures/products/toy/model/toy/widget.yaml`:
   ```yaml
   id: widget
   name: Widget
   part: part://plate
   glow: 3
   ```
   The **model family** `toy` (§3.1) reads `model/toy/*.yaml` with the schema `ToyThing`;
   `load_product(root).families["toy"]["widget"]` is the object; `toy://widget` names it.
   `validate_toy` adds a problem when `part:` names no part.
2. **The build runs the toy rule after the part.** The **rule family** `toy` (§3.2,
   `after=("part",)`) makes one rule, `toy:widget`, that writes `build/toy/widget.json` and
   records the reads `toy://widget#glow`, `toy://widget#name` and `part://plate`. The build
   runs `part:plate`, then `toy:widget`, then `checks` (`test_rule_family_runs_after_…`).
   `n2f build --target toy` builds the toy and what it waits for, nothing else.
3. **A requirement is checked by the toy's verify kind.** `model/requirements.yaml`:
   ```yaml
   - id: REQ-001
     title: The widget glows
     statement: The widget glows at 2 % of full glow or brighter.
     category: fun                       # the toy's requirement category (§3.10)
     verify: {kind: toy_glow, target: "toy://widget", op: ">=", value: 2}
     allocation: [part://plate]
   ```
   The **verify kind** `toy_glow` (§3.3) reads `build/toy/widget.json` and compares: the
   `req://REQ-001` row of `build/checks/checks.json` is `pass`, "glow = 3 >= 2", with the
   evidence key of `toy://widget` (`test_verify_kind_evaluates`).
4. **The checks get a row per toy thing.** The **check stage** `toy` (§3.4, after
   `interface`) adds the row `toy://widget`, kind `toy`, "Widget glows" (`test_check_stage_reports`).
5. **The Verify gate gets a row.** The **gate row** "Toy things" (§3.5) reads the stage's rows:
   `n2f status` prints `Toy things: 1 check: 1 OK` under Verify (`test_gate_row_shows_in_status`).
6. **The report gets a section.** The **report section** `toy` (§3.6) renders `toy.html.j2`
   at the end of the Product group; the report rule records `toy://widget#glow`
   (`test_report_section_renders`).
7. **A manual page reads the toy.** `model/docs/guide.md` says
   `The {{ toy("widget").name }} sits on the {{ part("plate").name }}.`; the **doc helper**
   `toy` (§3.7) records `toy://widget#name` with its value (`test_doc_helper_records_a_read`).
8. **The owner reads a word, not a scheme.** The **vocabulary** term `toy` (§3.8) makes
   `n2f check --all` say "toy thing widget" (`test_vocabulary_word_in_the_owner_view`).
9. **A joint of the toy's kind.** `model/interfaces/plate-peg.yaml` has `kind: toy-joint`,
   `spec: {snap: firm}`: the **interface kind** (§3.9) validates the spec with `ToySpec` and
   checks it ("it snaps firm"); an unknown kind is an error listing the known ones
   (`test_interface_kind_validates`).
10. **A part made by the toy's process.** `model/parts/plate.yaml` has `process: toy-cast`
    (§3.10); the general rule pack's `custom-part-complete@plate` row passes
    (`test_process_passes_the_general_rule_pack`).
11. **A napkin card is screened.** The **screen** `toy` (§3.11) reads `envelope.toys` and adds
    the estimate `toy_count` and the row `toy-count`; `n2f concept new` writes "toys (like 5)"
    into a card skeleton (`test_screen_runs_on_a_card`, `test_screen_declares_its_fields_and_phase`).
12. **A style role.** `toy-shell` (alias `casing`, §3.10) is a valid `role:` while the toy is
    installed, keys a palette colour, and a part naming it reads the toy's code hash
    (`test_style_role_is_a_role_while_the_domain_is_installed`).
13. **A module's context.** The **context contribution** (§3.12) adds
    `- toy://widget: Widget on part://plate (glow 3)` to `n2f context asm://box`
    (`test_context_contribution`).
14. **Impact and hashing.** `n2f impact --set toy://widget#glow=5` names `toy:widget` and not
    `part:plate`, and the rebuild reruns no more than that (`test_impact_is_a_superset_…`); a
    change to a file of the toy's package reruns `toy:widget`, `validate`, `doc:guide`, `checks`
    and `report`, and no part, assembly, drawing or bom rule (`test_a_domain_code_change_…`).

## 3. The registries, one by one

Each registry lists its entries in installation order (then the order the domain declares
them); rule families and check stages are ordered by their `after` lists. Every lookup of an
unknown name raises `UnknownName` (a `ValueError`) listing the known values ("unknown verify
kind 'x'; known: …"). `registry()` returns the registry; §8 lists the method that shows each one.

### 3.1 Model families — `families=(ModelFamily(...),)`
Files the product holds for the domain: `<folder>/*.yaml`, one object per file.

```python
from napkin2factory.core.model.base import Model, PartUri, Slug

class ToyThing(Model):          # strict: an unknown key is an error
    id: Slug                    # must equal the file name without .yaml
    name: str
    part: PartUri               # a URI field restricted to part://
    glow: int = 1

def validate_toy(product, problems) -> None:
    for thing in product.families.get("toy", {}).values():
        if thing.part.id not in product.parts:
            problems.add(product.files[f"toy://{thing.id}"], f"toy://{thing.id}",
                         f"names {thing.part}, which is not a part", "name an existing part",
                         rule="toy")

ModelFamily("toy", schema=ToyThing, folder="model/toy", validate_refs=validate_toy)
```
- `ModelFamily(name, schema, folder, validate_refs=None, scheme="", id_pattern=r"[a-z0-9]+(?:-[a-z0-9]+)*")`.
- Loaded with the product: `product.families["toy"]` maps id → object (an empty dict, or no
  key at all, when the folder is absent: use `.get("toy", {})`).
- Each object is `<scheme>://<id>` (`scheme` defaults to the family name; `id_pattern` is
  the regex an id must match). Requirements, sign-offs, decisions' links, reads and prose
  can name it; `product.files["<scheme>://<id>"]` is its file.
- `validate_refs(product, problems)` runs after the core's own cross-checks: one problem per
  broken reference, `problems.add(file, subject, message, hint="", severity="error", rule="")`
  (`severity="warn"` for a warning).
- A read of `<scheme>://<id>#<field>` is valued from the declared field (a manual page or a
  rule that reads it reruns when it changes); a read of `<scheme>://<id>` is the output hash
  of the rule that produces it (§3.2), else the object's own hash.

### 3.2 Build rule families — `rule_families=(RuleFamily(...),)`
Steps of `n2f build`. `make_rules(b: RuleBuild) -> list[Rule]` returns this family's rules
for `b.product`.

```python
RuleFamily("toy", toy_rules, after=("part",), produces="toy://", output_dir="toy",
           static_reads=toy_static_reads)

def toy_rules(b):
    return [Rule(id=f"toy:{tid}", kind="toy", produces=f"toy://{tid}", inputs={},
                 run=make_run(tid), description=f"the glow record of toy://{tid}",
                 depends_on=[f"part:{t.part.id}"])
            for tid, t in sorted(things(b.product).items())]

def make_run(tid):
    def run(ctx):                                    # ctx: RunContext
        thing = things(ctx.product)[tid]
        record = {"id": tid, "glow": thing.glow, "part": str(thing.part)}
        out = ctx.build_dir / "toy" / f"{tid}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
        return RunResult(reads=[f"toy://{tid}#glow", str(thing.part)], outputs=[out],
                         output_hash=sha256_json(record))
    return run
```
- `RuleFamily(name, make_rules, after=(), produces="", also_produces=(), code=(), reads_all=False, targets=(), output_dir=None, static_reads=None)`.
- A rule's `kind` is the family name and its id is `<family>:<id>`. `depends_on` lists the
  rule ids it waits for (rule ids of the mechanical domain: `validate`, `part:<id>`,
  `asm:<id>`, `drawing:<id>`, `bom`, `asmsheet:<id>`, `doc:<id>`, `checks`, `report`, `site`).
- `run(ctx)`: write under `ctx.build_dir / <output_dir>`; **every value you use must be in
  `reads`** (D5: a recorded read is what makes a change rerun the rule). A read is a URI
  (`part://plate`: that rule's output hash) or a URI with a field (`toy://widget#glow`: the
  value). `output_hash` is what downstream rules see when they read your URI.
- `after`: families whose rules run first (the mechanical ones: `validate`, `part`, `asm`,
  `drawing`, `bom`, `asmsheet`, `doc`). The family goes after them and always **before**
  `checks`, `report` and `site`, which read everything (`reads_all=True`; do not set it).
- `produces="toy://"`: a downstream read of `toy://<id>` resolves to the output hash of rule
  `toy:<id>`. `also_produces` lists further keys a rule of the family produces.
- Code hash: leave `"code"` out of `inputs`; the core adds the hash of your domain's code
  (the `code` folders, else `Domain.code`, else the whole `root`), so editing your domain
  reruns your rules and nothing else. Put any other input (a parameter value, a table hash)
  in `inputs` as `name → hash string`.
- `static_reads(product, rule) -> list[str]`: the reads `n2f impact` assumes before the first
  build; afterwards it uses the recorded ones.
- `output_dir`: the folder under `build/` the family writes; a rule's files there are removed
  when the rule disappears.
- Targets: the family's own name is a `--target` (`n2f build --target toy`, and
  `run_build(product, target="toy")`): itself and every family it waits for. `targets=("x",)`
  adds aliases. An unknown target is an error listing the known ones.

### 3.3 Verify kinds — `verify_kinds=(VerifyKind(...),)`
How a requirement is checked (`verify.kind`).

```python
VerifyKind("toy_glow", evaluate_glow, target_schemes=("toy",), compares=True)

def evaluate_glow(ctx, req, res, evidence) -> str | None:
    v = req.verify                                   # kind, target (a Uri), op, value
    path = ctx.build_dir / "toy" / f"{v.target.id}.json"
    if not path.is_file():
        res.message = f"{v.target} has not been built"
        return "skip"
    record = json.loads(path.read_text(encoding="utf-8"))
    glow = parse_quantity(record["glow"])
    res.message = f"glow = {format_quantity(glow)} {v.op} {format_quantity(v.value)}"
    evidence[str(v.target)] = sha256_json(record)
    return "pass" if compare(glow, v.op, v.value) else "fail"
```
- `VerifyKind(name, evaluate, target_schemes=(), compares=False, binary=False, title="", check=None, hypothetical=None)`.
- `evaluate(ctx, req, res, evidence)`: `ctx` is the evaluators' context (§4.4), `req` the
  requirement (§4.5), `res` the row being written (`CheckResult`, §4.3: set `res.message`,
  and `res.detail` for more). Return `"pass"`, `"fail"`, `"warn"`, `"skip"`, or `None` when a
  person must decide. The core applies sign-offs and safety (a safety requirement always
  needs a person).
- `evidence` maps a URI to a key; a sign-off (and a decided choice) is held against those
  keys and voids when one changes. For a URI of your scheme, use the output hash your rule
  wrote (the core recomputes `<scheme>://<id>` as that, or as the object's hash when no rule
  makes it), so the key you store equals the one the core checks later.
- The schema reads the rest: `target_schemes` (empty: the kind takes no target), `compares`
  (the requirement needs `op` and `value`; `value` arrives as a quantity), `binary` (a
  statement need not carry a number, lint L1), `check(verify)` (extra rules on the `verify`
  block: raise `ValueError` with the fix), `hypothetical(...)` (`n2f impact`'s "would it pass";
  leave it `None` and impact says "known after the rebuild").
- A requirement naming a kind that is not installed is a validation error listing the
  installed kinds. `n2f doctor` lists every installed kind with its targets (F14).

### 3.4 Check stages — `check_stages=(CheckStage(...),)`
Rows of `n2f check` (`build/checks/checks.json`).

```python
CheckStage("toy", toy_checks, after=("interface",), reads=toy_check_reads)

def toy_checks(sctx) -> list[CheckResult]:          # sctx: StageContext (§4.4)
    return [CheckResult(id=f"toy://{tid}", subject=str(t.part), status="pass", kind="toy",
                        title=f"{t.name} glows", message="it glows")
            for tid, t in sorted(things(sctx.product).items())]

def toy_check_reads(product) -> list[str]:
    return [f"toy://{tid}" for tid in things(product)]
```
- `CheckStage(name, run, after=(), whole_product=False, reads=None)`.
- The mechanical stages, in order: `interface`, `interference`, `requirements`, `count`,
  `hardware`, `reach`, `docs`, `sourcing`, `calc-case`. `after` puts yours after the ones named.
- Give your rows a `kind` of your own (your domain's name is a good one): the gate row
  (§3.5) and the report count rows by kind.
- `reads(product)`: the keys your rows depend on (your rules' `toy://<id>`), added to the
  `checks` rule's reads, so a change reruns the checks.
- `whole_product=True` leaves the stage out of `n2f check --scope asm://<id>` (a module's
  own checks). Without it, filter your rows with `sctx.keep(<the assembly id the row belongs
  to, or None>)`.
- A row may be a **choice** for the owner: §3.13.

### 3.5 Gate rows — `gate_rows=(GateRow(...),)`
The stage ladder is the core's (`intake → design → verify → released`); a domain adds a
**row** under Design or Verify (F4).

```python
GateRow(gate="verify", title="Toy things", row=toy_row)

def toy_row(product, build_dir):
    if not things(product):
        return None                       # no content: no row
    return check_rows_state(build_dir, "toy", {"pass": "OK", "fail": "needs attention"})
```
- `GateRow(gate, title, row)`; `gate` is `"design"` or `"verify"`.
- `row(product, build_dir) -> GateRowState | None`. `GateRowState(summary, blockers=[],
  caveats=[])`: `n2f status` prints `<title>: <summary>` under the gate; each blocker (a
  sentence) keeps the gate open; each caveat holds it without blocking a release.
- `check_rows_state(build_dir, kind, words)`: the summary of the `checks.json` rows of one
  `kind`, "3 checks: 2 OK, 1 needs attention" (`words`: status → owner words), or `None`
  before the checks ran. It adds no blocker (failing rows block Verify on their own).
- `n2f status --json` shows it as `{"title", "summary"}` in that gate's `detail.rows`.
- Scope can take the row away: §5.

### 3.6 Report sections — `report_sections=(ReportSection(...),)`
A section of the one-page report (F5).

```python
ReportSection("toy", "Toy things", group="Product", fragment="toy.html.j2",
              data=toy_report_data, reads=toy_report_reads)
```
- `ReportSection(id, label, group, fragment, data=None, reads=None, show=None)`.
- `fragment` is a Jinja file in your package (relative to `root`). It renders inside the page
  with `data` (the dict `data(product, build_dir)` returns) and the page's helpers: `h2(id,
  title)` (the heading), `badge(status)`, `w(status)` (owner words), the `ref` filter (a URI
  as a link). Start it with `<section class="card" id="<id>">`, end it with `</section>`:
  ```html
  <section class="card" id="toy">
    {{ h2('toy', 'Toy things') }}
    {% for t in data.things %}<p>{{ t.name }}: {{ t.glow }}</p>{% endfor %}
  </section>
  ```
  Keep it self-contained: no external file, no script source (D13, the page is `file://` safe).
- `group` is one of `""`, `"Product"`, `"Verification"`, `"Design record"`; the section goes
  at the end of its group in the side index. `show(product)` false leaves it off.
- `reads(product)`: the keys it shows, added to the report rule's reads.

### 3.7 Doc helpers — `doc_helpers={"toy": factory}`
Names a manual page (`model/docs/*.md`, a Jinja template) can call.

```python
def toy_helper(h):                                  # h: HelperContext (§4.4)
    def toy(tid):
        tid = tid.replace("toy://", "")
        if tid not in things(h.product):
            raise h.error(f"toy('{tid}') does not exist")
        return h.proxy(things(h.product)[tid], f"toy://{tid}")  # attribute reads are recorded
    return toy
```
`{{ toy("widget").name }}` records `toy://widget#name` with its value; the page reruns when
it changes. Record anything else you read with `h.log.add(key)`. The system's helper names
(`P`, `part`, `asm`, `req`, `iface`, `dec`, `build_step`, `bom`, `product`) are taken.

### 3.8 Vocabulary — `vocabulary={"owner": {"toy": "toy thing"}}`
Owner words for your terms; `"owner"` is the persona the system reads. A term named like your
URI scheme is said before the id: `toy://widget` reads "toy thing widget" in `n2f check`.
Engineers see the URI.

### 3.9 Interface kinds — `interface_kinds=(InterfaceKind(...),)`
```python
from napkin2factory.core.model.interfaces import InterfaceSpec

class ToySpec(InterfaceSpec):   # InterfaceSpec carries an optional `hardware`
    snap: str = "firm"

def check_toy_joint(product, iface, build_dir) -> dict:
    firm = iface.spec.snap == "firm"           # iface: id, kind, parties, spec
    return {"status": "pass" if firm else "fail", "message": f"it snaps {iface.spec.snap}"}

InterfaceKind("toy-joint", "Toy snap joint", spec=ToySpec, check=check_toy_joint)
```
- `InterfaceKind(name, title="", spec=None, check=None)`.
- An interface of that kind validates its `spec:` with your schema, cuts nothing in the
  geometry, reads as your title in the build plan, and gets the row `iface://<id>` from
  `check(product, iface, build_dir)` (no `check`: "not checked"). The interface file names
  two `parties` (part or assembly URIs), and each party part lists `iface://<id>` under its
  `interfaces:` (copy `tests/fixtures/products/toy/model/interfaces/plate-peg.yaml`).

### 3.10 Open sets (F6): processes, finishes, categories, drivers, style roles
- `processes=(Process("toy-cast", "Toy casting"),)` — values of a part's `process:`.
  `Process(id, title, declared=True)`; `declared=False` means "not decided" (the general rule
  pack then asks for one). A custom part with a declared process, a material, a finish and a
  tolerance class passes the general pack's `custom-part-complete` row.
- `finishes=("toy-glitter",)` — values of `style.yaml`'s `finish:` entries (how a role's
  surface renders; yours render with neutral factors). A part's own `finish:` is free text.
- `categories=("fun",)` — requirement categories.
- `drivers={"toy-swapped": "swapped between toys"}` — why a sub-assembly is built on its
  own (`driver: [toy-swapped]` in an assembly file), with its owner words.
- `style_roles=(StyleRoleSpec("toy-shell", "a toy's shell", styled=True, aliases=("casing",)),)`
  — `StyleRoleSpec(id, words, styled=False, aliases=())`: values of a part's or a rough
  shape's `role:` and keys of `style.yaml`'s `palette` and `finish`. `words` say the role for
  the owner; `styled=True` gives a part naming it the style's shape cues (corner radius,
  reveal …); `aliases` are other words read as it. A role the style preset gives no colour
  takes the `default` role's. A part naming your role reads your domain's code hash, so a
  change to your declaration rebuilds exactly those parts.

The system's own values are tables shipped with the package; yours are added after them (a
value the table already has stays the table's). An unknown value is an error listing the
known ones; `registry().processes()`, `.finishes()`, `.categories()`, `.drivers()`,
`.style_roles()`, `.interface_kinds()` show the lists.

### 3.11 Screens — `screens=(Screen("toy", toy_screen, fields=(TOYS,), phase="estimate"),)`
Napkin-stage screening of a concept card (`model/concepts/C-xxx.yaml`, before any design). A
screen declares the card fields it reads and the phase it runs in; `n2f concept new` writes
the fields into a new card's skeleton and `n2f concept lint` checks a card's numbers against
their kind.

```python
from napkin2factory.concepts.screens import CardField
from napkin2factory.core.domain import Screen
from napkin2factory.core.model import RuleRow

#                section     key    unit  kind of number  example  the owner's words
TOYS = CardField("envelope", "toys", None, "a count",     "5",     "how many toys it holds")

def toy_screen(card, massing, values) -> list[RuleRow]:
    toys = card.envelope.get("toys")
    if toys is None:
        return []                           # the card does not say: no row
    n = int(getattr(toys, "magnitude", toys))  # numbers arrive as quantities
    values.estimate.add("toy_count", n, f"{n} toys", "from the card", "toy screen")
    return [RuleRow(id="toy-count", title="Enough toys", status="pass", message=f"{n} toys")]

Screen("toy", toy_screen, title="Toy count", fields=(TOYS,), phase="estimate")
```
- `Screen(name, run, title="", fields=(), phase="")`;
  `CardField(section, key, unit, kind, example, words, aliases=(), param=None)`.
- `section` is `envelope` (the product's own sizes and figures), `site` (the space it must fit
  and what it plugs into) or `layout` (words: where things go). `unit` is the unit the screen
  converts to (`"mm"`, `"W"`; `None` for words or a bare count); `aliases` are earlier keys
  still read; `param` names the parameter an envelope field seeds at promotion when that is
  not the key with hyphens.
- `phase`: `measure` and `total` are the system's own steps (sizes and mass of the rough
  shapes; total mass, cost band, lift class). Take `estimate` when the totals read your
  numbers (append `(kg quantity, words, ref)` to `values.mass_items`, or `(name, process
  class, kg)` to `values.cost_items`, or leave raw values in `values.shared` for a later
  screen), else `check` (the default). An unknown phase is an error naming the known ones.
- Left empty, `fields` and `phase` come from a `@reads(*fields, phase=...)` decorator on the
  function (`from napkin2factory.concepts.screens import reads`); with neither, the screen
  reads no declared field and runs in `check`.
- `values` (`ScreenValues`): `values.computed`, `values.estimate`, `values.given` each
  `.add(name, raw, text, source, ref)` (`text` is what the card shows, `source` where it
  came from, `ref` the screen); `values.notes` is a list of owner sentences.
  `card.envelope` / `card.site` / `card.layout` are dicts; numbers in them are quantities.
- `RuleRow(id, title, status, message)`, `status` one of `pass`, `fail`, `warn`, `skip`.
  Rows come after the system's generic rows, in phase order.
- `massing` is the rough shapes' result, or `None` when the card has none yet.

### 3.12 Context contributions — `context=(ContextContribution(...),)`
What `n2f context asm://<id>` adds for a module:
`ContextContribution(name, title, collect)`, `collect(product, aid, members) -> list[str]`
(Markdown lines; `members` are the assembly id and the ids of the phantoms folded into it;
`product.assemblies[a].children` each have `.part` or `.asm`, a URI or `None`). Printed under
`## <title>`; nothing when the list is empty.

### 3.13 Choices from a check stage (F12)
A check that finds a trade-off with two or more valid designs hands it to the owner as a
**choice** instead of failing. Build the row, then pass it through `offer`:

```python
from napkin2factory.core.checks.choices import Option, offer

row = CheckResult(id=f"toy-fit://{tid}", subject=f"toy://{tid}", status="fail",
                  message="", kind="toy", title=f"{t.name} fits its box")
row.detail["evidence"] = [f"toy://{tid}", str(t.part)]   # the facts it is decided on
return offer(row, [
    Option("smaller-toy", "a smaller widget", "change glow to 2 in model/toy/widget.yaml"),
    Option("bigger-box", "a bigger box", "lengthen the plate by 10 mm", cost_delta="+2 USD"),
], blocks="verify", problem="The widget does not fit its box.")
```
- `Option(id, summary, what_it_takes, cost_delta=None, invalid="")`; `invalid` says why an
  option is not a valid design (it is then not offered).
- `offer(result, options, *, blocks, problem)`: two or more valid options make the row a
  `choice` carrying `detail.options` and `detail.blocks`; exactly one makes it a `fail` naming
  that fix; none, a `fail`. A choice is never a way to put off a failure.
- `blocks`: the gate it holds until decided, `"design"`, `"verify"`, `"release"` or `"none"`.
- `detail["evidence"]` (default: the row's `subject`) lists the URIs whose keys the decision
  is held against; when one changes, the choice reopens.
- The core does the rest: `build/checks/choices.json`, "Waiting on you" in `n2f status`,
  `n2f decide <row id> --pick <option> --by "<name>"` writing a `DEC-` entry, and the row
  reading `pass` with the decision afterwards. Write `what_it_takes` and `summary` in the
  owner's words: the project manager reads them out.

## 4. The objects you are handed (reference)

### 4.1 The contract's types (`napkin2factory.core.domain`)
```
Domain(name, root=Path(), title="", families=(), rule_families=(), verify_kinds=(),
       check_stages=(), gate_rows=(), report_sections=(), doc_helpers={}, vocabulary={},
       interface_kinds=(), processes=(), finishes=(), categories=(), drivers={},
       style_roles=(), screens=(), context=(), code=(), in_place=False)
ModelFamily(name, schema, folder, validate_refs=None, scheme="", id_pattern=SLUG)
RuleFamily(name, make_rules, after=(), produces="", also_produces=(), code=(),
           reads_all=False, targets=(), output_dir=None, static_reads=None)
VerifyKind(name, evaluate, target_schemes=(), compares=False, binary=False, title="",
           check=None, hypothetical=None)
CheckStage(name, run, after=(), whole_product=False, reads=None)
GateRow(gate, title, row)              GateRowState(summary, blockers=[], caveats=[])
ReportSection(id, label, group, fragment, data=None, reads=None, show=None)
InterfaceKind(name, title="", spec=None, check=None)
Process(id, title, declared=True)      StyleRoleSpec(id, words, styled=False, aliases=())
Screen(name, run, title="", fields=(), phase="")
ContextContribution(name, title, collect)
StageContext, HelperContext            (handed to you; §4.4)
SCREEN_PHASES = ("measure", "estimate", "total", "check")
```
`code` lists folders of your package (relative to `root`) hashed as its code; empty: all of
`root`. `in_place` is for the mechanical domain only; leave it `False`.

### 4.2 Build (`napkin2factory.core.graph.rules`)
- `Rule(id, kind, produces, inputs, run, version=1, description="", depends_on=[], also_produces=())`.
- `RuleBuild`: `product`, `render` (bool: renders requested), `rules` (the rules the earlier
  families made, in build order), `family`; `code_hash()` is your family's code hash.
- `RunContext`: `product`, `build_dir` (the product's `build/`), `render`, `payloads`
  (in-memory results of earlier rules this run, by rule id: a rule's `RunResult.payload`).
- `RunResult(reads, outputs, output_hash, payload=None)`: `outputs` are the absolute paths
  written; `payload` is handed to later rules in the same run.

### 4.3 Rows (`napkin2factory.core.checks.results.CheckResult`)
`CheckResult(id, subject, status, message, persona_message="", kind="requirement",
evidence={}, evidence_keys={}, safety=False, title="", detail={}, module=None)`. `status` is
one of `pass`, `fail`, `warn`, `skip`, `needs-human`, `signed`, `choice`; only `fail` blocks.
`id` is the row's address (a URI); `subject` the thing it is about; `title` a short owner
sentence; `message` what was found.

### 4.4 Contexts
- `StageContext` (a check stage): `product`, `build_dir`, `ectx` (the evaluators' context,
  below), `keep(home) -> bool` (for `n2f check --scope`), `within` (the scoped assembly id or
  `None`), `modules`.
- The evaluators' context (a verify kind's `ctx`, and `sctx.ectx`): `product`, `build_dir`,
  `props(uri)` (a part's or assembly's `props.json` as a dict, or `None`), `interfaces`
  (interface id → its check report), `rollups` (the bom totals when read).
- `HelperContext` (a doc helper): `product`, `doc` (the page), `log` (`log.add(key)`),
  `proxy(obj, uri)`, `error(msg)` (raise what it returns), `rollups`, `plan` (the bom
  rule's outputs when built), `state` (a dict for the page's render).

### 4.5 The product and its files
`load_product(root)` returns the product: `root`, `manifest` (`n2f.yaml`), `operator`,
`parts`, `assemblies`, `interfaces`, `requirements`, `parameters`, `decisions`, `docs`,
`signoffs` (each a dict id → object), `families` (family name → id → object), `files` (URI
string → source file). A requirement: `id`, `title`, `statement`, `category`, `priority`,
`safety`, `verify` (`kind`, `target`, `op`, `value`, `note`), `allocation`, `tags`. A URI
(`verify.target`, `thing.part`): `scheme`, `id`, `selector`; `str(uri)` is `scheme://id`.
A product's file formats (parts, assemblies, interfaces, requirements) are in
`docs/product-model.md`; the toy product is the smallest complete one.

### 4.6 Fields for your schema (`napkin2factory.core.model.base`)
`Model` (pydantic, unknown keys forbidden), `Slug` (lowercase words with hyphens), `PartUri`,
`AsmUri`, `ReqUri`, `ParamUri`, `IfaceUri`, `DocUri`, `CalcUri` (a URI of that scheme),
`UriField` (any URI), `uri_of("part", "asm")` (any of those schemes; your own scheme works
once your family is registered), `Quantity` (`"25 mm"` parsed to a quantity).

### 4.7 Numbers (`napkin2factory.core.units`)
`parse_quantity(text_or_number, default_unit=None)`, `compare(a, op, b)` (`op` one of `<`,
`<=`, `>`, `>=`, `==`, `!=`), `format_quantity(q)`, `is_quantity(x)`, `magnitude_in(q, unit)`.

## 5. Scope and a domain (F11)

The product's `n2f.yaml` may say where each domain's work stands:
```yaml
scope:
  toy: {state: later, decision: DEC-004, note: "the toys come in the next version"}
```
The key is your domain's `name`. Without an entry a domain is `in` when the product has
content for it, and absent (no row) when it has none.
- **`in`**: everything in this page applies.
- **`later`**: your gate rows are left out of Design and Verify, and each gate says so in a
  row of its own ("Toy: later (DEC-004) — …"). Your requirements are left out too, except
  safety ones, which still block. A requirement is yours when a tag or its category names the
  domain (`tags: [toy]`, which works before the domain is installed), or its category is one
  you register, or its verify kind is yours, or its verify target or allocation uses one of
  your schemes. Content for a `later` domain (objects in your families) is a lint warning
  ("content exists; set scope to in or remove it").
- **`external`** (said "done elsewhere"): the work is done outside this product; a
  sub-assembly with `build: external`, its `ports:` declared and no children, stands for it,
  and validation fails naming the file when it is missing. The build plan lists it as
  "supplied, not built here".
- Every state should name the decision behind it (`decision: DEC-xxx`); without one, a lint
  warning. The release records the scope and prints it on the package cover.

Your gate row does not need to read the scope: the core drops it for `later`. It should
still return `None` when the product has no content for you.

## 6. A product's own packs (F10)

A product can carry screens and rule-pack checks of its own, without a domain, in its folder.
They use the same contract as a domain's screens; they cannot register rule families, verify
kinds, report sections or gate rows (those are a domain's).

- **`model/screens/*.py`**: each module exposes `SCREENS = (Screen("name", run), ...)`, the
  functions declaring their fields and phase with `@reads(...)`. The kiln's
  `examples/kiln/model/screens/heated_enclosure.py` is the worked example. Hashed into the
  concept build. A module may also expose two promotion hooks (`n2f concept promote`):
  - `PROMOTE_REQUIREMENTS(card, seeded, top, notes) -> [(about, fields), ...]`: requirements
    the card's fields imply. `fields` is a requirement's `title`, `statement`, `category`,
    `verify` and `rationale` (`allocation` defaults to the top assembly `top`); `seeded` lists
    the parameters promotion seeded (each with `name` and `source`, like `envelope.power`);
    sentences appended to `notes` are said to the owner. Written after the space the product
    must fit and before its weight.
  - `PROMOTE_RATIONALE = ("key", ...)`: screening value keys the promotion decision quotes,
    after the size and mass.
- **`model/rulepacks/*.yaml`** with their checks in **`model/rulepacks/*.py`**: a pack file
  in the shipped packs' format (`pack`, `title`, `applies_to`, `rules:` each with `id`,
  `title`, `severity`, `check`, `params`, `message`), and a module exposing
  `CHECKS = {"name": fn}` (`fn(part, features, params, product) -> [violation dict, ...]`,
  empty when it passes) and optionally `ASSEMBLY_CHECKS` (`fn(assembly, params, product)`).
  Rows are `rule://<pack>/<rule>@<part>`. Hashed into the `checks` rule.

A module that fails to import is an error naming the file.

## 7. What the core does with a registered domain (so you do not have to)
- **Hashing (gate E).** Your domain's code hash is an input of your rules, and of every rule
  that reads a registry you add to: `validate` (model families and the open sets of §3.10),
  `doc:*` (doc helpers), `checks` (verify kinds, check stages), `report` (sections, gate
  rows, vocabulary), and each part whose `role:` is a style role you register. Change a file
  of your domain and exactly those rerun.
- **Impact.** `n2f impact` uses your rules' recorded reads (or `static_reads` before the
  first build), so it stays a superset of what the build reruns.
- **Order.** Your family runs after its `after` families and before `checks`; your stage
  after its `after` stages; your section at the end of its group.
- **Discoverable.** `n2f doctor` lists every installed domain with its verify kinds, check
  stages and screens (`--json` adds the rest), read from the registries.

## 8. Checklist: adding a domain, and proving it

**Build it.**
1. Make the package: `__init__.py` with `DOMAIN = Domain(name=..., root=Path(__file__).resolve().parent, ...)`
   (§1). For a test domain also make sure its parent folder is a package (an `__init__.py`).
2. For each thing you bring, fill its field (§3): families (3.1), rule families (3.2),
   verify kinds (3.3), check stages (3.4), gate rows (3.5), report sections and their
   fragment files (3.6), doc helpers (3.7), vocabulary (3.8), interface kinds (3.9),
   processes, finishes, categories, drivers, style roles (3.10), screens (3.11), context
   (3.12). Every name new (§1).
3. Record every read (`RunResult.reads`, `h.proxy` / `h.log.add`, `CheckStage.reads`,
   `ReportSection.reads`). A value you use and do not record never reruns anything.
4. Give it a product: a fixture folder using each thing. Copy `tests/fixtures/products/toy/`
   (`n2f.yaml`, `operator.yaml`, `model/parameters.yaml`, `model/decisions.yaml`,
   `model/requirements.yaml`, two parts, one assembly, one interface, one manual page) and
   change the toy's words for yours.

**Prove it: the test.** Copy `tests/unit/test_domain_contract.py`'s module fixture and these
tests, with your names: `test_every_registry_sees_the_toy`,
`test_rule_family_runs_after_the_parts_and_before_the_checks`,
`test_the_rule_family_is_a_build_target_on_the_command_line`, `test_verify_kind_evaluates`,
`test_check_stage_reports`, `test_gate_row_shows_in_status`, `test_report_section_renders`,
`test_doc_helper_records_a_read`, `test_vocabulary_word_in_the_owner_view`,
`test_interface_kind_validates`, `test_process_passes_the_general_rule_pack`,
`test_screen_runs_on_a_card`, `test_screen_declares_its_fields_and_phase`,
`test_style_role_is_a_role_while_the_domain_is_installed`, `test_context_contribution`,
`test_impact_is_a_superset_of_the_rebuild`, `test_a_domain_code_change_reruns_its_rules_only`.
The rest of that file tests the core, not a domain. The fixture:

```python
@pytest.fixture(scope="module")
def built(tmp_path_factory):
    with installed(gadget.DOMAIN):
        root = copy_product(PRODUCT, tmp_path_factory.mktemp("gadget") / "gadget")
        product = load_product(root)
        summary = run_build(product, render=False, quiet=True)
        yield root, product, summary
```
The calls the tests make, with their signatures:
- `copy_product(src, dst, git=True) -> dst` (`tests.conftest`): copies a product without
  `build/`; `git=True` also starts its change tracking.
- `load_product(root) -> product`; `validate(root) -> (product or None, problems)`,
  `problems.errors` each with `.message`.
- `run_build(product, target="all", render=True, quiet=False, ...) -> {"ran": [rule ids], ...}`;
  `explain_build(product, target="all", render=True) -> [(rule id, will_run, why), ...]`
  (pass `render=False` by name);
  `build_rules(product, render=True) -> [Rule]` in build order.
- `compute_impact(product, [parse_set("toy://widget#glow=5")])` → `.rules`, the rule ids it
  would rerun.
- `evidence_key(product, build_dir, uri) -> str`: the key the core holds a sign-off against.
- `module_context(product, aid) -> dict` (`["domains"]` is a list of `{"lines": [...], ...}`);
  `render_text(ctx) -> str`.
- `screen(card, massing) -> screening` (`napkin2factory.concepts.screening`):
  `.estimates[name].value` is the text, `.rules` the rows; a card is
  `ConceptCard.model_validate({"id": "C-001", "title": "…", "status": "exploring", "envelope": {...}})`.
  `render_card({"id": "C-001", "title": "…"}) -> str` is a new card's skeleton;
  `card_fields()`, `fields_of(screen)`, `phase_of(screen)` (`napkin2factory.concepts.screens`).
- `napkin2factory.core.model.style`: `STYLE_ROLES` (the role ids, yours last), `STYLED_ROLES`,
  `ROLE_ALIASES` (alias → role), `canonical_role(word)`, `StyleFile.model_validate({...}).colour(role)`.
- The CLI, in-process: `CliRunner().invoke(app, ["status", "-C", str(root)], env={"COLUMNS": "200"}).output`
  (also `["status", "-C", root, "--json"]`, `["check", "-C", root, "--all"]`,
  `["build", "-C", root, "--target", "<family>", "--explain", "--json"]`).
- The registry's views, for "every registry sees it": `reg = registry()`;
  `reg.rule_family(n)`, `reg.verify_kind(n)`, `reg.check_stage(n)`, `reg.gate_rows("verify")`,
  `reg.report_section(id)`, `reg.doc_helper(n)`, `reg.vocabulary("owner")`,
  `reg.interface_kind(n)`, `reg.processes()`, `reg.finishes()`, `reg.categories()`,
  `reg.drivers()`, `reg.screens()`, `reg.style_roles()`, `reg.context_contributions()`,
  `reg.model_family(n)`, `reg.domains`, `reg.target_kinds()` (target → rule kinds it runs).
- A code change, as `test_a_domain_code_change_reruns_its_rules_only` does it: copy your
  package to a temporary folder, `dataclasses.replace(DOMAIN, root=copy)`, swap it in with
  `unregister`/`register`, edit a file in the copy, and call
  `napkin2factory.core.registry._tree_hash.cache_clear()` (the code hashes are cached per run).

**Count.** `git diff --name-only <base> -- src/napkin2factory/core/` and
`git status --porcelain -- src/napkin2factory/core/` both print nothing.

**Install it** (a shipped domain only): add the module path to `INSTALLED` (§1), then
`n2f doctor` lists it.

## 9. Not registrable in v0.5

A domain cannot add these; each is the system's, and a domain that needs one asks for a
change to the system (a backlog row), not a core edit of its own:
- **Gates of the stage ladder** (`intake → design → verify → released`): a domain adds rows
  under Design or Verify, never a rung (F4).
- **The system's own words**: row statuses, severities, the labels `given` / `computed` /
  `estimate`, concept and change-request states (F6: closed sets).
- **CLI verbs**: one module per verb under `src/napkin2factory/cli/`; a domain adds rows,
  rules and targets, not an `n2f` verb.
- **Rule packs as a domain field**: a domain's checks are a check stage (§3.4). Rule packs
  (YAML rules bound to checks) are the system's (`src/napkin2factory/rulepacks/`) or a
  product's own (§6).
- **Calc packs**: the calc kit (`src/napkin2factory/calckit/`) is the system's; a domain's
  code may import it, and a product's `model/calcs/` holds its own calcs, but there is no
  `Domain` field for a pack of calcs.
- **Files in the release package**: `n2f release` packs the parts, drawings, parts list,
  manuals, report and checks it knows; a domain's `build/<output_dir>` files are not in it.
- **Schema migrations**: the migration registry (`docs/schema-policy.md`) is the system's; a
  change to a domain family's schema follows the same policy (additive and optional, or a
  migration shipped with the system).
- **Concept-card sections** (`envelope`, `site`, `layout`) and the screen phases: a screen's
  fields sit in one of the three sections and it runs in `estimate` or `check`.
- **Report groups**: a section joins one of the four groups (§3.6).
- **Personas**: vocabulary is read for `"owner"` only.
