# napkin2factory v0.1 — handoff report

## 1. What works, per definition-of-done item

| # | item | status | evidence |
|---|---|---|---|
| 1 | `uv sync && make check` green; `make check-full` green | done | `make check`: 330 passed, 1 skipped (Playwright-less fallback), 7 deselected (kiln/demos), 10 min 49 s on the Intel macOS host; `make check-full` pieces: kiln validate/lint/build/check + `tests/e2e/test_kiln.py` (5 passed incl. timing), `tests/e2e/test_demos.py` (2 passed, 13 min for both demos), `tests/e2e/test_timing.py` (1 passed). Clean clone of commit `4273561`: `uv sync`, `n2f doctor` all green, `uv build` + `twine check` pass, `make check` 331 passed in 10 min 39 s |
| 2 | `n2f init demo --template bracket && n2f build && n2f check` < 2 min, self-contained report | done | `N2F_TIMING=1 pytest tests/e2e/test_timing.py` passes (warm kernel: ≈ 20 s). Gate 4 measured the cold path on a fresh venv at ≈ 2 min 20 s, of which ≈ 2 min is the first `import build123d` (S-048, B-0016); the report is one 1.6 MB file that loads from `file://` with no console errors |
| 3 | kiln builds clean < 10 min; every artifact asserted by `tests/validate_outputs.py`; report ≤ 20 MB | done | clean `n2f build` with renders: 56 s; `n2f check`: 2 s; `tests/validate_outputs.py examples/kiln` passes; report 3.5 MB; check matrix 0 fail · 6 EXAMPLE sign-offs · 216 OK · 60 warn; 0 interferences; 110.5 kg; 995 mm wide |
| 4 | `demo.sh` and `demo-design.sh` run unattended | done | both pass under `tests/e2e/test_demos.py` (v1.0.0 → ECR-001 → v1.1.0 → diff; then ECR-002 from `changes/ECR-002.patch` → v1.2.0 → diff), ≈ 6–7 min each with `--no-render` |
| 5 | invalidation tests prove exact rebuild sets | done | `tests/e2e/test_invalidation.py` |
| 6 | fresh-context intake simulation → validate + lint + silhouette | done | `tests/e2e/intake-transcripts/monitor-bracket.md` |
| 7 | fresh-context README walk-through | done | gate 4: every README command ran in order; report and diff pages load from `file://` with no errors; two onboarding blockers fixed (S-048, README rewrite); see DECISIONS "Review gate 4" |
| 8 | `uv build` + `twine check`; PyPI names checked read-only | done | `dist/napkin2factory-0.1.0-py3-none-any.whl` (604 kB, 201 files incl. templates, vendored three.js, rule packs, catalog) and the sdist both pass `twine check`; see §7 |
| 9 | this report | this file | |

Commands as run on 2026-10-30 (Intel macOS, uv-managed Python 3.13.18, `N2F_OFFLINE=1`):

```
make check                                   # 10 min 49 s
N2F_TIMING=1 uv run pytest tests/e2e/test_kiln.py        # 5 passed (clean build 56 s)
N2F_TIMING=1 uv run pytest tests/e2e/test_demos.py tests/e2e/test_timing.py   # 3 passed, 13 min
uv build && uv run twine check dist/*        # both pass
```

## 2. Dropped or simplified

Nothing from the core loop (build → check → ECR → impact → apply → diff → release) was
dropped. Simplifications, each in `BACKLOG.md`:

- ⤵ `docs/vocabulary.md` localization hooks (M9 droppable): not done; the vocabulary lives in
  one table and two dicts (`report/builder.py` VOCAB, `cli/check.py` OWNER_WORDS).
- Section toggle in the report viewer is a single mid-height clipping plane (M5 ⤵ item was
  done minimally).
- Kiln: guard standoffs, the thermocouple entry hole and element tails are described in the
  manufacturer notes, not modelled (B-0010); the thermocouple is a BOM-only part.
- Concurrent `n2f build` runs in one folder are not locked (B-0004); interface parties are
  parts only, not sub-assemblies (B-0005).
- Owner-view polish left: URI prefixes in tables (B-0008), terminal hanging indents (B-0007),
  design-time wording for inspection sign-offs (B-0009).
- Python 3.14 untested (B-0003); the host was Intel macOS, Linux only via CI (S-001).
- Kiln after gate 3: the shells are still generated as one-piece developments; the notes let the
  shop build them as multi-piece weldments (B-0011). The door plug tapers but the opening is
  straight, so the hot-end gap is packed with fiber blanket (B-0014). The footprint check is
  evaluated with the door closed (B-0012). The cost target moved to 2500 USD pending the owner
  (DEC-012); the heat-up time is 7 h, not the owner's "about four hours" (DEC-004).

