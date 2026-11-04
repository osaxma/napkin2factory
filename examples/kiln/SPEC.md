# Benchmark Tier 3: mini electric test kiln (`SPEC.md`)

The comprehensive tier of the benchmark ladder (road-to-v1.0 §4, Track A §2.4): a front-loading
200 × 200 × 200 mm electric test kiln reaching 1200 °C on a single-phase 230 V supply.
Retrofitted from the shipped kiln model (`examples/kiln/`, `n2f.yaml`, `model/`, `concepts/C-001..C-004`)
to serve as the benchmark specification against which cold agents and regression trials are judged.
`SPEC.oracle.yaml` is written from §7 and the worked figures of §4; every figure below is derived from
the kiln's existing model, calc files (`model/calcs/`), reference cases (`*.cases.yaml`), and
hand-checked derivations (`model/tests/test_calcs.py`).

**Conventions.** Lengths in mm, areas in mm² or m², volumes in L (liter) or m³, power in W or kW,
energy in J or MJ, temperatures in °C or K, electrical current in A, resistance in Ω, and wire surface
load in W/cm². Results carry 3 to 4 significant figures. Margin against an upper bound is
`(limit − value) / limit`; margin against a lower bound is `(value − limit) / limit`. A promoted card
clears its site and performance bounds; a rejected card fails its governing criteria.
Where a figure's only source in the calc reference cases is hand computation (B-0204), this is stated
plainly. `[verify]` marks values requiring physical confirmation by the owner or installer.

---

## 1. Customer intent, envelope and limits

> "I want a small front-loading electric test kiln for glaze tests and small pieces: a 200 × 200 × 200 mm
> chamber, 1200 °C class. I am a hobby potter at home with no electrical or thermal background.
> My bench alcove was described as about 800 mm wide, and the kiln should sit on its own stand.
> It must reach 1200 °C in about four to seven hours, with a useful volume of at least 8 L.
> It runs on mains power; surfaces people touch must stay below 60 °C, the controller must stay cool,
> and a dedicated circuit will be installed by an electrician. Keep parts under about 2500 USD."

| Item | Value | Basis |
|---|---|---|
| Chamber interior | 200 × 200 × 200 mm (gross volume 8.0 L) | intake, REQ-001 |
| Usable chamber | ~160 × 160 × 200 mm (20 mm keep-clear zone from element grooves) | design, REQ-001 |
| Max firing temperature | 1200 °C (cone 6 stoneware / porcelain glaze firing) | intake |
| Heat-up time target | 4 to 7 hours to 1200 °C (cold to peak) | intake, parameter `heat-up-time: 7 hour` |
| Touch temperature limit | ≤ 60 °C on any accessible surface at 1200 °C steady state | intake, REQ-003 |
| Alcove width (initial intake) | ~800 mm (insufficient for 110° door swing; rejected C-001) | intake, DEC-011 |
| Alcove width (site revision) | 1750 mm (leaves 240.3 mm clearance beside hinge at 110° swing) | C-003, REQ-023, REQ-027 |
| Kiln footprint (closed) | ≤ 1000 mm wide (body 590.4 mm + guards + standoffs + controls = 995.4 mm) | REQ-002, DEC-011 |
| Total mass limit | ≤ 120 kg assembled (lifted in stages onto stand; standoffs separate) | intake, REQ-004, DEC-008 |
| Parts cost limit | ≤ 2500 USD (revised from 1500 USD after safety hardware additions) | intake, REQ-005, DEC-012 |
| Electrical supply | 230 V, single-phase, 50 Hz, dedicated 16 A circuit | DEC-006, DEC-025 |
| Rated element power | 2500 W (draws 10.87 A on 230 V, leaving 1.47× circuit headroom) | DEC-004, REQ-006 |
| Power margin requirement | ≥ 1.20 (element power / required heat-up + loss power) | REQ-016 |
| Ceremony | `standard` (mains electrical domain + 1200 °C thermal hazard) | Track A §3.4, DEC-025 |

---

## 2. Requirements (from `model/requirements.yaml`)

The kiln model defines 29 atomic, testable requirements covering performance, safety, geometry,
manufacturing, interfaces, usability, and electrical domain verification:

1. **REQ-001: Firing volume.** Chamber gross interior volume ≥ 8.0 L. Verification: `param_bound` (`param://chamber-volume >= 8 liter`).
2. **REQ-002: Footprint.** Complete kiln including door and controller box width ≤ 1000 mm. Verification: `geometry_prop` (`asm://kiln#props.bbox.x <= 1000 mm`). Measured: 995.4 mm.
3. **REQ-003: Touchable surfaces stay cool (safety).** Every surface touchable during operation stays < 60 °C at steady state with chamber at 1200 °C. `safety: true`, tag `hazard:high-temperature`. Verification: `calc` (`calc://thermal.max_touch_temperature < 60 degC`). Measured: 44.06 °C. Requires physical contact thermometer sign-off.
4. **REQ-004: Mass.** Complete kiln assembly mass < 120 kg. Verification: `geometry_prop` (`asm://kiln#props.mass < 120 kg`). Measured: 110.52 kg.
5. **REQ-005: Cost target.** Bill of materials totals < 2500 USD at quantity 1. Verification: `bom_rollup` (`bom://rollups#total_cost < 2500 USD`). Measured: 2196.60 USD.
6. **REQ-006: Element power within the circuit.** Heating element draws ≤ 3000 W from 230 V supply. Tag: `electrical`. Verification: `param_bound` (`param://element-power <= 3000 W`). Selected: 2500 W.
7. **REQ-007: Controller away from the hot zone (safety).** Controller enclosure hangs on 40 mm standoffs outside touch guard with lid fitted, and inside air stays < 50 °C after 1 hr at 1200 °C. `safety: true`, tags `hazard:high-temperature`, `hazard:mains`. Verification: manual inspection and thermal probe.
8. **REQ-008: Dedicated circuit disclosed (safety).** Installation manual and rating label specify dedicated 16 A circuit installed by licensed electrician. `safety: true`, tags `electrical`, `hazard:mains`. Verification: manual document and label inspection.
9. **REQ-009: Door latch and door switch (safety).** Door has positive latch holding against 50 N outward pull, and door switch drops contactor cutting element power whenever door opens. `safety: true`, tags `electrical`, `hazard:mains`, `hazard:high-temperature`. Verification: manual 50 N pull test and electrical dropout test.
10. **REQ-010: Parts do not collide.** No two parts in the assembly overlap in space. Verification: `interference` (`asm://kiln`). 47 pairs checked, 0 interferences.
11. **REQ-011: Guard bolts to the stand.** Guard mounting holes line up with stand holes within 0.5 mm. Verification: `interface` (`iface://shell-frame-mount`).
12. **REQ-012: Hinge post holes agree.** Hinge post bolt holes line up with guard left-wall holes within 0.5 mm. Verification: `interface` (`iface://guard-hinge-post`).
13. **REQ-013: Two side liners.** Assembly uses exactly 2 side liners. Verification: `count` (`part://liner-side == 2`).
14. **REQ-014: Door swing.** Door opens to ≥ 100° for front loading. Verification: `param_bound` (`param://door-swing >= 100 degree`). Selected: 110°.
15. **REQ-015: Element wire fits the spool.** Element requires < 40 m of 1.6 mm Kanthal A1 wire. Verification: `calc` (`calc://element.wire_length < 40 m`). Measured: 29.34 m.
16. **REQ-016: Power margin over heat loss.** Element power exceeds steady loss plus heat-up power by ratio ≥ 1.20 (20 % margin). Verification: `calc` (`calc://element.power_margin >= 1.2`). Measured: 1.258.
17. **REQ-017: Lead time.** No part has a lead time above 30 d. Verification: `bom_rollup` (`bom://rollups#max_lead_time <= 30 d`). Measured: 15 d.
18. **REQ-018: Independent over-temperature cut-out (safety).** Independent limit controller on separate thermocouple opens contactor if chamber exceeds 1250 °C; latches off until manual reset. `safety: true`, tags `electrical`, `hazard:high-temperature`. Verification: manual electrical trip test.
19. **REQ-019: Earth bonding (safety).** Inner shell, guard, door guard, stand, and controller box bonded to protective earth with resistance < 0.1 Ω to earth terminal. `safety: true`, tags `electrical`, `hazard:mains`. Verification: manual low-resistance ohmmeter test by electrician.
20. **REQ-020: Door plug clears the opening.** During swing, latch-side rear corner of plug clears opening by ≥ 3 mm. Verification: `calc` (`calc://swing.plug_clearance >= 3 mm`). Measured: 6.32 mm.
21. **REQ-021: Element surface load.** Element wire surface load ≤ 2.0 W/cm² at 1200 °C. Verification: `calc` (`calc://element.surface_load <= 2.0 W/cm**2`). Measured: 1.70 W/cm².
22. **REQ-022: Coil pitch.** Coil pitch ≥ 200 % of wire diameter (pitch factor ≥ 2.0). Verification: `calc` (`calc://element.pitch_factor >= 2`). Measured: 2.09.
23. **REQ-023: Fits the alcove with the door open.** Closed width plus 240.3 mm open-door protrusion stays ≤ 1509.7 mm (inside 1750 mm alcove). Verification: `geometry_prop` (`asm://kiln#props.bbox.x <= 1509.7 mm`). Measured: 995.4 mm.
24. **REQ-024: Runs on the site circuit.** Element power ≤ 3066.7 W so 230 V / 16 A circuit keeps 1.2 headroom. Tag: `electrical`. Verification: `param_bound` (`param://element-power <= 3066.7 W`). Selected: 2500 W.
25. **REQ-025: Rounded exposed corners.** Exposed corners have radius ≥ 1 mm. Verification: `rule` (`rule://form-v0/form-corner-radius`).
26. **REQ-026: Controls where they were sketched.** Controls sit side-right as on C-003. Verification: `rule` (`rule://form-v0/form-controls-placement`).
27. **REQ-027: Open door keeps to room beside hinge.** Open door takes ≤ 240.3 mm beside hinge. Verification: `param_bound` (`param://door-swing-clearance <= 240.3 mm`). Measured: 240.235 mm.
28. **REQ-028: Element fits the supply.** Element power circuit load margin > 0 A below circuit rating. Tag: `electrical`. Verification: `circuit` (`circuit://power#props.supply_margin > 0 A`). Measured: 5.13 A margin (16.0 A rating − 10.87 A load).
29. **REQ-029: Conductor ampacity margin.** Smallest conductor ampacity margin > 0 A above element current. Tag: `electrical`. Verification: `circuit` (`circuit://power#props.conductor_margin > 0 A`). Measured: 6.5 A margin on supply mains connection (4.13 A minimum overall).

