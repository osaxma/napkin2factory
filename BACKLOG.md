# Backlog

Items dropped, deferred, or out of scope for v0.1, each with a reason. `src/` may reference
an id here in a `TODO(B-xxxx)` comment.

| id | item | reason / origin |
|---|---|---|
| B-0001 | Playwright Chromium unavailable fallback: HTML-parse checks only | Reserved for environments where the browser download fails; on this host Playwright installed and runs, so the fallback is a `pytest.skip` with reason (D30-style, never silent) |
| B-0002 | Vectorize the z-buffer rasterizer per mesh (currently a Python loop per triangle) | Measured at M2: five views of the enclosure base take <1 s; build123d import warm-up (~5 s) dominates. Revisit only if kiln renders exceed ~60 s |
| B-0003 | Python 3.14 support | Not tried; OCP novtk wheels exist for cp314 per REVIEW E but 3.13 is pinned (D2) |

## Non-goals carried from GRAND_PLAN §1.2 (v0.2+)
Electrical stage (KiCad), FEA/sim gates, MCP server, hosted anything, orchestrator process,
multi-agent runtime, upgrade migrations, manufacturer quote APIs, electronics distributor
APIs, GD&T-grade drawings, tolerance stack-up analysis, manufacturer capability profiles
beyond the schema, Class-A surfacing, Tauri wrapper, npm shim, share mode (`n2f publish`).
| B-0004 | Lock file for concurrent `n2f build` in one product folder | Gate-1 C5: two builds at once would race on the manifest (last writer wins). Rare for a solo tool; revisit with share mode |
| B-0005 | Interface check for assembly-level parties (`asm://` as a party) | Gate-1 note; v0.1 interfaces are part-to-part only (both examples and the kiln) |
| B-0006 | `validate.json` embeds absolute paths | Gate-1 note; harmless (build/ is local), tidy when the report links to it |
| B-0007 | Indent wrapped continuation lines in `n2f status`/impact output at 80 columns | Gate-2 C13; cosmetic, rich wraps without hanging indent |
| B-0008 | ~~Hide URI prefixes in owner-view tables and captions~~ | Closed 2026-10-31 (S-061): `core.uris.display_uri`; report, `n2f check`, impact summary; engineer view and files keep them |
| B-0009 | Design-time wording for inspection-type sign-offs (e.g. "the package requires deburring") vs post-manufacture gates | Gate-2 C4; needs a `when: design\|manufacture` field on manual verifies |
| B-0010 | ~~Stand standoffs, thermocouple hole and element tails are described, not modelled, in the kiln~~ | Closed by the gate-3 rework: standoffs, hinge post, latch keeper, controller mount, tail and thermocouple holes are modelled with interfaces |
| B-0011 | Multi-piece sheet-metal generator (wrap + end panels, closed corners) | Gate-3 shop read-through: deep trays cannot be brake-formed from one blank and the blanks exceed stock sheet widths; v0.1 notes allow the shop to split the one-piece development |
| B-0012 | Door-swing envelope as a geometry check (`asm://kiln#props.bbox` with the door at `door-swing`) | Gate-3 C1: the footprint requirement is evaluated closed; the owner's 800 mm alcove is exceeded by the open door (DEC-011, flagged for the owner) |
| B-0013 | K26 hot-face option for the kiln (element grooves run hotter than the chamber) | Gate-3 C9: K23 is 1260 degC class for a 1200 degC kiln; swapping `brick-conductivity`/`brick-density` and the part specs is a parametric change request |
| B-0014 | Tapered opening (reveal boards) to match the tapered door plug | Gate-3 B5/C14: the plug tapers 6° and the opening is straight, so the hot-end gap is packed with fiber blanket (consumable) |
| B-0015 | ~~`n2f ecr close` should refuse while a requirement needs a sign-off~~ | Closed 2026-10-31 (S-060): `ecr/lifecycle._close_gate`, same wording as the stage blockers; example sign-offs pass |
| B-0016 | ~~Warm the CAD kernel import during `n2f init`~~ | Closed 2026-10-31 (S-057): `n2f init` starts the import in a detached background process; `N2F_NO_WARMUP=1` disables it |
| B-0017 | ~~Section render clips triangles whole, so the cut is hard to read on thick walls~~ | Closed 2026-10-31 (S-059): exact per-triangle clip at the plane plus hatched back-face caps; the kiln wall layers read as bands |
| B-0018 | ~~`n2f validate` hides expression errors while reference errors are present~~ | Closed 2026-10-31 (S-058): expressions are evaluated whenever `parameters.yaml` parsed; fixture `invalid/expr-and-ref-together` |
| B-0019 | Surface `Scene.notes` from the section render (open meshes are clipped but not capped) in the build output | S-059: the notes are collected but both `render_views` call sites drop them; no kiln mesh produces one today |
| B-0020 | A sign-off between `ecr apply` and `ecr close` makes its own snapshot, so `bump_revisions`' declared-field diff only sees that last snapshot; a design ECR whose only change is a part YAML edit with no output-hash change would miss its revision bump | Noted while closing B-0015 (S-060); geometry changes are still caught by output hashes; fix: diff against the ECR's `applied.before` snapshot |
| B-0021 | Massing silhouettes of `frame` are solid boxes, so a stand's estimated mass and welding cost are overstated (35 kg vs 7 kg for the kiln stand) | S-063/S-065: inherent to N3 silhouettes; fix: carry the member section area so massing props can report a hollow-section mass estimate |
| B-0022 | Cost bands in `calckit/data/cost_bands.yaml` are wide (8–68 USD/kg sheet metal) so the board's cost estimate spans ×3 | S-064/S-065: seeded from the kiln's per-part estimates; narrow them from real quotes, or per region |
| B-0023 | The alcove requirement written by `n2f concept promote` freezes the concept's door width (e.g. 250 mm) in its bound; a wider designed door is not re-checked | Gate A C8: verify with an `expr` over `part://<door>#props.bbox.x` once a door part exists; today the rationale states the frozen term |
| B-0024 | ~~`tests/e2e/test_release_diff.py::test_diff_page_loads_and_highlights` failed once in `make check` with a SwiftShader `THREE.WebGLProgram: Shader Error 0 - VALIDATE_STATUS false` on `part://base`, then passed three reruns in a row~~ | Closed 2026-10-31: recurred on CI (macOS, docs-only commit bcbb604); `tests/conftest.py::is_swiftshader_flake` recognises the exact message (empty info log), the diff-page test reloads once and the other four Playwright tests ignore it; any other console error still fails |
| B-0025 | `concept-v0` has no skin-temperature-vs-touch-limit or chamber-volume-vs-target rule (warn), so a green compact card's limitations box reads "screening found no limitations" while its notes list the trade-offs | M6 board judgment (S-069); C-002 |
| B-0026 | The enclosure flat-area × t ≈ volume identity is off by up to 3.7 % for thick sheet on low flanged boxes (t = 3, r = 1, h = 25); the hypothesis property in `test_kit_sheet.py` was widened 2 % → 4 % | M6; investigate the k-factor bend allowance at small r/t and the flange corners |
| B-0027 | `promote.door_swing_term` subtracts formatted (rounded) values: REQ-023 says 703 mm / 1047 mm where the raw numbers are 702.4 / 1047.6 | M6; use the raw screening values |
| B-0028 | `examples/kiln/model/**/*.py` is not ruff-clean (E501, E741, D103); `make lint` covers only `src` and `tests` | M6; fix the kiln's geometry/calc Python, then add examples to `make lint` |
| B-0029 | Screening's door swing always uses factor 1.0 (the leaf swung fully back); the kiln's 110° door needs ~300 mm, so C-003's 1750 mm alcove assumption is conservative by ~400 mm | M6 (S-069); read a card's `door_swing` angle for a leaf × |cos θ| term |
| B-0030 | ~~The promote note says "only 0 form requirements applies" (grammar/plural)~~ | Closed 2026-10-31 (gate B, B4): the note appears only when exactly one form requirement applies, in words |
| B-0031 | A concept build rewrites each card's screening `at` even when nothing changed, so `make kiln` builds the cards in a scratch copy `build/kiln-napkin` | M6; write `at` only when the screening content changes |
| B-0032 | The styled concept renders show no door, hinge, handle or controls face: a card's `layout` words (door hinged-left, controls side-right) are invisible in the picture, so the owner cannot judge layout from the images alone | Gate B C16; draw a thin door outline or a darker door panel from `layout.door` in `concepts/screenshot.py` |
| B-0033 | `n2f status --json` `stage` (and the report badge) mean "last gate passed" while the headline now names the first gate not complete; `ecr close` and the report read the old meaning | Gate B B5 [revisit]; unify once the report and `ecr close` are adjusted |
| B-0034 | Screening notes still name fields in places ("cost leaves out body (no material, so no mass)", the insulation-layer hints) | Gate B leftover; owner wording per note |
