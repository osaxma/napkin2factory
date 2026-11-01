# Calc kit

`napkin2factory.calckit` holds the envelope-grade engineering calcs that work from a
handful of numbers — a chamber size, layer thicknesses, a power, a region — before any
product model exists (NAPKIN_STAGE N4). Screening (`n2f concept build`) calls it with a
concept card's envelope numbers; a product's own calcs import it where they overlap, so
the screening estimate and the product's verified calc come from one source and cannot
drift apart (NAPKIN_STAGE §7).

Rules every function follows:

- takes and returns pint quantities from the shared registry
  (`napkin2factory.core.units`); floats are used only inside, in SI units; a bare number
  (an emissivity of `0.9` included — pass `Quantity(0.9, "")`) raises `UnitError`;
- its docstring states the method and cites the source of every correlation; material
  constants are the caller's (from datasheets) and are tagged `[verify]`;
- it is covered by a hand-checked test in `tests/unit/test_calckit.py` (the hand
  computation is in the test's comment) and by at least one reference case in its pack's
  `CASES` (below).

Results from the kit are **estimates**: screening labels them `estimate`, never
`computed`.

## The three packs

### `thermal_enclosure` — layered hot boxes

| function | returns | method |
|---|---|---|
| `Layer(thickness, conductivity, name, clearance=None)` | a wall layer | `conductivity=None` neglects its resistance (thin skin, air gap) but still grows the box; `clearance` is a fit gap on its inner side (geometry only) |
| `box_areas(inner, layers)` | chamber area + each layer's outer area (m²) | `A = 2(wd + wh + dh)`, each layer grows every side by `2(clearance + thickness)` |
| `layer_resistances(inner, layers)`, `wall_resistance(inner, layers)` | K/W | mean-area method `R = t / (k·√(A_in·A_out))` (Incropera & DeWitt ch. 3; DEC-015) `[verify]` |
| `steady_loss(inner, layers, t_hot, t_ambient, h_outer, emissivity_outer)` | `ThermalResult` | skin solved by bisection: conduction = convection + grey-body radiation (σ CODATA 2018) |
| `guard_temperature(hot_face, a_hot, a_guard, ε_hot, ε_guard, *, h_outer, t_ambient, h_gap_air=None, t_gap_air=None)` | degC | two grey surfaces, guard to room by convection + radiation (the kiln's guard model); optional gap-air convection on the guard's inner face |
| `guarded_loss(inner, layers, guard_gap, t_hot, t_ambient, t_gap_air, h, ε_skin, ε_guard)` | `ThermalResult` with `guard_temperature` | the kiln body: skin to gap air by convection, skin to guard by radiation, guard to room |
| `stored_heat(inner, layers, densities, specific_heats, t_hot, t_ambient, interface_temperatures)` | J | each layer's solid volume raised to the mean of its face temperatures |
| `heat_up_power(stored, loss, heat_up_time)`, `heat_up_time(stored, loss, power)` | W, h | `P = Q + E/t` (the full steady loss charged over the heat-up: conservative) |
| `bisect_root(f, lo, hi)` | float | the shared monotone solver |

`ThermalResult` has `loss` (W), `outer_skin_temperature` (degC),
`interface_temperatures` (outer face of each layer, degC), `wall_resistance` (K/W) and
`guard_temperature` (degC or `None`).

### `power` — elements and circuits

| function | returns | method |
|---|---|---|
| `element_current(power, voltage)` | A | `I = P/V` |
| `cold_resistance(power, voltage)` | Ω | `R = V²/P` |
| `wire_cross_section(diameter)` | mm² | `π/4·d²` |
| `wire_length(resistance, resistivity, diameter)` | m | `L = R·A/ρ` (Kanthal A1 ρ = 1.45 Ω·mm²/m at 20 °C, datasheet `[verify]`) |
| `surface_load(power, diameter, length)` | W/cm² | `P/(π·d·L)`; compare with `KANTHAL_GROOVE_SURFACE_LOAD_LIMIT` (2.0 W/cm², Kanthal handbook `[verify]`) |
| `circuit_class(region, current, *, voltage=None, headroom=1.2)` | `CircuitVerdict` | smallest class on file with `rating ≥ headroom·current` (plug before dedicated at equal rating) |
| `circuit_for_power(region, power, *, headroom=1.2)` | `CircuitVerdict` | tries every voltage on file for the region |

`CIRCUIT_HEADROOM_MIN = 1.2` follows the kiln's REQ-006 margin; US callers should pass
`headroom=1.25` (NEC 210.19/210.20 continuous loads) `[verify]`.

### `mass_cost` — mass, cost, handling, stock

| function | returns | method |
|---|---|---|
| `density(material)`, `mass(volume, material)` | kg/m³ + source, kg | `geometry/materials.py` handbook densities (unknown names fall back to mild steel, and the source says so) |
| `cost_estimate(process_class, mass=None, area=None, count=1)` | `CostEstimate(low, high, basis, source, known, verify)` | band × mass (`per_kg`), × area (`per_m2`) or per item, × count |
| `lift_class(mass)` | `LiftVerdict(label, mass, max_mass, source, verify)` | lightest handling class that covers the mass |
| `stock_sheet_fits(blank, material_class="mild-steel", margin=None)` | `StockVerdict(fits, sheet, fitting, known, source, message, verify)` | blank fits a sheet either way round; smallest sheet by area wins |

## Data tables and their `[verify]` status

Tables live in `src/napkin2factory/calckit/data/<name>.yaml` (shipped in the wheel with
the package) and are read with `load_table(name)`, which caches, returns a copy, and
refuses any row without a `source` or a `verify` key. **No row is verified by the
project:** every row is `verify: true` and is the owner's (or their electrician's,
fabricator's, supplier's) to confirm. DECISIONS.md lists each table as `[verify]`.

| table | rows | first source |
|---|---|---|
| `circuits` | 14 (SA 4, EU 2, UK 2, US 3, AU 3) | the plug and wiring standards named per row (SASO 2203, CEE 7/3, BS 1363, BS 7671, NEMA WD 6 / NEC 210, AS/NZS 3112 / 3000, IEC 60309 / 60898-1) |
| `cost_bands` | 7 (`sheet-metal`, `cut-sheet`, `cut-block`, `fiber-board`, `welding`, `machining`, `cots-controls`) | the kiln's own per-part estimates (basis `estimate`, DEC-012) over the built part masses; `cut-sheet` and `welding` rest on a single part each (low = high) |
| `materials` | 3 (K-23 insulating firebrick, ceramic fiber board (Kaowool 1260), mild steel) | the makers' datasheets (Morgan Thermal Ceramics K-23 and Kaowool 1260 board), at the kiln's chosen values: fiber board k 0.15 W/m·K at a ~400 °C mean (datasheet 0.12–0.18), ρ 260 kg/m³. Concept screening's insulation layers and the massing densities (`geometry/materials.py`) both read these rows, so the napkin and the factory use one number per material |
| `lift_classes` | 3 (one-person ≤ 25 kg, two-person ≤ 33 kg, equipment) | UK HSE INDG143 / L23 guideline weights — a screening filter, not a safe limit |
| `stock_sheets` | 10 (mild steel 4, stainless 3, aluminium 3) | common stockist formats (1000 × 2000, 1220 × 2440, 1250 × 2500, 1500 × 3000 mm) |

**Unknown keys warn, never fail.** A region, process class or material class a table
does not know returns a verdict instead of raising: `CircuitVerdict.status ==
"unknown_region"`, `CostEstimate.known is False`, `StockVerdict.known is False`. Callers
(the screening rules) turn these into a `warn` with the message, never a red verdict.

## Reference cases: every calc proves itself (F17)

A calc's reference case is an input, the expected result with its unit, a tolerance and the
source of the expectation. The build runs them: `n2f check` writes `calc-case` rows, so a
change to a formula that breaks a case fails the checks, naming the calc, the expected and
the computed value. A case passes when |computed − expected| ≤ max(`abs`, `rel` ·
|expected|) in the expected unit (default `rel` 1e-6, six significant figures).

- **The kit's own.** Each pack lists `CASES` (a list of `Case(fn, inputs, expect, source,
  rel=…, abs=…, pick=…, external=…)`), at least one per public function, and at least one
  marked `external=True`: a worked example from a handbook or datasheet, not the author's own
  arithmetic, so the formula is checked against a source and not against itself. Each pack a
  product's calcs use gets one `calc-case` row in that product's checks.
- **A product's.** `model/calcs/<module>.cases.yaml` beside `model/calcs/<module>.py`:

  ```yaml
  inputs:                 # parameter values every case below reads, unless it overrides them
    element-power: 2500 W
    mains-voltage: 230 V
  cases:
    current:              # the calc function's name
      - expect: 10.87 A
        rel: 0.001        # or abs: 0.01 (in the expected unit)
        source: "hand computation: 2500 W / 230 V = 10.87 A"
  ```
  A case runs the calc on its own inputs, never on the product's parameters: it checks the
  formula, not the design. A parameter the calc reads that the case does not give fails the
  case, naming it. A calc with no case is a `warn` row ("no reference case; add one so a
  change to this formula is caught") and lint `L16-calc-case`.
- **Write the case with the calc**, in the same edit: the source is a hand computation
  written out (the formula with its numbers) or a published worked example with its page.
  The kiln's three calc files carry 21 cases (`examples/kiln/model/calcs/*.cases.yaml`).

## Using the kit from a product calc

A product calc imports the pack and passes parameter quantities straight through; reads
still go through the `P` accessor, so dependency recording (D5) is unchanged:

```python
from napkin2factory.calckit import power as kit

def current(P):  # noqa: N803
    """Element current at rated power, A."""
    return kit.element_current(P["element-power"], P["mains-voltage"])
```

The kiln does this in `examples/kiln/model/calcs/thermal.py` (body walls, shell/guard
balance and door guard through `thermal_enclosure.guarded_loss` and
`guard_temperature`) and `element.py` (current, resistance, wire section, wire length,
surface load through `power`). The door-plug conduction and the stored heat stay in the
kiln: their geometry (an open-fronted liner, a tapered plug) is product-specific.
`tests/unit/test_calckit.py::test_kiln_numbers_reproduce_through_calckit` pins the
kiln's numbers, recorded before the refactor, to six significant figures.

Changing a calc module's source changes the evidence key of every calc in it (the key
hashes the module file), so a sign-off that cites one of them needs re-signing after a
refactor even when the numbers are identical.
