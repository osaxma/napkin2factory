# Backlog — every piece of open work, in one place

Bugs, deferred items, what the plans (`GRAND_PLAN.md`, `NAPKIN_STAGE.md`) left out, non-goals that may return,
and risks worth watching. One line per row; the detail lives in the `DECISIONS.md` entry that opened or closed
it. `src/` may reference an id in a `TODO(B-xxxx)` comment. Closed rows move to the table at the bottom with the
entry that closed them. Ids are never reused.

## Open

| id | item | origin / what would close it |
|---|---|---|
| B-0001 | Playwright Chromium unavailable fallback: HTML-parse checks only | Reserved for environments where the browser download fails; on this host Playwright installed and runs, so the fallback is a `pytest.skip` with reason (D30-style, never silent) |
| B-0002 | Vectorize the z-buffer rasterizer per mesh (currently a Python loop per triangle) | Measured at M2: five views of the enclosure base take <1 s; build123d import warm-up (~5 s) dominates. Revisit only if kiln renders exceed ~60 s |
| B-0003 | Python 3.14 support | Not tried; OCP novtk wheels exist for cp314 per REVIEW E but 3.13 is pinned (D2) |
| B-0004 | Lock file for concurrent `n2f build` in one product folder | Gate-1 C5: two builds at once would race on the manifest (last writer wins). Rare for a solo tool; revisit with share mode |
| B-0007 | Indent wrapped continuation lines in `n2f status`/impact output at 80 columns | Gate-2 C13; cosmetic, rich wraps without hanging indent |
| B-0009 | Design-time wording for inspection-type sign-offs (e.g. "the package requires deburring") vs post-manufacture gates | Gate-2 C4; needs a `when: design\|manufacture` field on manual verifies |
| B-0011 | Multi-piece sheet-metal generator (wrap + end panels, closed corners) | Gate-3 shop read-through: deep trays cannot be brake-formed from one blank and the blanks exceed stock sheet widths; v0.1 notes allow the shop to split the one-piece development |
| B-0012 | Door-swing envelope as a geometry check (`asm://kiln#props.bbox` with the door at `door-swing`) | Gate-3 C1: the footprint requirement is evaluated closed; the owner's 800 mm alcove is exceeded by the open door (DEC-011, flagged for the owner) |
| B-0013 | K26 hot-face option for the kiln (element grooves run hotter than the chamber) | Gate-3 C9: K23 is 1260 degC class for a 1200 degC kiln; swapping `brick-conductivity`/`brick-density` and the part specs is a parametric change request |
| B-0014 | Tapered opening (reveal boards) to match the tapered door plug | Gate-3 B5/C14: the plug tapers 6° and the opening is straight, so the hot-end gap is packed with fiber blanket (consumable) |
| B-0022 | Cost bands in `calckit/data/cost_bands.yaml` are wide (8–68 USD/kg sheet metal) so the board's cost estimate spans ×3 | S-064/S-065: seeded from the kiln's per-part estimates; narrow them from real quotes, or per region |
| B-0035 | Electrical stage: KiCad schematics as source, an `elec:` rule family, a `circuit` verify kind | GRAND_PLAN §1.2 non-goal; HANDOFF-REPORT §6 |
| B-0036 | MCP server wrapping the CLI verbs (concept verbs included) so chat clients run intake and builds | GRAND_PLAN §1.2; NAPKIN_STAGE §1.2 (v0.3) |
| B-0038 | Manufacturer capability profiles as a rule-pack dimension (`n2f check --profile`) | GRAND_PLAN §1.2; HANDOFF-REPORT §6 |
| B-0039 | Tolerance stack-up over chains of interface frames as a verify kind | GRAND_PLAN §1.2; HANDOFF-REPORT §6 |
| B-0040 | FEA / simulation gates | GRAND_PLAN §1.2 non-goal |
| B-0041 | Hosted service, orchestrator process, multi-agent runtime | GRAND_PLAN §1.2 non-goal |
| B-0043 | Manufacturer quote APIs and electronics distributor APIs | GRAND_PLAN §1.2 non-goal |
| B-0044 | GD&T-grade drawings and Class-A surfacing | GRAND_PLAN §1.2 non-goal |
| B-0045 | Tauri wrapper and npm shim | GRAND_PLAN §1.2 non-goal |
| B-0046 | `docs/vocabulary.md` localization hooks (the vocabulary lives in one table and two dicts) | GRAND_PLAN M9 ⤵, not done (HANDOFF-REPORT §2) |
| B-0047 | Second DoD 7 simulation playing an engineer persona driving the CLI directly | NAPKIN_STAGE §5 M5 ⤵, not done |
| B-0048 | The two remaining kit aesthetic parameters (six of the capped eight shipped) | NAPKIN_STAGE §7 [revisit]; S-066 |
| B-0049 | Image → interpretation card with a real sketch or photo (today: worded stand-ins in tests; owner-manual) | NAPKIN_STAGE N9; S-068 |
| B-0052 | Risk: Linux is covered only by CI; the reference platform is the macOS host | S-001; former STATUS open risk |
| B-0059 | A requirement bound that is a parameter (`param://` value), so the alcove rule is one row instead of two | S-085: a bound is a plain quantity today; needs the requirement schema and the evaluator |
| B-0060 | `ecr close` does not see edits never saved to a snapshot before closing; overlapping change requests can bump extra parts | S-089: `core/vcs.py` has no public diff of a snapshot against unsaved files |
| B-0061 | The board's live 3D viewer and the fallback pictures do not show the layout marks | S-093: the marks live on the styled screenshot page only |
| B-0062 | `n2f publish --online` run against a real GitHub project (first send, Pages from `gh-pages`) | S-094: tested against a local bare repository only |
| B-0064 | The placement warning (P1) does not look at joints through ports: a sub-assembly placed by coordinates although a port could place it is not flagged | S-107: `instances.json` records leaves only, not a sub-assembly's own `via`; record the group placements (M3, when the kiln's door is placed by its ports) |
| B-0065 | The kiln's rivets are in no parts list: two for the rating label (its note) and the latch keeper plate's (count stated nowhere) | S-113 (v0.4 M3b), product DEC-023; S-105 §2.2 error 4. Choose the rivets, count them, list them in the controls and the kiln |
| B-0067 | Two joints sharing an occurrence (the kiln's hinges): a 12 mm miss on the lower hinge is reported on `hinge-lower` as "400.0 mm apart", the distance to the other hinge | Gate C, C2 (v0.4): report an occurrence that meets none of its joints once, naming the nearest joint and its distance (`core/checks/interface.py`, the shared-occurrence excuse of S-113) |
| B-0069 | The check's "worth a look" list repeats itself: each bought part's vendor link is flagged twice (`cots-source-verified` and the `validation@` row), and "BOM-only part" rows flag bolts, nuts and standoffs the joint-hardware check already accounts for (42 of the kiln's 66) | Gate D concern 11 (S-118): merge the two vendor rows into one per part, drop "BOM-only" for hardware parts; touches `core/checks/engine.py` and the rulepack |
| B-0070 | Assembly sheets carry no item numbers on the pictures (balloons) | Gate D concern 8 (S-118): the footer's claim was dropped instead; a numbered leader on each custom item of the pulled-apart view would let a workshop tie a picture to a line |
| B-0071 | Check counts differ by what they count: a build step's (its joints, counts, requirements; a shared requirement in each step), the report's By-module table (every row of the unit) and `n2f check --scope` (no documents or sourcing) | Gate D concern 12 (S-118): each is now labelled; one count per unit everywhere would need the engine's module rows and the scope filter to agree |
| B-0072 | Python and dependency review: drop unused dev tools, declare Pillow, replace httpx, build123d 0.13 (OCCT 8), then Python 3.14, an optional screenshots extra | Review of 2026-11-01, set aside by the maintainer; reasoning, evidence and order in `docs/improvements.md` §6. Python 3.15 waits for cp315 OCP wheels and build123d's `<3.15` cap |
| B-0074 | `n2f build --target` offers a fixed list (`cli/build.py::TARGETS`): a domain's rule family is a target through the API (`run_build(target=...)`) but not on the command line | S-123; derive the option's choices from the rule-family registry |
| B-0075 | URIs in prose (`core/uris.py::find_uris`, used by lint and manual pages) know only the core's schemes: a domain's `<scheme>://id` in text is not found or checked | S-123; build the pattern from the registered schemes |
| B-0076 | A scope-only edit of `n2f.yaml` reruns neither the checks nor the report: no recorded read values the manifest's `scope:` (`manifest://product` reads only the product block), so the report's scope line stays as it was until something else it reads changes (a new `DEC-` does) | S-124; `n2f status` and `n2f release` compute scope live and are right. Value a `manifest://scope` key in `core/graph/values.py` and add it to the report's reads (`report/builder.py`) |
| B-0077 | An external stub (`build: external`) is not yet said in the build plan: its joints close in the step that fits it, but the step lists no "supplied, not built here" line, the joint words name the stub by its URI, and `general-v0/module-has-parts` warns that the stub has no parts | S-124; `BuildUnits.supplied(uid)` and `EXTERNAL_WORDS` hold the data; render them in `bom/build_plan.py` and the report's build fragment, name an asm party in `joint_words`, skip stubs in the rule pack |
| B-0079 | The `cases:` format is documented only in the `core/checks/calcs.py` docstring and the lint hint: no using-agent doc or role says to write a case with each calc | S-125; docs/checks.md, docs/calckit.md, the design and verifier roles |
| B-0080 | A part's mass reads `calckit/data/materials.yaml` (`geometry/materials.py::_shared`, used by `geometry/exporters.py::compute_props`) but the part and assembly rules hash only `geometry/`: editing a shared density there leaves built masses stale until something else reruns the part | S-126; hash the shared table into `code_hash_for_part` (`core/graph/rules.py`), or move the density rows into `geometry/` and have the calc kit read them; every part key moves once |

## Closed

| id | item | closed by |
|---|---|---|
| B-0005 | Interface check for assembly-level parties (`asm://` as a party) | Closed 2026-11-01 (S-107): `asm://` parties are refused by `n2f validate` with a pointer to ports; a sub-assembly exports a part's joint under `ports:` and is placed by it |
| B-0006 | `validate.json` embeds absolute paths | Closed 2026-11-01 (S-082): paths relative to the product root |
| B-0008 | Hide URI prefixes in owner-view tables and captions | Closed 2026-10-31 (S-061): `core.uris.display_uri`; report, `n2f check`, impact summary; engineer view and files keep them |
| B-0010 | Stand standoffs, thermocouple hole and element tails are described, not modelled, in the kiln | Closed by the gate-3 rework: standoffs, hinge post, latch keeper, controller mount, tail and thermocouple holes are modelled with interfaces |
| B-0015 | `n2f ecr close` should refuse while a requirement needs a sign-off | Closed 2026-10-31 (S-060): `ecr/lifecycle._close_gate`, same wording as the stage blockers; example sign-offs pass |
| B-0016 | Warm the CAD kernel import during `n2f init` | Closed 2026-10-31 (S-057): `n2f init` starts the import in a detached background process; `N2F_NO_WARMUP=1` disables it |
| B-0017 | Section render clips triangles whole, so the cut is hard to read on thick walls | Closed 2026-10-31 (S-059): exact per-triangle clip at the plane plus hatched back-face caps; the kiln wall layers read as bands |
| B-0018 | `n2f validate` hides expression errors while reference errors are present | Closed 2026-10-31 (S-058): expressions are evaluated whenever `parameters.yaml` parsed; fixture `invalid/expr-and-ref-together` |
| B-0019 | Surface `Scene.notes` from the section render (open meshes are clipped but not capped) in the build output | Closed 2026-11-01 (S-088): `renders/notes.json`, printed by `n2f build` in owner words |
| B-0020 | A sign-off between `ecr apply` and `ecr close` makes its own snapshot, so `bump_revisions`' declared-field diff only sees that last snapshot; a design ECR whose only change is a part YAML edit with no output-hash change would miss its revision bump | Closed 2026-11-01 (S-089): `ecr close` compares from the snapshot before "Apply" |
| B-0021 | Massing silhouettes of `frame` are solid boxes, so a stand's estimated mass and welding cost are overstated (35 kg vs 7 kg for the kiln stand) | Closed 2026-11-01 (S-087): frames weighed by member section × cut length; kiln stand 31.8 → 7.2 kg |
| B-0023 | The alcove requirement written by `n2f concept promote` freezes the concept's door width (e.g. 250 mm) in its bound; a wider designed door is not re-checked | Closed 2026-11-01 (S-085): promotion seeds the door as parameters and holds it with its own row |
| B-0024 | `tests/e2e/test_release_diff.py::test_diff_page_loads_and_highlights` failed once in `make check` with a SwiftShader `THREE.WebGLProgram: Shader Error 0 - VALIDATE_STATUS false` on `part://base`, then passed three reruns in a row | Closed 2026-10-31: recurred on CI (macOS, docs-only commit bcbb604); `tests/conftest.py::is_swiftshader_flake` recognises the exact message (empty info log), the diff-page test reloads once and the other four Playwright tests ignore it; any other console error still fails |
| B-0025 | `concept-v0` has no skin-temperature-vs-touch-limit or chamber-volume-vs-target rule (warn), so a green compact card's limitations box reads "screening found no limitations" while its notes list the trade-offs | Closed 2026-11-01 (S-086): skin-vs-touch-limit and chamber-volume-vs-target warn rules |
| B-0026 | The enclosure flat-area × t ≈ volume identity is off by up to 3.7 % for thick sheet on low flanged boxes (t = 3, r = 1, h = 25); the hypothesis property in `test_kit_sheet.py` was widened 2 % → 4 % | Closed 2026-11-01 (S-091): the gap is exactly the bend term; the test checks it at 1e-6 |
| B-0027 | `promote.door_swing_term` subtracts formatted (rounded) values: REQ-023 says 703 mm / 1047 mm where the raw numbers are 702.4 / 1047.6 | Closed 2026-11-01 (S-085): promotion works from the unrounded leaf |
| B-0028 | `examples/kiln/model/**/*.py` is not ruff-clean (E501, E741, D103); `make lint` covers only `src` and `tests` | Closed 2026-11-01 (S-092): kiln Python ruff-clean, `make lint` covers `examples` |
| B-0029 | Screening's door swing always uses factor 1.0 (the leaf swung fully back); the kiln's 110° door needs ~300 mm, so C-003's 1750 mm alcove assumption is conservative by ~400 mm | Closed 2026-11-01 (S-085): leaf × max(0, −cos θ); kiln C-003 1698 → 1236 mm |
| B-0030 | The promote note says "only 0 form requirements applies" (grammar/plural) | Closed 2026-10-31 (gate B, B4): the note appears only when exactly one form requirement applies, in words |
| B-0031 | A concept build rewrites each card's screening `at` even when nothing changed, so `make kiln` builds the cards in a scratch copy `build/kiln-napkin` | Closed 2026-11-01 (S-086): `at` moves only with the screening content; the scratch copy stays |
| B-0032 | The styled concept renders show no door, hinge, handle or controls face: a card's `layout` words (door hinged-left, controls side-right) are invisible in the picture, so the owner cannot judge layout from the images alone | Closed 2026-11-01 (S-093): door, hinge, handle and controls drawn from the layout words |
| B-0033 | `n2f status --json` `stage` (and the report badge) mean "last gate passed" while the headline now names the first gate not complete; `ecr close` and the report read the old meaning | Closed 2026-11-01 (S-090): people see the stage being worked in; `--json` adds `current_stage` |
| B-0034 | Screening notes still name fields in places ("cost leaves out body (no material, so no mass)", the insulation-layer hints) | Closed 2026-11-01 (S-086): every screening note in owner words, tested |
| B-0037 | Share mode `n2f publish`: `build/site/` and the board as pages a manufacturer can open | Closed 2026-11-01 (S-094): `n2f publish`, `--online` to an existing GitHub copy |
| B-0050 | Brand integration, rest: the wordmark and lockup | Closed 2026-11-01 (S-081): README lockup, wordmark in the generated pages' footer |
| B-0051 | Risk: headless-GL (SwiftShader) flakes under parallel test load beyond the one message now tolerated | Closed 2026-11-01 (S-093): a blank capture is detected and rendered once more |
| B-0053 | Keep review-gate reports in the repo with a reusable gate template | Closed 2026-11-01 (S-078): `docs/reviews/` holds v0.2 gates A, B and v0.1 gate 4 plus `TEMPLATE.md` |
| B-0054 | Run the three demos in parallel in `make check-full` | Closed 2026-11-01 (S-079): `-n 3`, demos ≈ 12 min → 8 min 19 s |
| B-0055 | Build each example product once per test worker | Closed 2026-11-01 (S-080): measured ≈ 30 s of wall to gain; long test files split instead, `make check` ≈ 8 min → 6 min 52 s |
| B-0056 | Visual milestones go to the maintainer as pictures before they are called done | Closed 2026-11-01 (S-078): `AGENTS.md` working-style rule |
| B-0057 | Client-neutral home for the product role skills | Closed 2026-11-01 (S-077): roles moved to `roles/` with no `.claude/` copy |
| B-0058 | The README and product `AGENTS.md` link the agent guide on `main` | Closed 2026-11-01 with the 0.3.0 release: `main` fast-forwarded to the release commit, which carries `docs/agent-guide.md` |
| B-0063 | `make check-full` fails: the kiln demo's ECR-002 patch (peephole) no longer applies | Closed 2026-11-01 (S-113): the patch re-made against the restructured door |
| B-0066 | Joint words name only the two parts: the kiln's two hinge joints read the same in the build plan, and long part names shrink a joint's row on the assembly sheet | Closed 2026-11-01 (S-118): an optional `name:` on the interface, joints in build order, sheet cells wrap instead of shrinking below 2.2 mm |
| B-0068 | An assembly sheet's "STEP n of N" reads the plan's `order` without recording it: a unit added elsewhere leaves N stale on the other sheets | Closed 2026-11-01 (S-118): the sheet's reads include `bom://build-plan#order` |
| B-0073 | A sign-off recorded on one machine is void on another (the first Linux nightly failed four kiln example sign-offs: a part's evidence key hashed the mesh) | Closed 2026-11-01 (S-121): parts and assemblies key on tolerance-compared invariants; the kiln's six sign-offs re-keyed with `scripts/rekey_signoffs.py`; the next Linux nightly is the proof |
| B-0042 | Upgrade migrations between schema versions (schema 1 unchanged so far, S-056) | Closed 2026-11-01 (S-125): `core/model/migrate.py`, the upgrade path in `n2f init .`, `docs/schema-policy.md`, `tests/fixtures/schema/v1` |
| B-0078 | The `checks` rule does not hash `calckit/`: a calc-kit formula change reruns neither the `calc-case` rows nor `calc` requirements (since v0.2) | Closed 2026-11-01 (S-126): the mechanical `checks` family's code includes `calckit`; `test_a_calc_kit_change_reruns_the_checks_and_no_part` |