---

## 3. Concept cards

The kiln's napkin stage explored four directions (`concepts/C-001..C-004`):

```
       C-001 (as built, v0.1)             C-002 (compact)                C-003 (promoted winner)
  ┌───────────────────────────────┐     ┌─────────────────┐         ┌───────────────────────────────┐
  │ Chamber: 200 mm cube (8.0 L)  │     │ Chamber: 150 mm │         │ Chamber: 200 mm cube (8.0 L)  │
  │ Wall: 64 brick + 125 fiber    │     │ Wall: 64 b + 50f│         │ Wall: 64 brick + 125 fiber    │
  │ Outer guard: 25 mm gap        │     │ No outer guard  │         │ Outer guard: 25 mm gap        │
  │ Door swing footprint: 1236 mm │     │ Footprint: 773mm│         │ Door swing footprint: 1236 mm │
  │ Site alcove: 800 mm           │     │ Site: 800 mm    │         │ Site alcove: 1750 mm (revised)│
  │ REJECTED: fails envelope      │     │ REJECTED:       │         │ PROMOTED: passes all criteria │
  └───────────────────────────────┘     │ touch temp 91 °C│         └───────────────────────────────┘
                                        │ volume 3.4 L    │
                                        └─────────────────┘
```

### 3.1 C-001: The kiln as built in v0.1 (rejected by envelope)
- **Chamber:** 200 × 200 × 200 mm (8.0 L gross volume).
- **Insulation:** 64 mm K-23 insulating firebrick ($k = 0.25\text{ W/(m}\cdot\text{K)}$), 125 mm ceramic fiber board ($k = 0.15\text{ W/(m}\cdot\text{K)}$), 1.2 mm mild steel inner shell, 25 mm ventilated air gap to outer touch guard.
- **Layout:** Front door hinged on left (110° swing), controller box side-right on 40 mm standoffs, welded four-leg tube stand.
- **Dimensions:** Width 995 mm closed; width with open door 1236 mm.
- **Site:** 800 mm bench alcove.
- **Outcome:** **REJECTED** by envelope check (`envelope` category). The open door requires 1236 mm, exceeding the 800 mm alcove by 436 mm.

### 3.2 C-002: Compact: fits the 800 mm alcove (rejected)
- **Chamber:** 150 × 150 × 150 mm (3.375 L volume; target 8.0 L abandoned).
- **Insulation:** 64 mm brick, fiber thickness reduced from 125 mm to 50 mm, no outer ventilated guard shell.
- **Layout:** Controller box moved underneath the body inside the stand to save width.
- **Dimensions:** Width 392 mm closed; width with open door 773 mm (fits 800 mm alcove).
- **Outcome:** **REJECTED**. Gives up customer volume requirement (3.38 L vs 8.0 L minimum). Thin insulation and absent guard cause outer skin temperature to reach 91 °C, severely violating the 60 °C touch limit (REQ-003).

### 3.3 C-003: As built, softer look, wider alcove assumed (promoted winner)
- **Chamber:** 200 × 200 × 200 mm (8.0 L gross volume).
- **Insulation:** 64 mm K-23 brick, 125 mm fiber board, 1.2 mm steel shell, 25 mm guard gap to ventilated touch guard.
- **Layout:** Side-right controls, front-loading left-hinged door (110° swing), four-leg stand.
- **Style:** Appliance preset, 1 mm corner radii, visible fasteners.
- **Site:** Revised 1750 mm alcove width (confirmed with owner, DEC-011).
- **Outcome:** **PROMOTED**. Retains full 8.0 L firing chamber, touchable surfaces stay at 44.06 °C (< 60 °C limit), door clears opening by 6.32 mm, element current draws 10.87 A on 16 A circuit, clears all envelope and performance limits.

### 3.4 C-004: As built, v0.1 industrial styling kept (rejected)
- Styling variant identical to C-003 in envelope, layout, and thermal performance, but retaining the harsh industrial styling preset.
- **Outcome:** **REJECTED** for owner aesthetic preference (owner selected appliance preset of C-003).