## 3. `[revisit]` decisions and `[verify]` numbers

`[revisit]` (system):
- S-001 host platform: the plan's Linux definition of done was exercised through `ci.yml`
  (ubuntu + macos matrix), not on this machine; run `make check-full` once on Linux.
- S-011 unattended git identity (`napkin2factory <n2f@localhost>` when none is configured):
  decide whether intake should ask the owner's name instead.
- DEC-011 footprint: the owner's "about 800 mm" alcove is exceeded (996 mm closed, more with
  the door open); flagged for the owner, not silently accepted (B-0012).
- B-0013: K26 instead of K23 for the hot face if the owner fires above cone 6 regularly.

`[verify]` (kiln engineering, all tagged `verify: true` in `examples/kiln/model/decisions.yaml`):
- K23 thermal conductivity 0.25 W/m·K at the mean wall temperature (Morgan datasheet range
  0.20–0.30): drives heat loss and the inner shell temperature.
- Ceramic fiber board k = 0.12 W/m·K and ρ = 260 kg/m³ (Kaowool 1260 class): drives skin
  temperature and 40 kg of the mass.
- Film coefficient 10 W/m²·K and emissivities 0.9/0.9 (powder coat): the guard temperature
  (53 °C vs the 60 °C limit) is sensitive to these; a 20 % lower h gives ≈ 58 °C.
- Kanthal A1 resistivity 1.45 Ω·mm²/m (datasheet, cold): wire length 24 m; hot resistance
  ≈ 4 % higher.
- Sheet-metal rule thresholds (r ≥ 1 t, hole ≥ 1 t, hole-to-bend ≥ 2 t + r, flange ≥ 4 t) and
  the K-factor table: shop rules of thumb, confirm with the fabricator.
- Thermal model (DEC-015): mean-area conduction (geometric mean of each layer's inner and
  outer areas) with a two-node radiation balance between shell and guard, gap air assumed at
  50 °C, convection 5 W/m²·K, emissivities 0.9. Predicts shell ≈ 79 °C, guard ≈ 44 °C, door
  tray ≈ 70 °C, door guard ≈ 42 °C, loss ≈ 0.9 kW. The flat-slab model it replaced gave twice
  the loss; a shape-factor model gives half. Measure the guard side, guard top, door guard
  and latch at steady state before trusting REQ-003.
- Stored heat (brick + fiber, steady profiles, ρ/cp as parameters): 27 MJ; with the loss it
  sets 2.5 kW / 7 h (margin 1.26) and ECR-001's 9 h.
- Element surface-load limit 2.0 W/cm² and pitch ≥ 2 d for Kanthal A-1 in grooves at 1200 °C
  (Kanthal handbook range); the design sits at 1.70 W/cm², 2.09 d.
- Cost target 2500 USD (DEC-012) against the intake's 1500: the estimate is ≈ 2200 USD after
  the review's safety additions; the owner has to confirm.

## 4. The 30-second demo script

For the ECO-loop GIF, in a fresh copy of `examples/kiln` (what `demo.sh` does unattended):

1. `n2f status` — "Verify: done · next: release" (2 s).
2. `n2f release v1.0.0 --allow-example-signoffs` — the Revision badge turns green; show the
   package ZIP path (3 s).
3. `n2f ecr impact ECR-001` — the impact report: parts that rebuild (shell, guard, door,
   liners), REQ-016 "known after rebuild", sign-offs that must be redone (6 s).
4. `n2f ecr approve ECR-001 --by Owner` · `n2f ecr apply ECR-001` — one-line diff in
   `parameters.yaml` (3 s).
5. `n2f build && n2f check` — only the affected rules rerun; the matrix shows the two
   invalidated safety sign-offs as "needs your sign-off" (6 s).
6. `n2f signoff REQ-003 …` (labelled EXAMPLE in the demo) · `n2f ecr close ECR-001` — revs
   bump A → B, changelog grows (3 s).
7. `n2f release v1.1.0 --allow-example-signoffs` · `n2f diff v1.0.0 v1.1.0` — open the diff
   page: red/green drawing overlay of the shell, BOM delta with cost and mass, side-by-side
   3D with the changed parts in amber (7 s).

Pages to show: `build/report/index.html` (section index on the left; every URI is a link),
`build/site/diff/v1.0.0..v1.1.0/index.html`.

## 5. Known rough edges in UX, ranked

1. **First build looks hung.** The first `import build123d` on a machine takes one to two
   minutes with no output. v0.1 prints a notice (S-048); warming the import at `n2f init` is
   B-0016.
