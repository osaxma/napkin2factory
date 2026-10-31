# Napkin2Factory — NAPKIN_STAGE.md: Grand Plan for v0.2 ("the napkin")

**Audience:** the autonomous agent that will build this. You are not supervised. Nobody will answer questions. You decide, you log, you continue.
**Companions:** `GRAND_PLAN.md` (v0.1 — its §0 operating contract, §8 testing strategy and §9 workflow rules apply here **unchanged** unless this file says otherwise), `DECISIONS.md`, `BACKLOG.md`, `HANDOFF-REPORT.md` (what v0.1 shipped), `docs/history/` (the why).
**Owner's bar, verbatim:** "impeccable UX of the ECO loop" — now extended one stage earlier: *iterating ideas, rough sketches, back-and-forth revisions of the idea itself and discussing limitations before deep design*. The owner saw the v0.1 kiln and did not like its appearance. That reaction is the founding requirement of this release.

---

## 0. Why this release (read once, it calibrates every judgment call)

v0.1 proved the factory: a text model becomes a quotable package, and changes rebuild exactly what they invalidate. But three of its four owner-parked decisions — DEC-011 (995 mm wide vs. an ~800 mm alcove), DEC-012 (≈2200 USD vs. a 1500 wish), DEC-004 (7 h heat-up vs. "about four hours") — are **concept-stage trade-offs that surfaced at hour forty instead of minute five**, and the fourth complaint (the kiln's looks) is taste, which an interview cannot capture because taste only shows up when you see something.

v0.2 therefore adds the **napkin stage**: cheap, plural, disposable concepts; honest feasibility screening with a limitations strip; aesthetic vocabulary in the kit; and a promotion step that turns the chosen concept — taste included — into traceable model content. Divergence before commitment. Nothing downstream of promotion changes its rigor.

The scope boundary in one sentence: **a concept answers "which product should exist and roughly what does it look like"; the factory answers everything else.** When unsure whether something belongs in the napkin stage, it does not.

## 1. Mission, non-goals, definition of done

### 1.1 Mission
Ship **napkin2factory v0.2**: the concept stage (`concepts/` + `n2f concept new|list|show|build|board|promote|reject`), massing fidelity in the kit, a system-level calc kit powering concept screening, styled concept imagery via viewer screenshots, `style.yaml` + aesthetic kit parameters, form requirements at promotion, the PM-skill napkin protocol with interpretation cards for dropped sketches/photos — plus the four v0.1 backlog items this stage depends on or touches (B-0008, B-0015, B-0016, B-0017). Retrofit the kiln with the concept history that *would have* caught DEC-011/012/004, and ship it as the demo.

### 1.2 Non-goals for v0.2 (stay in `BACKLOG.md`)
Everything in GRAND_PLAN §1.2 that is not named above, plus: image-to-geometry (scan/photo → CAD) in any form; AI image generation anywhere; freeform/sculpted massing beyond kit composition; concept-stage FEA; multi-concept merge tooling; MCP server and share mode (v0.3); electrical, manufacturer profiles, stack-up (v0.4). The board is not collaborative/multi-user. True multimodal (an actual image in the agent's context) is exercised by the owner manually, not by automated tests — tests use textual sketch stand-ins (see N9, M5).

### 1.3 Definition of done (all from a clean clone; macOS host with CI matrix as in v0.1, S-001)
1. `uv sync && make check` green; `make check-full` green (both grown per §6).
2. In a fresh `n2f init demo --template bracket`: create two concepts via CLI, `n2f concept board` produces `build/concepts/board.html` — self-contained (inline module viewer, no external refs), loads from `file://` with no console errors — in under 60 s warm total for both builds plus the board (asserted under `N2F_TIMING=1`).
3. `examples/kiln/concepts/` holds four concept cards including **one red** (fails screening, shown with reasons, never hidden); the board renders all four side by side with silhouette image, key dims, `computed` vs `estimate`-labelled numbers, and a limitations strip per concept. You open the board and judge it by eye against `docs/render-checklist.md` (extended, M3) and record the judgment in `STATUS.md`.
4. `n2f concept promote` on the kiln's chosen card seeds `parameters.yaml` entries, `style.yaml`, at least two **checkable form requirements** (e.g. exposed corner radii ≥ x, no visible fasteners on the front face), and a `DEC-` entry that attaches the rejected variants; `n2f build && n2f check` then passes with the form-requirement rows present in the matrix. `promote` refuses a red card without `--override` + a logged decision.
5. `examples/kiln/demo-napkin.sh` runs unattended in a temp copy (D23): three concepts built → board → one screened red with visible reasons → promote the winner → the existing factory loop proceeds (`n2f build && n2f check` green).
6. Concept imagery is produced by the **styled viewer screenshot path** (N6): Playwright screenshots of the three.js viewer with `style.yaml` materials and lighting; the z-buffer fallback only fires when Playwright is unavailable and is logged. You open at least one styled screenshot and confirm it reads as a *product image*, not a debug render.
7. Interpretation-card flow proven by a scripted simulation (M5): a fresh-context subagent given the PM skill text and a *textual* sketch description produces an interpretation card, receives one correction, and emits concept cards that pass `n2f concept lint`; transcript saved under `tests/e2e/intake-transcripts/`.
8. Backlog folds verified by test: first-build kernel warm-up at `n2f init` (B-0016); section renders show a true plane cut, readable on the kiln's thick walls (B-0017); owner-view tables drop URI prefixes (B-0008); `n2f ecr close` refuses while a sign-off is missing, like `release` (B-0015).
9. `HANDOFF-REPORT-v0.2.md` exists (same §11 shape as v0.1's, plus: the three DEC-011/012/004 stories retold as "what screening would have said in minute five", quoted for the launch material).

---

## 2. Locked decisions (N-series; GRAND_PLAN §2 D-series remains in force except where amended here)

| # | Decision | Why |
|---|---|---|
| N1 | **Concepts are outside the build graph.** They live in `concepts/C-\d{3}.yaml` (+ `concepts/refs/` for images), are never inputs to any `build/` rule, never gate anything, and are disposable. `n2f validate` ignores them; `n2f concept lint` is their only (light) validator. Deleting `concepts/` must change no build output | Divergence must be free; the factory's determinism must be untouched |
| N2 | **D17 is amended as S-052 shipped it, ratified by the owner 2026-10-31**: one report/board layout; persona lives in dialogue, status words, and *which artifacts lead in conversation* — never in CSS reshuffling. The board follows the same rule | Owner ratification on record; closes the one silent D-override from v0.1 |
| N3 | **Massing fidelity is a mode of the existing kit**, not new geometry code: every generator accepts `fidelity: massing` and returns silhouette solids only (no bends, holes, fillets, features; flat pattern/cut list omitted; features JSON carries `fidelity: massing`). A geometrically impossible composition must still fail for real. Concept massing is declared on the card as a list of kit calls with placements (agent-authored, ~20 lines) | Same generators = zero duplication; failures are real, not estimated |
| N4 | **A system-level calc kit** (`napkin2factory.calckit`) holds the envelope-grade engineering calcs (v0.2 packs: `thermal_enclosure` — layered conduction, skin/guard estimate, heat loss; `power` — element power, heat-up from stored heat, circuit class per region table; `mass_cost` — volumes × density, cost bands per process class; each function cited, pint-typed, with a hand-checked test, `[verify]` discipline per GRAND_PLAN §0.10). The kiln's product calcs are refactored to import from it where they overlap; screening calls it with card envelope numbers | Screening needs calcs before a product model exists; one source for both fidelities |
| N5 | **Screening is a third tier, distinct from verification**: massing build + calc-kit estimates + an envelope rule pack (`rulepacks/concept-v0.yaml`: fits declared site constraints incl. door-swing clearance; circuit class available for the region; mass vs. lift classes; max developed blank dimension vs. a stock-sheet table `[verify]` — the shop read-through's formability lesson; walls fit inside envelope; controls not adjacent to the hot face). Every board number is labelled **`computed`** (from massing geometry) or **`estimate`** (calc-kit). A red concept is **shown with reasons, never hidden** — red is information. `n2f concept promote` refuses red without `--override`, which requires a `DEC-` entry | Speed without lying; "impossible" surfaces in seconds; the limitations discussion is mechanical |
| N6 | **Concept imagery = styled viewer screenshots**: a headless Playwright page loads the same inline-module viewer (S-003/D13 machinery) with the massing GLB, `style.yaml` materials/palette and a fixed three-point lighting rig; screenshots (iso + front, 1200 px) are the images posted in chat and embedded in the board. The z-buffer renderer (D12) remains the *agent-eye correctness* path and the only fallback when Playwright is absent (logged, `[revisit]`). D12's "renders are for correctness, not marketing" now reads: **z-buffer for correctness, viewer screenshots for appearance** | v0.1's flat hash-colored renders are useless for "do I like it" — the owner's founding complaint |
| N7 | **`style.yaml` per product** (seeded at `init`, overridable per concept card): preset (`industrial` \| `appliance` \| `lab`), palette/finish map by part role, `radius_scale`, `reveal`, `fastener_visibility`. **Kit aesthetic parameters** (consumed from style defaults unless overridden per part): corner/edge radius, chamfer, panel reveal/gap, overhang, vent/grille pattern, fastener visibility. Scope discipline: 6–8 parameters across the kit, full fidelity only (massing ignores them except palette) | The difference between "welded box" and "product", at modest kit cost |
| N8 | **Promotion is the bridge and the arbitration event.** `n2f concept promote C-00x` writes: envelope numbers → `parameters.yaml`; layout + style choices → `style.yaml` + **form requirements** (ordinary `req://` rows, category `usability`/`geometry`, verified by `geometry_prop` or rule-pack checks — taste, once chosen, becomes checkable); the selection → one `DEC-` entry with every sibling card attached as rejected alternatives (cards flip to `rejected`, kept forever); the card → `promoted`. Site constraints on the card (alcove width, circuit) become requirements, not footnotes — DEC-011 must be structurally impossible to repeat | Taste gets the same traceability as engineering; the human stays the gate |
| N9 | **Images never become geometry.** A dropped sketch/photo/drawing produces an **interpretation card** (structured: estimated proportions, layout, style cues, any read dimensions tagged `[verify]`) that the user corrects *in words* before any card is built; the original lands in `concepts/refs/` and is referenced by the cards it informed. The PM skill carries this protocol; automated tests use textual sketch stand-ins; real-image runs are owner-manual (§1.2) | Scan-to-CAD is the least reliable tech in the space; provenance without fragility |
| N10 | **The board** (`n2f concept board` → `build/concepts/board.html`) is self-contained exactly like the report (inline module script, embedded GLBs/screenshots, ≤ 20 MB, `file://`-clean) and read-only: variants side by side with screenshot, interactive massing 3D, key dims, labelled estimates, limitations strip, refs thumbnails, red cards with reasons. Choosing happens in conversation or CLI, not on the board | One decision surface, same self-containment guarantees, no new UI machinery |
| N11 | **Stage model:** Napkin precedes Intake and is **optional** — `n2f status` shows it only when `concepts/` is non-empty, complete when a card is `promoted`; products without concepts (v0.1 examples, existing users) are untouched. `warn` never blocks (D10 unchanged) | Backward compatible; no forced ceremony for products born as specs |
| N12 | **Backlog folds are in-scope and tested**: B-0016 (kernel warm-up kicked off in the background by `n2f init`, plus the concept loop reuses one warm process); B-0017 (true plane section via OCCT section/per-triangle clipping — needed for honest concept and report imagery); B-0008 (owner tables drop URI prefixes; files and engineer contexts keep them); B-0015 (`ecr close` refuses on missing sign-offs with the same persona wording as `release`) | Each either blocks napkin UX or is a 1-line gate-consistency hole |
| N13 | **Branch `v0.2-build`**, same journal discipline (`STATUS.md`, `DECISIONS.md` S-numbers continuing, `BACKLOG.md`), same green-before-commit, same network policy as GRAND_PLAN §0.7 with one addition: Playwright's Chromium download is allowed (it already was) and **no other** new downloads | Continuity; the v0.1 run proved the discipline works |

---

## 3. Concept card schema (pydantic; the one new model file family)

```yaml
# concepts/C-003.yaml
id: C-003                     # C-\d{3}
title: Squared shell, flush door
status: exploring             # exploring | rejected | promoted
based_on: C-001               # optional lineage
refs: [refs/sketch-01.jpg]    # optional; informs provenance, never geometry (N9)
layout: {load: front, door: hinged-left, controls: side-right, stand: four-leg}
envelope:                     # free-form named quantities; these seed parameters at promote
  chamber: [200 mm, 200 mm, 200 mm]
  insulation: 170 mm
site:                         # constraints screening checks against; become requirements at promote
  alcove_width: 800 mm
  circuit: 240V-13A
  region: SA                  # circuit-class table key [verify]
style: {preset: appliance, corner_radius: 8 mm, fastener_visibility: hidden-front}
massing:                      # kit calls at fidelity: massing (N3); placements like assembly code but declarative
  - {kit: enclosure, as: body, args: {length: 540 mm, width: 540 mm, height: 620 mm}}
  - {kit: block, as: door, args: {...}, at: {...}}
  - {kit: frame, as: stand, args: {...}, at: {...}}
notes: >
  Flush door means the hinge post sits proud on the left; see refs/sketch-01.jpg.
screening: null               # written by `n2f concept build`: {computed: {...}, estimates: {...}, rules: [...], verdict: green|red}
decision: null                # set by promote/reject: {dec: DEC-0xx, at: ...}
```

`n2f concept lint`: id/status valid; every `refs` file exists; `massing` kit names valid; quantities parse; `site` keys from a known vocabulary (warn on unknown, never fail — divergence is free). That is all: concepts are deliberately under-validated.

## 4. CLI surface added

```
n2f concept new <title> [--from C-00x]      n2f concept list|show C-00x     n2f concept lint
n2f concept build [C-00x|--all]             # massing build + screening + styled screenshots; seconds, warm
n2f concept board                           # build/concepts/board.html
n2f concept promote C-00x [--override]      n2f concept reject C-00x --reason TEXT
```
Same exit codes, `--json` everywhere, persona vocabulary throughout (a red card prints "this direction has problems:" not "screening failed"). All verbs run equally well agent-driven or by hand (the v0.1 BYOA contract).

## 5. Milestones

Budgets are scope-control guidance (GRAND_PLAN §7 rules: ⤵ droppable only after the core is green; trims go to `BACKLOG.md`).

### M0 — Folds and ratifications (budget 3 h)
**Build:** branch `v0.2-build`; append the owner's S-052 ratification to `DECISIONS.md` (N2); implement B-0015 and B-0008 (small, isolated — do them first while the tree is quiet); B-0016 warm-up (background `import build123d` thread kicked off by `n2f init` and by the first `n2f concept` verb; notice text updated); B-0017 true plane section (OCCT section edges or per-triangle clipping; regression: the kiln mid-plane section shows wall layers as bands, not slivers — compare against the v0.1 artifact).
**Exit:** `make check` green with four new regression tests; kiln section render opened and judged in `STATUS.md`.

### M1 — Concept model + CLI skeleton (budget 4 h)
**Build:** card schema + loader + `concept lint`; `concept new|list|show|reject`; `concepts/` in templates (`_common` gets nothing — concepts are created, not scaffolded; `init` only seeds `style.yaml`, N7); stage computation gains optional Napkin (N11).
**Tests:** schema fixtures valid/invalid; lint rules each with a failing fixture; stage fixtures (no concepts → napkin hidden; cards → shown; promoted → complete).
**Exit:** `n2f concept new/list/show/reject` round-trip on a temp product; `n2f status` shows the stage correctly in all three states.

### M2 — Massing fidelity + calc kit + screening (budget 8 h)
**Build:** `fidelity: massing` through every kit generator (N3); declarative `massing:` composer (card → placed silhouettes → GLB/props through the existing exporters, under `build/concepts/C-00x/`); `napkin2factory/calckit/` (N4 packs, cited, tested against hand values — reuse the kiln's verified numbers as the first test vectors); `rulepacks/concept-v0.yaml` + runner reuse (S-022 pattern: rules are named Python checks, YAML carries thresholds/wording); screening writer (card.`screening` filled; `computed` vs `estimate` labels at the data level, not just display); red/green verdict; `concept build` orchestrates it all **in-process** (no DAG — concepts are outside the graph, N1) and must run in seconds warm.
**Tests:** every generator in massing mode (golden silhouettes: volume/bbox only); an impossible composition fails with an actionable error; calc-kit hand-value tests; each concept rule with a red fixture; a kiln-like card screens red on `alcove_width: 800 mm` **with the door-swing term included** (the DEC-011 regression — this exact test is the release's reason to exist); labels present in `screening` JSON.
**Exit:** `n2f concept build --all` on a fixture product with one green and one red card; screening output correct and labelled.

### M3 — Styled imagery + style.yaml + kit aesthetics (budget 6 h)
**Build:** `style.yaml` schema + seeding at `init` (N7); kit aesthetic parameters at full fidelity (6–8 params; enclosure and frame first, plate/panel/bracket_l as applicable); the screenshot rig (N6): a persistent Playwright page template loading the inline viewer with the massing GLB + style palette + fixed lighting; iso + front PNGs per card; z-buffer fallback wired and logged; `docs/render-checklist.md` extended with a "product image" section (reads as an object someone might buy: materials plausible, lighting neutral, no hash colors, no z-fighting).
**Tests:** style schema fixtures; aesthetic params reach geometry (a corner-radius golden); screenshot exists, non-blank, ≥ 1200 px, palette color actually present in pixels; fallback path logged when Playwright is absent (env-forced in test).
**Exit:** **open the styled kiln-concept screenshots and judge them** against the checklist; record the judgment. This is the owner's founding complaint — do not pass this exit on "it ran".

### M4 — Board + promotion + form requirements (budget 6 h)
**Build:** the board (N10) on the report's self-containment machinery; promotion (N8): parameter seeding (collision-safe: refuse to overwrite an existing parameter without `--override`), `style.yaml` merge, form-requirement synthesis (template library: corner-radius min, fastener-visibility-by-face, control-placement, plus site constraints → envelope/door-swing requirements), the `DEC-` with rejected siblings attached, card state flips; red-gate refusal + `--override` path writing its own `DEC-`; `concept-v0` form checks at full fidelity (verify kinds reuse `geometry_prop` and rule-pack rows — no new check machinery).
**Tests:** board self-containment + ≤ 20 MB + `file://` Playwright smoke; promote on green seeds exactly the expected model diff (golden YAML diff); promote on red refuses; `--override` writes the decision; post-promote `n2f build && n2f check` green with form rows in the matrix; site constraint became a requirement whose violation fails.
**Exit:** fixture product: concepts → board → promote → factory loop green end to end.
**Review gate A (honesty + architecture, fresh context):** checklist — Can any build-graph rule read `concepts/`? (must be no, N1.) Is every board number traceably `computed` or `estimate`, and is any estimate presented as computed anywhere (board, chat text templates, JSON)? Can a red card reach promotion without a logged decision? Do form requirements actually fail when violated (flip one and check)? Is the calc kit cited and unit-safe throughout?

### M5 — PM-skill napkin protocol + interpretation cards (budget 4 h)
**Build:** `n2f-pm` skill gains the napkin protocol: diverge-first framing, 3–5 variants by default, limitations talk sourced from `screening` (never invented), interpretation-card protocol for dropped images (N9: extract → play back → correct in words → then cards), promotion question in owner register ("lock this in as the design direction? Changing the basic form later is a bigger change"), red-card explanation pattern; `n2f-design` skill: consume `style.yaml`, respect form requirements, never edit `concepts/` post-promotion except status fields. `docs/napkin.md`.
**Tests/Exit:** scripted simulation per DoD 7 (textual sketch stand-in, one correction round, cards lint-clean, build green); transcript saved. ⤵ a second simulation playing an *engineer* persona driving the CLI directly.

### M6 — Kiln retrofit + demo + hardening (budget 6 h)
**Build:** `examples/kiln/concepts/`: four cards telling the true story — C-001 (the v0.1 design as-built: screens **red** on the 800 mm alcove with door swing, and its estimate strip shows the cost band screening can price (1130–2747 USD around DEC-012's ≈ 2200) and the honest heat-up estimate — 4.4 h at 2.5 kW, with DEC-004's 7 h named as the planned margin on top, never 7 h hard-coded as an estimate (gate A, C5) — i.e. *what screening would have said in minute five*), C-002 (compact: smaller chamber fitting the alcove — trade-offs visible), C-003 (the promoted direction with the owner-flavored style), C-004 (a rejected styling variant); `style.yaml` for the kiln; promote C-003's record reconciled with the existing model (promotion seeds must match what the model already declares — this retrofit is also the collision-safety test); `demo-napkin.sh` (DoD 5) and its `make check-full` test; README + docs updated (napkin is now the first act of the ten-minute run: two concepts on the bracket before the build); `HANDOFF-REPORT-v0.2.md`.
**Tests:** board golden for the kiln (card count, red reasons text, label counts); demo-napkin e2e; timing (DoD 2) under `N2F_TIMING=1`.
**Exit:** DoD 3–5; **open the kiln board, the red card, and the styled screenshots; judge and record.**
**Review gate B (UX, fresh context, owner persona):** play a novice with only chat-style `n2f` output and the board: Is divergence actually cheap (ask for "like C-002 but taller" — how many steps)? Does the red card read as information, not rejection? Is any git/engineering vocabulary visible? Is the promotion question comprehensible and its consequence clear? Could you tell which numbers are estimates? Fix blockers; log the rest.

### M7 — Close-out (budget 2 h)
`make check-full` from a clean clone; final `STATUS.md`; `HANDOFF-REPORT-v0.2.md` per DoD 9 including the minute-five retellings of DEC-011/012/004 and the 30-second napkin demo script (board → point → promote → the v0.1 ECO GIF continues from there — the full "napkin to factory" on screen).

---

## 6. `make check` / `make check-full` growth
`make check` adds per milestone (same rhythm as v0.1): M0 regressions → M1 concept unit/e2e → M2 massing goldens + calckit + screening (fixture product) → M3 style/screenshot tests (Playwright-marked, skipped with reason where absent) → M4 board + promote e2e → M5 intake sim artifacts check. `make check-full` adds: kiln concepts build + board golden + `demo-napkin.sh` + DoD 2/3 timing under `N2F_TIMING=1`. Coverage floor stays ≥ 80 % on `core` and extends to `calckit`.

## 7. Risk register additions (GRAND_PLAN §10 remains)

| Risk | Signal | Fallback |
|---|---|---|
| Playwright screenshots flaky/slow in loop | M3 timing | Persist one page across cards; cap at iso+front; last resort: board embeds live viewer only and chat posts z-buffer with a logged quality note `[revisit]` |
| Massing mode leaks features (bends/holes) into silhouettes | M2 goldens | Massing path constructs primitive solids directly in each generator, bypassing feature code entirely |
| Calc-kit duplication drifts from kiln calcs | M2 refactor | Kiln calcs import calckit; a test asserts the kiln's verified numbers reproduce through calckit |
| Promotion collides with an existing model (retrofit) | M6 | `promote` refuses to overwrite without `--override`; retrofit uses reconcile mode (seed only what is absent, assert equality on what exists) |
| Aesthetic params explode kit complexity | M3 budget | Hard cap 8 params; enclosure + frame first; others `[revisit]` |
| Circuit-class / stock-sheet tables wrong for a region | Always | Tables are data files with sources, `[verify]` tags, and a `warn`-not-fail unknown-region path |
| Style screenshots look worse than no styling | M3 exit judgment | Neutral preset ships first (grays + one accent); presets are data; judge before building more |

## 8. How the owner should run this plan (not for the agent)
Same rig as v0.1 (it worked): sandboxed macOS user, bypass permissions, `uv`-managed Python 3.13, Playwright Chromium available. Driver: Claude Fable 5.1, effort high; review gates A/B on fresh-context Fable 5.1 at xhigh; implementation subagents may run Opus 5.5. First message: **"Read `NAPKIN_STAGE.md`. It is your contract, and `GRAND_PLAN.md` §0/§8/§9 apply. Execute to completion."** Expect roughly one to two days of wall-clock. Before or during the run, do your four owner tasks if not done: react to the v0.1 kiln report (feed reactions as notes the M6 retrofit can use), answer DEC-011/012/004 + B-0013 (ideally as ECRs in a copy of the kiln), register `napkin2factory` and `n2f` on PyPI, and — already handled by N2 — S-052 stands ratified.
