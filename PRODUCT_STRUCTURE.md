# Napkin2Factory — PRODUCT_STRUCTURE.md: plan for v0.4 ("the tree")

**Audience:** the agents who build v0.4. Each works on one milestone or task at a time, and none
remembers an earlier session. Work flows as `AGENTS.md` says: one task per worktree, landed with
`make land`.

**Companions:** `GRAND_PLAN.md` (v0.1, D-series) and `NAPKIN_STAGE.md` (v0.2, N-series) stay in
force, except where a P-series decision below amends them. Also read `DECISIONS.md` and
`BACKLOG.md`.

**Origin:** a modularity review on 2026-11-01, plus a fresh-context review of this plan against
the code. The maintainer asked whether napkin2factory builds one monolithic assembly or
sub-assemblies joined together. The question came after research into how industry and recent
agent-CAD work structure assemblies. This plan answers the review's five findings.

---

## 0. Why this release (read once; it calibrates every judgment call)

The schema can already nest assemblies:
- it multiplies quantities through the levels;
- it indents the BOM and groups nodes in the GLB;
- it rebuilds a sub-assembly on its own (S-049).

The products do not use it. Measured on 2026-11-01:

- **The kiln is flat.** Its top assembly has 34 child lines. Its one sub-assembly, the door, has
  8. The bracket and the enclosure each have one level.
- **The manual knows more than the model.** The kiln's hand-written assembly manual describes five
  units: shell and guard, lining, door ("built as one unit"), controller box, and stand. The model
  records one of them.
- **Placement is hand arithmetic.**
  - `examples/kiln/model/geometry/kiln.py` (242 lines) places every part with offsets and Euler
    angles that the agent computed by hand.
  - 12 parameters named `*-half-*` exist only to write interface frame coordinates.
  - So do six more: `standoff-pattern-z-shell` and `-guard`, `mount-pattern-z-shell`,
    `hinge-post-z-guard`, `latch-keeper-z-guard` and `controller-mount-y`.
- **The interface check cannot see a misplaced part.** It compares hole patterns in each part's
  own coordinates, in 2D within the frame plane (`core/checks/interface.py`). It never checks that
  the two frames meet once the parts are placed: moving the controller box 10 mm in `kiln.py`
  would still pass `controller-mount`. The frames are not consistent in 3D either:
  - their origins sit 0–40 mm apart along the normal;
  - one interface (`controller-mount`) has its two normals facing each other, while every other
    interface has both pointing the same way.
- **The door has no declared joint to the kiln.** Interfaces join parts only, and the check skips
  assembly parties (B-0005, the interface check for assembly-level parties). The door is coupled
  to the kiln both ways:
  - `door.py` reads `hinge-pin-y` and `door-gap`, which are measured from the kiln's guard plane;
  - the kiln's `hinge-post-y` and `hinge-post-reach` read the door's `door-tray-depth` and
    `door-guard-width`.
- **One flat parameter namespace:** 159 parameters in one file, with name prefixes standing in for
  modules.
- **The build plan is not modelled.**
  - Bolts are typed-in numbers: 50 M6×16 at the top and 8 in the door. Nothing counts them
    against the interfaces that use them.
  - `shell-frame-mount` describes an M6×50 bolt but names the M6×16 part.
  - Nuts, rivet nuts and standoffs appear in no interface.
  - No field says whether a sub-assembly is built as a unit or is only a grouping.
  - There are no drawings of assemblies.

What the research found:

- **Middle-out design.** Fix the layout and the interfaces first, then detail each module against
  them (Creo skeletons, Onshape variable studios). Parts reference the parent's hub, never each
  other.
