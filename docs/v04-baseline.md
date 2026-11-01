# v0.4 baseline: the kiln's frames, hardware and placement code before M1 (M0, S-105)

Measured on 2026-11-01 on `main` at `92ed777` (S-103, the v0.4 plan), macOS host. This is the
evidence M1–M3 of `PRODUCT_STRUCTURE.md` start from. Nothing in the kiln was changed: M3 applies
the hardware reconciliation and logs each kiln fix as a `DEC-` in the product.

## 1. Interface frames in the world (P1, P2)

**Method.** `scripts/v04_frame_survey.py --fresh examples/kiln` copies the kiln to a temp folder,
runs `n2f build`, and reads `build/assemblies/kiln/instances.json`. Every leaf there is already
in the kiln's world frame, the door's group transform included (`geometry/assembly.py::flatten`
multiplies the parent location in). For each interface it resolves the frames through
`geometry/accessors.py::resolve_interface`, builds each party's basis with
`geometry/kit/hole_pattern.py::frame_basis` (the one the holes are cut with), moves origin,
normal and x axis into the world by the occurrence's rotation and translation, and reports:

- **normals / x axes**: `same` when the world directions agree, `facing` when opposite;
- **offset**: the signed distance from the first party's origin to the second's, along the
  first party's world normal (P2's `offset`);
- **origin miss**: the distance between the origins once the offset is removed (in-plane);
- **hole miss**: the worst in-plane distance from a hole centre of the first party to the
  nearest hole centre of the second, which also catches an x-axis error a symmetric pattern
  would hide.

Each party occurs once, so each interface has one occurrence pair.

| interface | parties (first → second) | normals | x axes | offset (mm) | origin miss | hole miss | offset as an expression |
|---|---|---|---|---|---|---|---|
| shell-frame-mount | guard-shell → stand | same | same | 0 | 0 | 0 | `0` |
| guard-standoff-left | outer-shell → guard-shell | same | same | 26.0 | 0 | 0 | `guard-gap + guard-thickness` |
| guard-standoff-right | outer-shell → guard-shell | same | same | 26.0 | 0 | 0 | `guard-gap + guard-thickness` |
| guard-standoff-top | outer-shell → guard-shell | same | same | 26.0 | 0 | 0 | `guard-gap + guard-thickness` |
| guard-standoff-bottom | outer-shell → guard-shell | same | same | 26.0 | 0 | 0 | `guard-gap + guard-thickness` |
| guard-hinge-post | guard-shell → hinge-post | same | same | 3.0 | 0 | 0 | `hinge-post-thickness` |
| guard-latch-keeper | guard-shell → latch-keeper | same | same | 3.0 | 0 | 0 | `hinge-post-thickness` |
| controller-mount | controller-box → guard-shell | **facing** | **facing** | 40.0 | 0 | 0 | see below |
| door-guard-standoff | door-tray → door-guard | same | same | −26.5 | 0 | 0 | `-(door-skin-thickness + guard-gap)` |

**What this confirms.**
- The reviewer's hand figures hold: 0, 3, 26, 40 (facing) and a negative door value, which is
  −26.5 mm. Every frame pair already meets in the world (origin and hole misses 0.00 mm), so the
  P3 alignment stage will pass on today's kiln once the controller box frame is rewritten.
