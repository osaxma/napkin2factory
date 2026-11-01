# Product model

A product repository (what `n2f init` writes; `examples/*` follow it exactly):

```
<product>/                  # its own tracked project (D23)
  n2f.yaml                  # schema: 1, system: ">=0.1,<0.2", product: {id, name}, units: metric
  operator.yaml             # persona, per-domain expertise, verbosity, delegation, language
  AGENTS.md                 # what this folder is, vocabulary, rules for agents
  roles/                    # pm.md, design.md, verifier.md, impact-analyst.md: plain Markdown, any agent
  model/
    requirements.yaml  parameters.yaml  decisions.yaml  intake.md
    parts/<id>.yaml  assemblies/<id>.yaml  interfaces/<id>.yaml
    geometry/<id_with_underscores>.py   calcs/*.py   docs/*.md   signoffs/REQ-xxx.yaml
  changes/ECR-xxx.yaml [ECR-xxx.patch]   reports/review-*.md   CHANGELOG.md   build/ (ignored)
  style.yaml                # the product's look (seeded by `n2f init` for new products)
  concepts/C-xxx.yaml  concepts/refs/   # concept cards, outside the build (when present)
```

## Files and their schemas (`src/napkin2factory/core/model/`)

**requirements.yaml** — `requirements: [{id: REQ-001, title, statement, category, priority,
safety, verify: {kind, target, op, value}, allocation: [uris] | unallocated, rationale, source}]`.
`verify.kind` ∈ `param_bound | geometry_prop | bom_rollup | calc | interference | count |
interface | manual | rule`; the target scheme must match the kind (`param://`,
`part://x#props.…`, `bom://rollups#…`, `calc://m.f`, `asm://`, `part://` (count), `iface://`,
`rule://<pack>/<rule>`; `rule` takes no `op`/`value` — see [checks.md](checks.md)). `n2f lint` adds:
a measurable value with a unit in the statement (unless the kind is binary), a verify block,
an allocation, and `safety: true` requirements need verify.

**parameters.yaml** — `parameters: {slug: {value, unit, description} | {expr, unit}}`.
Expressions are arithmetic over other parameter slugs (write `a - b` with spaces, since
slugs contain hyphens) plus `min/max/abs/sqrt/ceil/floor/round`.

**parts/<id>.yaml** — `id, rev, name, kind: custom|cots|reference (owner-supplied or existing, not quoted), process, material: {name, spec,
density?}, finish, tolerance_class: ISO2768-f|m|c|v (custom only), geometry: {kit, args} |
{module} | none, interfaces, satisfies, cost: {unit, basis, note}, lead_time, mass?,
source: {vendor, mpn, url, verified} (COTS), manufacturer_notes`. Kit args may reference
`param://` and `iface://`; quantities are strings like `15 mm`.

**assemblies/<id>.yaml** — `id, rev, name, build: unit|phantom, driver: [...], geometry:
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

**Build units and the build plan** (P7, P8, S-110): a sub-assembly is a *unit* (`build:
unit`, the default), put together on its own and fitted as a whole, or a *phantom* (`build:
phantom`), a grouping whose lines fold into the step of the unit that contains it. `driver:`
says why a unit is built on its own: `built-as-unit`, `tested-as-unit`, `serviced-as-unit`,
`separate-process-or-supplier`, `varies`, `agent-context`; `n2f lint` warns
(`L13-assembly-driver`) on a unit sub-assembly without one. The top assembly is always the last
step and needs neither field. The `bom` rule derives the plan from the tree,
`build/bom/build-plan.json`: one step per unit, children first, each with its items (numbered;
the same numbers on the unit's assembly sheet and in `build_step()`), the joints it closes (an
interface closes in the lowest assembly containing both parties' homes, folded up to its unit)
with their hardware, and the ids of the checks that cover it. The plan is also a "Build plan"
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

**interfaces/<id>.yaml** — `id, kind: bolt-pattern|mating-face, parties: [two uris],
frame: {origin, normal, x_axis?}, frames: {party uri: frame} (per-party copies),
offset?, spec: {pattern, count, diameter, spacing, pitch_circle, fastener, depth, hardware} |
{width, depth, flatness_note, hardware}`. Spec quantities may be `param://` references. A frame
coordinate and `offset` may be a number (mm), a quantity, a `param://` or
`{expr: "<expression over parameter slugs>", unit: mm}` (evaluated like a parameter `expr`;
every slug is a recorded read). `offset` (default 0) is the signed distance along the normal
from the first party's frame to the second's once placed. The one convention: placed, both
frames point the same way (same normal, same `x_axis`); `place_by` needs `x_axis` on both
(P1, P2, S-106).

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
{key: quantity | word}, style: {…}, massing: [{kit, as, args, at?}], notes, screening,
decision` (schema: `core/model/concepts.py`; the full example is in `NAPKIN_STAGE.md` §3).
Optional fields screening reads: `envelope.door_swing` (a hinged door's opening angle,
`110 degree`; without it the door counts swung fully back), `envelope.door_width` (the leaf
when no massing call is named `door`), `envelope.target_volume` (`8 L`, the chamber volume
aimed for) and `site.touch_limit` (`60 degC`, the hottest outside surface allowed); see
[napkin.md](napkin.md).
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
C3 every `massing[].kit` is a kit generator, C4 `based_on` names an existing card, C5 `site`
keys come from the known list (`alcove_width, alcove_depth, alcove_height, floor_load,
circuit, region, lift_class, mass_limit, door_clearance, ambient_max, outdoor,
touch_limit`; an unknown key only warns), C6 at most one card is promoted, C7 a `promoted`
card carries a screening and `decision.dec` naming an entry in `model/decisions.yaml` (what
`n2f concept promote` writes) and a `rejected` card a `decision.reason`, C8 every number
screening reads is the right kind (`envelope.power` a power, `site.alcove_width` a length;
`QUANTITY_KINDS` in `core/concepts.py`). While `concepts/` holds a card, `n2f status` shows
an optional **Napkin** stage before Intake, complete once a card is promoted by
`n2f concept promote` — a status typed by hand is a blocker, not a pass (N11, review gate A).

**style.yaml** — `preset: industrial | appliance | lab, palette: {part role: colour},
finish: {part role: finish}, radius_scale: 1.0, reveal: 2 mm, fastener_visibility:
visible | hidden-front | hidden` (schema: `core/model/style.py`). `n2f init` seeds it with
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
