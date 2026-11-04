# Test stand: benchmark specification (Tier 2)

The middle benchmark of Track A §2.3: a 2 kN motorized compression test stand on a 120 V / 60 Hz
supply (region US). Every figure below is worked from the stated geometry with its source (road to
v1.0 §4.1); `SPEC.oracle.yaml` is written from §7. Worked 2026-11-04. `[verify]` marks what a person
must still confirm. Re-derived independently by a second model from this spec alone on
2026-11-04: all 22 expected outcomes agree within 0.4 %; three intermediate centre-of-gravity and stress
figures differ by 1–3 % from rounding in the text, with no outcome changed.

**Margin convention.** For an upper bound (deflection, mass, cost, current):
margin = (limit − value) / limit. For a lower bound (a factor of safety): margin = (value − bound) / bound.
A pass is ≥ +30 %, a fail ≤ −30 % (road §4.1). Envelope dimensions (footprint, daylight, clear width)
are exact geometry, not models, and are checked as plain inequalities.

---

## 1. Customer intent, envelope and limits

> "I test springs and plastic snap-fits on my bench. I want a small motorized press that pushes up to
> about 200 kg, measures force and travel accurately, plugs into a normal US wall socket, stops dead
> when I hit the red button or open the shield, and that I can lift onto the bench on my own."

| Quantity | Value | Basis |
|---|---|---|
| Rated compressive load F | 2000 N (204 kgf) | owner's brief (Track A §2.3) |
| Test cycles over the life | N = 1.0 × 10⁶ (200 tests/day × 250 days/yr × 20 yr) | spec's choice |
| Frame deflection at the load axis, at F | ≤ 0.20 mm | owner's brief (measurement accuracy) |
| Daylight (lower platen to upper platen, rod retracted) | ≥ 250 mm | owner's brief |
| Clear width between frame members at the load axis | ≥ 200 mm (largest specimen 200 mm wide) | spec's choice, replaces Track A's 150 mm throat (§3.4) |
| Actuator stroke | 200 mm | spec's choice |
| Bench footprint | ≤ 400 mm wide × 350 mm deep | owner's brief |
| Mass | ≤ 25 kg (one-person lift) | `lift_classes.yaml` row `one-person`, max 25 kg, "HSE INDG143 … guideline weight for lifting close to the body" [verify] |
| Parts cost | ≤ 2400 USD, region US, as of 2026-11 [verify] | spec's choice, replaces Track A's 800 USD (§3.4) |
| Supply | 120 V, 60 Hz, single phase, NEMA 5-15 receptacle (15 A); input current ≤ 3 A | owner's brief; `circuits.yaml` US row "15 A receptacle (NEMA 5-15)" [verify] |
| `n2f.yaml` | `region: US`; ceremony derived `standard` (mains + moving machinery) | W6, W7 |

Factors of safety, quoted from `calckit/data/load_cases.yaml` (all `verify: true`):

| Check | Load kind | Factor | Row source (abridged) |
|---|---|---|---|
| deflection | static | 1.0 | "AISC 360-16 / IBC Table 1604.3: deflection limit serviceability ratio" |
| yield | cyclic | 2.0 | "Shigley … Section 1-10: design safety factor under fluctuating/cyclic fatigue load" |
| buckling | cyclic | 3.0 | "AISC / Shigley: column buckling safety factor under dynamic/cyclic loading …" |
| fatigue | cyclic | 1.5 | "Shigley … Section 6-11: Goodman fatigue margin design factor" |
| tip_over | static | 1.5 | "ANSI/BIFMA X5.5-2021 Section 4.3: ratio of restoring moment to overturning moment …" |

The load is applied slowly (quasi-static), so deflection uses the static row; with the cyclic row
(1.25) C-002 still passes (§4.3).

## 2. Requirements (for `model/requirements.yaml`)

