# Napkin2Factory — Grand Plan for v0.1

**Audience:** the autonomous agent that will build this. You are not supervised. Nobody will answer questions. You decide, you log, you continue.
**Companions:** `napkin2factory-handoff.md` (the why; read it once, fully), `REVIEW.md` (what the handoff got wrong; every finding there is resolved as a locked decision in §2).
**Owner's bar:** "as if you had an A+ engineering team" and "impeccable UX of the ECO loop". Time is not the constraint. Getting it right is.
**Amended 2026-10-30:** second review pass folded in — D12/D13 amended; D29–D32 added; M0, M4, M5, M8, §8, §9, §10, §12 touched accordingly.

---

## 0. Operating contract (read this before anything else)

1. **You own the outcome end to end.** Nothing in this plan is a suggestion to be confirmed with a human. Where the plan is silent, decide like a senior engineer would, write the decision to `DECISIONS.md` with rationale, and continue. Tag decisions the owner may want to revisit with `[revisit]`.
2. **Resumability.** Your context will be compacted several times. Keep `STATUS.md` current: current milestone, what is done, what is next, how to resume, open risks. Update it at every milestone boundary and after any significant decision. When you resume from a reset, read in this order: `GRAND_PLAN.md` → `STATUS.md` → `DECISIONS.md` → `git log --oneline -30` → run `make check`.
3. **Green before commit.** `make check` (as defined for the current milestone in §8.2; it grows) passes before every commit. Commit at least once per milestone on branch `v0.1-build`. Never force-push. Never commit `build/` outputs.
4. **A milestone is done when its exit criteria pass by running the listed commands,** not when the code "should work". Milestones cannot be skipped or reordered. A milestone may be trimmed only via the ⤵ droppable items in §7, and the trim goes into `BACKLOG.md` with the reason.
5. **Look at what you built.** Open rendered PNGs with your image-reading tool and judge them. Open generated HTML by parsing it, and with a headless browser when Playwright is available. A build that "ran" is not evidence; the artifact is.
6. **Use subagents deliberately.** Parallelize independent work (kit generators, doc templates, example products) with disjoint file ownership and integrate serially. At each review gate spawn a **fresh-context reviewer** (it must not have seen your design conversation) with the checklist in §8.3. Fix blockers; log the rest in `BACKLOG.md`.
7. **Network policy.** Allowed: package installation (`uv`, `pip`, Playwright's browser download), read-only PyPI name checks (`https://pypi.org/pypi/<name>/json`), the optional BOM URL check, and **one** download of the pinned viewer library (§2 D13) whose sha256 you record in `DECISIONS.md`. Forbidden: publishing to PyPI, npm, or GitHub; creating accounts; anything else.
8. **Also forbidden:** editing `LICENSE` (MIT plus liability disclaimer, pre-seeded by the owner; it is already in the repo — verify its presence at M0); deleting the handoff or review documents (move them to `docs/history/`); leaving failing tests or tests skipped without a reason string; bypassing a gate because it is inconvenient.
9. **Quality bar, enforced by `make check`:** `ruff` with rule sets `E`, `F`, `I`, `D` (public docstrings), `E722` (no bare except); `mypy --strict` on `napkin2factory.core` with `ignore_missing_imports` for `OCP` and `build123d`; pytest coverage ≥ 80 % on core; a grep that fails on `TODO`/`FIXME` in `src/` unless the line cites a `BACKLOG.md` id.
10. **Domain honesty.** When you need engineering data (thermal conductivity of ceramic fiber, Kanthal A1 resistivity, ISO 2768 bands) use published values, cite the source in the calc file, and flag the number as `[verify]` in `DECISIONS.md`. Never present an invented number as fact.
11. **Finish.** The run ends when §11's handoff deliverables exist and the definition of done in §1.3 passes from a clean clone.

---

## 1. Mission, non-goals, definition of done

### 1.1 Mission
Ship **napkin2factory v0.1**: a pip-installable Python package with CLI `n2f` that turns a text-only canonical product model into a manufacturable technical data package (3D, drawings, flat patterns, BOM, manuals, check matrix, HTML report), rebuilds exactly what an engineering change invalidates, and ships with the kiln as a complete worked example. Mechanical and BOM only.

### 1.2 Non-goals for v0.1 (go to `BACKLOG.md`, not into code)
Electrical stage (KiCad), FEA/sim gates, MCP server, hosted anything, orchestrator process, multi-agent runtime, upgrade migrations, manufacturer quote APIs, electronics distributor APIs, GD&T-grade drawings, **tolerance stack-up analysis** (v0.1 has only a per-part tolerance class, see D26), manufacturer capability profiles beyond the schema, Class-A surfacing, Tauri wrapper, npm shim, share mode (`n2f publish`).

### 1.3 Definition of done (all must pass from a clean clone on Linux)
_Amended 2026-10-31 (owner, DECISIONS S-001): the reference platform is the macOS sandbox host; Linux is covered by the CI matrix only._
1. `uv sync && make check` is green, and `make check-full` is green (§8.2).
2. `uv run n2f init demo --template bracket && cd demo && uv run n2f build && uv run n2f check` completes in under 2 minutes (asserted by `tests/e2e/test_timing.py`, which runs only under `N2F_TIMING=1`, see D30) and produces `build/report/index.html`, a self-contained page with a 3D view, a drawing, a BOM, and a check matrix that works when opened from disk (`file://`), with no external script, module, or asset references (D13).
3. `examples/kiln` builds from clean in under 10 minutes (asserted in `make check-full` under `N2F_TIMING=1`); `tests/validate_outputs.py` derives the expected artifact set from the model and asserts it: a drawing SVG for every custom part, a flat-pattern DXF for every sheet-metal part, STEP and GLB for every part and assembly, BOM CSV and XLSX with cost and mass rollups, a check matrix with no `fail`, manuals as HTML and PDF, example sign-offs present and labelled as examples, and a report no larger than 20 MB (D13).
4. `examples/kiln/demo.sh` runs the parametric ECO loop unattended: file ECR-001 → impact report → approve → apply → rebuild → check → re-sign (labelled example step) → release `v1.1.0` → diff page with SVG drawing overlays, BOM delta with cost impact, and changed-part 3D highlighting. `examples/kiln/demo-design.sh` then runs the design ECO loop for ECR-002 (pre-authored patch, see D7) to `v1.2.0`. Both run in a temporary copy of the example (D23).
5. Invalidation tests prove exact rebuild sets (change one parameter → precisely the expected artifacts rebuild, nothing else; an unused parameter → nothing).
6. Agent layer: a fresh-context subagent whose prompt contains only the product-repo `CLAUDE.md`, the `n2f-pm` skill text, and an instruction to work inside a given product directory runs a scripted intake for a new product ("wall bracket for a 10 kg monitor") and produces a model that passes `n2f validate` and `n2f lint`, then a first silhouette via `n2f build --target geometry`.
7. A fresh-context subagent follows `README.md` from scratch in a new venv (installing from source) and reaches the report page without help.
8. `uv build` and `twine check dist/*` pass. PyPI name availability for `napkin2factory` and `n2f` is checked read-only and recorded. Nothing is published.
9. `HANDOFF-REPORT.md` exists (§11).

---

## 2. Locked decisions (do not relitigate; add new ones to `DECISIONS.md`)

| # | Decision | Why |
|---|---|---|
| D1 | CLI binary `n2f`; package `napkin2factory`; manifest `n2f.yaml` | One brand token; resolves handoff inconsistency (REVIEW B1) |
| D2 | Python 3.13 pinned via `.python-version`; 3.14 allowed if OCP wheels install; `uv` for env and lock; commands documented as `uv run n2f …` until installed as a tool. **The chosen OCP wheel and the resulting render path (D12) are one paired decision, recorded together in `DECISIONS.md` at M0** — the `novtk` fallback wheel removes the VTK render path | OCP wheel maturity (REVIEW E); wheel/renderer coupling |
| D3 | Geometry: build123d on cadquery-ocp. No FreeCAD, no Zoo in v0.1 | Tier-0 pip-only (REVIEW B4) |
| D4 | **Kit of parts** is a core module; agents compose generators; generators emit features, dims, flat patterns | REVIEW A1 |
| D5 | **Runtime-recorded dependencies** via logging accessors `P[...]`, `I[...]`, plus declared edges; in-house hash DAG, no Snakemake | REVIEW A5 |
| D6 | Checks are the gate; agent roles are conventions. No orchestrator process in v0.1 | REVIEW B5 |
| D7 | ECR `kind` is `parametric` or `design`. Parametric ECRs are applied mechanically from `edits`. Design ECRs carry `tasks` for the designer agent and may carry `patch` (a unified diff over `model/`) that `n2f ecr apply` applies; this is how a design ECR can be demonstrated unattended | REVIEW A4; reviewer finding |
| D8 | Document prose is templated source; value reads are recorded; stale sections block release | REVIEW A4 |
| D9 | Safety: `safety: true` requirements need a sign-off file at release; sign-offs are bound to evidence hashes (D25); disclaimer everywhere | REVIEW C1 |
| D10 | Stage is computed from repo state by `n2f status`, never stored; `warn` never blocks anything | REVIEW C2 |
| D11 | Drawings = build123d SVG projections with hidden lines + programmatic dimension callouts + title block. DXF via ezdxf | REVIEW B4 |
| D12 | Renders for agent eyes: pick the first that works with zero system packages, in this order: VTK offscreen (**only available when the chosen OCP wheel bundles VTK; the `novtk` fallback removes this path — see D2**), numpy z-buffer rasterizer over the tessellation, matplotlib `Poly3DCollection`. Renders are for correctness checks, not marketing | REVIEW A2; wheel/renderer coupling |
| D13 | 3D viewer = **three.js** (pinned version: core, GLTFLoader, OrbitControls) vendored under `report/vendor/` as source, but **shipped inlined**: at report build the vendored modules and the ~200-line `viewer.js` are concatenated into a single inline `<script type="module">` block in the page — **external ES-module files do not load from `file://`** (opaque-origin CORS), inline module scripts do. Viewer features: node access by part URI (click → part card), exploded view by node transforms, changed-part highlighting. The report is **fully self-contained**: GLBs embedded as base64, **one mesh per part URI, instanced per occurrence** via node transforms (quantities come from assembly YAML), no external `<script src>`, `<link>`, or fetchable asset of any kind. `tests/validate_outputs.py` asserts: no external references, report ≤ 20 MB. `n2f serve` exists for convenience only. model-viewer is not used (no node API). **M0 must prove the inline-module viewer skeleton loads from `file://`** | REVIEW C7; reviewer findings (file:// modules, size budget, instancing) |
| D14 | Reproducibility is geometric (volume, bbox, area, tessellation hash at fixed deflection), tolerance-compared; title-block dates are excluded from hashing and from drawing diffs | REVIEW B3 |
| D15 | BOM validation tiers: structural → URL-resolves (offline-skippable) → curated catalog. No external APIs | REVIEW B2 |
| D16 | Interface = named frame + feature pattern, consumed by both parties' generators, verified by an `interface` check. v0.1 kinds: `bolt-pattern`, `mating-face` only | REVIEW B6 |
| D17 | One HTML report with an owner/engineer toggle; safety content is never behind the toggle **Amended 2026-10-31 (S-052): the toggle is gone; one layout with a section index, persona picks only the wording.** | REVIEW C6 |
| D18 | Assembly YAML declares membership and quantities (the BOM structure); assembly geometry is Python; checker verifies instance counts in geometry equal YAML quantities | Prevents BOM/CAD drift |
| D19 | Three example products: `bracket`, `enclosure`, `kiln`. `bracket` and `enclosure` are also the `n2f init` templates: `make templates` syncs them into `src/napkin2factory/templates/` and a test asserts equality | REVIEW C8; single source |
| D20 | Monorepo: `src/napkin2factory` (system) and `examples/` (products). Product repos pin `system: ">=0.1,<0.2"` | Handoff §6 |
| D21 | Units: pint everywhere in the model; geometry code converts at the boundary with `mm()` helper | Handoff §7 |
| D22 | Git stays hidden behind `n2f` verbs; solo mode = plain local git; vocabulary mapping (draft/snapshot/change request/released/Revision) in all user-facing text and schema field names | Handoff §8 |
| D23 | **Every product is its own git repository.** `n2f init` runs `git init` and makes the first snapshot. Examples are committed in the monorepo in pre-ECO state (ECRs `draft`, no sign-offs for changed evidence, no tags). Any test, demo, or e2e that applies ECRs, releases, or diffs first copies the example to a temporary directory and runs `git init` there. `n2f` refuses to release or diff when the product directory is not the root of a git repository | Reviewer finding |
| D24 | Addressing grammar: `<uri>#dotted.path` selects a field or computed property (`req://REQ-001#verify.value`, `part://outer-shell#props.bbox.x`, `asm://kiln#props.mass`, `bom://rollups#total_cost`). Used by ECR edits, `verify.target`, and docs | Reviewer finding |
| D25 | A sign-off records `evidence_keys` (the artifact keys of every item in `evidence` at signing time). If any evidence key changes, the requirement reverts to `needs-human` | Reviewer finding; handoff "never consent-wash" |
| D26 | Every custom part declares `tolerance_class` (ISO 2768 `f`/`m`/`c`/`v`); it appears in the title block and the manufacturer column; a general rule requires it. No stack-up analysis in v0.1 | Reviewer finding; handoff §9 L2 |
| D27 | `make check` (fast, every commit) = lint + types + unit + bracket + enclosure. `make check-full` (gates and before handoff) = `make check` + kiln + both demos + timing assertions (under `N2F_TIMING=1`, D30) | Reviewer finding |
| D28 | Markdown is the manual source format. Markdown → HTML via markdown-it-py. Markdown → Typst via a small in-house emitter (headings, paragraphs, emphasis, lists, tables, images, code, links). No Typst `@preview` packages (they download at compile time) | Reviewer finding |
| D29 | **Allowed-contact pairs in the interference check:** part pairs joined by a declared `mating-face` interface are expected to touch; the interference evaluator skips them and records them in the check evidence as `allowed-contact: iface://…`. The 1 mm³ threshold plus bbox prefilter covers incidental coincident faces elsewhere (e.g. stacked bricks). Boolean commons on coincident faces are numerically twitchy; design around them, don't fight them | Second-review finding |
| D30 | **Timing assertions run only under `N2F_TIMING=1`**, which `make check-full` and nightly CI set; `make check` never asserts timing. Margins are generous (the stated limits already include slack); a timing test is never skipped silently — if the environment can't meet it, that is a finding for `HANDOFF-REPORT.md` | Second-review finding (flakiness vs §0.8 no-skip rule) |
| D31 | **All git invocations go through one wrapper** (`core/vcs.py`) that captures stdout/stderr and translates every failure into persona vocabulary ("this folder isn't a napkin2factory project yet — run `n2f init`", "you have unsaved changes; snapshot or discard them before releasing"). Raw git output never reaches a user-facing stream. Runtime tests trigger the not-a-repo and dirty-tree paths and assert the wording | Second-review finding (D22/D23 would otherwise leak "fatal: not a git repository") |
| D32 | `core/units.py` **defines** the non-stock units the model relies on: `USD` (currency as its own pint dimension), `d` (day), and locked handling of `degC` (affine unit). Unit tests pin parsing and formatting of `60 degC`, `85 USD`, `10 d` at M1 so this never surfaces later inside a cost rollup | Second-review finding |

---

## 3. Repository layout

### 3.1 System repo (this repo)
```
napkin2factory/
  pyproject.toml            # package napkin2factory, console script n2f
  uv.lock  .python-version  Makefile  README.md  LICENSE   # LICENSE pre-seeded (MIT + disclaimer); do not edit
  GRAND_PLAN.md  STATUS.md  DECISIONS.md  BACKLOG.md  HANDOFF-REPORT.md
  CLAUDE.md                 # rules for agents working on the system repo
  docs/
    history/                # handoff + review, moved here in M0
    concepts.md  vocabulary.md  product-model.md  cli.md  kit.md  checks.md  ecr-loop.md  agent-layer.md  render-checklist.md
  src/napkin2factory/
    __init__.py
    cli/                    # typer app, one module per verb
    core/
      uris.py               # URI scheme, #path selectors, parsing, resolution
      model/                # pydantic schemas: requirements, parameters, parts, assemblies, interfaces, decisions, ecr, manifest, operator, signoff
      loader.py             # YAML → model, cross-ref validation
      units.py              # pint registry (degC, USD, d — D32), parsing "50 mm", formatting
      vcs.py                # git wrapper; persona-vocabulary errors (D31)
      graph/                # build DAG: rules, hashing, manifest, incremental, dependency recording, impact
      checks/               # evaluators, rule packs, check matrix, gate semantics, stage computation
    geometry/
      accessors.py          # P and I logging accessors, mm() helper
      kit/                  # one generator per file: plate, bracket_l, enclosure, frame, panel, block, tube, hole_pattern
      build.py              # build_part(), build_assembly(): the API the DAG rules call
      exporters.py          # STEP, GLB (node and material names = part URIs), props JSON, features JSON
      render.py             # PNG views (D12)
      drawings.py           # SVG views + dimensions + title block; flat-pattern DXF
      assembly.py           # placements, instance counting
    bom/                    # rollups, CSV/XLSX, catalog, validation tiers
    docs/                   # Jinja2 over Markdown with recorded reads; markdown-it-py HTML; Typst emitter + typst-py PDF
    report/                 # self-contained HTML report, templates/, vendor/three/ (source; inlined at build, D13), viewer.js, diff pages, site layout
    ecr/                    # ECR lifecycle, apply (edits and patch), impact summary, revisions, changelog, release packaging
    rulepacks/              # YAML rule packs + runner (sheet-metal-v0, general-v0)
    catalog/                # curated common-parts catalog (YAML)
    templates/              # product skeleton (blank) + synced copies of examples/bracket and examples/enclosure
  examples/
    bracket/  enclosure/  kiln/   # product repos in pre-ECO state; kiln has demo.sh and demo-design.sh
  tests/
    smoke/  unit/  golden/  e2e/  fixtures/  validate_outputs.py
  .github/workflows/ci.yml  # ubuntu + macos matrix: make check; nightly: make check-full (sets N2F_TIMING=1)
```

### 3.2 Product repo (what `n2f init` writes; `examples/*` follow it exactly)
```
<product>/                  # root of its own git repository (D23)
  n2f.yaml                  # schema: 1, system: ">=0.1,<0.2", product: {id, name}, units: metric, manufacturer_profile: null
  operator.yaml             # persona, per-domain expertise, verbosity, delegation, language
  CLAUDE.md  AGENTS.md      # identical content: what this repo is, vocabulary, rules for agents
  .claude/skills/n2f-pm/SKILL.md
  .claude/skills/n2f-design/SKILL.md
  .claude/agents/n2f-verifier.md
  .claude/agents/n2f-impact-analyst.md
  .github/workflows/        # build.yml (push), release.yml (tag → ZIP + Pages); written, actionlint-validated, not run
  model/
    requirements.yaml  parameters.yaml  decisions.yaml  intake.md
    parts/<part-id>.yaml
    assemblies/<asm-id>.yaml
    interfaces/<iface-id>.yaml
    geometry/<part_id>.py  <asm_id>.py        # file name = slug with '-' replaced by '_'
    calcs/*.py  tests/test_calcs.py
    docs/*.md               # manuals (templated Markdown)
    signoffs/REQ-xxx.yaml
    manufacturers/*.yaml    # optional capability profiles (schema only in v0.1)
  changes/ECR-xxx.yaml  changes/ECR-xxx.patch   # patch only for design ECRs
  reports/review-*.md       # verifier-agent reviews (committed; the only place that role may write)
  CHANGELOG.md
  build/                    # gitignored
```

---

## 4. Product model v0.1

### 4.1 URI scheme and selectors
`req://REQ-014`, `param://wall-thickness`, `part://outer-shell`, `asm://kiln`, `iface://shell-frame-mount`, `dec://DEC-031`, `ecr://ECR-019`, `doc://installation#power`, `calc://thermal.skin_temperature`, `rule://sheet-metal/min-bend-radius`, `bom://rollups`.
IDs: `REQ-\d{3}`, `DEC-\d{3}`, `ECR-\d{3}`; slugs `[a-z0-9]+(-[a-z0-9]+)*`. Selector (D24): `<uri>#dotted.path`. Instances in assemblies: `part://outer-shell#3`. Every URI in any file must resolve (`n2f validate` fails otherwise). Generators carry IDs into every output: GLB node and material names, SVG element ids, BOM rows, manual anchors, check matrix rows.

### 4.2 Schemas (pydantic; YAML on disk)

**requirements.yaml**
```yaml
requirements:
  - id: REQ-003
    title: Accessible surface temperature
    statement: Any surface a user can touch during operation stays below 60 degC at steady state.
    category: safety          # performance | geometry | cost | mass | safety | manufacturing | usability | interface
    safety: true
    priority: must            # must | should
    verify:
      kind: calc              # param_bound | geometry_prop | bom_rollup | calc | interference | count | interface | manual
      target: calc://thermal.skin_temperature     # or param://x, part://x#props.mass, bom://rollups#total_cost, asm://x, iface://x
      op: "<"
      value: 60 degC
    allocation: [part://outer-shell, param://fiber-thickness]   # or the string `unallocated` (lint requires one or the other)
    rationale: Burn prevention; see DEC-004.
    source: intake
```
`verify.kind` semantics: `param_bound` compares a parameter; `geometry_prop` compares a part/assembly prop selected by `#props.…` (bbox.x/y/z, volume, area, mass, centroid.z); `bom_rollup` compares `bom://rollups#…` (total_cost, total_mass, part_count, custom_ratio, max_lead_time); `calc` calls a calc function; `interference` runs the interference check on an assembly; `count` compares instance counts; `interface` runs the interface conformance check; `manual` always yields `needs-human` until a valid sign-off exists. Safety requirements yield `needs-human` even when their calc passes, and `signed` once a valid sign-off exists (D25).

**parameters.yaml**
```yaml
parameters:
  chamber-width:   {value: 200, unit: mm, description: Interior clear width, owner: intake}
  fiber-thickness: {value: 50, unit: mm, description: Ceramic fiber board layer}
  wall-thickness:  {expr: "brick-thickness + fiber-thickness", unit: mm}   # safe AST evaluator, params only
```

**parts/<id>.yaml**
```yaml
id: outer-shell
rev: A
name: Outer sheet-metal shell
kind: custom                 # custom | cots
process: sheet-metal         # sheet-metal | machining | welding | cut-block | cut-sheet | 3d-print | none
material: {name: mild steel, spec: "1.5 mm CR4"}
finish: powder coat, black
tolerance_class: ISO2768-m   # D26; required for custom parts
geometry:
  kit: enclosure             # declarative generator call …
  args: {length: param://shell-length, width: param://shell-width, height: param://shell-height, thickness: param://shell-thickness, bend_radius: param://shell-bend-radius, flange: 15 mm, cutouts: [...]}
  # … or: {module: geometry/outer_shell.py}  exposing  def build(P, I, kit) -> PartResult
interfaces: [iface://shell-frame-mount, iface://shell-door-hinge]
satisfies: [req://REQ-007]
cost: {unit: 85 USD, basis: estimate, note: "sheet-metal shop quote class"}
lead_time: 10 d
mass: null                   # computed from geometry + material density unless declared
```
COTS parts add `source: {vendor, mpn, url, verified: false}`, omit `tolerance_class`, and have `geometry` as a kit primitive (block/tube) or `none` (then they are BOM-only and absent from 3D; the checker warns).

**assemblies/<id>.yaml** (D18)
```yaml
id: kiln
name: Mini electric test kiln
geometry: {module: geometry/kiln_asm.py}   # def build(P, I, parts) -> AssemblyResult with named instances
children:
  - {part: part://outer-shell, qty: 1}
  - {part: part://firebrick-k23, qty: 26}
  - {asm: asm://door, qty: 1}
exploded: {axis: z, spacing: 80 mm}   # hint for the viewer's exploded mode
```

**interfaces/<id>.yaml** (D16)
```yaml
id: shell-frame-mount
kind: bolt-pattern                     # bolt-pattern | mating-face
parties: [part://outer-shell, part://frame]
frame: {origin: [0, 0, 0], normal: [0, 0, -1]}
spec: {pattern: rect, count: 4, diameter: 6.6 mm, spacing: [300 mm, 300 mm], fastener: part://m6x16-bolt}
# mating-face spec: {width: 200 mm, depth: 200 mm, flatness_note: "as cut"}
```

**decisions.yaml**
```yaml
decisions:
  - {id: DEC-004, date: 2026-10-30, title: 50 mm ceramic fiber over 65 mm K23 brick, context: ..., decision: ..., rationale: ..., links: [req://REQ-003, param://fiber-thickness], made_by: agent, disclosed: true}
```

**changes/ECR-001.yaml**
```yaml
id: ECR-001
title: Increase chamber height by 50 mm
status: draft                # draft → impact → approved → applied → closed | rejected
kind: parametric             # parametric | design
requested_by: human
reason: Need to fire taller pieces.
edits:
  - {set: param://chamber-height, to: 250 mm}
  - {set: req://REQ-001#verify.value, to: 250 mm}
tasks: []                    # design ECRs: checklist for the designer agent
patch: null                  # design ECRs may point at changes/ECR-00x.patch (unified diff over model/)
impact: null                 # filled by n2f impact (§6.3)
approval: null               # {by, at, note}
applied: null                # {snapshot, build_id}
released_in: null            # set by n2f release
```

**operator.yaml**
```yaml
persona: owner               # owner | engineer (wording in the CLI and report)
domains: {mechanical: novice, thermal: novice, electrical: novice, manufacturing: novice}
verbosity: normal
delegation: balanced         # conservative | balanced | autonomous
language: en
```

**signoffs/REQ-003.yaml** (D25)
```yaml
requirement: req://REQ-003
by: "<name>"
role: human
date: 2026-10-30
statement: "I have reviewed the skin-temperature calculation and the insulation layout."
evidence: [calc://thermal.skin_temperature, doc://installation#safety]
evidence_keys: {calc://thermal.skin_temperature: "sha256:…", doc://installation#safety: "sha256:…"}   # written by n2f signoff
example: true                # examples ship with this flag; the report labels them "EXAMPLE SIGN-OFF, NOT A REVIEW"
```

**docs/*.md** front matter: `{id: installation, title, audience: [owner, engineer], depends_on: [part://..., req://...]}`; body uses `{{ P["fiber-thickness"] }}`, `{{ part("outer-shell").name }}`, `{{ req("REQ-003").statement }}`, `{{ bom.total_cost }}`. Every templated read is recorded as a dependency.

### 4.3 Stage computation (D10)
`n2f status` derives: **Intake** complete when `requirements.yaml` and `operator.yaml` pass `n2f lint`; **Design** complete when every custom part has geometry and `n2f build` succeeds; **Verify** complete when `n2f check` has no `fail` and every `needs-human` has a valid sign-off (evidence keys match); **Released** when a tag exists for the current tree. `warn` never blocks. `n2f status` prints the stage, the gates, and exactly what blocks the next gate, in the operator's persona vocabulary. Tested per stage with fixture products and expected `n2f status --json`.

---

## 5. CLI surface (typer)
```
n2f init <dir> [--template blank|bracket|enclosure]      n2f validate          n2f lint
n2f build [--target geometry|drawings|bom|docs|checks|report|site|all] [--part ID] [--clean] [--jobs N]   # --jobs default 1
n2f check [--format table|json|md]                        n2f status            n2f graph [--format dot|json] [--around URI]
n2f impact (--ecr ECR-001 | --set param://x=50mm ...)     n2f ecr new|impact|approve|apply|close|reject|list|show
n2f signoff <REQ-id> --by NAME --statement TEXT           n2f diff <ref-a> <ref-b> [--out DIR]
n2f release <version> [--dry-run]                         n2f serve [--port]    n2f doctor    n2f version
```
Exit codes: 0 ok, 1 validation/lint failure, 2 check failure, 3 gate blocked, 4 environment problem. All commands accept `--json`. Human output uses persona vocabulary (`docs/vocabulary.md`): branch = draft, commit = snapshot, PR = change request, merge = approved and released, tag = Revision. Errors from git paths go through the D31 wrapper; raw git text never surfaces. Until the package is installed as a tool, docs show `uv run n2f …`.

---

## 6. Build graph and dependency recording (the ECO engine core)

### 6.1 Rules, keys, and the needs-run decision
A rule has: id, declared inputs (files, upstream artifacts, generator code hash, rule version), recorded inputs (parameter keys, interface ids, selectors read during the last run), outputs (paths under `build/`), and a run function. `build/.n2f/manifest.json` records per rule: the **post-run key** (sha256 over sorted hashes of declared inputs plus the values of every recorded read), the recorded read set, outputs with hashes, duration, system version.
**Needs-run:** if the rule has no manifest entry → run. Else recompute the key from the *last recorded read set* against current values; if it differs from the stored key or any output is missing → run. After running, store the new read set and key. This makes "unused parameter changed → nothing rebuilds" true from the second build onward, and is sound because a change that alters which keys get read must itself have been read. `--clean` wipes the manifest.

Rule ids and order v0.1: `validate` → `part:<id>` (STEP, GLB, props.json, features.json, renders/*.png) → `asm:<id>` (GLB with named nodes and materials, props, instance counts) → `drawing:<id>` (SVG; DXF flat pattern when features include bends) → `bom` (rollups.json, validation.json, CSV, XLSX) → `doc:<id>` (HTML, PDF, reads.json) → `checks` (checks.json, matrix; consumes every `doc:*/reads.json` for staleness) → `report` → `site`.

### 6.2 Recorded reads (D5)
`P` and `I` are mapping-like accessors that return pint quantities / interface specs and append every key to a run-local read log. `kit` generators receive `P` and `I`, never raw floats, so reads inside generators are recorded too. Doc templating uses the same accessors plus `part()`, `req()`, `bom` proxies that record selectors. Code hash = sha256 of the generator module source plus the `napkin2factory.geometry` package version.

### 6.3 Impact (`n2f impact`)
Given hypothetical edits (from an ECR or `--set`), compute: (a) rules whose recorded reads intersect the edited keys, transitively through the DAG; (b) requirements whose `verify` targets are affected, and for `param_bound` / `bom_rollup` on declared values evaluate the hypothetical verdict now ("REQ-021 would fail: 3.4 kW > 3 kW"); (c) parts touched, with revision bumps implied; (d) docs with affected reads; (e) interfaces whose parties are affected; (f) sign-offs that would be invalidated; (g) for design ECRs, the declared `tasks` and a note that geometry-dependent verdicts are estimates until rebuilt. Output: structured block written into the ECR plus a Markdown summary in persona vocabulary, including cost delta from declared costs where computable. Nothing in the model changes.

### 6.4 Invalidation tests (must exist before M3 closes)
Fixtures assert exact rebuild sets, e.g. on `enclosure`: change `lid-thickness` → runs `part:lid`, `asm:enclosure`, `drawing:lid`, `bom`, `doc:assembly` (reads lid thickness), `checks`, `report`, `site`; does not run `part:base`, `drawing:base`. Change an unused parameter → runs only `validate`. Change a generator's source → runs its parts and downstream only. Change an interface spec → runs both parties.

---

## 7. Milestones

Each milestone lists **Build**, **Tests**, **Exit** (commands that must pass), and where applicable a **Review gate**. Budgets are guidance for scope control, not deadlines. ⤵ marks droppable items, which may be dropped only after the core of that milestone is green.

### M0 — Bootstrap and toolchain proof (budget 2 h)
**Build:** project skeleton with `uv`; `pyproject.toml` (package `napkin2factory`, script `n2f`; deps: build123d, pint, pydantic, pyyaml, ruamel.yaml, typer, jinja2, ezdxf, openpyxl, typst, numpy, httpx, pygltflib, markdown-it-py; dev: pytest, pytest-cov, ruff, mypy, hypothesis, lxml, selectolax, actionlint-py, twine, playwright optional); `Makefile` with `check`, `check-full`, `templates`, `goldens` (§8.2); `.python-version`; `CLAUDE.md` for the system repo; `STATUS.md`, `DECISIONS.md`, `BACKLOG.md`; `.gitignore`; `.github/workflows/ci.yml`; verify `LICENSE` is present and untouched (§0.8); move handoff and review to `docs/history/`; download the pinned three.js modules into `src/napkin2factory/report/vendor/three/` and record their sha256. Toolchain spike `tests/smoke/test_toolchain.py`: build a box with a hole in build123d; export STEP, GLB, SVG; confirm whether `export_gltf` propagates node names (if not, note the pygltflib post-pass as mandatory); compile a Typst PDF from a string; write a DXF; write an XLSX; produce one PNG render by whichever D12 path works — and **record the OCP-wheel/render-path pairing as one `DECISIONS.md` entry (D2/D12)**. **Viewer skeleton proof (D13):** build a minimal fully-inlined page (vendored three.js + a one-cube GLB base64, one inline `<script type="module">`) and prove it loads from `file://` — with Playwright if its browser installs, otherwise by asserting the page contains zero external `<script src>`/`<link>`/module references and logging the Playwright gap in `BACKLOG.md`. Branch `v0.1-build`.
**Exit:** `uv sync` ok; `uv run n2f version` prints; `make check` (M0 definition) green; first commit.

### M1 — Product model, URIs, units, validate, init (budget 4 h)
**Build:** all schemas of §4.2; URI parser with `#` selectors; loader with cross-reference resolution and actionable errors (file, id, what to do); pint registry **defining** `degC`, `USD`, `d` (D32) with parse/format helpers; safe `expr` evaluator; `n2f validate`; `n2f lint` (REVIEW C4 rules: measurable statement with units, verify present, category, `allocation` present; plus: every decision links something, every safety requirement has `verify`, every COTS part has `source`, every custom part has `tolerance_class`); `n2f init` with templates `blank` and `bracket`, running `git init` and a first snapshot (D23) through the `core/vcs.py` wrapper (D31); `examples/bracket` (one L-bracket, three requirements, parameters, one decision, one manual page); `make templates` sync and its equality test (D19).
**Tests:** valid/invalid YAML fixtures for every schema; URI and selector resolution; unit parsing round-trips including the D32 units (`60 degC`, `85 USD`, `10 d`); each lint rule with a failing fixture; `n2f init` → `n2f validate` e2e; template equality; vcs wrapper errors in persona vocabulary (not-a-repo path).
**Exit:** `n2f validate` and `n2f lint` pass on `examples/bracket`; fail correctly on `tests/fixtures/invalid/*`; `make check` (M1 definition) green.

### M2 — Geometry, kit, exporters, renders, assembly (budget 8 h)
**Build:** accessors (§6.2); part protocol (`build(P, I, kit) -> PartResult{shape, features, dims, flat_pattern, cut_list, props}`); `geometry/build.py` with `build_part()` and `build_assembly()` callable without the DAG, and a thin `n2f build --target geometry [--part ID]` that calls them directly (M3 re-routes it through the DAG); kit generators, one file each: `plate`, `bracket_l`, `enclosure` (orthogonal bends with K-factor table, flanges, cutouts, lid option, flat pattern with bend lines), `frame` (angle or square-tube members, cut list), `panel`, `block`, `tube`, `hole_pattern` (shared with interfaces); exporters: STEP; GLB where every part instance is a node **and** has its own material, both named with the part URI (pygltflib post-pass if build123d does not do it), **one mesh per part URI reused across instances** (D13); props JSON (bbox, volume, surface area, mass from a material density table, centroid); features JSON; renders (D12): front, top, right, iso, one section at the assembly mid-plane, parts coloured by stable hash of ID; assembly module with placements and instance counting; `examples/enclosure` (base + lid + two brackets, one bolt-pattern interface, one safety requirement "all exposed sheet edges deburred" verified `manual`) and the matching `n2f init --template enclosure`; `tests/validate_outputs.py` (derives expected artifacts from the model and opens each with a real parser; grows with each milestone); `docs/render-checklist.md`.
**Tests:** golden geometry per generator (volume, bbox, face count, feature counts; flat-pattern area equals developed area within 1 %); hypothesis property tests with low `max_examples` (no exceptions, positive volume, bbox matches inputs); STEP re-import equals export within tolerance; GLB node and material names equal part URIs; mesh reuse across instances asserted; instance counts equal YAML quantities; renders exist and are non-blank (pixel variance above threshold).
**Exit:** `n2f build --target geometry` on bracket and enclosure; **open the iso renders and confirm they show a bracket and a box with a lid**; record what you saw in `STATUS.md`.

### M3 — Build graph, incremental rebuild, impact (budget 6 h)
**Build:** §6 in full; `n2f build` orchestrates all rules (docs, checks, report may be placeholders until M4/M5); `n2f graph`; `n2f impact --set`; `--jobs N` opt-in parallelism across independent parts using a spawn-context process pool (OCCT is not thread-safe), default 1.
**Tests:** §6.4 invalidation suite on enclosure; second build after a no-op is a full no-op; manifest survives interruption (kill mid-build, rerun, converges); impact output equals the invalidation set; hypothetical `param_bound` verdicts correct; `--jobs 2` produces identical props to `--jobs 1`.
**Exit:** invalidation suite green; `n2f impact --set param://lid-thickness=3mm` on enclosure prints the expected set.
**Review gate 1 (architecture):** fresh-context reviewer on `core/graph`, `core/model`, accessors. Checklist §8.3. Fix blockers before M4.

### M4 — Checks, rule packs, requirement verification, gates, stage (budget 6 h)
**Build:** `CheckResult{id, subject, status: pass|fail|warn|skip|needs-human|signed, evidence, message, persona_message}`; evaluators for every `verify.kind` including `interface` (both parties' `features.json` contain the pattern in the interface frame) and `interference` (pairwise boolean common volume > 1 mm³ after bbox prefilter, COTS-to-COTS pairs skipped, **declared `mating-face` pairs allowed-contact per D29, recorded in evidence**); envelope and mass checks; BOM core: `rollups.json` (cost, mass, counts, custom ratio, max lead time) and validation (D15: completeness, sourcing fields, catalog match, URL HEAD with `--offline` skip) → `validation.json`; rule-pack runner over YAML rules evaluated against `features.json`; `rulepacks/sheet-metal-v0.yaml` (min bend radius ≥ k·t, min hole diameter ≥ t, hole-to-bend ≥ 2t + r, flange ≥ 4t, relief present) and `general-v0.yaml` (custom parts have process, material, finish, tolerance_class; every part in an assembly; no COTS part without source); calc runner (`calc://module.fn` with pint); safety and sign-off semantics (D9, D25) and `n2f signoff`; doc staleness consumer (reads.json vs current values); check matrix (requirements × status, rules × parts); `n2f check`; stage computation and gate logic (§4.3) used by `n2f status` and later `n2f release`.
**Tests:** every evaluator with pass/fail/needs-human fixtures; rule pack with known-good and known-bad fixture parts (a bend radius too tight must fail); interference fixture (two overlapping blocks); **allowed-contact fixture (two parts joined by a `mating-face` interface, touching, must pass with `allowed-contact` evidence)**; interface fixture (one party with a wrong hole spacing must fail); sign-off: non-safety `needs-human` → `pass`, safety → `signed`, changed evidence → back to `needs-human`; stage fixtures with expected `n2f status --json` for each stage; `warn` never changes the stage.
**Exit:** `n2f check` on bracket and enclosure with a correct matrix; a deliberately broken fixture product fails with exit code 2; `make check` (M4 definition) green.

### M5 — Drawings, flat patterns, BOM files, manuals, report (budget 8 h)
**Build:** drawings (D11): third-angle three views plus iso, hidden lines dashed, overall dims always, generator `dims` as callouts, hole table for patterns, title block (part URI, rev, material, process, finish, tolerance class, scale, "generated by napkin2factory vX.Y", date from the snapshot being built, in a `<g id="titleblock">` excluded from diffs); sheet-metal parts get a flat-pattern view with bend lines and the DXF; BOM CSV and XLSX (indented structure, qty rollup across subassemblies, totals from rollups.json, sourcing status column, "what to tell the manufacturer" column: process, material, finish, tolerance class, qty); docs engine (D8, D28): Jinja2 over Markdown with recorded reads, `depends_on`, HTML via markdown-it-py, PDF via the in-house Typst emitter and typst-py, mandatory Safety section template; report (D13, D17): single fully self-contained HTML — vendored three.js + viewer.js concatenated into one inline `<script type="module">`, embedded base64 GLBs with per-URI meshes instanced per occurrence, zero external references — with viewer (orbit, click → part card with URI and BOM row, exploded toggle from the `exploded` hint, section toggle ⤵), drawings gallery, BOM table, check matrix, requirements trace table, parameters, decisions, changes, docs links, status badges, disclaimer, sign-offs labelled `EXAMPLE` when flagged; owner/engineer toggle reorders sections and swaps vocabulary, safety content always visible (superseded by S-052: one layout with a section index, persona picks only the wording); `n2f serve`. ⤵ Playwright smoke test (page loads from `file://`, no console errors, viewer reports the expected node count) with HTML-parse fallback.
**Tests:** SVG contains expected view groups and dimension texts; DXF parses with ezdxf and has a bend-line layer; XLSX totals equal rollups.json; doc staleness fixture; Markdown → Typst emitter golden tests; report HTML contains every part URI and every REQ id and the embedded GLB; **no external `<script src>`/`<link>`/asset references; report size ≤ 20 MB (D13)**; persona toggle markup present; `validate_outputs.py` extended to drawings, DXF, docs, report.
**Exit:** `n2f build` end to end on bracket and enclosure; **open the report in a headless browser (from `file://`) or parse it and confirm every section renders**; rasterize or inspect one drawing SVG and confirm dimensions are legible and correctly placed; `make check` (M5 definition) green.

### M6 — ECR lifecycle, diff, release, site (budget 6 h)
**Build:** `n2f ecr new|impact|approve|apply|close|reject|list|show`; parametric apply edits YAML in place preserving comments and order (ruamel.yaml); design apply applies `patch` if present and prints the `tasks` checklist; `close` requires a green `n2f check` on the applied state; revision bump rules (part rev increments when its post-run key or declared fields change; assembly rev when any child rev changes); `CHANGELOG.md` append per closed ECR; `n2f diff A B`: builds both refs in temporary worktrees, reusing `build/site/<version>/` when a ref is a released version; SVG overlay (old red, new green, both re-projected at one shared scale, title blocks excluded), BOM delta table with cost and mass impact, parameter and requirement verdict deltas, changed/added/removed part list consumed by a side-by-side 3D diff page; `n2f release vX.Y.Z`: refuses unless the directory is a git root (D23), gates pass (§4.3), and the tree is clean — refusals worded through the D31 wrapper; tags; builds ZIP (STEP, drawings PDF bundle, DXFs, BOM.xlsx, manuals PDF, report); writes `build/site/vX.Y.Z/` frozen and `build/site/diff/vA..vB/`; updates `build/site/index.html` (latest); sets `released_in` on closed ECRs; `--dry-run`.
**Tests (all in a temporary copy of `examples/enclosure` with `git init`, D23):** e2e new → impact → approve → apply → build → check → close → signoff → release → diff; diff page contains overlay SVG and delta tables; release refused when a check fails, when the safety sign-off is missing, and when evidence keys changed after signing; **refusal messages asserted in persona vocabulary with no raw git text (D31)**; revision bumps exact; a design ECR fixture with a patch applies and closes.
**Exit:** the enclosure ECO loop runs unattended by a script; diff page exists and is correct.
**Review gate 2 (UX):** fresh-context reviewer plays a non-technical owner using only `n2f` output text and the report; checklist §8.3 UX items.

### M7 — Agent layer and intake (budget 4 h)
**Build:** product-repo `CLAUDE.md`/`AGENTS.md` (repo purpose, vocabulary, "run `n2f validate` after every model edit, `n2f build --part` after every geometry edit, `n2f check` before claiming done", never edit `build/`, log every decision as `DEC-`, safety floor text); `n2f-pm` skill: intake protocol (what and why, who uses it, size envelope, performance targets, environment and safety, budget and quantity, manufacturing preferences, what exists already), question triage by consequence, register adaptation from `operator.yaml`, safety floor, turning asks into ECRs, explaining reports and impact in persona vocabulary; `n2f-design` skill: compose kit first, inner loop with renders, interface usage, decision logging, calc conventions; `n2f-verifier` agent (reads `build/` and `model/calcs`, writes `reports/review-*.md`, must not edit `model/`); `n2f-impact-analyst` agent; `n2f init` writes all of these; `docs/agent-layer.md`.
**Tests:** templates render and validate; `n2f lint` catches a weak requirement produced by a scripted bad-intake fixture.
**Exit:** scripted intake simulation (§1.3 item 6): you spawn a fresh-context subagent whose prompt contains the product `CLAUDE.md` text, the `n2f-pm` skill text, the absolute path of a freshly `n2f init`ed directory to work in, and a role-played user transcript; its result passes validate and lint and builds a silhouette. Save the transcript under `tests/e2e/intake-transcripts/`.

### M8 — The kiln (budget 10 h)
Build it **as a user would**, through `n2f` and the skills, in `examples/kiln`. Target: small front-loading electric test kiln, chamber about 200 × 200 × 200 mm, 1200 °C class, single-phase mains (decide region and log it). Parts (about 15): outer sheet-metal shell (kit enclosure), door assembly (sheet skin + brick + fiber, hinge and latch COTS), insulating firebrick K23 (COTS, with cut list), ceramic fiber board (COTS), floor slab, element grooves as brick-layer features, heating element coil (COTS Kanthal A1; resistance and power as parameters with a sizing calc; no electrical design), controller enclosure (kit), controller line items (PID, SSR, thermocouple as COTS), frame/stand (kit frame), fasteners. Interfaces: shell–frame mount (bolt-pattern), shell–door hinge (bolt-pattern), controller box–shell (mating-face). Calcs: 1-D steady-state conduction through layers → heat loss and skin temperature; element power from heat loss plus heat-up target; mass from geometry. About 15 requirements including safety (skin temperature, controller separated from hot zone, dedicated circuit disclosure, door interlock as a documented manual requirement), cost target, mass limit, envelope, chamber volume, door swing. Decisions logged for every material and sizing choice with citations and `[verify]` tags. Manuals: assembly, installation and safety (electrician required), operation, maintenance (element replacement), manufacturer package notes. Example sign-offs with `example: true`. ECR-001 parametric (chamber height +50 mm) in `draft`; ECR-002 design (add a peephole with plug to the door) in `draft` with a pre-authored `changes/ECR-002.patch` that you produce by making the change, capturing the diff, and reverting. `demo.sh`: copy to temp, `git init`, release `v1.0.0`, run ECR-001 to `v1.1.0` with the labelled re-sign step, print paths to the impact report, diff page, ZIP. `demo-design.sh`: same, then ECR-002 to `v1.2.0`.
**Tests:** kiln added to `make check-full` with the 10-minute assertion (under `N2F_TIMING=1`, D30); golden props for the kiln assembly; both demos run as tests in `make check-full`.
**Exit:** §1.3 items 3 and 4. **Open the kiln iso and section renders: it must read as a kiln (double wall, chamber cavity, door, stand, controller box). Open a rasterized flat pattern. Open the diff page.** Record your judgment in `STATUS.md`.
**Review gate 3 (engineering):** fresh-context reviewer with an adversarial mechanical and thermal engineer stance reviews calcs, requirements, decisions, and the manufacturer package for the kiln. **It also role-plays a sheet-metal shop and a brick supplier reading only the manufacturer package and writes `reports/shop-readthrough.md`: could they quote? what is missing or ambiguous?** Fix blockers; log the rest. This read-through is a launch-day artifact — keep it.

### M9 — Hardening, docs, packaging, handoff (budget 4 h)
**Build:** README (what it is; the liability disclaimer; install from source with `uv tool install .` or `pip install -e .`, noting `uvx napkin2factory` will work once published; 10-minute first run; the three doors with door 3 working and doors 1–2 described as planned); `docs/*.md`; `n2f doctor`; product-repo workflow templates validated with actionlint; `uv build`; `twine check`; read-only PyPI name checks; `HANDOFF-REPORT.md` (§11); final `STATUS.md`. ⤵ `docs/vocabulary.md` localization hooks.
**Exit:** §1.3 items 1, 2, 7, 8, 9; `make check-full` green from a clean clone. **Review gate 4 (onboarding):** a fresh-context subagent in a new venv follows README from scratch and reports friction; fix what is cheap, log the rest.

---

## 8. Testing and verification strategy

### 8.1 Layers
- **Unit:** schemas, URIs and selectors, units (including D32), evaluators, rule runner, graph keys and needs-run logic, ECR state machine, stage computation, Markdown → Typst emitter, vcs wrapper wording (D31).
- **Golden:** per-generator geometry props with tolerances (D14); kiln assembly props. Goldens are regenerated only by `make goldens` with a logged reason.
- **Property (hypothesis, low `max_examples`):** generators over argument ranges; graph invalidation under random edit sequences (rebuild set equals impact set; a clean rebuild yields identical props).
- **E2E (subprocess `uv run n2f`, in temporary copies with `git init`):** init → validate → build → check → ecr loop → release → diff, on every example.
- **Artifact assertions (`tests/validate_outputs.py`):** expected artifact set derived from the model; every output opened by a real parser (STEP re-import, GLB via pygltflib, SVG via lxml, DXF via ezdxf, XLSX via openpyxl, PDF page count, HTML via selectolax); report self-containment and ≤ 20 MB (D13); timing thresholds for DoD items 2 and 3 under `N2F_TIMING=1` only (D30).
- **Visual (you):** at M2, M5, M8 exits, open renders and judge them against `docs/render-checklist.md`.
- **Browser (optional):** Playwright smoke on the report and diff pages from `file://`.
- **Interruption:** kill a build mid-way; a rerun must converge with no corrupt manifest.
- **Clean-clone:** `make check-full` in a fresh clone and fresh venv before every review gate from gate 2 onward.

### 8.2 `make check` and `make check-full` (D27, D30)
`make check` grows by milestone and must be green at every commit:
- M0: `ruff check && ruff format --check && mypy src/napkin2factory/core && pytest tests/smoke tests/unit`
- M1: + `pytest tests/e2e` and for `bracket`: `uv run n2f validate && uv run n2f lint`; template equality test
- M2: + `pytest tests/golden`; for `bracket` and `enclosure`: `uv run n2f build --target geometry` then `python tests/validate_outputs.py`
- M3: + full `uv run n2f build` for both; invalidation suite
- M4: + `uv run n2f check` for both; `--cov=napkin2factory.core --cov-fail-under=80`
- M5 onward: + `validate_outputs.py` over all artifacts; TODO grep
`make check` never asserts timing. `make check-full` = `make check` + kiln validate/lint/build/check + `demo.sh` + `demo-design.sh` + the DoD 2/3 timing assertions, all with `N2F_TIMING=1` exported. Run at review gates 2–4 and before handoff; CI runs it nightly.

### 8.3 Review-gate checklists (give these to the fresh-context reviewer verbatim, plus file paths; do not give it your conclusions)
- **Architecture (gate 1):** Can any rule read model data without going through recording accessors? Are post-run keys complete (code hash, rule version, interface specs, selector reads)? Is the needs-run logic correct on first run, second run, and after an interrupted run? Is impact a superset of invalidation? Can the manifest be corrupted by interruption? Is OCCT state leaking across process-pool workers? Are errors actionable (file, id, what to do)?
- **UX (gate 2):** Run `n2f status`, file an ECR, run impact, approve, build, read the report as a novice. Is any git vocabulary visible — including in error paths (force the not-a-repo and dirty-tree errors and read them)? Is the impact report understandable without engineering vocabulary and still precise? Does the owner view lead with cost, pictures, and manufacturer instructions? Does the engineer view lead with the matrix? Is anything safety-relevant hidden behind a toggle (it must not be)? Does every error tell the user what to do next? Does the report work when opened from disk (`file://`), with no console errors?
- **Engineering (gate 3):** Are the thermal and power calcs dimensionally correct and cited? Are the requirement thresholds defensible? Are the safety requirements complete for a mains-powered 1200 °C device (at minimum: touch temperature, electrical isolation of the controller, dedicated circuit, element replacement procedure, ventilation note)? Would a sheet-metal shop be able to quote from the package — write `reports/shop-readthrough.md` role-playing the shop and the brick supplier? Is anything presented as verified that is only computed? Are example sign-offs unmistakably labelled?
- **Onboarding (gate 4):** README from scratch in a clean venv; time to first report; every command copy-pastable; nothing requires an account.

---

## 9. Workflow rules

- **Branch:** `v0.1-build`. Commit messages: `M<n>: <what>` plus body. Never rewrite history.
- **Journal cadence:** `STATUS.md` at every milestone boundary, after every review gate, and whenever you take a non-obvious decision. It must let a cold reader resume in under five minutes.
- **Subagents:** implementation subagents get a complete brief: files they own, the protocol they implement, tests they must add, the command that proves it. Reviewers get the §8.3 checklist, file paths, and nothing of your reasoning. Subagents inherit the system repo's context, not a product directory's `.claude/`; when a task must run "as a product user", paste the product `CLAUDE.md` and skill text into the prompt and give the absolute product path. Integrate one subagent's work at a time and run `make check` between integrations.
- **Blockers:** never stop. Apply the §10 fallback; if none fits, choose the simplest option that keeps the definition of done reachable, log it with `[revisit]`.
- **Scope control:** if a milestone passes about three times its budget, drop its ⤵ items first, then simplify (fewer kit generators, fewer kiln parts), never the loop (build → check → ECR → impact → apply → diff → release) and never tests.
- **No invented facts** in docs, calcs, or BOM. A COTS part needs a real vendor and a plausible URL marked `verified: false` if you could not check it.
- **Vocabulary:** no git words in user-facing strings or schema field names; `tests/unit/test_vocabulary.py` greps CLI strings, templates, and schema field names for `branch`, `commit`, `merge`, `PR` outside `docs/vocabulary.md` — **and runtime tests force the git error paths (not-a-repo, dirty tree) and assert the D31 wrapper's persona wording, so nothing leaks through stderr**.

---

## 10. Risk register and fallbacks

| Risk | Signal | Fallback |
|---|---|---|
| OCP wheels fail on this Python | `uv sync` error | Pin 3.13; try `cadquery-ocp-novtk` with build123d `--no-deps` plus explicit deps; last resort 3.12. Record the wheel/render pairing (D2/D12) |
| `export_gltf` missing, broken, or drops node names | Smoke test | Tessellate and write glTF with pygltflib (one node and one material per instance, named by URI; one mesh per part, instanced) |
| No offscreen render path works | Smoke test | numpy z-buffer rasterizer over tessellation (flat shading, 4 views); accept lower quality |
| Typst fails | Smoke test | PDF via Playwright `page.pdf()` on the HTML; only if both fail, PDF becomes a `[revisit]` item recorded in `HANDOFF-REPORT.md` and DoD 3 is reported as partially met |
| three.js download blocked | M0 | Report ships a turntable PNG gallery instead of the viewer; 3D viewer logged `[revisit]` |
| Inline-module report fails from `file://` or exceeds 20 MB | M0 skeleton proof; M5 size assertion | Coarser tessellation deflection for embedded GLBs; verify instancing is active; as last resort split GLBs into sibling files, document that the report then requires `n2f serve`, and log `[revisit]` |
| `ExportSVG` lacks hidden lines | M5 | Use OCCT HLR via OCP directly; or visible-only views with a logged limitation |
| Interference check slow on kiln | M4 timing | bbox prefilter, skip COTS-to-COTS pairs, allowed-contact pairs (D29), cache by pair keys |
| Process pool and OCCT crash | M3 | Keep `--jobs 1` default; parallel stays opt-in |
| Playwright cannot install Chromium | M5 | HTML-parse checks only; log |
| Flat-pattern math for flanges with reliefs is wrong | Golden area test | Restrict kit v0 to orthogonal bends with a K-factor table; log limitation |
| Markdown → Typst emitter gaps | Emitter goldens | Unsupported constructs render as plain text with a `warn` check, never a crash |
| Kiln engineering numbers uncertain | Always | Cite, `[verify]`, conservative margins, example sign-offs clearly labelled |
| Context reset mid-milestone | Always | `STATUS.md` discipline; manifest-based builds are idempotent |
| Subagent edits collide | Integration | Disjoint file ownership; serial integration; `git diff --stat` before accepting |

---

## 11. Handoff deliverables (`HANDOFF-REPORT.md`)
1. What works, per definition-of-done item, with the exact commands run and their timing.
2. What was dropped or simplified, with reasons (`BACKLOG.md` cross-references).
3. Decisions tagged `[revisit]` and numbers tagged `[verify]`, each with one line on why it matters.
4. The 30-second demo script: the exact sequence (commands and the report pages to show) for the ECO-loop GIF.
5. Known rough edges in UX, ranked.
6. Recommended next steps for v0.2 (electrical stage, MCP server, manufacturer profiles, share mode, stack-up analysis), each with a one-paragraph design sketch grounded in what exists.
7. Name availability results for `napkin2factory` and `n2f` on PyPI (read-only check only).
8. The `reports/shop-readthrough.md` verdict from gate 3, quoted: it is the launch-day credibility artifact.

---

## 12. How the owner should run this plan (not for the agent)
- **Driver:** Claude Fable 5.1, effort **high**, bypass permissions, sandboxed Linux with network for package installs, 4+ cores, 8+ GB RAM, Python 3.13 available. Not fast mode.
- **Subagents, as instructed above:** implementation chunks may run on Opus 5.5 at default effort; review gates run on Fable 5.1 at **xhigh**, fresh context.
- **First message to the driver:** "Read `GRAND_PLAN.md`. It is your contract. Execute it to completion."
- **Expect:** two to four days of wall-clock; several context compactions; a `v0.1-build` branch with milestone commits; `HANDOFF-REPORT.md` at the end.
