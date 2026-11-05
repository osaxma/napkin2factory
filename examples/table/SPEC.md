# Benchmark Tier 1: oak-and-steel table (`SPEC.md`)

The simple tier of the benchmark ladder (road-to-v1.0 §4, Track A §2.2). An agent builds a
product from this file alone; `SPEC.oracle.yaml` is written from §7 and checks the result.
Every figure below is worked from the stated geometry (road-to-v1.0 §4.1). Worked by hand on
2026-11-04; a second vendor re-derives it before the oracle is frozen (v0.7 W9).
Re-derived independently by a second model from this file alone on 2026-11-04: all 140
figures agreed within 0.35 %. That check was made before the cross-grain revision of
2026-11-05 (S-229, §3.4 and §4.1), which adds a steel cross rail under the middle of the top
and moves C-002's figures; §8.1 lists every figure it changed (old → new). A second model
re-derived those 44 figures and their intermediates from this file alone on 2026-11-05: all
agreed within 0.35 %, every outcome at least 30 % from its threshold.

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
| Load footprint | the 150 kg stands on a 100 × 100 mm base, centred on the top | spec's choice (§4.1) |
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
2. **Centre-load sag.** Mid-span sag under 1471.5 N at the middle (on a 100 × 100 mm base, over
   the cross rail) plus the self weight of the spanning members, with the cross rail's dip
   between the long rails added, ≤ 2.5 mm. Computed.
3. **Long-term sag.** Final sag under the sustained load (490.5 N at the middle plus self
   weight), timber creep included, with the cross rail's dip added, ≤ 2.5 mm. Computed.
4. **Strength.** Yield factor ≥ 1.5 in every spanning member (top, long rails, cross rail)
   under the loads of requirement 2. Computed.
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
13. **Leg room.** No member between the legs below the apron. Inspection. (The cross rail sits
    at the apron and hangs 25 mm below its lower edge: the one departure, §3.4.)