| # | Requirement | Bound | Verification | Safety / hazard |
|---|---|---|---|---|
| 1 | Actuator rated thrust | ≥ 2000 N (chosen part: 3000 N) | inspection (datasheet) | — |
| 2 | Load cell rated capacity | ≥ rated load 2000 N | inspection (datasheet) | — |
| 3 | Frame deflection at the load axis under F | ≤ 0.20 mm | computed | — |
| 4 | Daylight | ≥ 250 mm | computed (geometry) | — |
| 5 | Clear width between frame members | ≥ 200 mm | computed (geometry) | — |
| 6 | Footprint | ≤ 400 × 350 mm | computed (geometry) | — |
| 7 | Total mass | ≤ 25 kg | computed | — |
| 8 | Parts cost (high end of the band) | ≤ 2400 USD | computed (estimate) [verify] | — |
| 9 | Yield factor of every frame member under F | ≥ 2.0 | computed | `safety: true`, `hazard:structural-failure` |
| 10 | Fatigue factor of frame members and column-end bolts at 10⁶ cycles | ≥ 1.5 | computed | `safety: true`, `hazard:structural-failure` |
| 11 | Column buckling factor, rated load reversed (pull mode) | ≥ 3.0 | computed | — |
| 12 | Tip-over factor at a 10° tilt, door closed | ≥ 1.5 | computed | `safety: true`, `hazard:tip-over` |
| 13 | The manual tells the owner to bolt the stand to the bench (4 × M6 holes in the tray floor) | present | manual | `safety: true`, `hazard:tip-over` |
| 14 | Mains input current at full PSU output, 120 V | ≤ 3 A | computed | — |
| 15 | Inlet fuse: ≥ 1.25 × input current and ≤ the 18 AWG conductor's 7 A | T2.5 A | computed | `safety: true`, `hazard:mains` |
| 16 | Class I: all exposed metal bonded to the inlet's ground pin | ≤ 0.1 Ω (IEC 61010-1 §6.5.2 [verify]) | inspection + manual (bond test) | `safety: true`, `hazard:mains` |
| 17 | E-stop: red mushroom, positive-opening, cuts 24 V motor power directly (stop category 0, NFPA 79 §9.2.2 [verify]) | motor stops | inspection + manual test | `safety: true`, `hazard:moving-machinery` |
| 18 | Guard interlock: opening the door cuts 24 V motor power (positive-opening switch, ISO 14119 [verify]) | motor stops | inspection + manual test | `safety: true`, `hazard:pinch` |
| 19 | Fragment shield: 5 mm polycarbonate closes the test zone on four sides | present | inspection (impact rating [verify]) | `safety: true`, `hazard:stored-energy` |
| 20 | Upper and lower limit switches stop motion before the actuator's end stops | both ends | manual test | — |

## 3. Concept cards

Shared by all three cards (only the frame differs): console, platens, guard, bought-in parts and the
vertical stack of §3.2. Loads block for the `structural` screen (W4 fields):
`loads: {point_load: 2000 N, max_deflection: 0.20 mm, cycles: 1000000}`.

### 3.1 The three frames

| | C-001 C-frame | C-002 Twin-column portal (promoted) | C-003 Plate gantry |
|---|---|---|---|
| Idea | one column at the back, arms over and under the load axis | two columns, top crosshead and base beam: a closed rectangle | two solid side plates bridged top and bottom |
| Material | aluminum-6063-t5 | aluminum-6063-t5 (columns, beams) | mild steel |
| Column / side member | RHS 60 × 60 × 4, cut length 880 mm | 2 × RHS 40 × 40 × 3, member length L_c = 760 mm | 2 × plate 25 (x) × 250 (y) × 880 (z) mm |
| Height used in the calc | H = 820 mm (arm centreline to arm centreline) | L_c = 760 mm (beam face to beam face) | 760 mm between bridges |
| Horizontal members | 2 arms RHS 60 × 60 × 4, cut length 190 mm, welded | 2 beams RHS 60 tall × 40 wide × 5 wall, length 340 mm | 2 bridges solid 60 tall × 40 wide, length 275 mm |
| Load-path span / lever | lever a = 180 mm (load axis to column centreline: 150 mm throat + 30 mm half column) | span L = 300 mm (column centrelines) | span L = 300 mm (plate centrelines) |
| Supports in the calc | column carries M = F·a over H; arms cantilevered | beams simply supported at the column centrelines | bridges simply supported at the plate centrelines |
| Frame process (cost band) | welding | extrusion-cut | machining |
| Clear width at the load axis | open front; column 150 mm behind the axis | 260 mm (300 − 40) | 275 mm |

Each beam or bridge carries the rated load F at mid-span: the actuator pushes the top member up, the
specimen pushes the bottom member down, and the columns or plates carry F/2 = 1000 N each in tension.

### 3.2 Vertical stack (C-002; heights z from the bench, mm)

| Item | z bottom–top | Dimension, basis |
|---|---|---|
| Rubber feet (4, Ø20, centred 10 mm in from each edge) | 0–10 | spec's choice |
| Console: 2 mm 5052 tray, 380 × 350 × 110 | 10–120 | spec's choice (PSU 90 mm tall [verify]) |
| Console lid, 2 mm 5052, 380 × 350 | 120–122 | spec's choice |
| Base beam | 122–182 | 60 mm section |
| Lower platen, steel 100 × 100 × 15 | 182–197 | spec's choice |
| **Daylight** | 197–447 | **250 mm** |
| Upper platen, steel 80 × 80 × 10 | 447–457 | spec's choice |
| Load cell, 2 kN S-beam | 457–522 | 65 mm [verify] |
| Rod-end adapter | 522–542 | 20 mm |
| Actuator, retracted, flange-mounted under the crosshead | 542–942 | 400 mm allowance for 200 mm stroke [verify] |
| Top crosshead | 942–1002 | 60 mm section; overall height 1002 mm |
| Columns | 182–942 | L_c = 760 mm |
| Guard (shroud + door), 400 tall | 182–582 | covers platens, load cell and rod |

