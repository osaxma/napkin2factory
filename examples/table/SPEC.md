# Benchmark Tier 1: oak-and-steel table (`SPEC.md`)

The simple tier of the benchmark ladder (road-to-v1.0 §4, Track A §2.2). An agent builds a
product from this file alone; `SPEC.oracle.yaml` is written from §7 and checks the result.
Every figure below is worked from the stated geometry (road-to-v1.0 §4.1). Worked by hand on
2026-11-04; a second vendor re-derives it before the oracle is frozen (v0.7 W9).
Re-derived independently by a second model from this file alone on 2026-11-04: all 140
figures agreed within 0.35 %.

**Conventions.** Lengths in mm, forces in N, stresses in MPa (N/mm²), stiffness EI in N·mm².
Masses become weights with g = 9.80665 m/s², the value `calckit/structural.py` uses. The
owner's loads are stated in N as Track A gives them (150 kg → 1471.5 N, 50 kg → 490.5 N).
Results carry 3 significant figures. **Margin** against an upper bound is (limit − value) /
limit; against a lower bound (a factor of safety) it is (value − limit) / limit. A promoted
card clears every limit by ≥ 30 %; a rejected card misses its rejecting limit by ≥ 30 %.
`[verify]` marks a value a person must still confirm.

## 1. Customer intent and site

> "I want a solid oak table for my workshop that doubles as a dining table: about 1.6 m by
> 0.8 m, normal table height, on a black steel base. It must take a 150 kg load in the middle
> without visibly sagging, must not tip if someone leans or sits on the edge, and two of us
> must be able to move it. Keep it under about 1600 dollars. The top has to be allowed to
> move with the seasons so it does not crack."

| Item | Value | Basis |
|---|---|---|
| Top | 1600 × 800 mm, top surface 750 mm above the floor | given |
| Leg room | no stretcher or rail between the legs below the apron | given |
| Room | indoor, about 21 °C, relative humidity 30 % to 70 % over the year | given [verify] |
| Centre load | 1471.5 N (150 kg) at the middle of the top, short term | given |
| Edge load | 490.5 N (50 kg) downward at the middle of any edge, empty table | given |
| Lateral push | 300 N horizontal at top level, either direction | spec's choice [verify] against ANSI/BIFMA X5.5 and EN 15372 horizontal-load clauses |
| Sustained load | 490.5 N (50 kg: a vise and tools) left at the middle, plus self weight | spec's choice |
| Deflection limit | 2.5 mm mid-span sag (L/640 of the 1600 mm length) | given |
| Sway limit | 3.0 mm at top level | spec's choice (≈ H/230) [verify] |
| Factors of safety | from `calckit/data/load_cases.yaml`, quoted in §4.0 | cited |
| Mass limit | 70 kg assembled | given (changed from 55 kg, §8) |
| Budget | 1600 USD, US cost bands as of 2026-10/2026-11 | given [verify] (changed from 450 USD, §8) |
| Supply | none (no electrical domain) | given |

## 2. Requirements (for `model/requirements.yaml`)

1. **Size.** Top 1600 × 800 mm (± 2 mm); top surface 750 mm above the floor (± 10 mm, glide
   adjustment). Verification: computed (model geometry).
2. **Centre-load sag.** Mid-span sag under 1471.5 N at the middle plus the self weight of the
   spanning members ≤ 2.5 mm. Computed.
3. **Long-term sag.** Final sag under the sustained load (490.5 N at the middle plus self
   weight), timber creep included, ≤ 2.5 mm. Computed.
4. **Strength.** Yield factor ≥ 1.5 in every spanning member under the loads of requirement 2.
   Computed.
5. **Leg buckling.** Buckling factor ≥ 2.0 for a leg carrying the whole 1471.5 N plus a quarter
   of the table's weight. Computed.
6. **Tip-over (safety).** Tip-over factor ≥ 2.0 under 490.5 N downward at the middle of any
   edge of the empty table. Computed. `safety: true`, tag `hazard:tip-over`; one sign-off
   (furniture tip-over standards such as ASTM F2057 exist for this reason; which clause
   applies to a table is [verify]).
7. **Racking sway.** Sway at top level under 2.0 × 300 N lateral push ≤ 3.0 mm. Computed.
8. **Corner joints.** Welded leg-to-rail corner moment factor ≥ 2.0 under the 300 N push.
   Computed.
