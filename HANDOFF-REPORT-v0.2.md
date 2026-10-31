# napkin2factory v0.2 — handoff report

> **Next agent:** v0.2 is complete on `v0.2-build`; review gates A and B are closed. What remains is the owner's release call (see §7) and v0.3 (see §6).

## 1. What works, per definition-of-done item

| # | item (`NAPKIN_STAGE.md` §1.3) | status | evidence |
|---|---|---|---|
| 1 | `uv sync && make check` green; `make check-full` green | done | `make check` at 1ebca03 (parallel, S-070): 634 passed, 4 skipped in 5 min 33 s, coverage 90.2 % on `core` + `calckit`; goldens 132 passed in 72 s. `make check-full` at M6 (serial): same 634 + 132 (20 min 17 s + 83 s), kiln validate/lint/build/check, kiln cards + board, `test_kiln.py` 8 passed, `test_demos.py` 3 passed, timing + concept-build timing 6 passed, exit 0. CI on `v0.2-build`: green on every push from M2 through the xdist commit (1ebca03); the gate B commit's run was in progress when this was written. Clean clone of `eab10b1` (2026-10-31): `uv sync`, `n2f doctor` all green, `make check-full` exit 0 in 28 min 01 s — 642 passed, 4 skipped, coverage 90.2 %; goldens 132; bracket, enclosure, kiln and the kiln's napkin scratch copy all "artifacts complete and parseable" |
| 2 | fresh bracket product: two concepts + board, self-contained, `file://`-clean, < 60 s warm | done | `tests/e2e/test_timing.py::test_two_concepts_and_board_under_a_minute_warm` under `N2F_TIMING=1`: 4.8 s warm (STATUS M6). `tests/unit/test_board.py`: self-contained and within budget; opens from `file://` with every viewer and no console errors |
| 3 | kiln: four cards, one red; board shows all four with picture, dims, labels, limitations; judged by eye | done | `examples/kiln/concepts/C-001…C-004`; C-001 red (1698 mm with the door open vs the 800 mm alcove). Judged (S-069): four columns, every number badged given/computed/estimate, red reasons in place, sources under estimates. Golden `tests/golden/goldens/kiln-board.json`. Kiln board in this run: 2.68 MB (measured) |
| 4 | promote seeds parameters, `style.yaml`, ≥ 2 form requirements, a `DEC-` with rejected variants; build + check pass; red refused without `--override` | done | `promote C-003` (this run): "Seeded 0 parameters (10 already declared), 4 requirements (2 about form, 1 about the alcove, 1 about the supply), updated style.yaml" → REQ-023…026, DEC-018. Kiln check afterwards: 0 fail, "6 example sign-offs (not reviews) · 226 OK · 3 not checked · 60 worth a look". Red refusal and `--override` decision: `tests/e2e/test_concept_promote.py` (S-067) |
| 5 | `demo-napkin.sh` unattended in a temp copy | done | `test_demos.py::test_demo_napkin` in `check-full`: 1 min 52 s (STATUS M6); this run by hand: 118.7 s, exit 0 |
| 6 | concept imagery = styled viewer screenshots; fallback only without Playwright, logged | done | 1200 × 900 iso/front PNGs through the inline viewer (S-066). Judged at M3 (industrial and appliance fixture cards) and M6 (C-001 industrial, C-003 appliance): they read as products. Fallback picture labelled "correctness render" (gate A C7) |
| 7 | interpretation-card flow by scripted simulation | done | `tests/e2e/intake-transcripts/napkin-bench-kiln.md`: three cards, a board, a promotion, no red card promoted, every limitation traced to screening; its nine gaps became skill sentences pinned by `tests/e2e/test_napkin_protocol.py` (63 checks, S-068) |
| 8 | folds B-0016, B-0017, B-0008, B-0015 verified by test | done | S-057 (kernel warm-up at `init`), S-059 (true plane section; kiln section renders in 0.8 s, wall layers read as bands), S-061 (`display_uri`), S-060 (`ecr close` refuses on a missing sign-off); plus B-0018 (S-058). M0 `check-full`: 387 passed, 1 skipped, 7 deselected (12 min 25 s) |
| 9 | this report | this file | |

