# Product model

A product repository (what `n2f init` writes; `examples/*` follow it exactly):

```
<product>/                  # its own tracked project (D23)
  n2f.yaml                  # schema: 1, system: ">=0.5,<0.6", product: {id, name}, units: metric, scope?
  operator.yaml             # persona, per-domain expertise, verbosity, delegation, language
  AGENTS.md                 # what this folder is, vocabulary, rules for agents
  roles/                    # pm.md, design.md, verifier.md, impact-analyst.md: plain Markdown, any agent
  model/
    requirements.yaml  parameters.yaml  decisions.yaml  intake.md
    parts/<id>.yaml  assemblies/<id>.yaml  interfaces/<id>.yaml
    geometry/<id_with_underscores>.py   calcs/*.py  calcs/*.cases.yaml   docs/*.md
    signoffs/REQ-xxx.yaml   loads/<id>.yaml
    screens/*.py            # the product's own napkin screens (optional, F10)
    rulepacks/*.yaml *.py   # the product's own rule packs (optional, F10)
    <family>/<id>.yaml      # an installed domain's model files (docs/domains.md)
  changes/ECR-xxx.yaml [ECR-xxx.patch]   reports/review-*.md   CHANGELOG.md   build/ (ignored)
  style.yaml                # the product's look (seeded by `n2f init` for new products)
  concepts/C-xxx.yaml  concepts/refs/   # concept cards, outside the build (when present)
```

## Files and their schemas (`src/napkin2factory/core/model/`)

**n2f.yaml** — `schema` (the file format's version, `docs/schema-policy.md`), `system` (the
napkin2factory versions the product was made with; only ever warns), `product: {id, name,
description?}`, `units: metric`, and optionally `scope:` (F11): one line per domain (a step of
making the product, such as `electrical`) saying where its work stands, `{state: in |
external | later, decision: DEC-xxx, note: "…", stub: asm://<id>?}`. `in` (the default for a
domain with content) is done here; `external` (said "done elsewhere") is done outside the
product, and a sub-assembly with `build: external` and its `ports:` stands for it (`stub:`
names it); `later` leaves the domain's requirements (except safety ones) and gate rows out of
the Design and Verify gates, each gate saying so in a row. Every state names the decision
behind it (lint `L15-scope` warns otherwise, and on content left under a `later` domain).
`n2f status`, the report overview, the release package cover and `release.json` say the scope.

**requirements.yaml** — `requirements: [{id: REQ-001, title, statement, category, priority,
safety, verify: {kind, target, op, value}, allocation: [uris] | unallocated, rationale, source,
tags}]`. `category` is one of the categories on file (`performance`, `geometry`, `cost`,
`mass`, `safety`, `manufacturing`, `usability`, `interface`) or an installed domain's.
`verify.kind` is an installed verify kind (`n2f doctor` lists them; an unknown one is an
error listing them): the system's are `param_bound | geometry_prop | bom_rollup | calc |
interference | count | interface | manual | rule`; the target scheme must match the kind
(`param://`, `part://x#props.…`, `bom://rollups#…`, `calc://m.f`, `asm://`, `part://`
(count), `iface://`, `rule://<pack>/<rule>`; `rule` takes no `op`/`value` — see
[checks.md](checks.md)). `tags: [electrical]` ties a requirement to a domain for scope. `n2f lint` adds:
a measurable value with a unit in the statement (unless the kind is binary), a verify block,
an allocation, and `safety: true` requirements need verify.

**parameters.yaml** — `parameters: {slug: {value, unit, description} | {expr, unit}}`.
Expressions are arithmetic over other parameter slugs (write `a - b` with spaces, since
slugs contain hyphens) plus `min/max/abs/sqrt/ceil/floor/round`.
Optional (P5, S-114): `scope: asm://<id>` makes the parameter a size of that module (a
sub-assembly built as a unit, or the top; a phantom owns none), and `export: true` lets the
module's parents read it. Unscoped parameters are the whole product's, as before. A part or
assembly rule may read its own module's parameters, its ancestors' and unscoped ones, and a
descendant's only when exported; siblings never read each other's. Reads made while resolving
an interface (frames, offset, spec) are the joint's and exempt; doc, BOM, drawing, calc and
check rules are exempt. Out-of-reach reads are `reach://` rows in `n2f check` (`warn`).