9. **Top fixing.** Insert pull-out factor ≥ 2.5 when the assembled table is lifted by its top.
   Computed.
10. **Wood movement.** Free travel of each slotted fixing ≥ the across-grain movement at that
    fixing over 30 % to 70 % RH. Computed.
11. **Mass** ≤ 70 kg. Computed.
12. **Cost** ≤ 1600 USD at the high end of the cost band. Computed (estimate, [verify]).
13. **Leg room.** No member between the legs below the apron. Inspection.

The product has one domain and no hazardous energy, so its ceremony derives to `lite`
(Track A §3.4); requirement 6 keeps its sign-off.

## 3. Concept cards

Shared by all cards: top 1600 × 800 mm, grain along the 1600 mm length, top surface at 750 mm,
levelling glides 20 mm floor to leg (or foot) bottom. Plan coordinates: origin at the top's
centre, x along the length, y across the width.

### C-001: four corner tube legs, no apron, 22 mm pine top
- Top: southern-yellow-pine, 1600 × 800 × 22 mm.
- Legs: 4 × 40 × 40 × 2 mm square tube, mild steel, outer faces flush with the top's edges
  (leg centres 20 mm in from each edge: x = ±780, y = ±380), length 704 mm
  (750 − 22 − 4 − 20). Each leg carries a welded 80 × 80 × 4 mm top plate fixed to the top
  with 2 M8 inserts and bolts (8 of each). No rails.
- Sag model: the top alone, simply supported along its length between leg centres,
  span 1560 mm. Real support is four points, so real sag is larger still.

### C-002: perimeter steel apron frame, 30 mm white-oak top (the intended winner)
- Top: white-oak, 1600 × 800 × 30 mm, edge-glued strips, flat-sawn (tangential) assumed.
- Apron frame (one weldment, `geometry.kit.frame`, `top_rails: true`, `bottom_rails: false`):
  every member 50 × 50 × 1.5 mm square tube, mild steel (square, so rail orientation does not
  change any figure). Frame outer 1500 × 700 × 700 mm: inset 50 mm from every top edge.
  Legs 4 × 700 mm; long rails 2 × 1400 mm and short rails 2 × 600 mm between the legs, top
  faces flush with the leg tops. Leg centres at x = ±725, y = ±325 (75 mm in from each edge).