### 3.5 Napkin screening comparison table

| Quantity | C-001 (as built) | C-002 (compact) | C-003 (promoted) | C-004 (industrial) |
|---|---|---|---|---|
| Status | rejected (envelope) | rejected | **promoted** | rejected (styling) |
| Chamber volume (L) | 8.0 (261 L gross box) | 3.38 (67.8 L box) | **8.0 (261 L gross box)** | 8.0 (261 L gross box) |
| Width closed (mm) | 995 | 392 | **995** | 995 |
| Footprint with door swing (mm) | 1236 | 773 | **1236** | 1236 |
| Site alcove width (mm) | 800 (fails!) | 800 (passes) | **1750 (passes)** | 1750 (passes) |
| Insulation mass (kg) | 54.1 | 17.1 | **54.1** | 54.1 |
| Steady heat loss (W) | 824 | 715 | **824** | 824 |
| Skin / touch temp (°C) | 61 | 91 (fails 60 °C!) | **61 (guard: 44 °C)** | 61 (guard: 44 °C) |
| Stored heat (MJ) | 26.4 | 9.3 | **26.4** | 26.4 |
| Heat-up time estimate (h) | 4.4 | 1.4 | **4.4** | 4.4 |
| Element current (A) | 10.9 | 10.9 | **10.9** | 10.9 |
| Cost band (USD) | 650 – 2267 | 344 – 697 | **650 – 2267** | 650 – 2267 |

---

## 4. Worked figures (formulas, derivations and sources)

Every key figure computed by the kiln's model is derived below. References cite `model/calcs/`
modules (`thermal.py`, `element.py`, `swing.py`), their reference cases (`*.cases.yaml`),
and hand-calculation tests (`model/tests/test_calcs.py`). Where a figure's reference case source
is "hand computation" (B-0204), it is explicitly stated.

### 4.1 Thermal model: heat loss, node temperatures, and stored heat

Thick-walled furnace geometry requires mean-area spherical/box conduction shape factors
(Incropera & DeWitt, *Fundamentals of Heat and Mass Transfer*, ch. 3). For a rectangular box with inner
dimensions $w, d, h$, the surface area of a concentric layer is $A = 2(wd + wh + dh)$.

#### Layer box areas and thermal resistances
- Chamber interior: $200 \times 200 \times 200\text{ mm}$ cube $\implies A_{in} = 6 \times 0.200^2 = 0.2400\text{ m}^2$.
- Brick outer ($t_b = 64\text{ mm}$, $k_b = 0.25\text{ W/(m}\cdot\text{K)}$): outer side $0.200 + 2(0.064) = 0.328\text{ m} \implies A_b = 6 \times 0.328^2 = 0.645504\text{ m}^2$.
- Lining clearance: $lc = 3\text{ mm}$.
- Fiber outer ($t_f = 125\text{ mm}$, $k_f = 0.15\text{ W/(m}\cdot\text{K)}$): outer side $0.328 + 2(0.003 + 0.125) = 0.584\text{ m} \implies A_f = 6 \times 0.584^2 = 2.046336\text{ m}^2$.
- Fiber clearance $fc = 2\text{ mm}$, shell thickness $st = 1.2\text{ mm}$. Shell outer side $0.584 + 2(0.002 + 0.0012) = 0.5904\text{ m} \implies A_s = 6 \times 0.5904^2 = 2.09137\text{ m}^2$.
- Ventilated guard gap: $gap = 25\text{ mm}$. Guard outer side $0.5904 + 2(0.025) = 0.6404\text{ m} \implies A_g = 6 \times 0.6404^2 = 2.46067\text{ m}^2$.
- Resistances (geometric mean area):
  $$R_b = \frac{t_b}{k_b \sqrt{A_{in} A_b}} = \frac{0.064}{0.25 \sqrt{0.2400 \times 0.645504}} = 0.6504\text{ K/W}$$
  $$R_f = \frac{t_f}{k_f \sqrt{A_b A_f}} = \frac{0.125}{0.15 \sqrt{0.645504 \times 2.046336}} = 0.7251\text{ K/W}$$
  Total body conduction resistance: $R_{body} = R_b + R_f = 1.3755\text{ K/W}$.