**parts/<id>.yaml** — `id, rev, name, kind: custom|cots|reference (owner-supplied or existing, not quoted), process, material: {name, spec,
density?}, finish, tolerance_class: ISO2768-f|m|c|v (custom only), geometry: {kit, args} |
{module} | none, interfaces, satisfies, cost: {unit, basis, note}, lead_time, mass?,
source: {vendor, mpn, url, verified} (COTS), manufacturer_notes, role?`. `process` is one of
the processes on file (`sheet-metal`, `machining`, `welding`, `cut-block`, `cut-sheet`,
`3d-print`, `none`: not decided) or an installed domain's; an unknown one is an error listing
them. `role` is the part's style role (`body`, `opening`, `support`, `controls`, `trim`,
`lining`, `fastener`; `door` and `stand` are read as `opening` and `support` for v0.5). Kit args may reference
`param://` and `iface://`; quantities are strings like `15 mm`.

**assemblies/<id>.yaml** — `id, rev, name, build: unit|phantom|external, driver: [...], geometry:
{module} | none, children: [{part|asm, qty, spare?, loose?}], ports: [iface uris], exploded:
{axis, spacing}, satisfies`. The YAML is the BOM
structure; the module places instances, by interface with `place_by` or by coordinates with
`place`; the checker verifies instance counts equal quantities (D18).
`build/assemblies/<id>/instances.json` records each occurrence's `via` (`coordinates` or
`iface://<id>`) and `label`.

