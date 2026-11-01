# Domains: the contract (v0.5, FOUNDATION F1)

A **domain** is a step of making a product — mechanical, electrical, analysis, a
manufacturer's rule set — packaged as a folder that registers what it brings. The core knows
this contract, never a domain: adding a domain edits **no file under
`src/napkin2factory/core/`**. This page is the whole contract. You should not need to read the
core to add a domain; if you do, the page is missing something — say so in your report.

The worked example is the **toy domain**, `tests/fixtures/domains/toy/__init__.py` (one file
plus one template), with its product `tests/fixtures/products/toy/` and its test
`tests/unit/test_domain_contract.py`. Copy them.

## 1. What a domain is

A Python package exposing one object:

```python
# my_domain/__init__.py
from pathlib import Path
from napkin2factory.core.domain import Domain, ...

DOMAIN = Domain(
    name="wiring",                         # unique; also the key of its code hash
    title="Wiring: circuits, cables, connectors",
    root=Path(__file__).resolve().parent,  # every relative path below is relative to it
    families=(...), rule_families=(...), verify_kinds=(...), check_stages=(...),
    gate_rows=(...), report_sections=(...), doc_helpers={...}, vocabulary={...},
    interface_kinds=(...), processes=(...), finishes=(...), categories=(...),
    drivers={...}, screens=(...), context=(...),
)
```

Every field except `name` is optional. Only declare what the domain brings.

**Where it lives and how it is installed.**
- A shipped domain is a package under `src/napkin2factory/domains/<name>/` and is installed by
  adding its module path to `INSTALLED` in `src/napkin2factory/domains/__init__.py` (installation
  order is the order every registry iterates in). That list is not part of the core.
- A domain under test (like the toy) lives anywhere importable, e.g. `tests/fixtures/domains/<name>/`,
  and is registered for a block of code:

  ```python
  from napkin2factory.core.registry import installed
  from tests.fixtures.domains import toy

  with installed(toy.DOMAIN):
      ...  # load, build, check, status, report: everything sees the domain
  ```
  `register(domain)` / `unregister(name)` do the same without a block.