#### Shell and guard thermal balance
The ventilated inner shell loses heat by natural convection ($h_c = 5\text{ W/(m}^2\cdot\text{K)}$) to gap air ($T_{gap} = 50\ ^\circ\text{C} = 323.15\text{ K}$) and radiation ($\varepsilon_s = 0.9, \varepsilon_g = 0.9$) to the guard shell. The guard loses heat to room ambient ($T_{amb} = 25\ ^\circ\text{C} = 298.15\text{ K}$) by convection and radiation:
$$(T_{hot} - T_s) / R_{body} = A_s h_c (T_s - T_{gap}) + \frac{\sigma A_s (T_s^4 - T_g^4)}{\frac{1}{\varepsilon_s} + \frac{A_s}{A_g}\left(\frac{1}{\varepsilon_g} - 1\right)}$$
$$Q_{rad,received} = A_g \left[ h_c (T_g - T_{amb}) + \sigma \varepsilon_g (T_g^4 - T_{amb}^4) \right]$$
Solving the simultaneous non-linear balance by iteration yields:
- **Inner shell temperature:** $T_s = 78.75\ ^\circ\text{C}$ (351.90 K). Source: hand computation in `test_body_balance_by_hand`; case `shell_temperature` in `thermal.cases.yaml` expects 78.75 °C (±0.1 °C).
- **Body guard temperature:** $T_g = 44.04\ ^\circ\text{C}$ (317.19 K). Source: hand computation in `test_body_balance_by_hand`; case `guard_temperature` in `thermal.cases.yaml` expects 44.04 °C (±0.1 °C).
- **Brick/fiber interface temperature:**
  $$T_i = T_{hot} - q_{body} \times R_b = 1473.15\text{ K} - 815.2\text{ W} \times 0.6504\text{ K/W} = 942.95\text{ K} = 669.8\ ^\circ\text{C}$$
  Source: hand computation in `test_body_balance_by_hand`; case `interface_temperature` expects 669.8 °C (±0.5 °C). This confirms the fiber board class (Kaowool 1260 class board, rated to 1260 °C, operates safely at 670 °C).
- **Body steady loss:** $q_{body} = (1473.15 - 351.90) / 1.3755 = 815.2\text{ W}$.

#### Door plug thermal balance
- Plug dimensions: $324 \times 324\text{ mm}$ face ($A_{plug} = 0.104976\text{ m}^2$), opening $200 \times 200\text{ mm}$ ($A_{d\_in} = 0.0400\text{ m}^2$).
- Brick plug resistance ($t_b = 64\text{ mm}$): $R_{db} = 0.064 / (0.25 \sqrt{0.04 \times 0.104976}) = 3.951\text{ K/W}$.
- Fiber plug resistance ($t_f = 153\text{ mm}$): $R_{df} = 0.153 / (0.15 \times 0.104976}) = 9.717\text{ K/W}$.
- Total door resistance: $R_d = R_{db} + R_{df} = 13.667\text{ K/W}$.
- Door tray face area (spread factor 1.5): $A_{face} = 1.5 \times 0.104976 = 0.157464\text{ m}^2$.
- Solved door temperatures:
  - **Door skin temperature:** $T_d = 69.7\ ^\circ\text{C}$ (342.85 K). Source: hand computation in `test_door_by_hand`; case `door_skin_temperature` expects 69.7 °C (±0.2 °C).
  - **Door guard temperature:** $T_{dg} = 41.9\ ^\circ\text{C}$ (315.05 K). Source: hand computation in `test_door_by_hand`; case `door_guard_temperature` expects 41.9 °C (±0.2 °C).
  - **Door steady loss:** $q_{door} = (1473.15 - 342.85) / 13.667 = 82.7\text{ W}$.
- **Total steady-state heat loss:**
  $$q = q_{body} + q_{door} = 815.2\text{ W} + 82.7\text{ W} = 897.9\text{ W}$$
  Source: hand computation in `test_body_balance_by_hand`; case `heat_loss` in `thermal.cases.yaml` expects 897.9 W (±1.0 %).
- **Maximum touch temperature:**
  $$\max(T_g, T_{dg}) = \max(44.04\ ^\circ\text{C}, 41.9\ ^\circ\text{C}) = 44.04\ ^\circ\text{C}$$
  Source: hand computation in `test_door_by_hand`; case `max_touch_temperature` expects 44.04 °C. On the detailed CAD assembly with corner flanges, REQ-003 measures 44.06 °C (< 60 °C limit).

#### Stored heat and required power
Material volumes:
- Brick volume: $V_b = 0.328 \times 0.264 \times 0.328 - 0.200^3 + 0.324^2 \times 0.064 = 0.02040 + 0.00672 = 0.02712\text{ m}^3$.
- Fiber volume: $V_f = 0.584 \times 0.583 \times 0.584 - 0.334^2 \times (0.583 - 0.125) + 0.324^2 \times 0.153 = 0.14775 + 0.01606 = 0.1638\text{ m}^3$.
Volumetric heat capacities:
- Brick ($\rho = 480\text{ kg/m}^3, c_p = 1000\text{ J/(kg}\cdot\text{K)}$): $\rho c_b = 4.80 \times 10^5\text{ J/(m}^3\cdot\text{K)}$.
- Fiber ($\rho = 260\text{ kg/m}^3, c_p = 1050\text{ J/(kg}\cdot\text{K)}$): $\rho c_f = 2.73 \times 10^5\text{ J/(m}^3\cdot\text{K)}$.
Mean temperature rises above ambient ($T_{amb} = 25\ ^\circ\text{C}$):
- Brick mean rise: $\frac{1200 + 669.8}{2} - 25 = 909.9\text{ K}$.
- Fiber mean rise: $\frac{669.8 + 78.75}{2} - 25 = 349.3\text{ K}$.
- **Stored heat in insulation:**
  $$E = \rho c_b V_b \Delta T_b + \rho c_f V_f \Delta T_f = 4.80\times 10^5(0.02712)(909.9) + 2.73\times 10^5(0.1638)(349.3) = 11.84\text{ MJ} + 15.62\text{ MJ} = 27.46\text{ MJ}$$
  Source: hand computation in `test_stored_heat_and_power_by_hand`; case `stored_heat` in `thermal.cases.yaml` expects $27.46 \times 10^6\text{ J}$ (±1.0 %).