**Ports** (P4, S-107): a part's *home* is the lowest assembly containing all its
occurrences (a bolt used in the door and the kiln lives in the kiln). An interface whose two
parts have different homes crosses the boundary of every assembly from each home up to, not
including, the lowest assembly containing both; each of those lists it under `ports:`.
`n2f validate` refuses a missing port (naming the assembly file to edit) and a listed port
that crosses nothing. An interface's parties are parts, never `asm://`: the holes live on
the part that carries them, and the sub-assembly exports the joint as a port. The parent
places the sub-assembly by it: `place_by(I, res, "<iface-id>", "asm://door", parts["door"],
onto=…, inner=…, label=…)` moves the whole sub-assembly so its party's frame (found among
its leaves; `inner` names the leaf by label when the party occurs there more than once)
meets the placed party's. The placed party may itself be a leaf of a sub-assembly already
placed (`onto` then matches that sub-assembly's label or the leaf's).
A part joined to another at several places (the kiln's two hinges on one hinge post) has one
interface per place, each naming the same two parts with its own frames: in the alignment
check an occurrence that meets one of them is not a miss of the others, but each still needs a
pair that meets; in the build plan they share the occurrences (S-113).

**Build units and the build plan** (P7, P8, S-110): a sub-assembly is a *unit* (`build:
unit`, the default), put together on its own and fitted as a whole, or a *phantom* (`build:
phantom`), a grouping whose lines fold into the step of the unit that contains it. `driver:`
says why a unit is built on its own: `built-as-unit`, `tested-as-unit`, `serviced-as-unit`,
`separate-process-or-supplier`, `varies`, `agent-context`, or an installed domain's;
`n2f lint` warns
(`L13-assembly-driver`) on a unit sub-assembly without one. The top assembly is always the last
step and needs neither field. A *stub* (`build: external`, F11) stands for work done
elsewhere: no children, its `ports:` the joints it fits by; the plan lists it as supplied, not
built here. The `bom` rule derives the plan from the tree,
`build/bom/build-plan.json`: one step per unit, children first, each with its items (numbered;
the same numbers on the unit's assembly sheet and in `build_step()`), the joints it closes (an
interface closes in the lowest assembly containing both parties' homes, folded up to its unit)
with their hardware and each party's unit (`sides`), and the ids of the checks that cover it;
`between_units` lists the joints where two units meet (P13). The plan is also a "Build plan"
sheet in `bom.xlsx`, a report section, and one A3 sheet per unit
(`build/drawings/assemblies/<id>.svg`: the unit assembled and pulled apart, the item table, the
joints). On a child line, `spare: "<reason>"` says why the line holds more joint hardware than
its joints need, and `loose: true` marks a line packed loose for the installer.

**Joint hardware** (P9 as amended by S-105): `spec.hardware: [{part, per_hole: n} |
{part, per_joint: n}]` lists what one hole (or one joint) takes; without it `fastener: X` reads
as `[{part: X, per_hole: 1}]`, and `hardware: []` says "none" whatever `fastener:` says. A mating
face has no holes, so it counts `per_joint` only (rivets, a gasket; a welded joint lists none).
A joint occurs, per assembly it closes in, as often as the more numerous of its two parties.
Where two interfaces share holes (S-051), list each item once, on the interface whose joint it
is fitted to close. A *hardware part* is one named in some `hardware` (or `fastener`); other
lines (earth studs, glands, labels) are not counted and need no field.

**interfaces/<id>.yaml** — `id, kind: bolt-pattern|mating-face (or an installed domain's kind, whose `spec` it validates), parties: [two uris],
frame: {origin, normal, x_axis?}, frames: {party uri: frame} (per-party copies),
offset?, spec: {pattern, count, diameter, spacing, pitch_circle, fastener, depth, hardware} |
{width, depth, flatness_note, hardware}`. Spec quantities may be `param://` references. A frame
coordinate and `offset` may be a number (mm), a quantity, a `param://` or
`{expr: "<expression over parameter slugs>", unit: mm}` (evaluated like a parameter `expr`;
every slug is a recorded read). `offset` (default 0) is the signed distance along the normal
from the first party's frame to the second's once placed. The one convention: placed, both
frames point the same way (same normal, same `x_axis`); `place_by` needs `x_axis` on both
(P1, P2, S-106). Optional (S-118): `name:` is the joint in the owner's words ("Shell to guard,
top wall"), used by the build plan, the sheets and the check messages instead of "<part> to
<part>"; it is a label, left out of sign-off evidence. `closed_in: asm://<unit>` marks a joint
closed in a later step than the one where its parts meet (a lid after the final assembly's
wiring): it stays listed, with its hardware, where they meet ("closed later, in step 3") and
appears again in that unit's step; `n2f lint` warns (`L14-closed-in`) when the unit is not
built after the joint's own. The build plan lists a step's joints in the order its child lines
are written (a joint comes with the later of its two parts), so write the lines in fitting order.

**loads/<id>.yaml** (F11, reserved) — a load case: `id, name, kind, value, acts_on: part:// |
asm://, faces: [...], direction?, source?, note?`, cited as `load://<id>` by a requirement's
allocation. Validated; nothing computes with it yet.

**calcs/*.py** and **calcs/<module>.cases.yaml** — product calcs (`calc://<module>.<fn>`,
taking the parameter accessor `P`) and their reference cases (F17): `inputs:` (parameter
values the cases read) and `cases: {<fn>: [{expect: "<value with unit>", rel: | abs:,
source: "<hand computation or handbook example>", inputs?: {...}}]}`. `n2f check` runs them
as `calc-case` rows; see [calckit.md](calckit.md).

**screens/*.py** and **rulepacks/** (F10) — the product's own napkin screens and rule-pack
checks, loaded like `calcs/`; the formats are in `docs/domains.md` §6.

**decisions.yaml** — `decisions: [{id: DEC-001, date, title, context, decision,
rationale, links: [uris], made_by, disclosed, verify, sources}]`. Lint requires links.

**changes/ECR-xxx.yaml** — see `docs/ecr-loop.md`.

**signoffs/REQ-xxx.yaml** — `requirement, by, role, date, statement, evidence: [uris],
evidence_keys: {uri: sha}, example`. Written by `n2f signoff`; keys are compared at
every check (D25).

**docs/*.md** — front matter `{id, title, audience, depends_on, order, safety}` and a
Jinja2 Markdown body: `{{ P["x"] }}`, `{{ part("id").name }}`, `{{ req("REQ-001").statement }}`,
`{{ bom.total_cost }}`, `{{ product.name }}`, `{{ build_step("asm://door") }}` (one build step's
items, joints and hardware as Markdown; records `bom://build-plan#units.door`). Every read is
recorded; a stale page blocks release.

## Concepts (`concepts/`) and `style.yaml`

**concepts/C-xxx.yaml** — a concept card: one cheap, disposable direction for the product,
written before (or beside) the design. `id: C-001, title, status, based_on?, refs: [paths
under concepts/], layout: {word: word}, envelope: {name: quantity | [quantities]}, site:
{key: quantity | word}, style: {…}, modules?: {name: {driver: [...], build: unit | phantom}},
massing: [{kit, as, args, at?, module?}], notes, screening,
decision` (schema: `core/model/concepts.py`; the full example is in `NAPKIN_STAGE.md` §3).
`envelope` and `site` take any named quantity or word; the fields screening reads are
declared by the installed screens (the system's, a domain's, the product's own
`model/screens/`), and `n2f concept new` writes them into the skeleton. The system's read
`site.width/depth/height` (the space it must fit; `alcove_*` before v0.5, still read),
`layout.door`, `envelope.door_swing`, `envelope.door_width`, `site.lift_class`,
`site.mass_limit`; see [napkin.md](napkin.md).
`n2f concept new` writes a commented card with every section; `--from C-00x` copies the
content of an earlier card and records `based_on`.

Cards are **outside the build** (N1): no build rule reads them, `n2f validate` ignores them,
and deleting `concepts/` changes nothing `n2f build` writes. Images that informed a card go
in `concepts/refs/` and are provenance only, never geometry. Status words:

| status | meaning |
|---|---|
| exploring | a direction still on the table (every new card starts here) |
| rejected | set aside, with `decision: {reason, at}`; kept as a record of what was tried |
| promoted | the chosen direction; at most one card per product |

`screening` is written by `n2f concept build` and `decision` by reject/promote; neither is
written by hand. `n2f concept lint` is the only validator and is deliberately light: the
schema plus C1 id matches the file name, C2 every `refs` file exists under `concepts/`,
C3 every `massing[].kit` is a kit generator, C4 `based_on` names an existing card, C5 (a
warning) every `site` key is one some installed screen reads, C6 at most one card is promoted, C7 a `promoted`
card carries a screening and `decision.dec` naming an entry in `model/decisions.yaml` (what
`n2f concept promote` writes) and a `rejected` card a `decision.reason`, C8 every number
screening reads is the kind its screen declares (`site.width` a length), C9 (warnings only)
the modules use the assemblies' reason words and every module has a massing line and every
line's module an entry (P10), C10 (a warning) a key renamed in v0.5 (`alcove_width` →
`site.width`) is still read under its old name. While `concepts/` holds a card, `n2f status` shows
an optional **Napkin** stage before Intake, complete once a card is promoted by
`n2f concept promote` — a status typed by hand is a blocker, not a pass (N11, review gate A).

**style.yaml** — `preset: industrial | appliance | lab, palette: {part role: colour},
finish: {part role: finish}, radius_scale: 1.0, reveal: 2 mm, fastener_visibility:
visible | hidden-front | hidden` (schema: `core/model/style.py`). The part roles are
`body, opening, support, controls, trim, lining, fastener, default` plus any an installed
domain adds; finishes `powder-coat, brushed-steel, painted, ceramic, anodized, plastic` plus
a domain's. `n2f init` seeds it with
these defaults for a new product; `n2f concept promote` fills it from the chosen concept.

## Quantities and units

pint everywhere (D21/D32): `60 degC`, `85 USD`, `10 d`, `1.5 mm`. `USD` is its own
dimension so costs cannot be added to lengths. Geometry code converts at its boundary with
`mm()`.

## Validation layers

`n2f validate` loads every file against its schema and checks every URI resolves, parts
and interfaces agree, assembly graphs are acyclic, ports are listed exactly where joints
cross an assembly's boundary, expressions parse and have no cycles,
geometry modules and kit names exist, calc functions exist. `n2f lint` is stricter and
is the Intake gate. `n2f check` evaluates the built product.