Measured for this report on 2026-10-31 (Intel macOS, `N2F_OFFLINE=1`, scratch copies only):

```
DEMO_DIR=<scratch>/kiln bash examples/kiln/demo-napkin.sh      # 118.7 s, exit 0
n2f concept build C-001        # on a fresh copy of examples/kiln: 12.9 s, then 12.3 s (one process each)
```

## 2. Dropped or simplified

Nothing in the napkin loop (cards → build and screen → board → promote → factory) was dropped.
Narrowed or simplified, each with its record:

- **Images never become geometry** (N9, §1.2): a sketch or photo yields an interpretation card
  the owner corrects in words; tests use worded sketch stand-ins, real images are owner-manual (S-068).
- **Napkin verbs do not take a snapshot**, except `promote` (S-062).
- **Door swing counts the leaf swung fully back** (factor 1.0, S-065); a card's real swing angle is
  not read (B-0029).
- **Cost bands are wide** (8–68 USD/kg for sheet metal, B-0022) and cover only what screening can
  price; the kiln band leaves out the inner shell, door sheets and most bought-in parts (S-069).
- **No skin-temperature or chamber-volume rule** in `concept-v0` (B-0025); C-002's trade-offs live
  in its notes and numbers, not in its limitations box.
- **Massing frames are solid boxes**, so stand mass and welding cost are overstated (B-0021).
- **Six kit aesthetic parameters**, not eight (S-066); the appliance look's 8 mm corners and hidden
  front fasteners are not applied to the kiln, whose 1 mm folds and screwed-on door guard fail them —
  a future change request (S-069).
- **`form-fasteners-hidden-front` cannot see occlusion or screws**, only holes by axis and position (S-067).
- **The alcove requirement freezes the concept's door width** in its bound (B-0023).
- ⤵ **The second simulation** (an engineer persona driving the CLI, M5) is not on record as run.

## 3. `[revisit]` decisions and `[verify]` numbers

| tag | what | where | what a human must do |
|---|---|---|---|
| revisit | Version pin warns, never refuses | S-056 | decide whether CI wants a strict mode |
| revisit | A released product with a new exploring card reads "stage: Napkin" | S-062 | confirm with owners (gate B) |
| revisit | z-buffer fallback when Playwright is absent, labelled "correctness render" | S-066, N6, gate A C7 | judge whether a fallback picture should appear at all |
| verify | Mean-area conduction (Incropera & DeWitt ch. 3); ε 0.9 powder coat; film h 5–10 W/m²K | S-064, `calckit/thermal_enclosure.py` | measure the kiln skin at steady state |
| verify | Kanthal A1 ρ 1.45 Ω·mm²/m; groove surface load ≤ 2.0 W/cm² | S-064, `calckit/power.py` | check against the wire supplier's datasheet |
| verify | Circuit headroom 1.2 (screening and the promoted supply requirement); NEC 210.20 uses 1.25 | S-064, gate A B1, `concept-v0.yaml` | choose the factor for the owner's region |
| verify | Materials: K-23 k 0.25, ρ 480, c 1000; Kaowool 1260 board k 0.15 (DEC-002 range 0.12–0.18), ρ 260, c 1050; mild steel | gate A C4, `calckit/data/materials.yaml` | confirm each row against the supplier datasheet |
| verify | Circuits table, 14 rows (SA, EU, UK, US, AU) | S-064, `calckit/data/circuits.yaml` | confirm with a local electrician per region |
| verify | Cost bands, 7 process classes from the kiln's per-part estimates (two rows rest on one part) | S-064, B-0022, `calckit/data/cost_bands.yaml` | replace with real quotes |
| verify | Lift classes: 25 kg one person, 33 kg two people (HSE) | S-064, `calckit/data/lift_classes.yaml` | confirm for the owner's jurisdiction |
| verify | Stock sheets, 10 rows (1000×2000 … 1500×3000 mm; steel, stainless, aluminium) | S-064, `calckit/data/stock_sheets.yaml` | confirm with the sheet supplier |
| verify | Screening defaults: room 25 degC, h 5 W/m²K, ε 0.9, hot face 1200 degC; open-box blank (L + 2H) × (W + 2H), bracket (L + H) × W, no edge margin; door-swing factor 1.0 | S-065, `concept-v0.yaml` | review per product; B-0029 for the swing |
| verify | Kiln C-003 assumes a 1750 mm alcove the owner has not confirmed (~1.3 m may do with the 110° door) | DEC-018 (`verify: true`), B-0029 | owner gives the real alcove width |
| verify | v0.1's parked kiln decisions: alcove (DEC-011), cost target (DEC-012), heat-up (DEC-004), K26 hot face (B-0013) | `examples/kiln/model/decisions.yaml` | owner answers, ideally as change requests |