- **Required power (heat-up time $t = 7\text{ hours} = 25200\text{ s}$):**
  $$P_{req} = q + \frac{E}{t} = 897.9\text{ W} + \frac{27.46 \times 10^6\text{ J}}{25200\text{ s}} = 897.9 + 1089.7 = 1987.6\text{ W}$$
  Source: hand computation in `test_stored_heat_and_power_by_hand`; case `required_power` expects 1987.6 W (±1.0 %).
- **Power margin:**
  $$\frac{P_{rated}}{P_{req}} = \frac{2500\text{ W}}{1987.6\text{ W}} = 1.2577 \approx 1.26$$
  Source: hand computation; case `power_margin` in `element.cases.yaml` expects 1.26 (±0.02). REQ-016 bounds this at $\ge 1.20$.

---

### 4.2 Heating element sizing and electrical characteristics

Calculated from rated power $P = 2500\text{ W}$ on $V = 230\text{ V}$ using Kanthal A1 wire ($\rho = 1.45\ \Omega\cdot\text{mm}^2/\text{m}$, diameter $d = 1.6\text{ mm}$):

1. **Current:**
   $$I = \frac{P}{V} = \frac{2500\text{ W}}{230\text{ V}} = 10.8696\text{ A} \approx 10.87\text{ A}$$
   Source: hand computation; case `current` in `element.cases.yaml` expects 10.869565 A.
2. **Circuit headroom on 16 A dedicated breaker:**
   $$\text{Headroom} = \frac{16\text{ A}}{10.87\text{ A}} = 1.472$$
   Source: hand computation; case `circuit_headroom` expects 1.472.
3. **Cold resistance:**
   $$R = \frac{V^2}{P} = \frac{230^2}{2500} = 21.16\ \Omega$$
   Source: hand computation; case `resistance` in `element.cases.yaml` expects 21.16 Ω.
4. **Wire cross-section area:**
   $$A_{wire} = \frac{\pi}{4} d^2 = \frac{\pi}{4} (1.6\text{ mm})^2 = 2.01062\text{ mm}^2$$
   Source: hand computation; case `wire_area` expects 2.0106193 mm².
5. **Wire length:**
   $$L = \frac{R A_{wire}}{\rho} = \frac{21.16\ \Omega \times 2.01062\text{ mm}^2}{1.45\ \Omega\cdot\text{mm}^2/\text{m}} = 29.3412\text{ m}$$
   Source: hand computation; case `wire_length` in `element.cases.yaml` expects 29.341175 m. REQ-015 bounds wire length $< 40\text{ m}$.
6. **Coil turns:** Coil outer diameter $D = 12\text{ mm}$. Mean turn diameter $D - d = 12 - 1.6 = 10.4\text{ mm}$. Mean turn length $\pi(10.4) = 32.6726\text{ mm}$.
   $$N_{turns} = \frac{L}{\pi(D - d)} = \frac{29341.2\text{ mm}}{32.6726\text{ mm}} = 898.037\text{ turns}$$
   Source: hand computation; case `coil_turns` expects 898.037.
7. **Available groove length:** 5 grooves per wall across 2 side walls ($200\text{ mm}$) and rear wall ($200\text{ mm}$):
   $$L_{groove} = 5 \times (200 + 200 + 200) = 3000\text{ mm}$$
   Source: hand computation; case `available_groove_length` expects 3000 mm.
8. **Coil pitch:**
   $$\text{pitch} = \frac{L_{groove}}{N_{turns}} = \frac{3000\text{ mm}}{898.037} = 3.34062\text{ mm}$$
   Source: hand computation; case `coil_pitch` expects 3.34062 mm.
9. **Pitch factor:**
   $$\text{pitch factor} = \frac{\text{pitch}}{d} = \frac{3.34062\text{ mm}}{1.6\text{ mm}} = 2.08789 \approx 2.09$$
   Source: hand computation; case `pitch_factor` in `element.cases.yaml` expects 2.09 (±0.01). REQ-022 bounds pitch factor $\ge 2.0$.
10. **Wire surface load:**
    $$\text{Surface load} = \frac{P}{\pi d L} = \frac{2500\text{ W}}{\pi \times 0.16\text{ cm} \times 2934.12\text{ cm}} = 1.69509\text{ W/cm}^2 \approx 1.70\text{ W/cm}^2$$
    Source: hand computation; case `surface_load` in `element.cases.yaml` expects 1.69509 W/cm² (±1.0e-5). REQ-021 bounds surface load $\le 2.0\text{ W/cm}^2$.