**What a domain may import from the system** (the public API; anything else is the core's
business and may change): `napkin2factory.core.domain` (the contract's types),
`napkin2factory.core.registry` (`registry()`, `installed`, `UnknownName`),
`napkin2factory.core.model.base` (`Model`, `Slug`, `PartUri`, `AsmUri`, `UriField`, `Quantity`, …),
`napkin2factory.core.model.interfaces.InterfaceSpec`, `napkin2factory.core.model.RuleRow`,
`napkin2factory.core.graph.rules` (`Rule`, `RuleBuild`, `RunContext`, `RunResult`),
`napkin2factory.core.graph.hashing` (`sha256_json`, `sha256_file`, `sha256_text`),
`napkin2factory.core.checks.results.CheckResult`, `napkin2factory.core.checks.stage.check_rows_state`,
`napkin2factory.core.units` (`parse_quantity`, `compare`, `format_quantity`).

**The mechanical domain** (`src/napkin2factory/domains/mechanical/__init__.py`) is everything
v0.4 already did — parts, assemblies, drawings, the BOM and build plan, manuals, checks, the
report, the site — registered *in place* (F2): the code stays where it was and the domain only
declares it. It is the second worked example, for the bigger registries.

## 2. The registries, one by one

Each registry lists its entries in installation order (then the order the domain declares
them); rule families and check stages are ordered by their `after` lists. Every lookup of an
unknown name raises `UnknownName` with the known values ("unknown verify kind 'x'; known: …").

### 2.1 Model families — `families=(ModelFamily(...),)`
Files the product holds for the domain: `<folder>/*.yaml`, one object per file.

```python
class ToyThing(Model):          # strict: unknown keys are errors
    id: Slug                    # must match the file name
    name: str
    part: PartUri
    glow: int = 1

ModelFamily("toy", schema=ToyThing, folder="model/toy", validate_refs=validate_toy)
```
- Loaded with the product; objects are in `product.families["toy"]` (id → object).
- Each object is addressable as `<scheme>://<id>` (`scheme` defaults to the family name;
  `id_pattern` defaults to a slug). Requirements, sign-offs and reads can name it.
- `validate_refs(product, problems)` runs after the core's own cross-checks: add one problem
  per broken reference with `problems.add(file, subject, message, hint, rule="<id>")`
  (`product.files["<scheme>://<id>"]` is the object's file).
- A read of `<scheme>://<id>#<field>` is valued from the declared field, so a manual page or a
  rule that reads it reruns when it changes.

### 2.2 Build rule families — `rule_families=(RuleFamily(...),)`
Steps of `n2f build`. `make_rules(b: RuleBuild) -> list[Rule]` returns this family's rules for
`b.product` (`b.render`, `b.rules` = the rules made so far).

```python
RuleFamily("toy", toy_rules, after=("part",), produces="toy://", output_dir="toy",
           static_reads=toy_static_reads)
```
- A rule: `Rule(id=f"toy:{tid}", kind="toy", produces=f"toy://{tid}", inputs={}, run=fn,
  depends_on=[...])`. Its `kind` is the family name; ids are `<family>:<id>`.
- `run(ctx: RunContext) -> RunResult(reads, outputs, output_hash)`: write under
  `ctx.build_dir / <output_dir>`; **every value you use must be in `reads`** (D5: a recorded
  read is what makes a change rerun the rule); `output_hash` is what downstream rules see.
- `after`: families whose rules run first. The family goes after them and **before** the
  `checks`, `report` and `site` families, which read everything (`reads_all`).
- `produces="toy://"`: a downstream read of `toy://<id>` is this rule's output hash.
- Code hash: leave `"code"` out of `inputs`; the core adds the hash of your domain's code
  (`Domain.code` folders, or the whole `root`), so editing your domain reruns your rules and
  nothing else.
- `static_reads(product, rule)`: the reads `n2f impact` assumes before the first build.
- `targets=("wiring",)` are extra `--target` names (the family's own name is one already).

### 2.3 Verify kinds — `verify_kinds=(VerifyKind(...),)`
How a requirement is checked (`verify.kind`).

```python
VerifyKind("toy_glow", evaluate_glow, target_schemes=("toy",), compares=True)

def evaluate_glow(ctx, req, res, evidence) -> str | None:
    ...  # read ctx.build_dir; set res.message; evidence[uri] = key; return the verdict
```
- Returns `"pass"`, `"fail"`, `"warn"`, `"skip"`, or `None` when a person must decide. The
  core applies sign-offs and safety (a safety requirement always needs a person).
- `evidence` maps a URI to a key; a sign-off is held against those keys and voids when one
  changes. For a URI of your scheme use your rule's output hash (the core recomputes
  `<scheme>://<id>` as that, or as the declared object's hash when no rule makes it).
- The schema reads the rest: `target_schemes` (empty: no target), `compares` (needs `op` and
  `value`), `binary` (the statement need not carry a number; lint L1), `check(verify)` (extra
  rules: raise `ValueError` with the fix), `hypothetical(...)` (`n2f impact`'s answer;
  without it impact says "known after the rebuild").
- A requirement naming a kind that is not installed is a validation error listing the
  installed kinds (DoD 7).

### 2.4 Check stages — `check_stages=(CheckStage(...),)`
Rows of `n2f check` (`build/checks/checks.json`).

```python
CheckStage("toy", toy_checks, after=("interface",), reads=toy_check_reads)

def toy_checks(sctx: StageContext) -> list[CheckResult]: ...
```
- `sctx.product`, `sctx.build_dir`, `sctx.keep(home)` (a module check keeps only its rows),
  `sctx.ectx` (state shared with requirement evaluators).
- A row: `CheckResult(id, subject, status, message, kind="<yours>", title=...)`.
- `reads(product)`: the keys your rows depend on (e.g. your rules' `toy://<id>`), so a change
  reruns the checks. `whole_product=True` leaves the stage out of `n2f check --scope`.

### 2.5 Gate rows — `gate_rows=(GateRow(...),)`
The stage ladder is the core's (`intake → design → verify → released`); a domain adds a
**row** under Design or Verify (F4).

```python
GateRow(gate="verify", title="Toy things", row=toy_row)

def toy_row(product, build_dir) -> GateRowState | None:
    if not things(product):
        return None                       # no content: no row
    return check_rows_state(build_dir, "toy", {"pass": "OK", "fail": "needs attention"})
```
`n2f status` prints `Toy things: 1 check: 1 OK` under the gate; `GateRowState.blockers` keep
the gate open, `caveats` hold it without blocking a release.

### 2.6 Report sections — `report_sections=(ReportSection(...),)`
A section of the one-page report (F5).

```python
ReportSection("toy", "Toy things", group="Product", fragment="toy.html.j2",
              data=toy_report_data, reads=toy_report_reads)
```
- `fragment` is a Jinja file in your package. It renders inside the page with `data` (what
  `data(product, build_dir)` returns) and the page's helpers: `h2(id, title)`, `badge(status)`,
  `w(status)` (owner words), the `ref` filter (a URI as a link). Start it with
  `<section class="card" id="<id>">` and end with `</section>`. Keep it self-contained: no
  external file, no script source (D13).
- The section goes at the end of its `group` in the side index (`""`, `Product`,
  `Verification`, `Design record`). `show(product)` false leaves it off.
- `reads(product)`: the keys it shows, so the report rebuilds when they change.

### 2.7 Doc helpers — `doc_helpers={"toy": factory}`
Names a manual page (`model/docs/*.md`, a Jinja template) can call.

```python
def toy_helper(h: HelperContext):
    def toy(tid):
        return h.proxy(things(h.product)[tid], f"toy://{tid}")  # every attribute read is recorded
    return toy
```
`{{ toy("widget").name }}` records `toy://widget#name`; the page is flagged stale when it
changes. Record anything else you read with `h.log.add(key)`; fail with `raise h.error("…")`.

### 2.8 Vocabulary — `vocabulary={"owner": {"toy": "toy thing"}}`
Owner words for your terms. A term named like your URI scheme is shown before the id to the
owner: `toy://widget` reads "toy thing widget" in `n2f check`. Engineers see the URI.

### 2.9 Interface kinds — `interface_kinds=(InterfaceKind(...),)`
```python
class ToySpec(InterfaceSpec):   # InterfaceSpec carries optional `hardware`
    snap: str = "firm"

InterfaceKind("toy-joint", "Toy snap joint", spec=ToySpec, check=check_toy_joint)
```
An interface of that kind validates its `spec:` with your schema, cuts nothing in the
geometry, reads as your title in the build plan, and is checked by `check(product, iface,
build_dir) -> {"status", "message"}` (no `check`: "not checked").

### 2.10 Open sets (F6): processes, finishes, categories, drivers, style roles
- `processes=(Process("toy-cast", "Toy casting"),)` — values of a part's `process:`.
  `declared=False` means "not decided" (the general rule pack then asks for one).
- `finishes=("toy-glitter",)` — values of `style.yaml` finishes (neutral render factors).
- `categories=("fun",)` — requirement categories.
- `drivers={"toy-swapped": "swapped between toys"}` — why a sub-assembly is built on its own,
  with its owner words.
- `style_roles=(StyleRoleSpec("toy-shell", "a toy's shell", styled=True, aliases=("casing",)),)`
  — values of a part's or a rough shape's `role:` and the keys of `style.yaml`'s `palette`
  and `finish`. `words` say the role for the owner; `styled=True` gives a part that names it
  the style's shape cues (corner radius, reveal …, the opt-in rule); `aliases` are other
  words read as it. A role the preset gives no colour takes the `default` role's. A part
  naming your role reads your domain's code hash, so a change to your declaration rebuilds
  exactly those parts (and `validate` and `checks`).
The system's own values are the tables in `src/napkin2factory/core/data/*.yaml`; yours are
added to them (a value the table already has stays the table's). An unknown value is an
error listing the known ones.

### 2.11 Screens — `screens=(Screen("toy", toy_screen, fields=(TOYS,), phase="estimate"),)`
Napkin-stage screening of a concept card. A screen declares the card fields it reads and the
phase it runs in; `n2f concept new` writes the fields into a new card's skeleton and
`n2f concept lint` checks a card's numbers against their kind.

```python
from napkin2factory.concepts.screens import CardField
from napkin2factory.core.domain import Screen

TOYS = CardField("envelope", "toys", None, "a count", "5", "how many toys it holds")
#        section, key, unit it converts to (None: words), kind of number, example, words

def toy_screen(card, massing, values) -> list[RuleRow]:
    values.estimate.add("toy_count", n, f"{n} toys", "from the card", "toy screen")
    return [RuleRow(id="toy-count", title="Enough toys", status="pass", message=f"{n} toys")]

Screen("toy", toy_screen, title="Toy count", fields=(TOYS,), phase="estimate")
```
- `fields`: the `CardField`s the screen reads (`section` is `envelope`, `site` or `layout`;
  `aliases` are earlier keys still read; `param` names the parameter an envelope field seeds
  at promotion when it is not the key with hyphens).
- `phase`: `measure` and `total` are the system's own steps; take `estimate` when the totals
  (mass, cost band) read your numbers (`values.mass_items`, `values.cost_items`, or
  `values.shared` for a later screen), else `check` (the default). An unknown phase is an
  error naming the known ones (`core.domain.SCREEN_PHASES`).
- Left empty, both come from a `@reads(*fields, phase=...)` decorator on the function (the
  form a product's own `model/screens/*.py` may use too); with neither, the screen reads no
  declared field and runs in `check`.

`values.computed`, `values.estimate`, `values.given` each `.add(name, raw, text, source, ref)`;
`values.notes` is a list of owner sentences. `card.envelope` / `card.site` numbers are quantities.
The rows come after the system's generic rows, in phase order.

### 2.12 Context contributions — `context=(ContextContribution(...),)`
What `n2f context asm://<id>` adds for a module: `collect(product, aid, members) -> list[str]`
(Markdown lines; `members` are the assembly and the phantoms folded into it). Printed under
`## <title>`; nothing when empty.

## 3. What the core does with a registered domain (so you do not have to)
- **Hashing (gate E).** Your domain's code hash is an input of your rules, and of every rule
  that reads a registry you add to: `validate` (families, tables), `doc:*` (doc helpers),
  `checks` (verify kinds, check stages), `report` (sections, gate rows, vocabulary). Change a
  file of your domain and exactly those rerun.
- **Impact.** `n2f impact` uses your rules' recorded reads (or `static_reads` before the first
  build), so it stays a superset of what the build reruns.
- **Order.** Your family runs after its `after` families and before checks; your stage after
  its `after` stages; your section at the end of its group.

## 4. Checklist: adding a domain
1. Make the package (`__init__.py` with `DOMAIN = Domain(name=..., root=Path(__file__).resolve().parent, ...)`).
2. For each thing you bring, fill its field (section 2): families, rule families, verify kinds,
   check stages, gate rows, report sections (+ fragment file), doc helpers, vocabulary,
   interface kinds, processes, finishes, categories, drivers, screens, context.
3. Record every read (`RunResult.reads`, `h.proxy`/`h.log.add`, `CheckStage.reads`,
   `ReportSection.reads`). A value you use and do not record never reruns anything.
4. Give it a product: a fixture product folder using each thing (copy `tests/fixtures/products/toy/`).
5. Give it a test: copy `tests/unit/test_domain_contract.py`'s fixture
   (`with installed(DOMAIN): copy_product → load_product → run_build`) and assert each
   registry sees it.
6. Install it (shipped domains): add the module path to `INSTALLED` in
   `src/napkin2factory/domains/__init__.py`.
7. Count: `git diff --stat main -- src/napkin2factory/core/` must be empty.

## 5. Not registrable yet (v0.5 milestones still to come)
- `n2f build --target <family>` on the command line lists the fixed names; a family's own
  target works through the API (`run_build(product, target="toy")`).
- `n2f doctor` listing the installed domains (M7), scope rows `in / external / later` (M4),
  choices (M5), product-local packs (`model/screens/`, `model/rulepacks/`, F10, M3).