- Fixing tabs: 8 × 40 × 40 × 4 mm steel plate welded to the rails' inner faces, top faces
  flush with the rails. Six on the long rails (x = −600, 0, +600; y = ±280, i.e. 20 mm in from
  the rail face) with a 9 × 22 mm slot running across the width; two on the short rails
  (x = ±680, y = 0) with a round 9 mm hole (these fix the top's centreline).
- Hardware: 8 M8 × 20 flanged inserts in the top, 8 M8 × 25 button-head screws with washers,
  4 M10 levelling glides.
- Sag model: the top and the two long rails bend together along the length as one simply
  supported beam between leg centres, span 1450 mm. Their EI add (the slotted fixings carry
  no shear, so there is no composite action); the full 800 mm width of the top acts; legs and
  short rails are rigid supports; the top's local dishing between the long rails is not
  included. Self weight (top plus long rails) is spread over the span; the relieving moment
  of the 75 mm end overhangs is ignored (conservative).

### C-003: heavy welded plate trestles, 45 mm white-oak top
- Top: white-oak, 1600 × 800 × 45 mm.
- Two trestle ends (weldments, mild steel), centred at x = ±600 (top end overhang 200 mm),
  each: upright plate 600 (y) × 661 (z) × 12 mm; foot bar and top bar each 700 (y) × 80 (x)
  × 12 mm. Height: 20 glide + 12 foot bar + 661 upright + 12 top bar + 45 top = 750.
- Stretcher: 100 × 50 × 3 mm rectangular tube (100 mm vertical), 1188 mm between the uprights'
  faces, its top face level with the uprights' top edges (z = 593 to 693), so it is an apron
  and leaves the leg room clear.
- Glides under the foot-bar ends, 40 mm in from each end (y = ±310). Top fixed to each top
  bar with 4 M8 inserts and bolts (8 of each).
- Sag model: the top alone, simply supported between trestle centres, span 1200 mm.

## 4. Worked calculations

### 4.0 Inputs

| Input | Value | Source |
|---|---|---|
| mild steel | ρ 7850 kg/m³, E 200 GPa, σy 250 MPa | `materials.yaml` row `mild steel` (ASTM A36 / EN 10025-2 S235; ASM Handbook Vol 1) [verify] |
| white-oak | ρ 750 kg/m³, E 12.3 GPa, proportional-limit stress 55.2 MPa (12 % MC) | `materials.yaml` row `white-oak` (USDA Wood Handbook FPL-GTR-190 Table 5-3a) [verify] |
| southern-yellow-pine | ρ 590 kg/m³, E 12.3 GPa, proportional-limit stress 49.6 MPa (12 % MC) | `materials.yaml` row `southern-yellow-pine` (FPL-GTR-190 Table 5-3b) [verify] |
| oak across-grain change | C_T = 0.00365 per % MC | `wood_movement.yaml` row `white-oak` (FPL-GTR-190 Ch. 4) [verify] |
| equilibrium MC at 21 °C | 6.2 % at 30 % RH, 13.1 % at 70 % RH, 9.2 % at 50 % RH | FPL-GTR-190 Table 4-2 (70 °F column) [verify]; the Hailwood–Horrobin equation (4-5) at 21.1 °C gives 6.17 % and 13.09 % |
| timber creep | k_def = 0.60 (solid timber, service class 1) | EN 1995-1-1 Table 3.2, as in `joints.wood_creep_deflection` |
| M8 insert in hardwood | 6800 N ultimate pull-out each | `joints.THREADED_INSERT_ROWS` (RAMPA SK catalogue) [verify] |
| leg effective length | K = 2.0 (foot pinned; top fixed in rotation, free to sway) | AISC 360 Commentary Table C-A-7.1, case (f) |
| weld efficiency | η = 0.7 for the fillet-welded thin-wall corner | spec's choice [verify] |
| yield factor | 1.5 | `load_cases.yaml` {check: yield, load_kind: static}: AISC 360-16 / Shigley Table 1-5 [verify] |
| buckling factor | 2.0 | {check: buckling, load_kind: static}: AISC 360-16 Ch. E [verify] |
| tip-over factor | 2.0 | {check: tip_over, load_kind: edge_load}: ANSI/BIFMA X5.5-2021 §4.3 [verify] |
| pull-out factor | 2.5 | {check: pullout, load_kind: edge_load}: ANSI/BIFMA X5.5, human pull or pry [verify] |
| racking factor | 2.0 (sway and corners) | {check: racking, load_kind: edge_load}: ANSI/BIFMA X5.5 §7, lateral user push [verify] |
| deflection factor | 1.0 | {check: deflection, load_kind: static}: AISC 360-16 / IBC Table 1604.3 [verify] |
| woodworking band | 9.0 to 22.0 USD/kg | `cost_bands.yaml` {process_class: woodworking, region: US, as_of: 2026-11} [verify] |
| welding band | 19.5 USD/kg | `cost_bands.yaml` {process_class: welding, region: US, as_of: 2026-10} [verify] |
| hardware | glide 0.080 kg, 4.00 USD; M8 insert 0.010 kg, 1.50 USD; M8 × 25 screw + washer 0.020 kg, 1.00 USD | spec's estimates, US, 2026-11 [verify] against a supplier catalogue |

Hardware set (every card: 4 glides, 8 inserts, 8 screws): mass 4 × 0.080 + 8 × 0.010 + 8 × 0.020
= **0.560 kg**; cost 4 × 4.00 + 8 × 1.50 + 8 × 1.00 = **36.0 USD** (same at both band ends).
Holes, slots and weld fillets are not subtracted or added (< 0.05 kg per card).

Modelling choices (the spec's own; each is conservative or below the tolerances):
- **Glides.** Each glide is a pin at the floor: its 20 mm M10 stem is taken as rigid in both
  leg buckling (uniform 50 × 50 × 1.5 tube over the full 720 mm, no stepped column) and racking
  (no stem bending in the sway). The glide pad diameter is not used: the tipping edge is the
  glide centreline, inside the pad's outer edge.
- **Sag self weight** counts the top and the long rails only; the six long-rail tabs
  (6 × 0.0502 = 0.301 kg, 2.96 N) are left out, which changes the sag by 0.002 mm (0.1 %).
- **Top width.** The full 800 mm of the top acts in bending: no shear-lag or effective-width
  reduction across the span between the rails.
- **End overhangs.** The 75 mm (C-002) top overhangs past the supports are ignored in both the
  sag and the bending moment; their counter-moment would only reduce both.
- **Welds.** Weld leg size and throat are not specified; the corner capacity rests on the tube's
  section modulus times the efficiency η = 0.7 (full-perimeter fillet weld assumed).

Cost rule: a card passes when the band's **high** end ≤ budget and is rejected when its **low**
end > budget, so neither outcome depends on where in the band the real price falls.

### 4.1 C-002

**Section properties** (hollow square, `structural.rect_tube_section`; plate,
`structural.rect_section`; Roark Table A.1):
- Tube 50 × 50 × 1.5: A = 50² − 47² = 2500 − 2209 = **291 mm²**;
  I = (50⁴ − 47⁴)/12 = (6 250 000 − 4 879 681)/12 = **114 193 mm⁴** (114 193.25);
  Z = I/25 = **4 568 mm³** (4 567.73); r = √(I/A) = √392.42 = **19.8 mm** (19.810);
  mass per metre 291 × 10⁻⁶ m² × 7850 = **2.284 kg/m** (2.28435).
- Top 800 × 30: I = 800 × 30³/12 = **1.80 × 10⁶ mm⁴**; Z = 800 × 30²/6 = **120 000 mm³**.

**Mass roll-up** (density × volume, `mass_cost.mass`):

| Part | Volume | Mass |
|---|---|---|
| top-board | 1600 × 800 × 30 = 38.4 × 10⁶ mm³ × 750 kg/m³ | 28.8 kg |
| apron-frame tube | (4 × 700 + 2 × 1400 + 2 × 600) = 6800 mm × 291 mm² = 1.979 × 10⁶ mm³ × 7850 | 15.53 kg (15.534) |
| apron-frame tabs | 8 × 40 × 40 × 4 = 51 200 mm³ × 7850 | 0.402 kg |
| apron-frame total | | **15.9 kg** (15.936) |
| hardware set | §4.0 | 0.560 kg |
| **Table** | 28.8 + 15.936 + 0.560 | **45.3 kg** (45.296) |

Margin against 70 kg: (70 − 45.3)/70 = **35.3 %**. Weight W_table = 45.296 × 9.80665 = 444.2 N.

**Cost roll-up** (band × mass, `mass_cost.cost_estimate`, US, [verify]):
top 28.8 kg × 9.0 to 22.0 = 259.2 to 633.6 USD; frame 15.936 kg × 19.5 = 310.7 USD; hardware 36.0.
Total **606 to 980 USD** (605.9 to 980.3). Margin of the high end against 1600 USD:
(1600 − 980.3)/1600 = **38.7 %**.

**Sag** (`structural.beam_deflection_simply_supported`, Roark Table 8.1 cases 1d and 1e):
- EI_top = 12 300 × 1.80 × 10⁶ = 2.214 × 10¹⁰; EI_rails = 2 × 200 000 × 114 193.25
  = 4.568 × 10¹⁰ (4.5677); ΣEI = **6.78 × 10¹⁰ N·mm²** (6.7817).
- L = 1450, L³ = 3.0486 × 10⁹ mm³.
- Point: δ_P = F L³/(48 ΣEI) = 1471.5 × 3.0486 × 10⁹ / (48 × 6.7817 × 10¹⁰)
  = 4.4861 × 10¹²/3.2552 × 10¹² = **1.38 mm** (1.378).
- Self weight: top 28.8 kg + long rails 2 × 1400 mm × 2.28435 kg/m = 6.396 kg → 35.196 kg,
  W = 35.196 × 9.80665 = 345.2 N. δ_W = 5 W L³/(384 ΣEI) = 5 × 345.16 × 3.0486 × 10⁹ /
  (384 × 6.7817 × 10¹⁰) = 5.2613 × 10¹²/2.6042 × 10¹³ = **0.202 mm**.
- Total **1.58 mm** (1.580) ≤ 2.5 × 1.0; margin **36.8 %**.

**Bending stress and yield factor** (`structural.beam_bending_stress`; members bending together
share the moment in proportion to EI, so σ_i = M E_i c_i / ΣEI):
- M = F L/4 + W L/8 = 533 419 + 62 560 = **5.96 × 10⁵ N·mm** (595 978).
- Top (c = 15): σ = 595 978 × 12 300 × 15 / 6.7817 × 10¹⁰ = **1.62 MPa**; factor 55.2/1.621
  = **34.0** ≥ 1.5 (margin 2170 %).
- Rails (c = 25): σ = 595 978 × 200 000 × 25 / 6.7817 × 10¹⁰ = **43.9 MPa**; factor 250/43.94
  = **5.69** ≥ 1.5 (margin 279 %).

**Long-term sag** (EN 1995-1-1 §2.3.2.2: the timber member's final modulus E/(1 + k_def); steel
does not creep):
- EI_fin = 12 300/1.60 × 1.80 × 10⁶ + 4.5677 × 10¹⁰ = 1.3838 × 10¹⁰ + 4.5677 × 10¹⁰
  = 5.9515 × 10¹⁰.
- δ_fin = L³ (F_s/48 + 5W/384)/EI_fin = 3.0486 × 10⁹ × (10.219 + 4.494)/5.9515 × 10¹⁰
  = 4.4854 × 10¹⁰/5.9515 × 10¹⁰ = **0.754 mm** ≤ 2.5; margin **69.9 %**.
- Note: `joints.wood_creep_deflection` multiplies the whole elastic sag by 1.6
  (0.661 × 1.6 = 1.06 mm); that overstates a steel-and-wood pair. The oracle asserts 0.754 mm.

**Leg buckling** (Johnson parabola, Shigley *Mechanical Engineering Design*, intermediate
columns; the slenderness is below the Euler limit, so `structural.euler_buckling_load` refuses
this column, by design):
- Load: P = 1471.5 + 444.2/4 = **1583 N** (1582.55).
- KL = 2.0 × 720 (floor to the underside of the top) = 1440 mm; KL/r = 1440/19.810 = **72.7**;
  Euler limit √(2π²E/σy) = √(2π² × 200 000/250) = **125.7**; 72.7 < 125.7, so Johnson applies.
- σ_cr = σy − (σy · KL/r / 2π)²/E = 250 − (250 × 72.69/6.2832)²/200 000 = 250 − 41.83
  = **208 MPa**; P_cr = 208.17 × 291 = **60 600 N** (60 578).
- Factor 60 578/1582.55 = **38.3** ≥ 2.0 (margin 1810 %).

**Tip-over** (`structural.tip_over_safety_factor`, FS = m g x_cg / (F x_edge)). The CG is at the
plan centre (the frame is symmetric and centred under the top); its height does not enter for
vertical loads. Tipping edge: the line through the two front glide centres, y = 325
(conservative: the glide pad's outer edge is further out).
- Long (front) edge: x_cg = 325, x_edge = 400 − 325 = 75. Restoring 444.2 × 0.325
  = 144.4 N·m; overturning 490.5 × 0.075 = 36.8 N·m; FS = **3.92** ≥ 2.0 (margin 96.2 %).
- End edge: x_cg = 725, x_edge = 75: FS = 444.2 × 0.725/36.79 = 8.75. The front edge governs.

**Racking** (`joints.frame_racking`, pinned bases: δ = P H³/(6 E I_c) + P H² L/(12 E I_b),
Roark Table 8.2 and slope-deflection). Glides are pins; welded corners rigid; the top's
stiffening as a diaphragm is ignored (conservative). H = 750 − 30 − 25 = 695 (floor to the rail
centreline). A push along the length is shared by the front and back frames, P = 150 N each,
L = 1450:
- Columns: 150 × 695³/(6 × 200 000 × 114 193.25) = 5.0355 × 10¹⁰/1.3703 × 10¹¹ = 0.367 mm.
- Rail: 150 × 695² × 1450/(12 × 200 000 × 114 193.25) = 1.0506 × 10¹¹/2.7406 × 10¹¹ = 0.383 mm.
- Sway **0.751 mm**; across the width (L = 650) the rail term is 0.172 mm and the sway 0.539 mm,
  so along the length governs. Factored 2.0 × 0.7508 = 1.50 mm ≤ 3.0; margin **49.9 %**.
- Corner moment (`joints.joint_moment_capacity`, welded M = Z σy η): each of four legs takes
  75 N of shear, M = 75 × 695 = 52 125 N·mm; capacity 4567.73 × 250 × 0.7 = 799 353 N·mm;
  factor **15.3** ≥ 2.0 (margin 667 %).

**Insert pull-out** (`joints.insert_pullout`). Case: the assembled table is lifted by its top,
the base hanging; conservatively two inserts carry the whole base (a warped base hangs on two).
Base = frame 15.936 + glides 0.320 + screws 0.160 = 16.416 kg → 161.0 N. Capacity 2 × 6800
= 13 600 N; factor 13 600/161.0 = **84.5** ≥ 2.5 (margin 3280 %).

**Wood movement** (`joints.wood_movement`, ΔW = W C_T ΔMC, FPL-GTR-190 Ch. 4). ΔMC = 13.1 − 6.2
= 6.9 points.
- Whole width: 800 × 0.00365 × 6.9 = **20.1 mm** (20.15); the top must never be fixed at both
  long edges.
- At a long-rail fixing, 280 mm from the fixed centreline: 280 × 0.00365 × 6.9 = **7.05 mm**.
- Slot 9 mm wide (the M8 clearance) × 22 mm long: free travel taken as 22 − 9 = 13 mm
  (conservative; the 8 mm screw itself has 14 mm); margin
  (13 − 7.05)/13 = **45.8 %**. Fitted centred at 50 % RH (MC 9.2 %), the worst side needs
  280 × 0.00365 × (13.1 − 9.2) = 3.99 mm against 6.5 mm (margin 38.7 %).
- The short-rail fixings sit on the centreline (y = 0) and move 0 mm across the grain; movement
  along the grain is about 1 % of the across-grain value (FPL-GTR-190 Ch. 4) and is ignored.
- Note: `wood_movement` called with only the RH pair converts RH to MC with the Hailwood-Horrobin
  equation (S-207) and returns 7.07 mm here, a little above the 7.05 mm by hand (the equation
  gives 6.92 points of moisture, the table rounds to 6.9); pass `delta_mc=6.9` to match exactly.

### 4.2 C-001

- Tube 40 × 40 × 2: A = 40² − 36² = 1600 − 1296 = **304 mm²**.
- Top 800 × 22: I = 800 × 22³/12 = **709 867 mm⁴**; Z = 800 × 22²/6 = **64 533 mm³**.

| Part | Volume × density | Mass |
|---|---|---|
| top (pine) | 1600 × 800 × 22 = 28.16 × 10⁶ mm³ × 590 | 16.6 kg (16.614) |
| legs | 4 × 704 × 304 = 856 064 mm³ × 7850 | 6.72 kg (6.720) |
| leg plates | 4 × 80 × 80 × 4 = 102 400 mm³ × 7850 | 0.804 kg |
| hardware set | §4.0 | 0.560 kg |
| **Table** | | **24.7 kg** (24.698) |

Cost: 16.614 × 9.0 to 22.0 = 149.5 to 365.5; steel 7.524 kg × 19.5 = 146.7; hardware 36.0;
total **332 to 548 USD**.

Sag: EI = 12 300 × 709 867 = 8.7314 × 10⁹; L = 1560, L³ = 3.7964 × 10⁹.
δ_P = 1471.5 × 3.7964 × 10⁹/(48 × 8.7314 × 10⁹) = 5.5864 × 10¹²/4.1911 × 10¹¹ = **13.3 mm**
(13.33). Self weight 16.614 × 9.80665 = 162.9 N; δ_W = 5 × 162.93 × 3.7964 × 10⁹/(384 × 8.7314
× 10⁹) = **0.922 mm**. Total **14.3 mm** (14.25) against 2.5: **470 % over**. Rejected.

Strength (so the rejection is stiffness, not strength): M = 1471.5 × 1560/4 + 162.93 × 1560/8
= 605 657 N·mm; σ = 605 657/64 533 = 9.39 MPa; factor 49.6/9.385 = **5.28** ≥ 1.5.

Tip-over (front edge): x_cg = 380, x_edge = 20; FS = 24.698 × 9.80665 × 0.380/(490.5 × 0.020)
= 92.04/9.81 = **9.38**.

### 4.3 C-003

| Part | Volume × density | Mass |
|---|---|---|
| top (oak) | 1600 × 800 × 45 = 57.6 × 10⁶ mm³ × 750 | 43.2 kg |
| uprights | 2 × 600 × 661 × 12 = 9.518 × 10⁶ mm³ × 7850 | 74.7 kg (74.719) |
| foot and top bars | 4 × 700 × 80 × 12 = 2.688 × 10⁶ mm³ × 7850 | 21.1 kg (21.101) |
| stretcher | (100 × 50 − 94 × 44) = 864 mm² × 1188 mm × 7850 | 8.06 kg (8.057) |
| hardware set | §4.0 | 0.560 kg |
| **Table** | steel 103.88 kg | **148 kg** (147.64) |

Mass against 70 kg: **111 % over**. Cost: top 43.2 × 9.0 to 22.0 = 388.8 to 950.4; steel
103.88 × 19.5 = 2025.6; hardware 36.0; total **2450 to 3010 USD** (2450.4 to 3012.0). Low end
against 1600 USD: **53.2 % over**. Rejected on mass and cost.

Sag (it passes, so the rejection is not structural): I = 800 × 45³/12 = 6.075 × 10⁶;
EI = 7.4723 × 10¹⁰; L = 1200, L³ = 1.728 × 10⁹. δ_P = 1471.5 × 1.728 × 10⁹/(48 × 7.4723 × 10¹⁰)
= **0.709 mm**; W = 43.2 × 9.80665 = 423.6 N, δ_W = 5 × 423.65 × 1.728 × 10⁹/(384 × 7.4723
× 10¹⁰) = **0.128 mm**; total **0.837 mm**.

Tip-over (front edge): x_cg = 310, x_edge = 90; FS = 147.64 × 9.80665 × 0.310/(490.5 × 0.090)
= 448.8/44.15 = **10.2**.

## 5. Chosen design (C-002): parts and interfaces

| # | Part | Process | Material | Description |
|---|---|---|---|---|
| 1 | top-board | woodworking | white-oak | 1600 × 800 × 30 mm, edge-glued, grain along the length; 8 M8 insert ports underneath at the tab positions of §3 |
| 2 | apron-frame | welding | mild steel, powder-coated | `geometry.kit.frame`, 1500 × 700 × 700 mm outer, 50 × 50 × 1.5 square tube, `top_rails: true`, `bottom_rails: false`; 8 fixing tabs (6 slotted 9 × 22 mm, 2 round Ø 9 mm); M10 thread at each leg foot |
| 3 | leveling-foot | COTS × 4 | steel/nylon | M10 levelling glide with its tube-end insert, 20 mm set height |
| 4 | wood-insert-m8 | COTS × 8 | zinc alloy | M8 × 20 flanged threaded wood insert |
| 5 | mounting-bolt-m8 | COTS × 8 | steel | M8 × 25 button-head hex screw with ISO 7089 washer (25 − 4 tab − 1.6 washer = 19.4 mm into a 20 mm insert) |

Interfaces:
- top-board ↔ apron-frame: 8 × `threaded-insert` (M8), the six long-rail ones slotted across the
  width, the two short-rail ones round (they locate the top's centreline).
- leveling-foot ↔ apron-frame: 4 × `threaded-insert` (M10) at the leg feet.

One sub-assembly level (flat), one domain (mechanical), no supply, ceremony `lite`.

## 6. Planned change requests

1. **ECR-1, parametric: top 30 → 32 mm** (the owner wants a heavier look; legs shorten to
   698 mm to keep 750). Expected: **accepted**, every requirement still passes by ≥ 30 %.
   Top 1600 × 800 × 32 × 750 = 30.72 kg; frame (4 × 698 + 4000) = 6792 mm × 2.28435 kg/m
   + 0.402 = 15.917 kg; table **47.2 kg** (47.197; margin 32.6 %). Cost 30.72 × 9.0 to 22.0
   = 276.5 to 675.8, frame 15.917 × 19.5 = 310.4, hardware 36.0: **623 to 1022 USD**
   (622.9 to 1022.2; margin 36.1 %). Sag: EI_top = 12 300 × 800 × 32³/12 = 2.6870 × 10¹⁰,
   ΣEI = 7.2547 × 10¹⁰, δ_P = 4.4861 × 10¹²/(48 × 7.2547 × 10¹⁰) = 1.288 mm; W = (30.72 +
   6.396) × 9.80665 = 364.0 N, δ_W = 5 × 363.99 × 3.0486 × 10⁹/(384 × 7.2547 × 10¹⁰) = 0.199 mm;
   sag **1.49 mm** (1.487; margin 40.5 %). Tip-over 47.197 × 9.80665 × 0.325/36.79 = **4.09**
   (margin 104 %). Strength, creep, buckling, racking, pull-out and movement only improve or
   keep at least the C-002 margins of §4.1 (a thicker top only stiffens it). The screws reach 19.4 mm into a 32 mm top.
2. **ECR-2, design: a 500 mm seating overhang at one end** (top 2100 × 800 × 30, base unchanged,
   one end of the top 575 mm beyond the end glides). Expected: **refused**, the tip-over
   requirement (6) fails and n2f names it. Top 37.8 kg with its centre at x = +250; table
   54.30 kg; CG x = 37.8 × 250/54.30 = 174.0 mm. Tipping edge: the end glides at x = 725; arm
   725 − 174.0 = 551.0 mm; edge load at x = 1300, 575 mm out. FS = 54.30 × 9.80665 × 0.5510 /
   (490.5 × 0.575) = 293.4/282.0 = **1.04** < 2.0 (48 % below).

## 7. Expected outcomes

| Card | Outcome | Deciding check |
|---|---|---|
| C-001 | rejected | structural: sag 14.3 mm > 2.5 mm (+470 %) |
| C-002 | promoted (chosen) | passes all; closest margins: mass 35.3 %, sag 36.8 %, cost 38.7 % |
| C-003 | rejected | mass 148 kg > 70 kg (+111 %); cost low end 2450 USD > 1600 USD (+53.2 %) |

| Figure | C-001 | C-002 | C-003 | Tolerance |
|---|---|---|---|---|
| mid-span sag, centre load + self weight (mm) | 14.3 | 1.58 | 0.837 | ± 5 % |
| total mass (kg) | 24.7 | 45.3 | 148 | ± 2 % |
| cost band (USD, US, 2026-11) | 332–548 | 606–980 | 2450–3010 | ± 2 % each end |
| tip-over factor (governing edge) | 9.38 | 3.92 | 10.2 | ± 5 % |
| top yield factor | 5.28 | 34.0 | — | ± 5 % |
| rail yield factor | — | 5.69 | — | ± 5 % |
| long-term sag (mm) | — | 0.754 | — | ± 5 % |
| leg buckling factor (Johnson) | — | 38.3 | — | ± 5 % |
| racking sway, 300 N (mm) | — | 0.751 | — | ± 5 % |
| corner joint factor | — | 15.3 | — | ± 5 % |
| insert pull-out factor | — | 84.5 | — | ± 5 % |
| across-grain movement at a slot (mm) | — | 7.05 | — | ± 5 % |
| ECR-1 / ECR-2 | — | accepted (1.49 mm, 47.2 kg, 623–1022 USD, tip-over 4.09) / refused (tip-over 1.04) | — | as above |

Gate statuses for C-002's product: `lite` ceremony; one `safety: true` requirement (tip-over)
with one sign-off; every computed requirement in §2 passes.

## 8. Changes from Track A's draft

| Draft (Track A §2.2) | Here | Why |
|---|---|---|
| mass limit 55 kg | 70 kg | 55 kg needs C-002 ≤ 38.5 kg. A scan of common tube sizes and 25–30 mm tops found nothing better than 38.4 kg with 1.73 mm sag (25 mm top, 60 × 30 × 1.5 rails, 40 × 40 × 1.5 legs, two stocks): both 30–31 % inside their limits, a borderline card. C-002 here is 45.3 kg. |
| budget 450 USD | 1600 USD | The repository's own bands (woodworking 9–22 USD/kg, welding 19.5 USD/kg) price the oak top alone at 259–634 USD. C-002's high end is 980 USD, C-003's low end 2450 USD. |
| C-002 top 35 mm | 30 mm | Mass (Track A suggested it). ECR-1 goes to 32 mm, not 35: at 35 mm the mass margin is 28.5 % (50.05 kg). |
| legs 50 × 50 × 2, rails 50 × 25 × 2 | all members 50 × 50 × 1.5 | The frame kit cuts every member from one stock (`frame.py` `MemberSpec`); the thinner wall keeps mass under the margin while the square rails keep the sag margin (36.8 %). |
| oak E 12.5 GPa | 12.3 GPa | The `materials.yaml` row (FPL-GTR-190 Table 5-3a). |
| bolts M8 × 35 | M8 × 25 | M8 × 35 through a 4 mm tab would reach 29.4 mm into a 30 mm top. |
| C-001 top "pine" | southern-yellow-pine, legs flush with the corners | The table row that exists; leg position and span stated. |
| C-003 "heavy plate trestle" | 12 mm plates as in §3 | Dimensions stated so the mass and cost failures (+111 %, +53 %) follow from them. |
| slot length unstated | 9 × 22 mm | From the movement at the fixing (7.05 mm) with 45.8 % margin. |