---

### 4.3 Door swing clearance

The tapered plug swings about a hinge pin located outside the guard lip plane:
- Hinge pin coordinates: $x_p = -358.2\text{ mm}, y_p = 62.0\text{ mm}$.
- Opening latch-side edge: $a_{open} = 167.0\text{ mm}, y_{open} = 26.0\text{ mm}$.
- Pin radius to opening edge:
  $$R_0^2 = (a_{open} - x_p)^2 + (y_{open} - y_p)^2 = (167 - (-358.2))^2 + (26 - 62)^2 = 525.2^2 + (-36)^2 = 277131.04\text{ mm}^2$$
- Plug depth $217\text{ mm}$, half-width $162\text{ mm}$, taper $6^\circ$.
- Latch-side rear corner in closed position:
  $$a_{rear} = 162 - 217 \tan 6^\circ = 162 - 22.81 = 139.19\text{ mm}, \quad y_{rear} = 217 - 2 = 215.0\text{ mm}$$
- **Swing clearance:**
  $$\text{Clearance} = \sqrt{R_0^2 - (y_{rear} - y_p)^2} + x_p - a_{rear} = \sqrt{277131.04 - (215 - 62)^2} - 358.2 - 139.19$$
  $$\text{Clearance} = \sqrt{277131.04 - 23409} - 497.39 = 503.71 - 497.39 = 6.32\text{ mm}$$
  Source: hand computation in `test_swing_by_hand`; case `plug_clearance` in `swing.cases.yaml` expects 6.32 mm (±0.01 mm). REQ-020 bounds clearance $\ge 3.0\text{ mm}$.

---

### 4.4 Mass and cost rollups

- **Kiln assembly mass (`asm://kiln`):** 110.52 kg (bounded $< 120\text{ kg}$ by REQ-004).
- **Total assembled mass (BOM rollup `total_mass`):** 118.89 kg (includes controller box, stand, hardware, shelf set).
- **Total unit cost (BOM rollup `total_cost`):** 2196.60 USD (bounded $< 2500\text{ USD}$ by REQ-005).
- **BOM part counts:** 145 total components across 46 distinct parts.
- *Source note:* McMaster-Carr catalogue pricing for hardware and COTS items; supplier quotes for refractory bricks (Morgan K-23) and Kaowool ceramic fiber board; shop fabrication estimates for laser-cut and formed sheet metal.

---

## 5. Electrical supply and installation

- **Supply specification:** Single-phase 230 V AC, 50 Hz, TT earthing system, region EU (DEC-006, DEC-025).
- **Dedicated circuit:** 16 A branch circuit with dedicated upstream circuit breaker and 30 mA residual-current device (RCD).
- **Circuit margins:**
  - Element rated load: 10.87 A.
  - Supply breaker margin: $16.0\text{ A} - 10.87\text{ A} = 5.13\text{ A}$ margin ($> 0\text{ A}$, REQ-028).
  - Smallest conductor margin: 2.5 mm² PVC internal wiring rated 17.4 A gives $17.4 - 10.87 = 6.53\text{ A}$ margin ($> 0\text{ A}$, REQ-029). Overall worst-case conductor margin is 4.13 A.
- **Safety cutouts:** Dual-switching safety architecture. Main temperature regulation uses a solid-state relay (SSR); in series with the SSR is a definitive electromagnetic contactor actuated by:
  1. Door interlock switch (cuts power immediately when door opens, REQ-009).
  2. Independent limit controller on a separate thermocouple (trips if chamber exceeds 1250 °C, latches off, REQ-018).

---

## 6. Safety, ceremony and sign-offs

The mini electric test kiln combines a mains electrical domain (230 V / 16 A) with high thermal
energy (1200 °C operating temperature). Under Track A §3.4 and DEC-025, its ceremony derives to
`standard`.

The model designates exactly six requirements as safety requirements (`safety: true`):
1. **REQ-003:** Touchable surface temperature < 60 °C (`hazard:high-temperature`).
2. **REQ-007:** Controller enclosure internal temperature < 50 °C (`hazard:high-temperature`, `hazard:mains`).
3. **REQ-008:** Dedicated 16 A circuit disclosed on rating label and manual (`hazard:mains`).
4. **REQ-009:** Positive door latch and contactor door cut-off switch (`hazard:mains`, `hazard:high-temperature`).
5. **REQ-018:** Independent over-temperature limit controller at 1250 °C (`hazard:high-temperature`).
6. **REQ-019:** Protective earth bonding < 0.1 Ω to all metal housings (`hazard:mains`).

Each safety requirement carries a sign-off record under `model/signoffs/` documenting physical test
procedures and electrical inspection sign-offs.

---

## 7. Expected outcomes and benchmark summary