Daylight check: 942 − 400 − 20 − 65 − 10 = 447; 447 − 197 = 250 mm ≥ 250 mm. Clear width 260 mm ≥ 200.
Footprint: console 380 × 350 mm (guard 350 × 160 and frame 340 × 40 sit inside it) ≤ 400 × 350.

### 3.3 Shared parts (all cards)

Lower and upper platens (mild steel); console tray and lid (aluminum-5052-h32, 2 mm); guard shroud
(polycarbonate 5 mm, line-bent U: back 350 + two sides 160 = 670 mm developed × 400 mm) and door
(polycarbonate 5 mm, 350 × 400 mm), hinged at the front of the shroud (shroud spans y = −80 to +80 mm);
bought-in parts with the mass allowances of §4.6 (spec's choices, each [verify] against the chosen
catalogue part). C-001 puts the lower platen on its base arm; C-003 on its bottom bridge.

### 3.4 What changed from Track A's draft, and why

1. **C-002 closes the load loop with a base beam.** Track A's δ = FL³/48EI + δ_axial leaves out the
   member under the specimen. A 12 mm steel base plate, 250 mm wide, spanning 300 mm instead would
   deflect FL³/(48EI) = 2000 × 0.3³ / (48 × 200 GPa × 36 000 mm⁴) = 0.156 mm on its own. The base beam
   (same section as the crosshead) replaces it, so the 12 mm plate is dropped; the console carries only weight.
2. **Aluminium 6063-T5 for C-002 and C-001** (Track A: "steel/aluminum"; C-001 steel). A steel C-002
   frame (same sections) weighs 10.10 kg and puts the stand at 23.1 kg, over the 17.5 kg pass line. C-001 in steel weighs 21.9 kg in all,
   within 30 % of the mass limit (an undecided outcome); in the same alloy as C-002 the comparison is the
   architecture alone. In steel C-001 would still fail stiffness (0.656 mm).
3. **Column height stated from the stack**: C-002 L_c = 760 mm; C-001 H = 820 mm (Track A: 400 mm).
   The actuator hangs under the crosshead from its flange, so no bore weakens the crosshead at mid-span.
4. **C-001 lever arm** taken to the column centreline (180 mm), and its arm under the load, its base arm
   and column stretch included: 1.90 mm, not Track A's ~0.2 mm.
5. **Sections made definite**: C-002 columns 40 × 40 × 3; crosshead read as RHS 60 tall × 40 wide × 5.
6. **Throat → clear width.** A portal has no throat; the requirement becomes clear width ≥ 200 mm.
7. **Budget 800 → 2400 USD.** With the US bands on file, the parts every card shares already span
   401–1500 USD (§4.7): 800 USD sits inside that band and could decide nothing.
8. **C-003 dimensioned**: plates 25 × 250 × 880, bridges solid 60 × 40 × 275.
9. **Guard = fixed U-shroud + hinged door.** The frame is only 40 mm deep; fragments leave sideways.
10. **Part count 11 → 19 part definitions (25 items)**: Track A's own list names 17; added base beam,
    upper platen, feet and shroud, and the console split into tray and lid; base plate dropped.

## 4. Worked calculation

### 4.1 Inputs

| Material (`materials.yaml` row) | ρ kg/m³ | E GPa | σ_y MPa | Other, source |
|---|---|---|---|---|
| aluminum-6063-t5 | 2700 | 68.9 | 145 | S_ut 186 MPa, S_f 68.9 MPa at 5 × 10⁸ cycles (ASM Handbook Vol 2 / MatWeb, 6063-T5) [verify] |
| aluminum-5052-h32 | 2680 | 70.3 | 193 | — |
| mild steel | 7850 | 200 | 250 | — |
| polycarbonate | 1200 | 2.3 | 65 | — |
| Bolt M8 ISO 898-1 class 8.8 | — | — | — | A_t 36.6 mm², S_ut 800 MPa, S_p 580 MPa (ISO 898-1); S_e 129 MPa (Shigley Table 8-17, rolled threads, listed for M16–M36) [verify] |

Formulas are those of `calckit/structural.py` and `calckit/joints.py` with the sources they cite.

### 4.2 Section properties (Roark 7th ed., Table 1, Cases 1 and 2)

RHS b × h × t: A = bh − (b−2t)(h−2t); I = [bh³ − (b−2t)(h−2t)³]/12; Z = I/(h/2).

