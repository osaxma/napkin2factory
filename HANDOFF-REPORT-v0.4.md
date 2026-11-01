# napkin2factory v0.4 — handoff report ("the tree")

> **Next agent:** v0.4 is closed on `main` with version 0.4.0 and the product pins `>=0.4,<0.5`;
> it is **not tagged**. Tagging, the clean-clone `make check-full` and the maintainer's visual
> judgment (DoD 7) are the maintainer's. Then continue with v0.5, `FOUNDATION.md` (§9).

Plan: `PRODUCT_STRUCTURE.md` (decisions P1–P14). Every number below is copied from the decision
entry named beside it, or was measured for this report on 2026-11-01 (macOS host, Intel,
`N2F_OFFLINE=1`, a fresh tracked copy of `examples/kiln` at e1fc18e plus the version bump);
where neither holds, it says "not measured".

## 1. What v0.4 set out to do

A modularity review on 2026-11-01 (S-103, v0.4 is the product's structure) asked whether
napkin2factory builds one monolithic assembly or sub-assemblies joined together. Its five findings
(`PRODUCT_STRUCTURE.md` §0, measured on the kiln then):

1. **The tree is flat and the manual knows more than the model.** 34 child lines at the top and
   one sub-assembly (the door, 8 lines); the hand-written manual describes five units.
2. **Placement is hand arithmetic.** `kiln.py` (242 lines) placed every part by hand-computed
   offsets and angles; 18 parameters existed only to write interface frame coordinates.
3. **The interface check could not see a misplaced part**, and the door had no declared joint
   to the kiln: frames were compared in each part's own coordinates, and `controller-mount`'s
   normals faced each other while every other interface's agreed.
4. **One flat parameter namespace:** 159 parameters in one file, name prefixes standing in for
   modules.
5. **The build plan was not modelled.** Bolts were typed-in numbers (50 M6×16 at the top, 8 in
   the door) counted against nothing; nothing said whether a group is built as a unit; no
   assembly drawings.

The scope in one sentence (§0): an agent decides what joins what and why a group exists; the
code does the placement arithmetic, the counting and the checking, one module at a time.
Electrical (B-0035), manufacturer profiles (B-0038) and stack-up (B-0039) moved out of v0.4.

## 2. What shipped, per milestone

| milestone | what it delivered | entry | commit |
|---|---|---|---|
| plan | `PRODUCT_STRUCTURE.md`, P1–P14 | S-103, v0.4 is the product's structure | 92ed777 |
| M0 | baseline: every kiln frame pair surveyed in the world, the hardware reconciled by hand, the shared-hole rule, `docs/v04-baseline.md` | S-105, the M0 baseline | acdc2c3 |
| M1 | `place_by` places a part by its interface frame; frames and offsets take expressions; the alignment stage in the assembly (0.5 mm / 0.5°); the 18 frame-only helpers removed | S-106, interfaces place parts | 1bc995b |
| M2 | `ports:` on sub-assemblies, a part's home, `place_by` for sub-assemblies; `asm://` parties refused (closes B-0005) | S-107, sub-assemblies have ports | 1e52083 |
| M3a | `build: unit\|phantom`, `driver:`, the build plan derived from the tree (JSON, XLSX sheet, report section, `build_step()`), one assembly sheet per unit, joint hardware counted (`hardware://`) | S-110, build units and the build plan | e2dcb17 |
| M5 | concept cards name modules; promotion seeds a top assembly, one stub and three size budgets per module, or only suggests modules | S-112, promotion keeps the napkin's modules | f162da1 |
| M3b | the kiln built from units: door (built and serviced as a unit) and controls (tested as a unit, another process) hung by their ports, the lining a phantom; hardware per S-105 option A; product DEC-019–023 | S-113, the kiln built from units | 3967e42 |
| M4 | `scope:` and `export:` on parameters with a reach check; `n2f context asm://<id>`; `n2f build --asm`; `n2f check --scope`; the report's matrix grouped by module | S-114, scoped parameters and `n2f context` | 920c058 |
| M6 | joints between units in the plan and the report; verifier and impact-analyst roles for two-level review; the DoD 5 protocol | S-115, joints between units reviewed | 016689b |
| M6 | the door simulation: a fresh agent changed the door from its context alone | S-116, the DoD 5 run | a19a2e9 |
| M7 | gate C and its fixes | S-117, the build plan is a valued read; "Review gate C — outcome" | 0bff573 |
| M7 | gate D and its fixes | S-118, joints in owner words; "Review gate D — outcome" | e1fc18e |
| M7 | version 0.4.0, product pins, this report | S-119, v0.4 closed | this commit |

Landed alongside, not part of the plan: S-104 (closed versions' entries in `docs/decisions/`),
S-108 (a styled screenshot whose shader fails under load is rendered once more), S-109 (a landing
that stops after giving out ids puts the task's commits back), S-111 (the v0.5 and v0.6 plans).

## 3. Definition of done, item by item (`PRODUCT_STRUCTURE.md` §1.3)

| # | item | status | evidence |
|---|---|---|---|
| 1 | builds and compatibility | met, except `check-full` from a clean clone (pending, maintainer) | `make check` green at this commit (§4). Last `make check-full` green: 23 min 24 s at M3b (S-113). Goldens: only `kiln-board.json` moved, a declared M5 change (gate C §7); bracket and enclosure unchanged since v0.3.0. Gate C §7: v0.3.0's own examples build under v0.4 code with no fail, and a v0.3 enclosure gets the same evidence keys from v0.3.0 and v0.4 code; outputs differ by timestamps, the new `label`/`via` fields and the new files |
| 2 | placement by interfaces in the kiln | met | `place_by` places every joint that has an interface (gate C §10.2); `grep -c -- "-half-"` on the parameters is 0 (run for this report); the alignment rows pass for all 13 kiln interfaces (gate C; survey in §4); `test_alignment.py::test_controller_box_moved_10_mm_fails` names both occurrences and the distance; line counts before and after in S-106 and S-113 (§4) |
| 3 | the kiln's tree | met | door and controls are units with drivers, the lining a phantom on coordinates (S-113, DEC-019, DEC-020); every cross-unit joint is a port (`n2f validate` refuses otherwise, S-107); `reach://door` passes, 0 warnings (S-114) |
| 4 | build plan | met | `build/bom/build-plan.json`, the XLSX sheet and the report section (S-110); three assembly sheets (controls, door, kiln); the manual's three steps use `build_step()` (gate C §10.4); every `hardware://` row passes (S-113; this run: "the hardware for its 11 joint(s) is all listed"); `test_build_plan.py::test_a_missing_bolt_fails_naming_joints_and_number`; plan reads valued since S-117 |
| 5 | one module, one agent | met | `n2f context asm://door`: 16,653 B text (S-114), 16,524 B in this run; the S-116 run met all four criteria (scoped check, kiln check, file scope, files opened); transcript `tests/e2e/module-transcripts/door-2026-11-01.md`. One run, one easy change |
| 6 | promotion with modules | met | fresh product: top assembly, stubs, three budgets per module, build and check green with empty modules `warn` (S-112, gate C §8); `test_promote_modules.py::test_promotion_on_the_kiln_only_suggests_modules`. The shipped kiln refuses promotion because C-003 is already the chosen direction (gate C §10.6) |
| 7 | review gates | met: gates closed; the maintainer judged the build plan section and the door sheet "looking right" | gate C `docs/reviews/v0.4-gate-c.md` and gate D `docs/reviews/v0.4-gate-d.md`, both NOT READY at 016689b, blockers fixed in S-117 and S-118. Screenshots judged by the agent only so far (gate D outcome) |
| 8 | docs | met | agent guide carries `n2f context`, `build --asm`, `check --scope` (gate C §10.8); design, verifier, pm and impact-analyst roles in `templates/_common/roles/`, synced; `docs/vocabulary.md` has unit, phantom, driver and port; this report |

## 4. Measured numbers

**Placement** (`scripts/v04_frame_survey.py --lines`; placement = `place` + coordinate lines):

| when | source | kiln | door | controls | lining |
|---|---|---|---|---|---|
| before (M0) | S-105 | 242 file lines; 180 placement; 22 `place()` sites; 9 literal offsets | 78; 47; 6; 4 | in `kiln.py` | in `kiln.py` |
| after M1 | S-106 | 175 placement; 17 `place()` | 43; 5 | in `kiln.py` | in `kiln.py` |
| after M3b | S-113 | parts placed by coordinates in `kiln.py` 17 → 2; literal offsets 13 → 0 | | | |
| now (e1fc18e) | this run | 84 file lines; 46 placement; 8 `place()`; 0 literal | 80; 43; 6; 0 | 60; 36; 6; 0 | 122; 86; 10; 0 |

The placement code is now spread over four modules (211 lines against 227 before), so the line
count barely moves; what changed is that no position is typed in (0 literal offsets) and the
joints are placed by their frames. In this run's `instances.json`, 6 of the kiln's 28 leaves
record `via: iface://…`; the door and the controls are hung by their ports, which `instances.json`
does not record (B-0064).

**Frames in the world** (survey on this run's build): all 13 interfaces (15 frame pairs, the two
hinges each seen from both joints) have normals and x axes the same way; origin miss 0.0 mm
everywhere, hole miss 0.0 mm where there are holes. At M0 `controller-mount` was the one facing
pair (S-105).

**The kiln is the same object:** mass 110.517 kg, bounding box 995.4 × 666.7 × 1370.4 mm in this
run; `tests/golden/goldens/kiln.json` (unchanged since v0.1) holds 110.52 kg and the same box;
S-113 records bbox, mass and centroid identical before and after the restructure.

**Parameters:** 159 (M0, S-105) → 141 (M1, the 18 helpers gone, S-106) → 147 (M3b: seven door
frame sizes for the hinges and latch added, one removed, DEC-019; `git diff 1bc995b 3967e42`) →
147 with 38 scoped (door 32, controls 6) and 4 exported (M4, S-114). Counted for this report.

**Hardware:** before, 50 M6×16 at the top and 8 in the door, counted against nothing (S-105).
Now (this run's `build-plan.json`, demand = declared on every line): kiln 38 M6×16, 4 M6×50 through
bolts, 16 + 4 standoffs (25 / 40 mm), 6 nuts, 4 rivet nuts; door 8 M6×16, 4 standoffs; controls 4
lid screws. Bolt lengths and the lid screw are `[verify]` (DEC-021, DEC-022).

**Context sizes** (`n2f context`, text / `--json` bytes):

| module | S-114 | this run |
|---|---|---|
| door | 16,653 / 30,192 | 16,524 / 30,206 |
| controls | 10,632 / 17,343 | 10,512 / 17,339 |
| kiln | 31,156 / 51,881 | 31,338 / 51,995 |
| kiln, flat (before the split) | 49,570 / 77,527 | not measured |

The door simulation's whole bundle (role, context, geometry code) was 34,259 B (S-115, S-116).

**Report size:** 3,614,355 B before M3a → 3,714,969 (S-110) → 3,783,308 (S-113) → 3,792,417
(S-115) → 3,792,169 B in this run; the budget is 20 MB (D13).

**Door simulation** (S-116): one fresh-context subagent, the 34,259 B bundle, the owner's request
(spacers 10 mm further apart); it changed one line (`door-standoff-inset` 120 → 115 mm, pitch
452.4 → 462.4 mm), seven tool calls, about 1 min 43 s, no failure, nothing signed, every opened
and changed file inside the context.

**This run:** `n2f build` on the fresh copy 62.4 s (64 rebuilt); `n2f check` 2.7 s, "6 example
sign-offs (not reviews) · 251 OK · 3 not checked · 66 worth a look", no fail.

**Times recorded per milestone** (`make check` / `make kiln`): M1 8 min 51 s / 2 min 42 s; M2
9 min 32 s / 3 min 1 s; M3a 9 min 24 s / 2 min 55 s; M5 12 min 38 s / –; M3b 8 min 42 s / 2 min
45 s (demos 9 min 7 s, `check-full` 23 min 24 s); M4 8 min 45 s / 2 min 53 s; M6 11 min 8 s / 3 min
21 s. The plan's hour budgets were not compared with actual hours: not measured.

`make check` at this commit (version bump applied): green in 10 min 8 s wall; tests 870 passed,
5 skipped in 7 min 51 s, coverage 92.2 %; goldens 141 passed in 80 s; the fast examples build.

## 5. What the gates found and how it was fixed

**Gate C (architecture and honesty), at 016689b:** NOT READY on two D5 blockers; placement,
ports, hardware counts, scope, context and v0.3 compatibility held.
- B1: `bom://build-plan#…` did not parse, so every plan read was a constant: a changed `driver:`
  or a renamed part left the sheet, the manual and the report stale. Fixed in S-117: `build-plan`
  is a valued `bom` id the bom rule also produces; tests change a driver and a part name and see
  the sheet, the page and the report rebuild.
- B2: the hardware stage read `spare:` without recording it. Fixed in S-117: the checks record
  each assembly's name, children, build, driver and ports.
- Concerns: C7 (a test that every recorded read has a value; it found the report's `drawing://`
  reads), C1 (contradictory port advice) fixed in S-117; C3–C6 fixed with gate D (S-118); C2 →
  B-0067; the sheet's unrecorded step total → B-0068, closed by S-118.

**Gate D (UX in the owner persona, a hobby potter), at 016689b:** NOT READY on two blockers,
both joint messages.
- A misaligned joint read as identifiers only (`part://outer-shell#1 and part://guard-shell#1 do
  not meet in asm://kiln …`); a passing joint and the "Joints between units" section were written
  for an engineer. Fixed in S-118: messages name the parts and the joint, give the distance with
  its allowance and what to do; ids, offsets and frames move to `--json`.
- Concerns 3–7, 9, 10, 13–17 fixed (lining items marked, driver reasons joined with "and",
  "Fitted in step N", optional `name:` and `closed_in:` on interfaces, joints in build order,
  sheet text never below 2.2 mm, the lid joint closed in the final assembly as the manual says,
  owner words in `n2f status`, the README's build plan); 8 by dropping the footer's claim; 12 by
  labelling each count. To BACKLOG: 11 → B-0069, balloons → B-0070, one count per unit → B-0071.

## 6. Dropped or simplified

- **No kinematics, no solver** (§1.2): the door's swing stays B-0012.
- **The lining stays on coordinates** as a phantom (DEC-020); the build marks its leaves
  `coordinates`.
- **The P1 warning does not see joints through ports** (B-0064): a sub-assembly placed by
  coordinates although a port could place it is not flagged.
- **Two joints sharing an occurrence** (the hinges) excuse each other in alignment; a miss is
  reported against the wrong joint and distance (B-0067).
- **Card `driver`/`build` words are free text**: lint C9 warns, never refuses (S-112; the plan
  said "rejects").
- **The reach warning stays `warn`** (plan §7); four door sizes are exported so the kiln reads
  them through a declared export (S-114).
- **P11's 32 kB split line** is one product's measurement, not an agent limit (S-114).
- **Assembly sheets have no balloons** (B-0070); the footer no longer promises item numbers.
- **The DoD 5 simulation ran once**, on one easy change, and only the agent's final message was
  exported (S-116).

## 7. `[revisit]` decisions and `[verify]` numbers added in v0.4

| tag | what | where | what a human must do |
|---|---|---|---|
| verify | Alignment tolerance 0.5 mm / 0.5° is a design choice, not measured | S-106 | confirm against the workshop's hole tolerance |
| verify | One M6×50 through bolt per bottom corner | DEC-021, S-105 | confirm the length through standoff, guard and stand |
| verify | M6×16 bolts may be too long for the 25 mm standoffs | DEC-022 | measure the standoffs' thread depth |
| verify | The controller lid screw | S-113 | choose and size it |
| open | The kiln's rivets are in no parts list | B-0065, DEC-023 | choose, count and list them |

v0.2's `[revisit]` and `[verify]` list (`HANDOFF-REPORT-v0.2.md` §3) stands; `make verify-list`
prints every one.

## 8. Open after v0.4

v0.4's own rows in `BACKLOG.md` (B-0063, B-0066 and B-0068 are closed):
- B-0064, the placement warning does not look at joints through ports.
- B-0065, the kiln's rivets are in no parts list.
- B-0067, two joints sharing an occurrence blame the wrong joint and distance.
- B-0069, the check's "worth a look" list repeats itself (42 of the kiln's 66 rows).
- B-0070, assembly sheets carry no item numbers on the pictures.
- B-0071, check counts differ by what they count.

Also open:
- **The Linux nightly `check-full` fails on a sign-off evidence key.** Known and owned by a
  separate task; no BACKLOG row yet: being opened by the planning session.
- **DoD 7's visual judgment** (the build-plan section and one assembly sheet) waits on the
  maintainer.
- **`make check-full` from a clean clone** and the tag are the maintainer's (§10).

## 9. What v0.5 inherits

S-111 (v0.5 is the foundation, v0.6 the first domain as its proof):
- **v0.5, `FOUNDATION.md` (F1–F16):** one domain contract with registries (rule families,
  verify kinds, check stages, report sections, doc helpers, vocabulary, interface kinds, …), a toy
  domain, the kiln's words out of the package, a schema policy and migration hook, scope as data,
  choices (`n2f decide`), the five files over 700 lines split, calcs with reference cases. Its
  F16 keeps v0.4 behaviour as the default and moves the pin to `>=0.5,<0.6`.
- **v0.6, `ELECTRICAL_STAGE.md` (E1–E12):** the electrical domain built through that contract;
  the count of core edits is its headline. `docs/reviews/v0.6-independent-trial.md` briefs an
  outside model afterwards.
- From v0.4 itself: ports, scopes and `n2f context` are what F's "scope as data" builds on; the
  build plan and the joints review are the first report sections a registry must carry; the
  open rows in §8; electrical (B-0035), profiles (B-0038) and stack-up (B-0039), the last now
  able to walk explicit frame chains.

## 10. Release

Done in this close-out (S-119, v0.4 closed):

```
pyproject.toml                    version = "0.4.0"
packaging/n2f/pyproject.toml      version = "0.4.0"; dependencies = ["napkin2factory==0.4.0"]
src/napkin2factory/__init__.py    __version__ = "0.4.0"
```

The product pin `>=0.4,<0.5` (S-083's places): the manifest default
(`core/model/manifest.py`), every template and example `n2f.yaml`, the product CI workflows
(`uv tool install "napkin2factory>=0.4,<0.5"`), and the test fixtures; `uv.lock` records 0.4.0.
A 0.3 product still loads and prints the one-line pin notice (S-056).

Left to the maintainer: `make check-full` from a clean clone of `main`, push, CI green, tag
`v0.4.0` on that commit (S-072); `publish.yml` checks the three version files agree.

**Draft release notes (0.4.0):**

> **napkin2factory 0.4 — the tree.** A product is now built from units, the way a workshop
> builds it. A door or a control box that is put together, tested or serviced on its own is its
> own unit with its reason written down; the build plan says what is built first, what is
> fitted where, and counts the fixings for every joint against the parts list. Each unit gets an
> assembly sheet.
>
> Parts are placed by the joints between them, not by typed-in positions, and every joint is
> checked where the parts meet in the assembled product: move a box by 10 mm and the check names
> the two parts, the joint and the distance, in plain words.
>
> One unit can be worked on alone: its sizes have a scope, `n2f context` prints everything an
> agent needs for it, and its checks run on their own. In the showcase kiln a fresh agent moved
> the door's spacers from the door's context alone and left the rest of the kiln green.
>
> Concept cards can name their modules, and promotion keeps them.
>
> **Upgrading:** every new field is optional; a 0.3 product builds as before, plus the build
> plan files, and prints a one-line note until its pin is moved to `>=0.4,<0.5`.

## 11. Where things are

- **Commits** on `main` (linear): 92ed777 plan · acdc2c3 M0 · 1bc995b M1 · 1e52083 M2 ·
  e2dcb17 M3a · f162da1 M5 · 3967e42 M3b · 920c058 M4 · 016689b M6 · a19a2e9 simulation ·
  0bff573 gate C fixes · e1fc18e gate D fixes · the close-out commit that carries this report.
- **Journals:** `STATUS.md`; `DECISIONS.md` S-103–S-118, gates C and D, S-119; `BACKLOG.md`
  B-0063 onward; plan `PRODUCT_STRUCTURE.md`; baseline `docs/v04-baseline.md`; gate reports
  `docs/reviews/v0.4-gate-{c,d}.md`.
- **Code:** `core/frames.py`, `core/tree.py`, `core/build_units.py`, `core/reach.py`,
  `core/context.py`, `core/checks/modules.py`, `core/checks/interface.py` (alignment),
  `core/checks/hardware.py`, `bom/build_plan.py`, `drawings/assembly_sheet.py`,
  `geometry/assembly.py` (`place_by`), `cli/context.py`.
- **Example:** `examples/kiln/model/assemblies/{kiln,door,controls,lining}.yaml`,
  `model/geometry/{kiln,door,controls,lining}.py`, product DEC-019–023.
- **Tests:** `tests/unit/test_alignment.py`, `test_build_plan.py`, `test_promote_modules.py`,
  the ports and units fixtures, `tests/e2e/test_module_transcript.py` and
  `tests/e2e/module-transcripts/`.
- **Scripts:** `scripts/v04_frame_survey.py` (frames and placement lines),
  `scripts/module_sim_bundle.py` (the DoD 5 bundle and `--verify`).