Correction to v0.1's §3: the kiln's element wire is 29.3 m at 2.5 kW / 230 V, not 24 m (S-064).

## 4. The 30-second napkin demo script

In a scratch copy prepared by `examples/kiln/demo-napkin.sh` (it rewinds the shipped kiln's
napkin stage; off camera). Screen seconds for the GIF; wall time on this host in brackets.

1. `n2f status` — "Mini electric test kiln — stage: Napkin" · "4 concepts exploring, none chosen
   yet — `n2f concept build --all` first" (2 s) [1.8 s].
2. `n2f concept build --all` — the red block first: "✗ C-001 — this direction has problems:" ·
   "it needs 1698 mm of width — 995 mm for the body plus 702 mm for the open door … — but the
   alcove is 800 mm"; then three "✓ … holds up" lines (5 s) [19 s, cut].
3. `n2f concept board` · open `build/concepts/board.html` — "4 directions side by side (1 with
   problems)". Point at the red C-001 column: the reason, the badges "computed" on 1698 mm and
   "estimate" on 4.4 h and 1130–2747 USD; then C-003's appliance picture (8 s) [1.8 s].
4. `n2f concept reject C-004 --reason "the owner did not like the v0.1 appearance …"` —
   "• C-004 rejected: …" · "the card stays in concepts/ as a record of what was tried" (2 s) [1.5 s].
5. `n2f concept promote C-003 --by "Owner (demo)"` — "✓ C-003 is now the design direction
   (DEC-018). Seeded 0 parameters (10 already declared), 4 requirements …" and the four lines
   REQ-023 "Fits the alcove with the door open" … REQ-026 "Controls where they were sketched" (6 s) [2.5 s].
6. `n2f build && n2f check` · `n2f status` — "6 example sign-offs (not reviews) · 226 OK ·
   3 not checked · 60 worth a look"; "✓ Napkin ✓ Intake ✓ Design ○ Verify" (5 s) [≈ 88 s, cut].
7. Then continue with v0.1's steps 1–7 (`HANDOFF-REPORT.md` §4: release v1.0.0 → change request
   → impact → apply → rebuild → re-sign → release v1.1.0 → diff page): napkin to factory on one screen.

Pages to show: `build/concepts/board.html`, `build/concepts/C-001/renders/styled-iso.png`,
`build/concepts/C-003/renders/styled-iso.png`, then v0.1's report and diff pages.

## 5. Known rough edges in UX, ranked