- Eight of nine interfaces follow P1's convention (normals and x axes the same way).
  `controller-mount` has both its normals **and** its x axes opposed (the box frame is a mirror
  of the guard's; their y axes agree).
- All 18 frames name an explicit `x_axis`, so P1's missing-`x_axis` error never fires on the
  kiln. The top-level `frame:` of every kiln interface is never used (both parties have
  `frames:` entries) and does not match either party; M1 may leave it or drop it.
- The offsets are between the faces the frames were written on (each sheet's outer face, the
  far face of the angle's leg), not the standoff lengths. That is fine for P2: the expressions
  above reproduce each one from existing parameters.

**What M1 must rewrite.**
- `controller-mount`, box frame: `normal: [1, 0, 0]`, `x_axis: [0, -1, 0]` (box coordinates).
  Checked with `centers_from_spec`: the box's four hole centres are identical before and after
  (the rect pattern is symmetric and the frame's y axis is unchanged). With the parties in their
  current order the offset is `-controller-standoff` (−40); swapping the parties to
  `[guard-shell, controller-box]` (parent first) makes it `controller-standoff`. Recommended:
  swap, so every kiln offset reads from the part already placed to the part being placed.
- `guard-hinge-post` and `guard-latch-keeper`: the post and keeper frames are literals
  `[-3, 20, 0]` and `[3, 20, 0]`, which are `hinge-post-thickness` and `hinge-post-leg / 2`
  typed as numbers. Not among the 18 helpers, but the same fault: change the angle's thickness
  and the frame stays put. M1 writes them as expressions.
- The 18 helper parameters (section 3) become frame expressions.

## 2. Hardware reconciliation (P9)

**Method.** By hand, from `assemblies/kiln.yaml`, `assemblies/door.yaml`, the nine interface
files, the part notes, `docs/assembly.md`, `docs/installation.md`, `decisions.yaml`, and the
built guard's hole table (`build/parts/guard-shell/features.json`).

### 2.1 Every hardware line today

| line (assembly, qty) | holes that use it | per hole | demand | verdict |
|---|---|---|---|---|
| m6-standoff-25 (kiln, 16) | guard-standoff-left/right/top/bottom, 4 holes each | 1 | 16 | matches |
| m6-standoff-25 (door, 4) | door-guard-standoff, 4 holes | 1 | 4 | matches |
| m6-standoff-40 (kiln, 4) | controller-mount, 4 holes | 1 | 4 | matches |
| m6x16-bolt (kiln, 50) | standoffs left/right/top 12 × 2; standoffs bottom 4 × 2; stand mount 4 × 1; hinge post 4 × 1; latch keeper 2 × 1; controller 4 × 2 | see left | 50 | the sum matches, but the bottom corners are impossible (2.2) |
| m6x16-bolt (door, 8) | door-guard-standoff, 4 × 2 | 2 | 8 | matches |
| m6-nut (kiln, 6) | guard-hinge-post 4, guard-latch-keeper 2 (part notes: "bolts and nuts") | 1 | 6 | matches; no interface names the nut |
| m6-rivnut (kiln, 4) | shell-frame-mount, stand side (set in the hollow rails, stand notes, DEC-009) | 1 | 4 | matches; **it is interface hardware**, not loose |
| earth-stud (kiln, 5) | none: one per metal part (shell, guard, door guard, stand, controller box) | — | — | not hardware under P9; the door guard's stud belongs in `door.yaml` |
| m20-gland (kiln, 3) | none: the controller box's three base cutouts | — | — | not hardware under P9 |
| ceramic-bush (kiln, 2) | none: the element tail holes (cutouts) | — | — | not hardware under P9 |
| fiber-anchor (kiln, 4) | none: hold the door plug to the door tray, holes drilled on assembly | — | — | not hardware; belongs in `door.yaml` |
| fiber-gasket (kiln, 1) | none: consumable laid on the door slab and round the plug | — | — | not hardware; belongs in `door.yaml` (assembly step 5.3) |

The 50 is explained exactly: 32 for sixteen standoffs at two bolts each, plus 4 stand bolts,
4 hinge-post bolts, 2 latch-keeper bolts and 8 controller bolts. The guard's built hole table
has 26 holes for 30 interface holes: the four stand holes are the bottom standoff holes (S-051,
confirmed: the two interfaces' guard hole centres are identical).

### 2.2 Kiln errors found
1. **Bottom corners: three accounts that disagree.** The shell → standoff → guard → rail stack
   shares one guard hole per corner (S-051).
   - `guard-standoff-bottom`'s description says one M6 × 50 bolt per corner into the rail's
     rivet nut. (The plan, S-103, attributes the M6 × 50 to `shell-frame-mount`; it is in
     `guard-standoff-bottom`. `shell-frame-mount` says only "four M6 bolts".)
   - Both interfaces name `part://m6x16-bolt`, and no M6 × 50 part exists.
   - The assembly manual bolts all sixteen standoffs from inside the shell and from outside the
     guard, then the installation manual bolts the guard to the rail's rivet nuts "through its
     four mounting holes" with M6 × 16. The BOM counts all three bolts per corner.
   - Physically one guard hole cannot take a bolt up into the standoff and another down into the
     rivet nut. Only a through bolt (shell → standoff → guard → rivet nut) fits the shared hole
     and DEC-007's load path; it needs a standoff threaded right through or a plain spacer
     [verify], and its head sits inside the shell, so it must go in after the body is on the
     stand and before the fiber floor: the manual's order changes.
2. **M6 × 16 into a 25 mm female-female standoff from both ends.** Thread left in the standoff
   per bolt: 16 − 1.2 (shell) = 14.8 mm and 16 − 1.0 (guard) = 15.0 mm, together 29.8 mm in a
   25 mm standoff; at the door 14.5 + 15.0 = 29.5 mm. If the standoff is tapped right through the
   two bolts meet; if each end is tapped blind, each must be shallower than 15 mm. The thread
   depth of McMaster 93655A135 was not checked [verify]. The 40 mm controller standoffs
   (15 + 15 = 30 mm) do not have this problem.
3. **Lines in the wrong assembly.** The door guard's earth stud, the four fiber anchors and the
   door's share of the fiber gasket are fitted while the door is "built as one unit" (assembly
   step 5) but are listed in `kiln.yaml`. Under P5's home rule and P8's build steps they belong
   in `door.yaml` (kiln: 4 earth studs, door: 1).
4. **Missing BOM lines.** The controller lid's four self-tapping screws (lid notes, assembly
   step 7.4), the rivets for the rating label (step 7.5) and for the latch keeper plate (keeper
   notes). The rivet counts are stated nowhere.
5. **Earth studs: two stories.** The part notes say "fitted by the installer"; the assembly
   manual fits each one during assembly (steps 1, 3, 5, 7).

### 2.3 Proposal for M3: `spec.hardware` per interface
Option A (recommended, the through bolt at the bottom corners; needs a new part
`m6x50-bolt` and the manual's order changed):

| interface | `spec.hardware` | holes | demand |
|---|---|---|---|
| guard-standoff-left, -right, -top | `[{part: part://m6-standoff-25, per_hole: 1}, {part: part://m6x16-bolt, per_hole: 2}]` | 4 each | 12 standoffs, 24 bolts |
| guard-standoff-bottom | `[{part: part://m6-standoff-25, per_hole: 1}]` (shares its holes with shell-frame-mount, which lists the through bolt) | 4 | 4 standoffs |
| shell-frame-mount | `[{part: part://m6x50-bolt, per_hole: 1}, {part: part://m6-rivnut, per_hole: 1}]` | 4 | 4 bolts, 4 rivet nuts |
| guard-hinge-post | `[{part: part://m6x16-bolt, per_hole: 1}, {part: part://m6-nut, per_hole: 1}]` | 4 | 4 bolts, 4 nuts |
| guard-latch-keeper | `[{part: part://m6x16-bolt, per_hole: 1}, {part: part://m6-nut, per_hole: 1}]` | 2 | 2 bolts, 2 nuts |
| controller-mount | `[{part: part://m6-standoff-40, per_hole: 1}, {part: part://m6x16-bolt, per_hole: 2}]` | 4 | 4 standoffs, 8 bolts |
| door-guard-standoff | `[{part: part://m6-standoff-25, per_hole: 1}, {part: part://m6x16-bolt, per_hole: 2}]` | 4 | 4 standoffs, 8 bolts |

Resulting lines: kiln `m6x16-bolt` 50 → 38, new `m6x50-bolt` 4, `m6-standoff-25` 16,
`m6-standoff-40` 4, `m6-nut` 6, `m6-rivnut` 4; door unchanged (`m6-standoff-25` 4,
`m6x16-bolt` 8). The bolt lengths stay subject to error 2. When the controls become a
sub-assembly (M3), `controller-mount` closes at the kiln level (box in the controls, guard at the
top), so its standoffs and bolts stay in `kiln.yaml`, not in the controls unit.

Option B keeps M6 × 16 everywhere but needs four separate stand holes beside the bottom
standoffs (a geometry change, and the lining load no longer goes straight down, DEC-007).

**Lines with no interface: no `spare:` or `loose:` needed.** By P9's own definition a hardware
part is one named in some `spec.hardware`; earth studs, glands, bushes, anchors, the gasket,
mortar, the label and the shelf set never are, so the check never counts them. Proposed `loose:`
meaning, if kept: shipped loose for the installer (the door switch; the earth studs if the part
note wins over the manual). No kiln line needs `spare:` under option A.

**Shared holes (S-051).** Proposed rule, replacing P9's "one interface lists everything, the
other `hardware: []`": *each item of a shared hole is listed once, on the interface whose joint
it is fitted to close*. The check sums demand per part, so a shared hole still counts once as
long as no item is listed twice; and the build plan (P8) puts the standoff in the step that
joins shell and guard and the through bolt and rivet nut in the step that puts the body on the
stand, which the all-on-one rule cannot do once those joints close in different units.

## 3. Measurements

**Placement code** (`scripts/v04_frame_survey.py --lines <product>`): each top-level statement
of `build()` is classed and its non-blank, non-comment lines counted. `place` is a statement that
calls `place(...)`; `coordinates` is any other assignment (position arithmetic); `reads` is an
assignment that only reads parameters; literal offsets are numbers other than 0 inside
`translate=` that are not scale factors (`/ 2`).

| module | file lines | place | coordinates | reads | place() call sites | literal offsets |
|---|---|---|---|---|---|---|
| kiln.py | 242 | 166 | 14 | 22 | 22 | 9 (all in the controls: 70, 76, 10, 76, 45, 20, 1, 100, 1) |
| door.py | 78 | 46 | 1 | 8 | 6 (7 occurrences: a loop of two hinges) | 4 (30, 7.5, 22, 12.5) |

Placement and coordinate code: **180 lines in `kiln.py`, 47 in `door.py`**; this is DoD 2's
"before". Of the 22 kiln call sites, 6 are joints with an interface that M1 migrates (stand,
guard, shell, hinge post, latch keeper, controller box); the door, 10 lining parts, the lid and
the 4 instruments have no interface and stay on coordinates until M3. In `door.py`, 1 of 6 has
an interface (the door guard on the tray).

**Parameters:** 159 in `examples/kiln/model/parameters.yaml`.

**The 18 frame-only helpers** (12 `*-half-*`, `standoff-pattern-z-shell`,
`standoff-pattern-z-guard`, `mount-pattern-z-shell`, `hinge-post-z-guard`,
`latch-keeper-z-guard`, `controller-mount-y`). Searched across the repository (`examples/`,
`src/`, `tests/`, docs) and in the built manifest's recorded reads. Each is read only by
interface frames, directly or through another helper's `expr`:
- `controller-half-width` is read only by `controller-neg-half-width`'s expr;
  `shell-half-width`, `shell-half-height`, `guard-half-width` and `guard-half-height` also
  feed their `neg-` twins; `guard-half-depth` also feeds `mount-pattern-z-shell`.
- Recorded reads: only the part rules of the parties (through `I[...]`, which resolves every
  frame of the interface) and the `report` rule, which lists all parameters.
- No geometry module, part YAML, doc, calc, requirement or concept reads any of them.

So all 18 can go when frames take expressions (P2). Mirror helpers of the same kind exist
outside interface frames (`tail-neg-hole-x`, `thermocouple-neg-offset-x`, `tail-hole-z-shell`,
`thermocouple-z-shell`, read by part cutouts); they are not in v0.4's scope.

**Times.** `n2f build` of a fresh kiln copy: 1 min 31 s wall, measured while `make check-full`
ran in parallel on the same machine. `make check-full` in the task folder: **19 min 28 s** wall
(1168 s), exit 2. `make check` passed inside it (unit tests: 745 passed, 5 skipped, 7 min 29 s),
the kiln end-to-end tests passed (8), and one demo failed: `test_demo_design`, because
`examples/kiln/changes/ECR-002.patch` (the peephole) no longer applies with `git apply` to
`model/geometry/door.py` and `door_fiber.py`, both last changed in f1d6680 (S-085–S-096). It
`git apply --check` fails the same way on a fresh copy of `examples/kiln`, which M0 does not
touch, so it predates M0; not fixed here (B-0063).

## 4. What the evidence changes in the plan
- P9, shared holes: the rule in 2.3 replaces "one interface lists everything, the other `[]`".
- P9, non-interface lines: drop "hardware that serves no interface carries `spare:` or
  `loose: true`"; rivet nuts are interface hardware, and the rest are not hardware parts by P9's
  own definition. The §3 schema example (`m6-rivnut … loose: true, spare: …`) is wrong for the
  kiln.
- §0 and M0: the M6 × 50 is described by `guard-standoff-bottom`, not `shell-frame-mount`.
- M0 says "log each kiln fix as a `DEC-`": M0 recorded them here and changed no product file;
  M3 applies and logs them.
- P1, controller-mount: x axes are opposed as well as normals; the rewrite in section 1 fixes
  both. Recommend the parties in parent-first order so offsets read from the placed party.