2. **`uv run n2f` only works inside the checkout.** From anywhere else uv cannot find the
   project; the README now says to `uv tool install .` for that. Publishing to PyPI removes it.
3. **Door swing is not in the footprint check.** REQ-002 is evaluated with the door closed;
   the open door needs ~250 mm beside the hinge side (B-0012).
4. **`n2f ecr close` does not refuse while a sign-off is missing** (only `n2f release` does), so
   an owner can close a change request and be stopped one step later (B-0015).
5. **Owner-view tables still show URI prefixes** (`part://`, `req://`) and wrapped terminal lines
   have no hanging indent (B-0007, B-0008).
6. **Inspection-type sign-offs read as post-manufacture gates** at design time ("the package
   requires deburring") (B-0009).
7. **Example sign-offs** are now impossible to mistake for reviews in every view (S-047), but a
   demo Revision still has to be released with `--allow-example-signoffs`, which prints a banner
   an owner may find alarming. Intended.

## 6. Recommended next steps for v0.2

- **Electrical stage (KiCad).** Add `model/electrical/*.kicad_sch` as source with an
  `elec:<id>` rule family (kicad-cli ERC/DRC → `features.json`-style facts), `wire://` URIs,
  and a `circuit` verify kind; the kiln's controller box, PID, SSR and element become one
  schematic whose DRC is a check row. The graph, URIs and report sections already generalise.
- **MCP server.** Wrap the CLI verbs (`status`, `impact`, `ecr *`, `check`, `build`) as MCP
  tools over the same `core` functions so chat clients (door 1) can run intake and builds in
  their sandbox; `--json` outputs are the tool results already.
- **Manufacturer profiles.** `model/manufacturers/*.yaml` exists as schema only; v0.2 gives
  rule packs a `profile` dimension (tolerances held, min bend radius per material, sheet
  sizes, processes) and lets `n2f check --profile shop-x` evaluate against it; the BOM's
  "what to tell the manufacturer" column becomes a quote request per profile.
- **Share mode (`n2f publish`).** `n2f init` already writes `build.yml`/`release.yml`; share
  mode creates the GitHub repo (the one OAuth), pushes, and turns `build/site/` into Pages so
  `/kiln/v1.1.0/` and `/kiln/diff/v1.0.0..v1.1.0/` are URLs a manufacturer can open.
- **Tolerance stack-up.** Parts carry `tolerance_class` (D26); add `stackup://` calcs over
  chains of interface frames (worst-case and RSS) as a verify kind, and flag over-toleranced
  parts with a cost multiplier in the BOM.
- **Smaller:** owner-view table wording without URI prefixes (B-0008), hanging indents in
  terminal output (B-0007), design-time vs post-manufacture sign-offs (B-0009), a lock for
  concurrent builds (B-0004), Python 3.14 (B-0003).

## 7. PyPI name availability
Read-only `GET https://pypi.org/pypi/<name>/json` on 2026-10-30: `napkin2factory` → HTTP 404 (**available**), `n2f` → HTTP 404 (**available**). Nothing was published. Recommendation unchanged from the handoff: publish `napkin2factory`; register `n2f` as a defensive placeholder depending on it.

## 8. Shop read-through verdict (gate 3)

Quoted from `examples/kiln/reports/shop-readthrough.md`, written by the fresh-context gate-3
reviewer role-playing a sheet-metal shop and a refractory supplier against the M8 package:

> **Controller box and door skin: quotable this week with the answers to Q6–Q7. Outer shell
> and guard: not quotable as drawn — one-piece deep trays we cannot form, blanks wider than
> stock sheet, standoff and penetration holes missing, and the notes contradict the DXF on
> where the hinges go. Expect the shell price to double against your 180/160 USD estimate
> once they become multi-piece, powder-coated, deburred weldments.**

> **Boards and plain slabs: quotable today as cut pieces. Grooved liners and the door block:
> quotable with an allowance for a cut plan we would have to make ourselves, and with a line
> on the quote saying every brick-to-brick and brick-to-board joint in this package is drawn
> at zero clearance and will need trimming on site.**

The same review's engineering verdict was NOT READY with nine blockers (DECISIONS "Review
gate 3"). All nine were addressed before handoff (the tool fix S-047; the kiln rework
DEC-012…DEC-017: every hole in the DXFs, hinges on a bolted post, a tray-and-guard plug door
that clears on the swing, multi-piece shells allowed, 3 mm lining clearance, ceramic-sheathed
probes, independent over-temperature limit, mean-area thermal model with both guards
computed, 2.5 kW element in five grooves). The read-through is kept verbatim with a preface
saying what changed; nobody at a real shop has read either version, and the estimate is now
about 2200 USD against an intake wish of 1500 USD (DEC-012, owner to confirm).