- **A module needs a reason, a "driver"** (Erixon's modular function deployment). It is built or
  tested as a unit, serviced as a unit, made by a different process or supplier, or varies between
  product variants. A grouping without a driver is a phantom: in the build plan its parts fold
  into its parent.
- **Interfaces are contracts with an owner and a check** (NASA SE handbook §6.3). In CAD they are
  named frames that parts are placed by: Onshape mate connectors, build123d joints.
- **One tree; the factory's build plan is derived from it**, never kept as a second, hand-edited
  tree.
- **Recent agent-CAD work** (ArtiCAD, AssemCAD, 2026 preprints):
  - plan the structure and the connection points as data first;
  - generate each part on its own;
  - place the parts with plain code;
  - check and redo one unit at a time.

The scope in one sentence: **an agent decides what joins what and why a group exists; the code
does the placement arithmetic, the counting and the checking, one module at a time.** When unsure
whether something belongs in v0.4, ask whether it makes a module buildable and checkable on its
own. If it doesn't, it waits.

## 1. Mission, non-goals, definition of done

### 1.1 Mission
Ship **napkin2factory v0.4**:
- parts placed by their interfaces, with alignment checked in the assembly;
- sub-assemblies with ports, so modules never reach into each other;
- a build plan derived from the tree: build units and phantoms, with hardware counted from the
  interfaces;
- scoped parameters, and a command that prints one module's whole working context;
- promotion that keeps the napkin's modules;
- checks at two levels, and a review of the joints between units.

Restructure the kiln with all of it and ship it as the demo. The bracket and the enclosure stay
flat, and their outputs must not change.

### 1.2 Non-goals for v0.4 (stay in `BACKLOG.md`)
- Everything that `GRAND_PLAN.md` §1.2 and `NAPKIN_STAGE.md` §1.2 exclude, except what is named
  above.
- **Moved to v0.5 or later:** electrical (B-0035), manufacturer profiles (B-0038) and tolerance
  stack-up (B-0039), all earlier slated for v0.4. Stack-up becomes easier once P1–P3 make chains
  of frames explicit.
- **Not in v0.4 at all:**
  - kinematic joints (a hinge that swings), degrees of freedom, a numeric constraint solver,
    closed loops;
  - automatic module clustering (DSM);
  - one folder per module on disk;
  - product variants and platforms;
  - a multi-agent runtime (B-0041);
  - hidden-line assembly drawings with balloons;
  - turning one drawn part into a weldment or kit in the build plan;
  - schema migrations (B-0042).

### 1.3 Definition of done (from a clean clone; the macOS host plus the CI matrix, S-001)
1. **Builds and compatibility.**
   - `make check` and `make check-full` are green.
   - The bracket and enclosure goldens are unchanged.
   - A product made by `n2f init` from a 0.3 template builds with the same outputs, plus the new
     build-plan files.
2. **Placement by interfaces in the kiln.**
   - `kiln.py` places every joint that has an interface with `place_by` (P1).
   - The 18 frame-only helper parameters are gone, replaced by frame expressions (P2).
   - The alignment stage of the interface check (P3) passes for every kiln interface.
   - A fixture with the controller box shifted 10 mm fails, naming both occurrences and the
     distance. This regression test is the release's reason to exist.
   - The decision entry records the coordinate-placement line count before and after.
3. **The kiln's tree.**
   - The kiln has at least two build units with drivers: the door and the controls.
   - A grouping without a driver is a phantom.
   - Every interface whose parties sit in different modules is a port (P4), including the door's
     hinge and latch joints.
   - Parts with no interface at all (the lining) are placed by coordinates, and the build marks
     them as such.
   - `door.py` reads no parameter outside its reach (P5).
4. **Build plan.**
   - The build plan exists as `build/bom/build-plan.json`, as a sheet in the BOM XLSX and as a
     report section.
   - Each build unit gets one assembly sheet.
   - The kiln's assembly manual takes each unit's part and hardware lists from `build_step(...)`.
   - The kiln's hardware check (P9) passes with every hardware line accounted for, and a fixture
     with a missing bolt fails.
5. **One module, one agent.**
   - `n2f context asm://door` prints the door's working context (P6). Record its size in bytes.
   - A fresh-context agent gets only the design role and that output, then makes a scripted
     change to the door. Use a subagent where the client has them, otherwise a new session with
     no history.
   - The agent must pass `n2f check --scope asm://door`, leave the kiln-level checks green, and
     open no file outside the context it was given.
   - Save the transcript under `tests/e2e/module-transcripts/`.
6. **Promotion with modules.**
   - In a fresh `n2f init`, a concept card with modules promotes into a top assembly, one stub per
     module, and three size budgets per module.
   - `n2f build && n2f check` is green, with empty modules shown as `warn`.
   - On the kiln, which already has assemblies, promotion only suggests modules.
7. **Review gates.**
   - Gate C (architecture and honesty) and gate D (UX in the owner persona) are closed, with their
     reports in `docs/reviews/`.
   - The maintainer judges a screenshot of the report's build-plan section and one assembly sheet
     (S-078).
8. **Docs.**
   - The agent guide is updated.
   - The design, verifier, pm and impact-analyst roles are updated in
     `templates/_common/roles/`, then synced with `make templates`.
   - `docs/vocabulary.md` is updated.
   - `HANDOFF-REPORT-v0.4.md` exists.

---

## 2. Locked decisions (P-series)

| # | Decision | Why |
|---|---|---|
| P1 | **Interfaces place parts.** An assembly module calls `place_by(I, res, "<iface-id>", "part://x", parts["x"], onto="<label>", label="…")`. This places the child so that its frame coincides with the frame of the party already placed in `res`. `onto` picks the occurrence when there are several. <br><br>**One convention:** both parties' frames point the same way in the world, with the same normal and the same `x_axis`. The second party's origin sits `offset` along the normal from the first party's. Eight of the nine kiln interfaces already follow this convention. `controller-mount` has facing normals, so M1 rewrites the controller box's frame. <br><br>**Placing by coordinates.** `place(...)` with coordinates stays for parts with no interface. Each `Placement` records how it was placed, and `n2f check` warns when a part was placed by coordinates although it has an interface with a party already placed in the same assembly. <br><br>**Reuse:** `place_by` takes the frame basis from `geometry/kit/hole_pattern.py::frame_basis`, the one the holes are cut with. It raises a `GeometryError` with the fix when a frame it uses has no `x_axis`. | Hand-computed placement is the weakest step for an agent. The agent chooses the joint; code does the arithmetic (build123d joints, ArtiCAD) |
| P2 | **Interface frames are complete and computable.** <br>• `offset` is the signed distance along the normal from the first party's frame to the second's. Default 0. It accepts a quantity, a `param://` or an expression. <br>• A frame coordinate may be `{expr: "<expression over parameter slugs>", unit: mm}`, evaluated exactly like a parameter `expr`, with the same grammar and the same unit handling. <br>• Every slug named in an expression is a recorded read (D5). It is also seen by the impact analysis of change requests (`core/graph/impact.py::_static_reads`) and by loader reference validation. <br>• The kiln's measured offsets (M0) are its first test vectors | Frames become connectors that need no helper parameters, and every read stays visible |
| P3 | **Alignment is checked in the assembly.** The `interface` check gains a second stage. <br>• It runs in the lowest assembly that contains both parties. <br>• Every occurrence of each party needs a partner occurrence whose world frame matches: origin plus `offset`, normal, and `x_axis`. <br>• The tolerances are 0.5 mm and 0.5°. That is a design choice, not a measured value; record it so. <br>• A failure names both occurrences and the distance between them | Today a misplaced part passes, because only part-local 2D patterns are compared |
| P4 | **Sub-assemblies have ports; siblings never reach into each other.** <br>• An interface whose parties sit in different assemblies is listed under `ports:` in every assembly between each party and the lowest assembly containing both. <br>• "Sits in" uses the party's home (P5). <br>• `place_by` places a sub-assembly by a port: it finds the party's occurrence inside the built sub-assembly. <br>• A missing port is a validation error that names the file to edit. <br>• `asm://` as an interface party is refused, with a pointer to ports. Holes live on the parts that carry them, and assemblies export those joints. This closes B-0005, the interface check for assembly-level parties | The KiCad hierarchical-label rule and SysML ports. A module can be built and checked alone |
| P5 | **Parameters have a scope.** <br>• A parameter may carry `scope: asm://<id>` and `export: true`. <br>• **Home:** a part's home is the lowest assembly containing all its occurrences. A hardware part used in several assemblies therefore lives at the top. <br>• **Reach:** a part or assembly rule whose home is inside X may read X's parameters, its ancestors' and the unscoped ones. A parent may read a child's parameter only when it is exported. Siblings never read each other's. <br>• **What is checked:** part and assembly rules only. Reads made while resolving an interface frame are exempt: P2 records the other party's frame reads, and these are the port's business. Doc, bom, drawing, calc and check rules are exempt. Parameter `expr` dependencies are checked statically. <br>• **Severity:** `warn` in v0.4. Unscoped parameters behave as today. <br>• **Kiln coupling:** the door's `door-tray-depth` and `door-guard-width` become `export: true`, because the kiln's hinge post depends on them | One hub per level (Creo published geometry, Onshape variable studios), and a bounded context for a module's agent |
| P6 | **A module's context is a command, not a folder.** `n2f context asm://<id> [--json]` prints: <br>• the assembly YAML and its parts; <br>• its scoped parameters; <br>• the ancestor parameters it reads, taken from the last build's recorded reads (it says so when nothing is built yet); <br>• its ports, with the other parties' frames but not their geometry; <br>• the requirements allocated to it or its parts; <br>• the two commands: `n2f build --asm <id>` and `n2f check --scope asm://<id>`. <br>Files stay where they are | No migration, and one layout. The module becomes the unit of agent work |
| P7 | **Every sub-assembly says why it exists and how it is built.** <br>• `build:` is `unit` (the default) or `phantom`. <br>• `driver:` is a list drawn from `built-as-unit`, `tested-as-unit`, `serviced-as-unit`, `separate-process-or-supplier`, `varies` and `agent-context`. <br>• Lint warns on a sub-assembly without a driver. <br>• A phantom is a grouping only: its parts fold into its parent's build step. <br>• The top assembly needs neither field | Module drivers (modular function deployment), and phantom assemblies as in a manufacturing BOM |
| P8 | **The build plan is derived from the tree.** The assembly YAML stays the one tree (D18). The build plan comes from it: <br>• one step per build unit, children before parents, phantoms folded in; <br>• each step lists its parts, the joints it closes (interfaces whose lowest common assembly it is), their hardware, and the ids of the checks that cover it. The ids are static, because `bom` runs before `checks`; the report joins them to verdicts. <br><br>**Outputs:** <br>• `build/bom/build-plan.json`; <br>• a sheet in the BOM XLSX; <br>• a report section; <br>• a docs helper `{{ build_step("asm://door") }}`, through recorded reads (D5); <br>• an assembly sheet per build unit, made by a new `asmsheet:<id>` rule that depends on `asm:<id>` and `bom`. It reuses the iso and exploded renders and adds an item table keyed to BOM lines. <br><br>**Owner text** names a build unit ("the door, built as one unit") and calls a port "a joint between units"; field names stay in files and `--json` (N5, D17) | One tree, two views. Each unit becomes a step with its own instructions and checks |
| P9 | **Interface hardware is counted (the `hardware` check stage; `count` is already taken by D18).** <br>• `spec.hardware: [{part, per_hole}]` lists everything one hole takes, e.g. `[{part: part://m6-standoff-25, per_hole: 1}, {part: part://m6x16-bolt, per_hole: 2}]`. The old `fastener: X` is read as `[{part: X, per_hole: 1}]`. <br>• A hardware part is any part named in some `spec.hardware`. <br>• Where holes are shared (S-051: one hole, two interfaces), only one of the interfaces lists hardware; the other has `hardware: []` and a description saying which one does. <br>• In each assembly, the declared quantity of a hardware part, phantom children included, must be at least the demand of the joints that close there. <br>• Fewer is a `fail` that names the joints and the missing number. More needs `spare: "<reason>"` on the child line, otherwise it is a `warn`. <br>• Hardware that serves no interface (rivet nuts, earth studs, glands) carries `spare:` or `loose: true` with a reason | The kiln's bolt counts become numbers with a source. Today they cannot be reconciled |
| P10 | **Promotion keeps the napkin's modules.** <br>• A massing line may carry `module: <slug>`, and a card may carry `modules: {<slug>: {driver: [...], build: unit\|phantom}}`. <br>• When the product has no assembly yet, promotion seeds the top assembly, one sub-assembly stub per module, and three size budgets per module: `geometry_prop` requirements on `asm://<m>#props.bbox.x`, `.y` and `.z`, taken from the module's massing box and labelled `computed`. Changing a budget is a decision. <br>• A new rule, `general-v0` "module has parts", reports an empty stub as `warn`. <br>• When assemblies already exist, promotion only prints the modules as a suggestion. <br>• A card without modules promotes as today | The napkin already sketches the modules (body, door, controls, stand). Keeping them is middle-out design |
| P11 | **Start flat; split for a reason.** <br>• The design role says: a product starts as one assembly. Make a sub-assembly only when a P7 driver applies, or when the module's `n2f context` would exceed what one agent can hold. That threshold is set from the M4 measurement, not guessed. <br>• Splitting later is cheap because the interfaces are already explicit (P1–P4). <br>• The bracket and the enclosure stay single-level | A sub-assembly without a reason is handling overhead; a product without explicit interfaces cannot be split |
| P12 | **Checks run at two levels, and rework stays narrow.** <br>• `n2f check --scope asm://<id>` runs one module's checks: its parts' rules and requirements, its internal interfaces (both stages), interference inside it, and its hardware. It writes to `build/checks/scope/<id>/` and never overwrites the full matrix. <br>• The check matrix groups rows by module. <br>• The verifier role classes each failure as inside a module (rework that module) or at a port (an interface change, so a change request touching both sides). The impact-analyst role reports which ports a change request crosses. <br>• Editing an interface invalidates both parties. This holds today through recorded reads; it gets a test | Redo only the failing unit (ArtiCAD's rollback). Interface changes are the costly ones (NASA SE handbook) |
| P13 | **The joints between units get a design-for-assembly review.** <br>• The report lists every joint between units with its hardware count. <br>• For each part at such a joint, the verifier role asks Boothroyd's three questions: does it move, must it be a different material, must it be separate to assemble or service? <br>• Merge candidates are logged as `DEC-` entries or as product notes. <br>• No automatic verdict: this is judgment | Splitting a product into modules adds brackets and fasteners exactly at those joints |
| P14 | **Backward compatible.** <br>• Every new field is optional, with a default that reproduces v0.3 behaviour. <br>• Schema version 1 stays (S-056). <br>• Product pin `>=0.4,<0.5` at release (S-083) | Existing products and the two flat examples must not move |

## 3. Schema additions (all optional; shapes only, not kiln data)

```yaml
# model/interfaces/guard-standoff-left.yaml
frames:
  part://outer-shell: {origin: [{expr: "-shell-outer-width / 2", unit: mm}, 0, {expr: "...", unit: mm}],
                       normal: [-1, 0, 0], x_axis: [0, 0, 1]}
offset: {expr: "guard-gap + guard-thickness", unit: mm}       # P2: signed, first party → second
spec: {pattern: rect, count: 4, diameter: param://mount-bolt-clearance, spacing: [...],
       hardware: [{part: part://m6-standoff-25, per_hole: 1}, {part: part://m6x16-bolt, per_hole: 2}]}

# model/interfaces/hinge-upper.yaml — a welded hinge: no holes cut (P4, M3)
kind: mating-face
parties: [part://hinge, part://hinge-post]

# model/assemblies/door.yaml
build: unit                                                    # P7
driver: [built-as-unit, serviced-as-unit]
ports: [iface://hinge-upper, iface://hinge-lower, iface://latch-catch]   # P4
children:
  - {part: part://m6x16-bolt, qty: 8}

# model/assemblies/kiln.yaml
children:
  - {part: part://m6-rivnut, qty: 4, loose: true, spare: "rail fixings for the stand bolts"}   # P9

# model/parameters.yaml
door-guard-width: {expr: "...", unit: mm, scope: asm://door, export: true}   # P5

# concepts/C-00x.yaml
modules: {door: {driver: [built-as-unit]}, controls: {driver: [tested-as-unit]}}
massing:
  - {kit: block, as: door, module: door, args: {...}, at: {...}}             # P10
```

## 4. CLI surface added
```
n2f build --asm <id>                  # one assembly and what it needs (an only_asm filter in rules_for_target)
n2f check --scope asm://<id>          # P12: one module's checks, written under build/checks/scope/<id>/
n2f context asm://<id> [--json]       # P6: one module's working context
```
Each verb or option lives in its own module under `cli/`. The task that adds it updates the agent
guide's command reference.

## 5. Milestones

Every milestone is one or more `make task` worktrees that land on `main`. Budgets are guesses:
record the actual times in the decision entries.

**Order:** M0 → M1 → M2 → M3, then M4 and M5 in parallel, then M6, then M7.

**Ownership for the parallel pair:**
- M4 owns `core/model/parameters.py`, `core/graph/rules.py`, `core/checks/engine.py`, `cli/` and
  the kiln's `parameters.yaml`.
- M5 owns `core/model/concepts.py`, `concepts/`, the design and pm roles, and the kiln's
  `concepts/`.
- Both touch `core/loader.py`. Keep each one's validation in its own function, and rebase before
  landing.

### M0 — Baseline and reconciliation (budget 3 h)
**Build:**
- Land this plan, its decision entry and the STATUS line.
- Write a throwaway script, outside `src/`, that computes each party's world frame for every kiln
  interface from `build/assemblies/*/instances.json` and the interface frames.
  - Run it on today's kiln. Record in the entry, per interface: the direction convention, the
    offset along the normal, and the in-plane miss. The reviewer's hand figures to confirm or
    correct:
    - shell-frame-mount 0;
    - hinge post and latch keeper 3 mm;
    - each guard-standoff interface 26 mm (= `guard-gap` + `guard-thickness`);
    - controller-mount 40 mm, with facing normals;
    - door-guard-standoff negative.
  - Fix nothing yet.
- Reconcile the kiln's hardware by hand, for each hardware line: which holes use it, and how many
  per hole. Cover the 50 and 8 M6×16 bolts, the standoffs, the nuts, the rivet nuts and the
  M6×50 that `shell-frame-mount` describes but no part provides. Decide how S-051's shared holes
  count. Log each kiln fix as a `DEC-` in the product.
- Measure and record:
  - the lines of `place(...)` and coordinate code in `kiln.py` and `door.py`;
  - the parameter count;
  - the `make check-full` time.

**Tests:** none beyond the journal checks.

### M1 — Interfaces place parts (P1–P3) (budget 9 h)
**Build:**
- `core/model/interfaces.py`: `offset`, and `{expr, unit}` coordinates.
- `geometry/accessors.py::resolve_interface`: evaluate them, recording the reads.
- `core/graph/impact.py::_static_reads` and the loader's reference validation: see the slugs
  named inside expressions.
- `geometry/assembly.py`: `place_by` for parts only, reusing `frame_basis`; `Placement` records
  how it was placed.
- `core/checks/interface.py`: the alignment stage, with evidence (world frames and distance); the
  coordinate-placement warning (P1).
- Enclosure, as the small proof:
  - `lid-base-mount.yaml` gets `x_axis: [1, 0, 0]`, the computed default, so no hole moves;
  - migrate `examples/enclosure/model/geometry/enclosure.py`;
  - `make templates`. Its goldens must not move.
- Kiln:
  - migrate the part-level joints in `kiln.py`: stand, guard, shell, hinge post, latch keeper and
    controller box;
  - rewrite the controller box's frame to the one convention;
  - replace the 18 helper parameters with expressions.

**Tests:**
- `place_by` with a rotation, a positive and a negative offset, a part with qty > 1, and `onto`.
- A `GeometryError` for a missing `x_axis`.
- Alignment pass and fail fixtures, including the 10 mm controller shift (DoD 2).
- Facing normals fail.
- An expression coordinate is a recorded read and appears in change-request impact: changing
  `shell-outer-width` rebuilds both parties.

**Goldens:** kiln goldens are regenerated only with `make goldens REASON="..."` naming what moved
and why.

### M2 — Ports and module boundaries, part 1 (P4) (budget 5 h)
**Build:**
- `ports:` in `core/model/assemblies.py`.
- `core/loader.py`: home and lowest-common-assembly computation, the missing-port error, and the
  refusal of `asm://` as a party (closes B-0005, the interface check for assembly-level parties).
- Persist placement labels: `instances.json` and `FlatInstance` gain `label`, and
  `load_built_assembly` (S-049) reads it back.
- `place_by` for sub-assemblies: it resolves the party's leaf occurrence through
  `BuiltAssembly.leaves`, in the sub-assembly's frame.
- The alignment stage across levels.

**Tests:**
- A missing-port fixture is refused, naming the file.
- A port on a two-level fixture product places and aligns.
- A sub-assembly reloaded from disk places by port with `onto`.

### M3 — Build plan, hardware and the kiln's tree (P7–P9, rest of P4) (budget 10 h)
**Build:**
- Schema:
  - `core/model/assemblies.py`: `build`, `driver`, and the missing-driver lint;
  - `core/model/interfaces.py`: `spec.hardware` with the `fastener` alias;
  - `spare` and `loose` on child lines.
- `bom/build_plan.py`: the derived plan.
- Outputs:
  - the build-plan sheet in `bom/files.py`;
  - the report section, and the vocabulary entries for unit, phantom, joint between units and
    driver;
  - the `build_step()` docs helper in `docs/engine.py`;
  - the `asmsheet:<id>` rule in `core/graph/rules.py`;
  - `drawings/assembly_sheet.py`. Keep the report ≤ 20 MB and record its size.
- Checks: the `hardware` stage.
- Kiln:
  - **Door joints.** Add hinge-upper and hinge-lower (hinge to hinge post) and the latch catch.
    These are `mating-face` interfaces, because the hinge halves and the latch body are welded
    (`parts/hinge.yaml`, `parts/latch.yaml`). Declare the door's ports, place the door by port,
    and stop `door.py` reading kiln-frame parameters.
  - **Controls sub-assembly**: box, lid, controllers, SSR and contactor, with drivers
    `tested-as-unit` and `separate-process-or-supplier`.
  - **Lining**: a phantom unless a driver applies, placed by coordinates (it has no interface).
    Log the judgment as a `DEC-`.
  - Apply M0's hardware reconciliation.
  - Rewrite the assembly manual's unit sections around `build_step()`.

**Tests:**
- Build-plan order: children first, phantoms folded.
- Hardware fixtures: a missing bolt fails; a surplus without `spare` warns; shared holes count
  once.
- The XLSX sheet.
- One sheet per build unit and none for phantoms.
- Report self-containment and size.
- The door placed by port matches its previous position, or the golden reason explains the
  difference.

### M4 — Scope and module context (P5, P6, P12) (budget 7 h)
**Build:**
- `scope` and `export` in `core/model/parameters.py`, validated against existing assemblies.
- The reach check: read the manifest's recorded reads, apply the P5 exemptions, check `expr`
  dependencies statically, and emit `warn` rows in plain words with a rule id kept in `--json`.
- Commands:
  - `n2f build --asm` (the `only_asm` filter);
  - `n2f check --scope` (separate output folder, check matrix grouped by module);
  - `n2f context` in `cli/context.py`.
- Kiln: scope its parameters, and export the door's two coupled ones.
- Measure `n2f context` for the door, the controls and the kiln in bytes, and set P11's threshold
  from those numbers.

**Tests:**
- Reach: a sibling read warns; an ancestor read is clean; a read of an unexported child warns; a
  frame read through an interface is exempt; an `expr` across scopes warns.
- A context golden for the door, as a JSON key set.
- `--asm` builds exactly the expected rule set.
- `--scope` leaves `build/checks/` untouched.
- Editing an interface invalidates both parties.

### M5 — Napkin modules and promotion (P10, P11) (budget 5 h)
**Build:**
- `module:` and `modules:` in `core/model/concepts.py`, with the concept lint.
- Promotion (`concepts/promote.py`):
  - seeds the top assembly, the stubs and three budgets per module when no assembly exists;
  - prints a suggestion otherwise;
  - never overwrites anything, as today.
- The `general-v0` "module has parts" rule.
- The board lists each card's modules.
- The design role gets P11's rule; the pm role learns to ask what is built, bought or serviced as
  a unit.
- Kiln: add modules to its concept cards, and regenerate `goldens/kiln-board.json` with a reason.

**Tests:**
- A promotion golden YAML diff with modules.
- Suggestion only, on a product with assemblies.
- `n2f build && n2f check` green after promotion, with stubs as `warn`.
- The concept lint rejects an unknown driver.

### M6 — Two-level verification and the joint review (P12, P13) (budget 5 h)
**Build:**
- The report's table of joints between units.
- The verifier role: per-module review from `n2f context`, the inside-a-module vs at-a-port
  classification, and the three design-for-assembly questions.
- The impact-analyst role: which ports a change request crosses.
- `make templates`.
- Run DoD 5's module simulation (a subagent, or a fresh session where the client has none) and
  save the transcript.

**Tests:**
- The joints table on the kiln.
- The transcript exists, and `check --scope` passed in it.

### M7 — Review gates and close-out (budget 5 h)
- Gate C (architecture and honesty), then gate D (UX in the owner persona), each briefed from
  `docs/reviews/TEMPLATE.md`. Fix their blockers.
- Send the maintainer the build-plan section and one assembly sheet, with one question.
- The agent guide; `HANDOFF-REPORT-v0.4.md`.
- Bump the three version files and the product pins.
- `make check-full` from a clean clone.
- Tagging is the maintainer's call.

## 6. `make check` / `make check-full` growth
- New unit tests go into the parallel `make check`.
- The kiln's alignment and hardware checks run inside the existing kiln build in
  `make check-full`; record the time they add.
- The DoD 5 simulation is run by the M6 agent, not by CI. CI checks only that the transcript
  exists.

## 7. Risks
| Risk | Watch | Fallback |
|---|---|---|
| M0 finds kiln frames that cannot share one convention | M0 records every interface | Rewrite that frame (as for the controller box); never add a per-interface convention flag without a decision |
| The hardware reconciliation exposes kiln errors (the M6×50) | M0 lists them | Fix them in the kiln with a `DEC-`; this is the point |
| Pairing occurrences when qty > 1 | Partner-exists rule, grid fixtures | Require `onto` labels, and say so in the error |
| The reach warning is noisy | Unscoped parameters and interface-frame reads are exempt | It stays `warn` until a later version decides |
| Assembly sheets push the report past 20 MB | Measure in M3 | Lower-resolution sheets, linked from the BOM tab |
| Scope creep toward a mate solver or kinematics | Non-goal | Door swing stays B-0012 (the door-swing envelope as a geometry check) |
| Agents keep placing by coordinates out of habit | The P1 warning, the design role | The M6 simulation shows whether the role text works |

## 8. How the maintainer should run this plan
Start each milestone with `make tasks`, then `make task NAME=v04-m<n>-<slug>`. M4 and M5 can run as
two agents at once after M3 lands; every other milestone runs alone. Push only when asked.