Every benchmark evaluation asserts the following outcomes without citing internal model IDs:

### Napkin stage concept cards
- Total concept cards: 4 (`count: 4`).
- Exactly one card promoted: C-003, using block shape kit, soft appliance styling, for the wider alcove.
- Promoted card shows zero failing screening rows (`promoted_has_no_failure: true`).
- Every rejected card matches its rejection reason:
  - C-001 rejected by `envelope` (open door swing requires 1236 mm in an 800 mm alcove).
  - C-002 rejected (compact 150 mm chamber gives up 8 L volume and reaches 91 °C skin temperature).
  - C-004 rejected (industrial styling variant turned down for owner aesthetic preference).

### Key figures and acceptable tolerances

| Label | What | Finder surface | Unit | Expected | Tol |
|---|---|---|---|---|---|
| `c1-width` | As-built card closed width | `screen_value: width` | mm | 995 | ±2 % |
| `c1-width-with-door` | As-built card door-swing width | `screen_value: footprint_with_door_swing` | mm | 1236 | ±2 % |
| `c1-heat-loss` | As-built card estimated heat loss | `screen_value: heat_loss` | W | 824 | ±5 % |
| `c1-stored-heat` | As-built card estimated stored heat | `screen_value: stored_heat` | MJ | 26.4 | ±5 % |
| `c1-insulation-mass` | As-built card insulation mass | `screen_value: insulation_mass` | kg | 54.1 | ±5 % |
| `c2-volume` | Compact card chamber volume | `screen_value: volume` | L | 67.8 | ±5 % |
| `c2-skin-temp` | Compact card skin temperature | `screen_value: skin_temperature` | °C | 91 | ±5 % |
| `c2-footprint` | Compact card door-swing width | `screen_value: footprint_with_door_swing` | mm | 773 | ±2 % |
| `c3-current` | Promoted card element current | `screen_value: current` | A | 10.9 | ±5 % |
| `c3-heat-loss` | Promoted card steady loss | `screen_value: heat_loss` | W | 824 | ±5 % |
| `c3-cost-low` | Promoted card low cost band | `screen_value: cost_low` | USD | 650 | ±5 % |
| `c3-cost-high` | Promoted card high cost band | `screen_value: cost_high` | USD | 2267 | ±5 % |
| `c3-heat-up-time` | Promoted card heat-up time | `screen_value: heat_up_time` | h | 4.4 | ±5 % |
| `product-mass` | Finished kiln total mass | `rollup: total_mass` | kg | 118.89 | ±2 % |
| `product-cost` | Finished kiln unit cost | `rollup: total_cost` | USD | 2196.60 | ±2 % |
| `product-part-count` | Total BOM parts | `rollup: part_count` | — | 145 | exact |
| `product-distinct-parts`| Distinct BOM parts | `rollup: distinct_parts` | — | 46 | exact |
| `req-chamber-volume` | Gross chamber volume | `requirement: {bound: 8 liter}` | L | 8.0 | ±1 % |
| `req-touch-temp` | Max touchable temperature | `requirement: {bound: 60 degC}` | °C | 44.06 | ±5 % |
| `req-kiln-mass` | Kiln assembly mass | `requirement: {bound: 120 kg}` | kg | 110.52 | ±2 % |
| `req-cost` | Cost ceiling | `requirement: {bound: 2500 USD}` | USD | 2196.60 | ±2 % |
| `req-element-power` | Element power limit | `requirement: {bound: 3000 W}` | W | 2500.0 | ±1 % |
| `req-power-margin` | Heat-up power margin | `requirement: {bound: '1.2'}` | — | 1.258 | ±5 % |
| `req-wire-length` | Element wire length | `requirement: {bound: 40 m}` | m | 29.34 | ±5 % |
| `req-plug-clearance` | Door plug swing clearance | `requirement: {bound: 3 mm}` | mm | 6.32 | ±5 % |
| `req-pitch-factor` | Element coil pitch factor | `requirement: {bound: '2', op: '>='}` | — | 2.09 | ±5 % |
| `req-door-swing` | Door opening angle | `requirement: {bound: 100 degree}` | ° | 110.0 | ±1 % |
| `req-open-door-clearance`| Protrusion beside hinge | `requirement: {bound: 240.3 mm}` | mm | 240.235 | ±2 % |
| `req-alcove-width` | Kiln width limit for alcove | `requirement: {bound: 1509.7 mm}` | mm | 995.4 | ±2 % |
| `req-circuit-headroom` | Element power for 16 A circuit | `requirement: {bound: 3066.7 W}` | W | 2500.0 | ±1 % |

### Product facts

- `ceremony`: `standard`
- `supply`: `present`
- `supply_voltage`: `230 V`
- `supply_frequency`: `50 Hz`
- `assemblies`: `3` (sub-assemblies: controls, door, lining)
- `safety_requirements`: `6`
- `safety_signoffs`: `6`
- `no_failing_requirements`: `0` failing rows