Review gate B (a fresh-context reviewer as a hobby potter, 2026-10-31) found six owner-facing blockers
and eleven concerns; the blockers and ten concerns are fixed on `v0.2-build` (DECISIONS "Review gate B
— outcome"). What remains, most visible first:

1. The styled pictures show a closed box: no door, hinge, handle or controls face, so "door hinged-left"
   and "controls on the right" cannot be judged from the image (B-0032).
2. The cost band is wide (the kiln's 1130–2747 USD) and covers only what screening can price; the board
   now says so in one line, but the number still alarms before the line is read (B-0022).
3. C-002's limitations box reads "screening found no limitations" while its notes list three
   trade-offs: the concept pack has no skin-temperature or chamber-volume rule (B-0025).
4. `n2f status --json` reports the last gate passed while the headline names the next gate to pass;
   the two agree in meaning but not in word (B-0033).
5. Screening notes still name fields in places ("cost leaves out body (no material …)") (B-0034).
6. The alcove requirement shows rounded numbers, 703 / 1047 mm for 702.4 / 1047.6 (B-0027).
7. "loading the CAD kernel…" prints on every run, warm or cold; the kiln's lint shows the owner one
   `L5-units-agree` warning on REQ-021; the "(set aside)" tail on a long result line reads tacked on.
8. A card's long notes paragraph is the only place some stories live (C-001's 1500 USD / four-hour
   lines); the demo now narrates them, the board does not.

## 6. Recommended next steps for v0.3

1. **MCP server and share mode** (`NAPKIN_STAGE.md` §1.2: v0.3): wrap the CLI verbs, concept verbs
   included, as tools; `n2f publish` turns `build/site/` and the board into pages.
2. **Screening honesty:** the door-swing angle (B-0029), skin-temperature and chamber-volume rules
   (B-0025), narrower cost bands from quotes (B-0022), hollow-section massing mass (B-0021), the
   alcove bound over the designed door (B-0023).
3. **Napkin polish:** write `at` only on change (B-0031), raw numbers in the swing term (B-0027),
   the plural (B-0030), plus gate B's list (§5).
4. **Kiln and kit:** multi-piece sheet metal (B-0011), door-swing envelope as a geometry check
   (B-0012), kiln Python under `make lint` (B-0028), flat-area tolerance (B-0026), tapered
   opening (B-0014).
5. **Smaller:** section notes surfaced (B-0019), revision diff from `applied.before` (B-0020),
   headless-GL retry (B-0024), terminal indents (B-0007), design-time sign-off wording (B-0009),
   build lock (B-0004), Python 3.14 (B-0003).
6. **Later (v0.4):** electrical (KiCad), manufacturer profiles, tolerance stack-up (v0.1 report §6).

Owner-side, not agent work: DEC-011, DEC-012, DEC-004, B-0013 and DEC-018's 1750 mm alcove.

## 7. Release

Per S-054 and S-056: fix gate B's blockers; `make check-full` green; bring `v0.2-build` into
`main`; push the `v0.2.0` tag only after CI is green on `main`. `publish.yml` checks that the tag,
both package versions and the alias pin agree, then publishes `napkin2factory` (environment
`pypi`) and `n2f` (`pypi-alias`), both used for 0.1.0. The versions are already 0.2.0:

```
pyproject.toml:3                version = "0.2.0"
packaging/n2f/pyproject.toml:5  version = "0.2.0"
packaging/n2f/pyproject.toml:11 dependencies = ["napkin2factory==0.2.0"]
src/napkin2factory/__init__.py:3 __version__ = "0.2.0"
```

Every example and template `n2f.yaml` pins `system: ">=0.2,<0.3"`; the product CI templates
install `"napkin2factory>=0.2,<0.3"`.

**Draft release notes (0.2.0):**

> **napkin2factory 0.2 — the napkin stage.** Before any detailed design, sketch several
> directions for your product as concept cards: a few lines of rough shapes, the site it must
> fit and the look you want. `n2f concept build` turns each into a styled picture and screens it
> in seconds: does it fit the space with the door open, does the supply circuit carry it, can it
> be lifted, do its sheets fit stock sizes. `n2f concept board` puts every direction side by side
> in one page that opens from disk.
>
> Every number on the board says where it comes from: **given** (your own input), **computed**
> (measured from the rough shapes) or **estimate** (from the calc kit, with its source). A
> direction with problems is shown in red with its reasons, never hidden: red is information.
> `n2f concept promote` makes your choice the design direction; it seeds the design's numbers,
> records the look in `style.yaml`, turns the site and the look into checkable requirements, and
> keeps the other directions as rejected alternatives with the reasons.
>
> The showcase kiln now starts with its napkin stage. The kiln as first built is red: with the
> door open it needs 1698 mm against an alcove of about 800 mm — found in minute five, not at
> hour forty. Its cost band and heat-up estimate sit beside it.
>
> Also: the first build no longer looks hung (the CAD kernel warms up at `n2f init`), section
> pictures are true cuts, owner tables drop link prefixes, and closing a change request waits
> for human sign-offs, as releasing does.
>
> **Upgrading:** product files are unchanged; a 0.1 product opens as before. A product pinned to
> 0.1 prints a one-line note and still works — the pin warns, never refuses. Update its pin to
> `>=0.2,<0.3` when convenient.

## 8. The three stories: what screening would have said in minute five

The kiln's C-001 card is the v0.1 kiln as built, sketched after the fact from its own parameters.
`n2f concept build C-001`, run on a copy for this report, prints:

```
✗ C-001 — this direction has problems:
    • it needs 1698 mm of width — 995 mm for the body plus 702 mm for the open door (hinged-left: the 702 mm door leaf swung open beside the hinge) — but the alcove is 800 mm
  995 × 667 × 1370 mm (computed), 2.5 kW (on the card) on the 230V-16A circuit — fits with 1.2 headroom (estimate), 4.4 h to temperature (estimate), 1130–2747 USD (estimate)
```

**DEC-011 — the alcove.** In v0.1 the kiln came out "just under 1 m wide" (995 mm) against an
alcove of about 800 mm, found when the report was built, at hour forty. Screening says it in the
time one card takes to build: 1698 mm, red. The numbers differ because they answer different
questions. 995 mm is the closed width; 1698 mm adds the 702 mm door leaf swung fully back,
which is screening's deliberately cautious case (the real 110° door needs about 300 mm, B-0029).
Both say the same thing: the kiln does not fit, and it does not fit even with the door shut.

**DEC-012 — the cost.** v0.1's per-part estimate came to about 2200 USD against a wish of about
1500, and the target moved to 2500 USD pending the owner. Screening prints 1130–2747 USD,
labelled estimate. The card says why the band is short: it prices only "the guard sheets, the
stand, the hinge, one control box, the brick and the fiber". It is wide because the cost tables
span about ×3 (B-0022). 2200 sits inside it, and the minute-five message is the honest one: "the
1500 USD wish sits at the bottom of a band that is not even complete".

**DEC-004 — the heat-up.** v0.1 planned seven hours at 2.5 kW; the owner asked for about four.
Screening prints 4.4 h at 2.5 kW, labelled estimate, close to what the owner asked. It is not
the 7 h, and it should not be. 4.4 h is what the element can do on paper; the 7 h is margin
planned on top, because "2.5 kW is 1.28 times the 1.95 kW a 7 h heat-up needs" (the card,
citing `calc://element.power_margin`). In minute five, the owner would have been choosing a
margin, not discovering a shortfall.

## 9. Where things are

- **Branch** `v0.2-build`, cut from `53bd7bc`: `bcd1451` M0 · `aa8c6f6` M1 · `5304dbc`, `c529bad`
  M2 · `2b5ed1b` M3 · `b6a3589` M4 · `82df19c` M5 · `7478a11` brand (design assets only, another session's work; not wired into the product) · `9a84cc8` M6 · `1ebca03` M7 xdist · `eab10b1` M7 gate B fixes · the close-out commit that carries this report.
- **Contract and journals:** `NAPKIN_STAGE.md`, `STATUS.md`, `DECISIONS.md` (S-055…S-070,
  "Review gate A — outcome"), `BACKLOG.md` (B-0019…B-0031).
- **Docs:** `docs/napkin.md`, `docs/calckit.md`, `docs/render-checklist.md`, README (napkin act first).
- **Code:** `src/napkin2factory/concepts/` (build, massing, screening, screenshot, board, promote),
  `calckit/` and `calckit/data/`, `rulepacks/concept-v0.yaml`, `rulepacks/form-v0.yaml`,
  `core/model/concepts.py`, `core/model/style.py`.
- **Example:** `examples/kiln/concepts/`, `examples/kiln/style.yaml`, `examples/kiln/demo-napkin.sh`.
- **Tests:** `tests/unit/test_{concepts,massing,calckit,screening,screenshot,style,board,promote}.py`,
  `tests/e2e/test_concept_*.py`, `test_napkin_protocol.py`, `intake-transcripts/napkin-bench-kiln.md`,
  goldens `massing.json`, `aesthetics.json`, `kiln-board.json`.
- **Not in the repository:** nothing needed; review briefs and scratch runs stay outside it.