| Section | A mm² | I mm⁴ | Z mm³ |
|---|---|---|---|
| RHS 40 w × 60 h × 5 (C-002 beams) | 2400 − 30·50 = 900 | (40·216 000 − 30·125 000)/12 = 407 500 | 13 583 |
| RHS 40 × 40 × 3 (C-002 columns) | 1600 − 34² = 444 | (40⁴ − 34⁴)/12 = (2 560 000 − 1 336 336)/12 = 101 972 | 5 099 |
| RHS 60 × 60 × 4 (C-001) | 3600 − 52² = 896 | (60⁴ − 52⁴)/12 = (12 960 000 − 7 311 616)/12 = 470 699 | 15 690 |
| Solid 40 w × 60 h (C-003 bridges) | 2400 | 40·60³/12 = 720 000 | 24 000 |
| Plate 25 × 250 (C-003 side plate, axial) | 6250 | — | — |

C-002 column radius of gyration r = √(101 972 / 444) = 15.15 mm.

### 4.3 C-002 twin-column portal

**Frame deflection at the load axis** (Roark Table 8.1 Case 1d, simply supported centre load, for
each beam; Hooke's law for the columns):

- Each beam: δ_b = F L³/(48 E I) = 2000 × 0.300³ / (48 × 68.9 × 10⁹ × 4.075 × 10⁻⁷)
  = 54 / 1 347 684 = 4.007 × 10⁻⁵ m = **0.0401 mm**.
- Columns (two in parallel, 1000 N each): δ_c = (F/2) L_c/(E A) = 1000 × 0.760 / (68.9 × 10⁹ × 4.44 × 10⁻⁴)
  = 760 / 30 591 600 = 2.484 × 10⁻⁵ m = **0.0248 mm**.
- Total δ = 2 × 0.04007 + 0.02484 = **0.105 mm** ≤ 0.20 mm; margin **+47.5 %**.

Not in the asserted figure, stated so the outcome is shown robust: shear deflection of each beam
F L/(4 G A_w), G = E/2(1+ν) = 25.9 GPa (ν = 0.33 [verify]), A_w = 2 × 5 × 60 = 600 mm² → 0.0097 mm per beam;
total with shear 0.124 mm (margin +37.9 %). With the cyclic deflection factor 1.25: 0.131 mm (+34.4 %).
Self weight: the upper assembly (actuator 4.0 + load cell 0.35 + upper platen 0.50 + limit switches 0.10
= 4.95 kg, 48.6 N, 2.4 % of F) hangs on the crosshead before a test starts and does not change during
it, so it is excluded from the measured deflection. Bolted-joint compliance is not modelled; simple
supports ignore the joints' partial fixity (conservative).

**Bending stress and yield factor** (Roark §8.1; Shigley §1-10): M = F L/4 = 2000 × 0.300/4 = 150 N·m;
σ_b = M/Z = 150 / 1.3583 × 10⁻⁵ = **11.0 MPa**; FS_y = 145/11.04 = **13.1** ≥ 2.0, margin +557 %.
The actuator's flange bolts pass the crosshead's bottom flange and the platen's bolts the base beam's
top flange: both the compression side.

**Column axial stress**: σ = 1000 / 444 mm² = **2.25 MPa**; FS_y = 145/2.252 = **64.4** ≥ 2.0, margin +3119 %.

**Fatigue at 10⁶ cycles, 0 → F → 0 (R = 0)** (`joints.fatigue_margin`, modified Goodman, Shigley Ch. 6):
- Beams: σ_a = σ_m = 11.04/2 = 5.521 MPa; S_f = 68.9 MPa (the 5 × 10⁸ value used at 10⁶, conservative);
  n_f = 1/(5.521/68.9 + 5.521/186) = 1/(0.08014 + 0.02969) = **9.11** ≥ 1.5, margin +507 %.
- Column-end bolts, 2 × M8 8.8 per column end, external load 0 → 500 N per bolt; preload
  F_i = 0.75 A_t S_p (Shigley Eq. 8-31 [verify]), σ_i = 0.75 × 580 = 435 MPa; joint constant taken C = 1
  (bolt sees all the external load, conservative): σ_a = 500/(2 × 36.6) = 6.831 MPa. Goodman for a
  preloaded bolt (Shigley §8-11 [verify equation number]):
  n_f = S_e (S_ut − σ_i) / [σ_a (S_ut + S_e)] = 129 × 365 / (6.831 × 929) = 47 085 / 6345.6 = **7.42** ≥ 1.5,
  margin +395 %. (A hand check; `fatigue_margin` has no preload term.)

**Buckling** (`structural.euler_buckling_load`; Roark Table 15.1, AISC Table C-A-7.1). The columns are in
tension under the rated load; they go into compression only if the stand pulls (a pull test, or
misuse), so the check uses the rated load reversed, 1000 N per column, and the sway
mode K = 2.1 (fixed-free design value, the base beam rigid on the console, the top free to sway).
λ = K L_c / r = 2.1 × 760 / 15.155 = 105.3 ≥ λ_c = √(2π² E/σ_y) = √(2π² × 68.9 × 10⁹ / 145 × 10⁶) = 96.8, so
Euler applies. P_cr = π² E I/(K L_c)² = 9.8696 × 68.9 × 10⁹ × 1.01972 × 10⁻⁷ / 1.596² = 69 342 / 2.5472 = 27 223 N;
FS = 27 223 / 1000 = **27.2** ≥ 3.0, margin +807 %.

**Tip-over at a 10° tilt** (IEC 61010-1:2010 §7.3, equipment must not overbalance when tilted 10°
[verify clause]); `structural.tip_over_safety_factor` with mass m, edge_load = m g tan 10° acting at the
CG height (overhang_x = z_cg), cg_x = distance from the CG to the tipping edge, so
FS = x/(z_cg tan 10°). Tipping edges: lines through the foot centres, y = ±165 mm, x = ±180 mm. CG from
the stack of §3.2 and the part masses of §4.6 (y + towards the front):

| Part | m kg | y mm | z mm | m·z | m·y |
|---|---|---|---|---|---|
| feet | 0.100 | 0 | 5 | 0.50 | 0 |
| console tray (floor at 11, sides at 65, area-weighted) | 1.574 | 0 | 40.5 | 63.79 | 0 |
| console lid | 0.713 | 0 | 121 | 86.26 | 0 |
| base beam | 0.826 | 0 | 152 | 125.58 | 0 |
| lower platen | 1.178 | 0 | 189.5 | 223.14 | 0 |
| columns (2) | 1.822 | 0 | 562 | 1024.06 | 0 |
| top crosshead | 0.826 | 0 | 972 | 803.07 | 0 |
| upper platen | 0.502 | 0 | 452 | 227.08 | 0 |
| load cell | 0.350 | 0 | 489.5 | 171.32 | 0 |
| actuator (CG at mid-length [verify]) | 4.000 | 0 | 742 | 2968.00 | 0 |
| guard shroud (back at −80, sides centred) | 1.608 | −41.8 | 382 | 614.26 | −67.20 |
| guard door (closed) | 0.840 | 80 | 382 | 320.88 | 67.20 |
| PSU (on the tray floor, 90 tall) | 0.600 | 0 | 57 | 34.20 | 0 |
| controller (50 tall) | 0.400 | 0 | 37 | 14.80 | 0 |
| E-stop (on the lid, front) | 0.150 | 130 | 150 | 22.50 | 19.50 |
| limit switches | 0.100 | 0 | 742 | 74.20 | 0 |
| inlet (back face) | 0.080 | −175 | 65 | 5.20 | −14.00 |
| interlock switch | 0.150 | 80 | 382 | 57.30 | 12.00 |
| hinges | 0.100 | 80 | 382 | 38.20 | 8.00 |
| fasteners, joint plugs, wiring (at frame mid-height) | 0.600 | 0 | 562 | 337.20 | 0 |
| **Sum** | **16.519** | | | **7211.55** | **25.50** |

z_cg = 7211.55/16.519 = 436.6 mm; y_cg = 25.50/16.519 = +1.5 mm (forward). Worst edge: front,
x = 165 − 1.5 = 163.5 mm. FS = 163.5 / (436.6 × 0.17633) = 163.5/76.98 = **2.12** ≥ 1.5, margin +41.6 %
(back edge 2.16, sides 180/76.98 = 2.34). For the manual (requirement 13), not asserted: unanchored, a
horizontal push at the crosshead top tips it at m g x / h = 16.519 × 9.81 × 0.1635 / 1.002 = 26.4 N.

**Supply current** (requirement 14): worst case is the PSU at its full 150 W output; efficiency
η = 0.88 and power factor 0.95 (a PSU with active PFC, spec's choice [verify datasheet]).
I = P/(η V PF) = 150/(0.88 × 120 × 0.95) = 150/100.32 = **1.50 A** ≤ 3 A, margin +50.2 % (at 108 V low
line: 1.66 A). Fuse: 1.25 × 1.495 = 1.87 A ≤ T2.5 A ≤ 7 A (18 AWG MTW, `conductors.yaml` row `awg18-mtw`,
NFPA 79 Table 12.5.1). 24 V side: motor branch 96 W/24 V = 4.0 A on 18 AWG (7 A, margin +43 %); PSU
trunk 150 W/24 V = 6.25 A on 16 AWG (`awg16-mtw`, 10 A, margin +37.5 %).

### 4.4 C-001 C-frame (rejected: stiffness)

Frame analysis on centrelines; the column carries M = F a over H (Roark Table 8.1 Cases 1a and 3a, as
`structural.beam_deflection_cantilever`), each arm is a cantilever of length a, the column also
stretches. E I = 68.9 × 10⁹ × 4.70699 × 10⁻⁷ = 32 431 N·m².

- Column rotation: F a² H/(E I) = 2000 × 0.180² × 0.820 / 32 431 = 53.136/32 431 = **1.638 mm**
- Upper arm: F a³/(3 E I) = 2000 × 0.180³ / (3 × 32 431) = 11.664/97 293 = **0.120 mm**
- Base arm (same): **0.120 mm**
- Column stretch: F H/(E A) = 2000 × 0.820 / (68.9 × 10⁹ × 8.96 × 10⁻⁴) = 1640/61 734 400 = **0.0266 mm**
- Total δ = 1.6384 + 0.1199 + 0.1199 + 0.0266 = **1.90 mm** vs 0.20 mm: margin **−852 %**. The two
  terms `beam_deflection_cantilever` returns (1.758 mm) fail on their own.

Yield: σ = F a/Z + F/A = 360/1.5690 × 10⁻⁵ + 2000/896 = 22.9 + 2.2 = 25.2 MPa; FS_y = 145/25.18 = **5.76**
(+188 %). Weld heat-affected-zone strength is not checked; the card is rejected on stiffness first.

### 4.5 C-003 plate gantry (rejected: mass and cost)

- Each bridge: δ = 54 / (48 × 200 × 10⁹ × 7.2 × 10⁻⁷) = 54/6 912 000 = 0.00781 mm; plates:
  1000 × 0.760 / (200 × 10⁹ × 6.25 × 10⁻³) = 0.00061 mm. Total δ = **0.0162 mm** (margin +91.9 %).
- Bridge stress 150 / 2.4 × 10⁻⁵ = 6.25 MPa; FS_y = 250/6.25 = **40.0** (+1900 %).
- Mass and cost: §4.6, §4.7.

### 4.6 Mass roll-up (mass = ρ × volume; bought-in parts by allowance)

| Part | Volume or basis | Mass kg |
|---|---|---|
| C-002 top crosshead / base beam (each) | 900 mm² × 340 mm = 3.06 × 10⁻⁴ m³ × 2700 | 0.8262 |
| C-002 column (each) | 444 mm² × 760 mm = 3.3744 × 10⁻⁴ m³ × 2700 | 0.9111 |
| **C-002 frame** | 2 × 0.8262 + 2 × 0.9111 | **3.4746** |
| C-001 C-frame | 896 mm² × (880 + 190 + 190) mm = 1.12896 × 10⁻³ m³ × 2700 | **3.0482** |
| C-003 side plates (2) | 2 × 25 × 250 × 880 mm = 1.1 × 10⁻² m³ × 7850 | 86.350 |
| C-003 bridges (2) | 2 × 60 × 40 × 275 mm = 1.32 × 10⁻³ m³ × 7850 | 10.362 |
| **C-003 frame** | | **96.712** |
| Lower platen | 100 × 100 × 15 mm = 1.5 × 10⁻⁴ m³ × 7850 | 1.1775 |
| Upper platen | 80 × 80 × 10 mm = 6.4 × 10⁻⁵ m³ × 7850 | 0.5024 |
| Console tray | (0.38 × 0.35 + 2 × 0.38 × 0.11 + 2 × 0.35 × 0.11) = 0.2936 m² × 0.002 m × 2680 | 1.5737 |
| Console lid | 0.38 × 0.35 = 0.133 m² × 0.002 m × 2680 | 0.7129 |
| Guard shroud | 0.67 × 0.40 × 0.005 m = 1.34 × 10⁻³ m³ × 1200 | 1.6080 |
| Guard door | 0.35 × 0.40 × 0.005 m = 7.0 × 10⁻⁴ m³ × 1200 | 0.8400 |
| Shared made parts | | **6.4145** |
| Bought-in allowances [verify] | actuator 4.00, load cell 0.35, PSU 0.60, controller 0.40, E-stop 0.15, limit switches 2 × 0.05, inlet 0.08, interlock 0.15, hinges 2 × 0.05, feet 4 × 0.025, fasteners/plugs/wiring 0.60 | **6.6300** |
| Shared total | 6.4145 + 6.6300 | **13.0445** |

| Card | Total mass | vs 25 kg | Lift class |
|---|---|---|---|
| C-001 | 13.0445 + 3.0482 = **16.09 kg** | +35.6 % | one-person |
| C-002 | 13.0445 + 3.4746 = **16.52 kg** | +33.9 % | one-person |
| C-003 | 13.0445 + 96.712 = **109.8 kg** | −339 % | equipment |

### 4.7 Cost roll-up (`cost_bands.yaml`, region US, quantity 1, all rows `verify: true`)

| Item | Band (row, as_of) | Quantity | Low USD | High USD |
|---|---|---|---|---|
| Platens (mild steel; the row has no process class, the spec assigns machining) | machining 31.8–128.9 /kg (2026-10) | 1.6799 kg | 53.42 | 216.54 |
| Console tray + lid | sheet-metal 8.0–67.6 /kg (2026-10) | 2.2866 kg | 18.29 | 154.57 |
| Guard shroud + door (cut polycarbonate sheet; spec assigns cnc-routing over the row's machining) | cnc-routing 35–120 /m² (2026-11) | 0.268 + 0.140 = 0.408 m² | 14.28 | 48.96 |
| Actuator, load cell, PSU, controller, E-stop, 2 limit switches, inlet, interlock | cots-controls 35–120 /item (2026-10) | 9 items | 315.00 | 1080.00 |
| **Shared** | | | **400.99** | **1500.07** |
| C-002 frame | extrusion-cut 15–45 /m (2026-11) | 2 × 0.34 + 2 × 0.76 = 2.20 m | 33.00 | 99.00 |
| C-001 frame | welding 19.5 /kg (2026-10, one source) | 3.0482 kg | 59.44 | 59.44 |
| C-003 frame | machining 31.8–128.9 /kg | 96.712 kg | 3075.44 | 12 466.18 |

Hinges, feet and fasteners have no band on file and are left out (the cost screen says so). The
cots-controls band was drawn from kiln controls (35–120 USD); a 2 kN actuator or load cell may cost more:
a quote replaces the band [verify]. Decision rule: a card passes cost when the band's high end fits the
budget, fails when even its low end exceeds it.

| Card | Band USD | Test | Margin |
|---|---|---|---|
| C-001 | **460 – 1560** (460.43 – 1559.51) | high ≤ 2400 | +35.0 % |
| C-002 | **434 – 1599** (433.99 – 1599.07) | high ≤ 2400 | +33.4 % |
| C-003 | **3476 – 13 966** (3476.44 – 13 966.25) | low > 2400 | −44.9 % |

## 5. The chosen design (C-002)

### 5.1 Parts (19 part definitions, 25 items)

| Sub-assembly | Part | Qty | Process | Material / kind |
|---|---|---|---|---|
| `asm://base-console` | console tray (4 × M6 bench-anchor holes, earth stud) | 1 | sheet-metal | aluminum-5052-h32, 2 mm |
| | console lid (grommet hole, E-stop hole) | 1 | sheet-metal | aluminum-5052-h32, 2 mm |
| | mains inlet, IEC C14, fused T2.5 A, switched | 1 | none (bought) | electrical: inlet |
| | power supply 24 V 150 W DIN-rail, active PFC | 1 | none | electrical: `psu` |
| | motion controller (stepper drive, load-cell amplifier, I/O) | 1 | none | electrical: `controller` |
| | E-stop, red mushroom, 2 NC positive-opening contacts | 1 | none | electrical: `e-stop` |
| | rubber foot Ø20 | 4 | none | rubber |
| `asm://portal-gantry` | base beam, RHS 60 × 40 × 5 × 340 | 1 | extrusion-cut | aluminum-6063-t5 |
| | top crosshead, RHS 60 × 40 × 5 × 340 | 1 | extrusion-cut | aluminum-6063-t5 |
| | column, RHS 40 × 40 × 3 × 760, tapped end plugs 2 × M8 each end | 2 | extrusion-cut | aluminum-6063-t5 |
| | lower platen 100 × 100 × 15 | 1 | machining | mild steel |
| | upper platen 80 × 80 × 10 | 1 | machining | mild steel |
| | linear actuator, 24 V stepper + ball screw, 3 kN, 200 mm stroke, ≤ 96 W | 1 | none | electrical: `motor` |
| | load cell, S-beam 2 kN, 4-wire | 1 | none | electrical: `sensor` |
| | limit switch (upper, lower), NC | 2 | none | electrical: `sensor` |
| `asm://guard-shield` | guard shroud, U, 5 mm, 670 × 400 developed | 1 | cnc-routing | polycarbonate |
| | guard door 350 × 400 × 5 | 1 | cnc-routing | polycarbonate |
| | hinge | 2 | none | steel, bought |
| | interlock switch, positive-opening, tongue actuator | 1 | none | electrical: `interlock` |

### 5.2 Interfaces

| Between | Kind | Detail |
|---|---|---|
| portal-gantry ↔ base-console (2, one at each base-beam end, "column feet") | bolt-pattern | 2 × M6 through the lid into the tray floor spacers |
| column ends ↔ base beam and crosshead (4, inside the gantry) | bolt-pattern | 2 × M8 class 8.8 per joint (the bolts of §4.3) |
| actuator flange ↔ crosshead underside | bolt-pattern | 4 × M6 on the actuator's flange pattern [verify] |
| lower platen ↔ base beam | bolt-pattern | 2 × M6 countersunk, top flange |
| guard shroud ↔ columns | bolt-pattern | 4 × M5 on standoffs |
| guard door ↔ shroud | hinge-pin | vertical axis at the shroud's left front edge |
| gantry and guard harness ↔ console | cable-entry | one grommet in the lid: motor, load cell, 2 limit switches, interlock |

### 5.3 Electrical devices and circuits (region US; colours from `wire_colours.yaml` US rows)

1. **Mains, 120 V 60 Hz**: detachable NEMA 5-15P cord into the C14 inlet (switch + T2.5 A fuse);
   line (black) and neutral (white) in 18 AWG MTW to the PSU input. Input ≤ 1.50 A (§4.3).
2. **Protective earth (Class I)**: the inlet's ground pin (green) to the tray's earth stud; bonding
   jumpers to the lid, the base beam (scraped through the anodising with a star washer), the actuator
   body and the PSU earth terminal. The guard is non-conductive.
3. **24 V DC trunk**: PSU output in 16 AWG to the controller's logic supply and to the motor branch.
4. **Motor power safety chain**: +24 V → E-stop NC contact 1 → guard interlock NC contact → motor drive
   power input (18 AWG, blue DC control colour). Opening either removes motor power (category 0);
   a back-driven screw lets a compressed specimen relax, the safe direction.
5. **Monitoring and sensors (24 V signal level)**: E-stop contact 2 and the interlock's second contact,
   the upper and lower limit switches (NC, fail-safe on a broken wire) to controller inputs; the load cell
   4-wire (excitation ±, signal ±, shielded) to the controller's amplifier.

## 6. Planned change requests

**CR-1 (parametric): rated load 2000 → 2500 N.** Everything scales with F. Expected: deflection
0.105 × 1.25 = **0.131 mm** (+34.4 %, passes); beam FS_y 13.13/1.25 = 10.5; beam fatigue 9.11/1.25 = **7.28**;
bolt σ_a = 625/73.2 = 8.538 MPa, n_f = 47 085/(8.538 × 929) = **5.94**; buckling 27 223/1250 = **21.8**;
mass, cost, tip-over and supply unchanged (the 3 kN actuator already covers it). Requirement 2 (load
cell ≥ rated load) **fails** with the 2 kN cell until it is swapped for a 3 kN S-beam (same allowance and
band [verify]); then all pass and the change is released as a new revision.

**CR-2 (design): the hinged door becomes a vertically sliding door.** Hinges (2, 0.10 kg) removed; two
6063-T5 U-channels 10 × 10 × 1.5, 400 mm long, added on the shroud's front edges (area 15 + 2 × 8.5 × 1.5
= 40.5 mm², 2 × 40.5 × 400 mm³ × 2700 = 0.0875 kg; extrusion-cut 0.80 m). The hinge-pin interface becomes
a mating-face. Expected: mass 16.519 − 0.100 + 0.0875 = **16.51 kg** (+34.0 %); cost **446 – 1635 USD**
(+31.9 %); tip-over with the door raised 400 mm (z 382 → 782): z_cg = 457.0 mm, y_cg = +1.5 mm,
FS = 163.5/(457.0 × 0.17633) = **2.03** (+35.3 %, passes); frame figures unchanged. Requirements 18 and
19 (interlock, shield) lose their sign-offs and must be signed again (`standard` ceremony).

## 7. Expected outcomes

| Card | Outcome | Deciding check |
|---|---|---|
| C-001 | rejected | `structural`: frame deflection 1.90 mm > 0.20 mm (−852 %); mass and cost pass |
| C-002 | promoted (chosen) | passes every check; binding margins: cost +33.4 %, mass +33.9 % |
| C-003 | rejected | `mass-cost`: mass 109.8 kg > 25 kg (−339 %) and cost low end 3476 USD > 2400 USD (−44.9 %); structural passes |

| Card | Figure | Expected | Tolerance |
|---|---|---|---|
| C-002 | frame deflection at the load axis (beams + columns) | 0.105 mm | ±5 % |
| C-002 | beam bending stress / yield factor | 11.0 MPa / 13.1 | ±5 % |
| C-002 | column axial stress / yield factor | 2.25 MPa / 64.4 | ±5 % |
| C-002 | beam fatigue factor, 10⁶ cycles | 9.11 | ±5 % |
| C-002 | column-end bolt fatigue factor (hand check, no screen figure) | 7.42 | ±5 % |
| C-002 | column buckling factor, load reversed (K = 2.1) | 27.2 | ±5 % |
| C-002 | tip-over factor at 10° tilt | 2.12 | ±5 % |
| C-002 | supply input current at 120 V | 1.50 A | ±5 % |
| C-002 | total mass | 16.52 kg | ±2 % |
| C-002 | cost band | 434 – 1599 USD | ±2 % (each end; mass × rate) |
| C-001 | frame deflection at the load axis | 1.90 mm | ±5 % |
| C-001 | yield factor | 5.76 | ±5 % |
| C-001 | total mass / cost band | 16.09 kg / 460 – 1560 USD | ±2 % |
| C-003 | frame deflection | 0.0162 mm | ±5 % |
| C-003 | total mass / cost band | 109.8 kg / 3476 – 13 966 USD | ±2 % |
| All | ceremony / region / supply | `standard` / `US` / 120 V 60 Hz | exact |
| CR-1 | deflection / requirement 2 before the swap | 0.131 mm / fails | ±5 % / exact |
| CR-2 | tip-over with the door raised / mass | 2.03 / 16.51 kg | ±5 % / ±2 % |