14. **Top bearing.** Bearing factor ≥ 1.5 for the oak top resting across its grain on the cross
    rail under the 1471.5 N centre load on its 100 × 100 mm base. Computed.

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
- Fixing tabs: 6 × 40 × 40 × 4 mm steel plate welded to the rails' inner faces, top faces
  flush with the rails. Four on the long rails (x = ±300, y = ±280, i.e. 20 mm in from the rail
  face, 300 mm either side of the middle) with a 9 × 22 mm slot running across the width; two
  on the short rails (x = ±680, y = 0) with a round 9 mm hole (these fix the top's centreline).
- Cross rail (a part of its own, `geometry.kit.tube`, S-229): 75 × 75 × 1.5 mm square tube,
  mild steel, 600 mm long, running across the width at x = 0 and welded at both ends to the
  inner faces of the long rails (y = ±300). Its top face is flush with the long rails' top
  faces, so the top rests on it; no screw, the top slides on it. It hangs 25 mm below the
  long rails (its underside 625 mm above the floor).
- Hardware: 6 M8 × 20 flanged inserts in the top, 6 M8 × 25 button-head screws with washers,
  4 M10 levelling glides.
- Sag model: the top and the two long rails bend together along the length as one simply
  supported beam between leg centres, span 1450 mm. Their EI add (the slotted fixings carry
  no shear, so there is no composite action); the full 800 mm width of the top acts; legs and
  short rails are rigid supports. Self weight (top plus long rails) is spread over the span;
  the relieving moment of the 75 mm end overhangs is ignored (conservative). The centre load
  stands on a 100 × 100 mm base over the cross rail, which carries it across to the long rails
  as a simply supported beam of span 650 mm (rail centre to rail centre) with the load at
  midspan; the oak resting on it is given no share. The weight of the cross rail (20.4 N)
  joins the load at the middle of the long-rail beam. The sag is the sag along the length plus
  the cross rail's dip (§4.1).

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

### 3.4 What the cross-grain check changed in C-002 (S-229)

The landed spec (2026-11-04) took the top and the long rails as one beam along the length and
assumed the 150 kg at the middle reached the rails through the oak. §4.1 works that
assumption: the grain runs along the length, so across the 650 mm between the rails the top is
soft, and left alone it dishes 3.79 mm under the load (3.88 mm for a point load), more than the
whole 2.5 mm limit before the 1.60 mm of sag along the length is added. The design changes
below follow; the other cards are unchanged.

| What | Landed spec | Now | Why |
|---|---|---|---|
| Member under the middle | none | cross rail, 75 × 75 × 1.5 mm tube, 600 mm, welded between the long rails | carries the centre load across to the long rails; the frame kit builds legs and perimeter rails only, so it is a part of its own (cut from the `tube` kit) |
| Its section | — | 75 × 75 × 1.5 | chosen from the scan below: sag, mass and ECR-1 margins all ≥ 31 % (70 × 70 passes at 30.8 % on the sag, too close to the line) |
| Long-rail fixing tabs | 6 (x = −600, 0, 600) | 4 (x = ±300) | the middle pair sat where the cross rail is welded in |
| Fixings of the top (tabs, inserts, screws) | 8 | 6 | the same |
| Hardware set of C-002 | 0.560 kg, 36.0 USD | 0.500 kg, 31.0 USD | six inserts and six screws instead of eight; C-001 and C-003 keep eight each |
| ECR-1 (§6) | top 30 → 32 mm | top 30 → 31 mm | at 32 mm the planned change gives 49.1 kg, a mass margin of 29.8 % |
| Requirements | 15 | 16 (REQ-016, top bearing) | the oak meets the steel across its grain at the cross rail |

Section scan (square tube, 1.5 mm wall unless stated; six fixings; load at the middle; ECR-1 at
31 mm):

| Cross rail | I (mm⁴) | Table mass, margin | Sag, margin | ECR-1 mass margin |
|---|---|---|---|---|
| 50 × 50 (the frame's stock) | 114 193 | 46.51 kg, 33.6 % | 1.96 mm, 21.5 % | 32.2 % |
| 60 × 60 | 200 333 | 46.79 kg, 33.2 % | 1.81 mm, 27.8 % | 31.8 % |
| 60 × 60 × 2 | 260 459 | 47.32 kg, 32.4 % | 1.76 mm, 29.5 % | 31.0 % |
| 70 × 70 | 321 573 | 47.07 kg, 32.8 % | 1.73 mm, 30.8 % | 31.4 % |
| **75 × 75** | 397 231 | 47.21 kg, 32.6 % | 1.71 mm, 31.8 % | 31.2 % |
| 80 × 80 | 483 913 | 47.35 kg, 32.4 % | 1.69 mm, 32.5 % | 31.0 % |

Other ways to meet the limit, and why not: a thicker top alone (the dish scales with the
thickness to the power −3): a total sag of 1.75 mm needs about 49 mm of oak, a table of about
63 kg (9 % under the mass limit, short of the 30 % margin). Credit for the partial fixity of the
welded ends would let a lighter tube pass (a rough estimate from the long rails' torsional
stiffness takes about a quarter off the dip of the 50 × 50 tube), but it is not taken.

The cross rail protects the middle only. The requirement is for the middle (the owner's words);
a 150 kg base elsewhere on the centre line is not covered, and the top would dish there as in
§4.1. The manual says so.

## 4. Worked calculations

### 4.0 Inputs

| Input | Value | Source |
|---|---|---|
| mild steel | ρ 7850 kg/m³, E 200 GPa, σy 250 MPa | `materials.yaml` row `mild steel` (ASTM A36 / EN 10025-2 S235; ASM Handbook Vol 1) [verify] |
| white-oak | ρ 750 kg/m³, E 12.3 GPa, proportional-limit stress 55.2 MPa (12 % MC) | `materials.yaml` row `white-oak` (USDA Wood Handbook FPL-GTR-190 Table 5-3a) [verify] |
| southern-yellow-pine | ρ 590 kg/m³, E 12.3 GPa, proportional-limit stress 49.6 MPa (12 % MC) | `materials.yaml` row `southern-yellow-pine` (FPL-GTR-190 Table 5-3b) [verify] |
| oak across-grain change | C_T = 0.00365 per % MC | `wood_movement.yaml` row `white-oak` (FPL-GTR-190 Ch. 4) [verify] |
| oak across-grain stiffness | E_T / E_L = 0.072, so E_T = 0.072 × 12 300 = 885.6 MPa (the 10 % the handbook allows on E_L from bending is not taken) | FPL-GTR-190 Table 5-1, white oak, 12 % MC [verify] |
| oak across-grain strength | compression ⟂ grain 7.4 MPa (fibre stress at proportional limit); tension ⟂ grain 5.5 MPa (maximum) | FPL-GTR-190 Table 5-3a, white oak (*Quercus alba*), 12 % MC [verify] |
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

Hardware sets. C-001 and C-003 (4 glides, 8 inserts, 8 screws): mass 4 × 0.080 + 8 × 0.010 +
8 × 0.020 = **0.560 kg**; cost 4 × 4.00 + 8 × 1.50 + 8 × 1.00 = **36.0 USD**. C-002 (4 glides, and
one insert and one screw for each of its 6 fixings): mass 0.320 + 0.060 + 0.120 = **0.500 kg**;
cost 16.0 + 9.0 + 6.0 = **31.0 USD**. Both are the same at both band ends. Holes, slots and
weld fillets are not subtracted or added (< 0.05 kg per card).

Modelling choices (the spec's own; each is conservative or below the tolerances):
- **Glides.** Each glide is a pin at the floor: its 20 mm M10 stem is taken as rigid in both
  leg buckling (uniform 50 × 50 × 1.5 tube over the full 720 mm, no stepped column) and racking
  (no stem bending in the sway). The glide pad diameter is not used: the tipping edge is the
  glide centreline, inside the pad's outer edge.
- **Sag self weight** counts the top and the long rails as a uniform load, and the cross rail
  (2.077 kg, 20.4 N) as a point load at the middle; the four long-rail tabs
  (4 × 0.0502 = 0.201 kg, 1.97 N) are left out, which changes the sag by 0.001 mm (0.1 %).
- **Top width.** Along the length, the full 800 mm of the top acts in bending: no shear-lag or
  effective-width reduction across the span between the rails. Across the grain the top is
  not trusted with the centre load at all (§4.1).
- **Cross rail.** A simply supported beam of span 650 mm (rail centre to rail centre; the
  600 mm clear span would give a dip 21 % smaller), load at midspan, steel only: the oak on it
  gets no share, the partial fixity of the welded ends is not credited, and its own weight is
  not in the dip (0.2 %).
- **Load footprint.** The 150 kg stands on a 100 × 100 mm base, centred over the cross rail: a
  heavy tool, anvil or stack of stock, or a person kneeling or sitting, spreads over more than
  that, so a small base is the harder case for bearing and costs little for the dip (§4.1).
- **End overhangs.** The 75 mm (C-002) top overhangs past the supports are ignored in both the
  sag and the bending moment; their counter-moment would only reduce both.
- **Welds.** Weld leg size and throat are not specified; the corner capacity rests on the tube's
  section modulus times the efficiency η = 0.7 (full-perimeter fillet weld assumed).

Cost rule: a card passes when the band's **high** end ≤ budget and is rejected when its **low**
end > budget, so neither outcome depends on where in the band the real price falls.

### 4.1 C-002

**The top across its grain** (the check that added the cross rail, §3.4). The grain runs along
the 1600 mm length, so across the 650 mm between the long rails (centre to centre) the oak is
soft: E_T = 885.6 MPa against E_L = 12 300 MPa (§4.0). Model: the top as an orthotropic plate,
t = 30 mm, endless along the length, simply supported on the two long rails and on nothing
else; its twisting stiffness and Poisson coupling are left out (both only stiffen it). Per
millimetre of width, D_x = E_L t³/12 = 12 300 × 2250 = 2.7675 × 10⁷ N·mm and
D_y = E_T t³/12 = 885.6 × 2250 = 1.9926 × 10⁶ N·mm. A point load F at the middle gives, from
the Fourier series of the plate equation D_x w,xxxx + D_y w,yyyy = q summed over the odd
half-waves across the width,

  w = F b² S / (√2 π³ D_x^¼ D_y^¾), with S = Σ 1/n³ over odd n = 7ζ(3)/8 = 1.0518 and b = 650 mm.

D_x^¼ = 72.53 and D_y^¾ = 53 035, so w = 1471.5 × 422 500 × 1.0518 / (43.85 × 72.53 × 53 035)
= 6.539 × 10⁸ / 1.687 × 10⁸ = **3.88 mm** (3.877).

The load is not a point (the footprint is a spec choice, §4.0). On a 100 × 100 mm base (the
same plate by a double Fourier series, 12 m long so the ends do not matter) the dish is
**3.79 mm**, the cross-grain bending moment is M_y = 263 N·mm per mm and the bending stress is
σ = 6 M_y/t² = 6 × 263.2/900 = **1.75 MPa**; a point load would make the stress unbounded,
which is why the base is stated. On a 300 × 300 mm base: 3.34 mm and 1.12 MPa. Where the model
errs: hinging the plate at the short rails, 725 mm from the middle (the real top is continuous
over them), gives 3.93 mm and 1.80 MPa; adding the twisting stiffness (G_LT taken as G_LR =
0.086 E_L = 1.06 GPa, because the handbook has no G_LT for white oak) gives 2.96 mm. The strip
across the full 650 mm that gate review I used gives 6.50 mm and 2.45 MPa; it overstates both,
because the stiff grain spreads the load over about 1.1 m along the length.

Reading it. The oak would not break: tension across the grain 5.5 MPa against 1.75 MPa is a
factor **3.1** ≥ 1.5 (hinged: 3.06). It would dish: 3.79 mm alone is 52 % over the 2.5 mm limit,
and with the 1.60 mm of sag along the length (below) the unsupported top sags 5.39 mm, 116 % over.
The landed spec's 1.58 mm assumed the load reached the long rails through the oak; it does
not. So the load is given a path that does not depend on the oak across its grain: the cross
rail of §3, a steel beam from rail to rail under the middle, with the top resting on it. The
rest of this section is C-002 with the cross rail.

**Section properties** (hollow square, `structural.rect_tube_section`; plate,
`structural.rect_section`; Roark Table A.1):
- Tube 50 × 50 × 1.5 (legs and rails): A = 50² − 47² = 2500 − 2209 = **291 mm²**;
  I = (50⁴ − 47⁴)/12 = (6 250 000 − 4 879 681)/12 = **114 193 mm⁴** (114 193.25);
  Z = I/25 = **4 568 mm³** (4 567.73); r = √(I/A) = √392.42 = **19.8 mm** (19.810);
  mass per metre 291 × 10⁻⁶ m² × 7850 = **2.284 kg/m** (2.28435).
- Cross rail 75 × 75 × 1.5: A = 75² − 72² = 5625 − 5184 = **441 mm²**;
  I = (75⁴ − 72⁴)/12 = (31 640 625 − 26 873 856)/12 = **397 231 mm⁴** (397 230.75);
  Z = I/37.5 = **10 593 mm³** (10 592.8); mass per metre 441 × 10⁻⁶ × 7850 = **3.462 kg/m**.
- Top 800 × 30: I = 800 × 30³/12 = **1.80 × 10⁶ mm⁴**; Z = 800 × 30²/6 = **120 000 mm³**.

**Mass roll-up** (density × volume, `mass_cost.mass`):

| Part | Volume | Mass |
|---|---|---|
| top-board | 1600 × 800 × 30 = 38.4 × 10⁶ mm³ × 750 kg/m³ | 28.8 kg |
| apron-frame tube | (4 × 700 + 2 × 1400 + 2 × 600) = 6800 mm × 291 mm² = 1.979 × 10⁶ mm³ × 7850 | 15.53 kg (15.534) |
| apron-frame tabs | 6 × 40 × 40 × 4 = 38 400 mm³ × 7850 | 0.301 kg |
| apron-frame total | | **15.8 kg** (15.835) |
| cross-rail | 600 × 441 = 264 600 mm³ × 7850 | **2.08 kg** (2.077) |
| hardware set | §4.0 | 0.500 kg |
| **Table** | 28.8 + 15.835 + 2.077 + 0.500 | **47.2 kg** (47.212) |

Margin against 70 kg: (70 − 47.2)/70 = **32.6 %**. Weight W_table = 47.212 × 9.80665 = 463.0 N.

**Cost roll-up** (band × mass, `mass_cost.cost_estimate`, US, [verify]):
top 28.8 kg × 9.0 to 22.0 = 259.2 to 633.6 USD; frame 15.835 kg × 19.5 = 308.8 USD; cross rail
2.077 kg × 19.5 = 40.5 USD; hardware 31.0. Total **639 to 1014 USD** (639.5 to 1013.9). Margin
of the high end against 1600 USD: (1600 − 1013.9)/1600 = **36.6 %**.

**Sag** (`structural.beam_deflection_simply_supported`, Roark Table 8.1 cases 1d and 1e). Along
the length, the top and long rails as one beam:
- EI_top = 12 300 × 1.80 × 10⁶ = 2.214 × 10¹⁰; EI_rails = 2 × 200 000 × 114 193.25
  = 4.568 × 10¹⁰ (4.5677); ΣEI = **6.78 × 10¹⁰ N·mm²** (6.7817).
- L = 1450, L³ = 3.0486 × 10⁹ mm³. The cross rail's weight, 2.07711 × 9.80665 = 20.37 N, joins
  the load at the middle.
- Point: δ_P = (F + 20.37) L³/(48 ΣEI) = 1491.87 × 3.0486 × 10⁹ / (48 × 6.7817 × 10¹⁰)
  = 4.5481 × 10¹²/3.2552 × 10¹² = **1.40 mm** (1.397).
- Self weight: top 28.8 kg + long rails 2 × 1400 mm × 2.28435 kg/m = 6.396 kg → 35.196 kg,
  W = 35.196 × 9.80665 = 345.2 N. δ_W = 5 W L³/(384 ΣEI) = 5 × 345.16 × 3.0486 × 10⁹ /
  (384 × 6.7817 × 10¹⁰) = 5.2613 × 10¹²/2.6042 × 10¹³ = **0.202 mm**.
- Along the length: 1.397 + 0.202 = **1.60 mm** (1.599).

The cross rail, carrying the whole 1471.5 N at its middle between the long rails (span
L_c = 650 mm, L_c³ = 2.74625 × 10⁸ mm³):
- δ_c = F L_c³/(48 E I_c) = 1471.5 × 2.74625 × 10⁸ / (48 × 200 000 × 397 230.75)
  = 4.0411 × 10¹¹/3.8134 × 10¹² = **0.106 mm** (0.10597).

Total **1.71 mm** (1.705) ≤ 2.5 × 1.0; margin **31.8 %**.

**Bending stress and yield factor** (`structural.beam_bending_stress`; members bending together
share the moment in proportion to EI, so σ_i = M E_i c_i / ΣEI):
- M = (F + 20.37) L/4 + W L/8 = 540 803 + 62 560 = **6.03 × 10⁵ N·mm** (603 362).
- Top (c = 15): σ = 603 362 × 12 300 × 15 / 6.7817 × 10¹⁰ = **1.64 MPa**; factor 55.2/1.6415
  = **33.6** ≥ 1.5 (margin 2140 %).
- Long rails (c = 25): σ = 603 362 × 200 000 × 25 / 6.7817 × 10¹⁰ = **44.5 MPa**; factor
  250/44.48 = **5.62** ≥ 1.5 (margin 275 %). The long rails govern.
- Cross rail: M_c = F L_c/4 = 1471.5 × 650/4 = 239 119 N·mm; σ = 239 119/10 592.8 = **22.6 MPa**;
  factor 250/22.57 = **11.1** ≥ 1.5 (margin 638 %).

**Bearing of the top on the cross rail** (the oak meets the steel across its grain). The load
stands on its 100 × 100 mm base over the cross rail and reaches the oak through the rail's top
face, 75 mm wide (the tube's full face; its real corner radii would take a few mm off) and
100 mm long: 75 × 100 = 7500 mm², so 1471.5/7500 = **0.196 MPa** across the grain. Against the
7.4 MPa compression limit (fibre stress at proportional limit, §4.0) the factor is
7.4/0.1962 = **37.7** ≥ 1.5 (margin 2410 %).

**Long-term sag** (EN 1995-1-1 §2.3.2.2: the timber member's final modulus E/(1 + k_def); steel
does not creep):
- EI_fin = 12 300/1.60 × 1.80 × 10⁶ + 4.5677 × 10¹⁰ = 1.3838 × 10¹⁰ + 4.5677 × 10¹⁰
  = 5.9515 × 10¹⁰.
- Along the length: δ_fin = L³ ((F_s + 20.37)/48 + 5W/384)/EI_fin = 3.0486 × 10⁹ ×
  (10.643 + 4.494)/5.9515 × 10¹⁰ = 4.6147 × 10¹⁰/5.9515 × 10¹⁰ = 0.775 mm.
- The cross rail's dip under the sustained load (steel, no creep):
  490.5 × 2.74625 × 10⁸ / (48 × 200 000 × 397 230.75) = 0.035 mm.
- Total **0.811 mm** (0.8107) ≤ 2.5; margin **67.6 %**.
- Note: `joints.wood_creep_deflection` multiplies the whole elastic sag by 1.6
  (0.716 × 1.6 = 1.15 mm); that overstates a steel-and-wood pair. The oracle asserts 0.811 mm.

**Leg buckling** (Johnson parabola, Shigley *Mechanical Engineering Design*, intermediate
columns; the slenderness is below the Euler limit, so `structural.euler_buckling_load` refuses
this column, by design):
- Load: P = 1471.5 + 463.0/4 = **1587 N** (1587.25).
- KL = 2.0 × 720 (floor to the underside of the top) = 1440 mm; KL/r = 1440/19.810 = **72.7**;
  Euler limit √(2π²E/σy) = √(2π² × 200 000/250) = **125.7**; 72.7 < 125.7, so Johnson applies.
- σ_cr = σy − (σy · KL/r / 2π)²/E = 250 − (250 × 72.69/6.2832)²/200 000 = 250 − 41.83
  = **208 MPa**; P_cr = 208.17 × 291 = **60 600 N** (60 578).
- Factor 60 578/1587.25 = **38.2** ≥ 2.0 (margin 1810 %).

**Tip-over** (`structural.tip_over_safety_factor`, FS = m g x_cg / (F x_edge)). The CG is at the
plan centre (the frame and the cross rail are symmetric and centred under the top); its height
does not enter for vertical loads. Tipping edge: the line through the two front glide centres,
y = 325 (conservative: the glide pad's outer edge is further out).
- Long (front) edge: x_cg = 325, x_edge = 400 − 325 = 75. Restoring 463.0 × 0.325
  = 150.5 N·m; overturning 490.5 × 0.075 = 36.8 N·m; FS = **4.09** ≥ 2.0 (margin 104 %).
- End edge: x_cg = 725, x_edge = 75: FS = 463.0 × 0.725/36.79 = 9.12. The front edge governs.

**Racking** (`joints.frame_racking`, pinned bases: δ = P H³/(6 E I_c) + P H² L/(12 E I_b),
Roark Table 8.2 and slope-deflection). Glides are pins; welded corners rigid; the top's
stiffening as a diaphragm and the cross rail's are ignored (conservative). H = 750 − 30 − 25
= 695 (floor to the rail centreline). A push along the length is shared by the front and back
frames, P = 150 N each, L = 1450:
- Columns: 150 × 695³/(6 × 200 000 × 114 193.25) = 5.0355 × 10¹⁰/1.3703 × 10¹¹ = 0.367 mm.
- Rail: 150 × 695² × 1450/(12 × 200 000 × 114 193.25) = 1.0506 × 10¹¹/2.7406 × 10¹¹ = 0.383 mm.
- Sway **0.751 mm**; across the width (L = 650) the rail term is 0.172 mm and the sway 0.539 mm,
  so along the length governs. Factored 2.0 × 0.7508 = 1.50 mm ≤ 3.0; margin **49.9 %**.
- Corner moment (`joints.joint_moment_capacity`, welded M = Z σy η): each of four legs takes
  75 N of shear, M = 75 × 695 = 52 125 N·mm; capacity 4567.73 × 250 × 0.7 = 799 353 N·mm;
  factor **15.3** ≥ 2.0 (margin 667 %).

**Insert pull-out** (`joints.insert_pullout`). Case: the assembled table is lifted by its top,
the base hanging; conservatively two inserts carry the whole base (a warped base hangs on two).
Base = frame 15.835 + cross rail 2.077 + glides 0.320 + screws 0.120 = 18.352 kg → 180.0 N.
Capacity 2 × 6800 = 13 600 N; factor 13 600/180.0 = **75.6** ≥ 2.5 (margin 2920 %).

**Wood movement** (`joints.wood_movement`, ΔW = W C_T ΔMC, FPL-GTR-190 Ch. 4). ΔMC = 13.1 − 6.2
= 6.9 points. The cross rail is not fixed to the top and does not restrain it.
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

Across the grain: nothing to add. The top rests on four corner plates, so the load travels
along the grain to them (the stiff direction); the cross-grain check of §4.1 has no rail pair
to cross, and the rejection stands on the sag alone.

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

Across the grain: nothing to add. The top rests on two bars 700 mm long that run across its
whole width (80 mm wide each, at x = ±600), so the load at the middle travels along the grain
to the bars; there is no pair of long rails for it to cross to.

## 5. Chosen design (C-002): parts and interfaces

| # | Part | Process | Material | Description |
|---|---|---|---|---|
| 1 | top-board | woodworking | white-oak | 1600 × 800 × 30 mm, edge-glued, grain along the length; 6 M8 insert ports underneath at the tab positions of §3 |
| 2 | apron-frame | welding | mild steel, powder-coated | `geometry.kit.frame`, 1500 × 700 × 700 mm outer, 50 × 50 × 1.5 square tube, `top_rails: true`, `bottom_rails: false`; 6 fixing tabs (4 slotted 9 × 22 mm, 2 round Ø 9 mm); M10 thread at each leg foot |
| 3 | cross-rail | welding | mild steel, powder-coated | `geometry.kit.tube`, 75 × 75 × 1.5 square tube, 600 mm, across the width at x = 0, welded to the inner faces of the long rails, top face flush with them (§3, §3.4) |
| 4 | leveling-foot | COTS × 4 | steel/nylon | M10 levelling glide with its tube-end insert, 20 mm set height |
| 5 | wood-insert-m8 | COTS × 6 | zinc alloy | M8 × 20 flanged threaded wood insert |
| 6 | mounting-bolt-m8 | COTS × 6 | steel | M8 × 25 button-head hex screw with ISO 7089 washer (25 − 4 tab − 1.6 washer = 19.4 mm into a 20 mm insert) |

Interfaces:
- top-board ↔ apron-frame: 6 × `threaded-insert` (M8), the four long-rail ones (x = ±300) slotted
  across the width, the two short-rail ones round (they locate the top's centreline).
- apron-frame ↔ cross-rail: one `mating-face`, the weld at both ends (no loose hardware).
- leveling-foot ↔ apron-frame: 4 × `threaded-insert` (M10) at the leg feet.

One sub-assembly level (flat), one domain (mechanical), no supply, ceremony `lite`.

## 6. Planned change requests

1. **ECR-1, parametric: top 30 → 31 mm** (the owner wants a slightly heavier look; legs shorten
   to 699 mm to keep 750; 31, not 32, because of the mass margin, §3.4). Expected:
   **accepted**, every requirement still passes by ≥ 30 %. Top 1600 × 800 × 31 × 750 = 29.76 kg;
   frame (4 × 699 + 4000) = 6796 mm × 2.28435 kg/m + 0.301 = 15.826 kg; cross rail 2.077 kg;
   hardware 0.500 kg; table **48.2 kg** (48.163; margin 31.2 %). Cost 29.76 × 9.0 to 22.0
   = 267.8 to 654.7, steel (15.826 + 2.077) × 19.5 = 349.1, hardware 31.0: **648 to 1035 USD**
   (647.9 to 1034.8; margin 35.3 %). Sag: EI_top = 12 300 × 800 × 31³/12 = 2.4429 × 10¹⁰,
   ΣEI = 7.0106 × 10¹⁰, δ_P = 4.5481 × 10¹²/(48 × 7.0106 × 10¹⁰) = 1.352 mm; W = (29.76 +
   6.396) × 9.80665 = 354.6 N, δ_W = 5 × 354.57 × 3.0486 × 10⁹/(384 × 7.0106 × 10¹⁰) = 0.201 mm;
   cross rail dip 0.106 mm; sag **1.66 mm** (1.658; margin 33.7 %). Tip-over 48.163 × 9.80665 ×
   0.325/36.79 = **4.17** (margin 109 %). Strength, creep, buckling, racking, pull-out and
   movement keep margins far above 30 % (a thicker top only stiffens it; the cross rail does
   not depend on it). The screws reach 19.4 mm into a 31 mm top.
2. **ECR-2, design: a 500 mm seating overhang at one end** (top 2100 × 800 × 30, base unchanged,
   one end of the top 575 mm beyond the end glides). Expected: **refused**, the tip-over
   requirement (6) fails and n2f names it. Top 37.8 kg with its centre at x = +250; table
   56.21 kg (37.8 + 15.835 + 2.077 + 0.500); CG x = 37.8 × 250/56.212 = 168.1 mm. Tipping
   edge: the end glides at x = 725; arm 725 − 168.1 = 556.9 mm; edge load at x = 1300, 575 mm
   out. FS = 56.212 × 9.80665 × 0.5569 / (490.5 × 0.575) = 307.0/282.0 = **1.09** < 2.0
   (46 % below).

## 7. Expected outcomes

| Card | Outcome | Deciding check |
|---|---|---|
| C-001 | rejected | structural: sag 14.3 mm > 2.5 mm (+470 %) |
| C-002 | promoted (chosen) | passes all; closest margins: sag 31.8 %, mass 32.6 %, cost 36.6 % |
| C-003 | rejected | mass 148 kg > 70 kg (+111 %); cost low end 2450 USD > 1600 USD (+53.2 %) |

| Figure | C-001 | C-002 | C-003 | Tolerance |
|---|---|---|---|---|
| mid-span sag, centre load + self weight (mm) | 14.3 | 1.71 (1.60 along the length + 0.106 cross rail) | 0.837 | ± 5 % |
| total mass (kg) | 24.7 | 47.2 | 148 | ± 2 % |
| cost band (USD, US, 2026-11) | 332–548 | 639–1014 | 2450–3010 | ± 2 % each end |
| tip-over factor (governing edge) | 9.38 | 4.09 | 10.2 | ± 5 % |
| top yield factor | 5.28 | 33.6 | — | ± 5 % |
| long-rail yield factor | — | 5.62 | — | ± 5 % |
| cross rail yield factor | — | 11.1 | — | ± 5 % |
| cross rail dip (mm) | — | 0.106 | — | ± 5 % |
| top bearing factor (across the grain) | — | 37.7 | — | ± 5 % |
| long-term sag (mm) | — | 0.811 | — | ± 5 % |
| leg buckling factor (Johnson) | — | 38.2 | — | ± 5 % |
| racking sway, 300 N (mm) | — | 0.751 | — | ± 5 % |
| corner joint factor | — | 15.3 | — | ± 5 % |
| insert pull-out factor | — | 75.6 | — | ± 5 % |
| across-grain movement at a slot (mm) | — | 7.05 | — | ± 5 % |
| dish of the top with nothing under it (mm; information, no requirement bounds it) | — | 3.88 (point), 3.79 (100 × 100 mm base) | — | ± 5 % |
| ECR-1 / ECR-2 | — | accepted (1.66 mm, 48.2 kg, 648–1035 USD, tip-over 4.17) / refused (tip-over 1.09) | — | as above |

Gate statuses for C-002's product: `lite` ceremony; one `safety: true` requirement (tip-over)
with one sign-off; every computed requirement in §2 passes.

## 8. Changes from Track A's draft

| Draft (Track A §2.2) | Here | Why |
|---|---|---|
| mass limit 55 kg | 70 kg | 55 kg needs C-002 ≤ 38.5 kg. A scan of common tube sizes and 25–30 mm tops found nothing better than 38.4 kg with 1.73 mm sag (25 mm top, 60 × 30 × 1.5 rails, 40 × 40 × 1.5 legs, two stocks): both 30–31 % inside their limits, a borderline card. C-002 here is 47.2 kg. |
| budget 450 USD | 1600 USD | The repository's own bands (woodworking 9–22 USD/kg, welding 19.5 USD/kg) price the oak top alone at 259–634 USD. C-002's high end is 1014 USD, C-003's low end 2450 USD. |
| C-002 top 35 mm | 30 mm | Mass (Track A suggested it). ECR-1 goes to 31 mm, not 35 or 32: at 35 mm the mass margin is 25.8 % (51.97 kg), at 32 mm 29.8 % (49.11 kg). |
| legs 50 × 50 × 2, rails 50 × 25 × 2 | frame members all 50 × 50 × 1.5, plus a 75 × 75 × 1.5 cross rail | The frame kit cuts every member from one stock (`frame.py` `MemberSpec`); the thinner wall keeps mass under the margin while the square rails keep the sag margin (31.8 % with the cross rail, §3.4). |
| oak E 12.5 GPa | 12.3 GPa | The `materials.yaml` row (FPL-GTR-190 Table 5-3a). |
| bolts M8 × 35 | M8 × 25 | M8 × 35 through a 4 mm tab would reach 29.4 mm into a 30 mm top. |
| C-001 top "pine" | southern-yellow-pine, legs flush with the corners | The table row that exists; leg position and span stated. |
| C-003 "heavy plate trestle" | 12 mm plates as in §3 | Dimensions stated so the mass and cost failures (+111 %, +53 %) follow from them. |
| slot length unstated | 9 × 22 mm | From the movement at the fixing (7.05 mm) with 45.8 % margin. |
| (not in the draft) the top carries the centre load across to the long rails | a cross rail carries it; the oak is not trusted across its grain | §4.1: the unsupported top dishes 3.79 mm under the 150 kg on a 100 × 100 mm base. Gate review I, concern C8. |

### 8.1 Figures the cross-grain revision changed (old → new)

For a second re-derivation. C-001 and C-003 are unchanged; so are the wood movement
(7.05 mm, 5.95 mm clearance), the racking sway (0.751 mm, 1.50 mm factored), the corner joint
factor (15.3) and every input of §1 except the load footprint.

| Figure (C-002) | Old | New |
|---|---|---|
| fixings of the top (tabs, inserts, screws) | 8 (6 long-rail, 2 short-rail) | 6 (4 long-rail at x = ±300, 2 short-rail) |
| hardware set (kg, USD) | 0.560, 36.0 | 0.500, 31.0 |
| apron-frame mass (kg) | 15.936 | 15.835 |
| cross rail mass (kg) | — | 2.077 |
| table mass (kg), margin | 45.296, 35.3 % | 47.212, 32.6 % |
| table weight (N) | 444.2 | 463.0 |
| cost band (USD), high-end margin | 605.9 to 980.3, 38.7 % | 639.5 to 1013.9, 36.6 % |
| frame cost (USD) | 310.7 | 308.8 (cross rail 40.5) |
| sag along the length (mm) | 1.580 (1.378 point + 0.202 weight) | 1.599 (1.397 + 0.202) |
| cross rail dip (mm) | — | 0.106 |
| centre-load sag (mm), margin | 1.580, 36.8 % | 1.705, 31.8 % |
| bending moment M (N·mm) | 595 978 | 603 362 |
| top stress (MPa), factor | 1.621, 34.0 | 1.641, 33.6 |
| long-rail stress (MPa), factor | 43.94, 5.69 | 44.48, 5.62 |
| cross rail stress (MPa), factor | — | 22.57, 11.1 |
| top bearing (MPa), factor | — | 0.196, 37.7 |
| long-term sag (mm), margin | 0.754, 69.9 % | 0.811, 67.6 % |
| leg buckling load (N), factor | 1582.55, 38.3 | 1587.25, 38.2 |
| tip-over factor (front edge, end edge) | 3.92, 8.75 | 4.09, 9.12 |
| insert pull-out: base (kg, N), factor | 16.416, 161.0, 84.5 | 18.352, 180.0, 75.6 |
| ECR-1 | 32 mm: 47.2 kg, 623–1022 USD, 1.49 mm, tip-over 4.09 | 31 mm: 48.2 kg, 648–1035 USD, 1.66 mm, tip-over 4.17 |
| ECR-2 tip-over factor | 1.04 | 1.09 |
| requirements, parts | 15, 5 | 16, 6 |
