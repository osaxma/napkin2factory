"""Tests for the joints, wood, fatigue and load-case structural mechanics pack (W1).

Covers:
- All reference cases in ``joints.CASES`` tested via ``calckit._cases.run_pack``.
- Hand calculations with worked numbers in comments.
- Unit errors: bare numbers raise :class:`napkin2factory.core.units.UnitError`.
- Loosening refusal: ``factor_of_safety`` refuses a factor lower than the default.
- Missing S-N failure: ``fatigue_margin`` fails loudly for non-ferrous materials
  without an endurance limit when ``sn_strength`` is omitted.
"""

from __future__ import annotations

import pytest

from napkin2factory.calckit import _cases, joints
from napkin2factory.calckit.joints import (
    PortalFrame,
    factor_of_safety,
    fatigue_margin,
    frame_racking,
    insert_pullout,
    joint_moment_capacity,
    lag_screw_withdrawal,
    wood_creep_deflection,
    wood_movement,
    wood_screw_withdrawal,
)
from napkin2factory.core.units import Quantity as Q
from napkin2factory.core.units import UnitError

# --- 1. Cases suite -----------------------------------------------------------------


def test_every_joint_function_has_a_case_and_every_case_passes() -> None:
    """Every public function in joints has at least one reference case that passes."""
    funcs = _cases.public_functions(joints)
    assert funcs, "joints has no public functions"
    uncovered = _cases.uncovered(joints)
    assert uncovered == [], f"uncovered functions in joints: {uncovered}"
    for case, outcome in _cases.run_pack(joints):
        assert outcome.ok, (
            f"{case.fn} failed: {outcome.message} "
            f"(expected {outcome.expected}, got {outcome.actual})"
        )
        assert case.source.strip(), f"{case.fn} case missing source citation"


def test_joints_has_external_cases_with_precise_citations() -> None:
    """The pack has external reference cases citing published handbooks."""
    external = [c for c in joints.CASES if c.external]
    assert len(external) >= 4, f"expected at least 4 external cases, got {len(external)}"
    for c in external:
        assert not c.source.lower().startswith("hand computation"), c.source
        assert len(c.source) > 40, f"citation too short: {c.source!r}"


# --- 2. Withdrawal calcs ------------------------------------------------------------


def test_wood_screw_withdrawal_hand_worked() -> None:
    """Hand check for wood screw withdrawal per NDS-2018 Section 12.2.1.

    Formula: W = 2850 * G^2 * D (lbs/in).
    Given:
      - Screw: #10 (shank diameter D = 0.190 inch = 4.826 mm)
      - Substrate: White oak, specific gravity G = 0.68
      - Thread penetration: L = 1.0 inch = 25.4 mm
    Worked:
      - G^2 = 0.68^2 = 0.4624
      - W = 2850 * 0.4624 * 0.190 = 250.3956 lbs/in
      - Total capacity = W * 1.0 in = 250.3956 lbs
      - In Newtons: 250.3956 * 4.448221615 = 1113.815 N
    """
    res = wood_screw_withdrawal(Q(0.190, "inch"), Q(1.0, "inch"), 0.68)
    expected_n = 250.3896 * 4.4482216152605
    assert abs(res.to("N").magnitude - expected_n) < 1e-3

    # Check metric input: 5 mm diameter (#10 ~ 4.83 mm), 30 mm penetration, G = 0.50 (pine)
    # D_in = 5 / 25.4 = 0.19685 in, L_in = 30 / 25.4 = 1.1811 in
    # W = 2850 * 0.25 * 0.19685 = 140.2488 lbs/in
    # Total = 140.2488 * 1.1811 = 165.648 lbs = 736.84 N
    res_metric = wood_screw_withdrawal(Q(5.0, "mm"), Q(30.0, "mm"), Q(0.50, ""))
    assert 730.0 < res_metric.to("N").magnitude < 745.0


def test_lag_screw_withdrawal_hand_worked() -> None:
    """Hand check for lag screw withdrawal per NDS-2018 Section 12.2.1.

    Formula: W = 1800 * G^(3/2) * D^(3/4) (lbs/in).
    Given:
      - Diameter D = 0.25 inch (1/4" lag screw)
      - Substrate: Southern pine, specific gravity G = 0.50
      - Thread penetration: L = 2.0 inch
    Worked:
      - G^(1.5) = 0.50^1.5 = 0.353553
      - D^0.75 = 0.25^0.75 = 0.353553
      - W = 1800 * 0.353553 * 0.353553 = 1800 * 0.125 = 225.0 lbs/in
      - Total capacity = 225.0 * 2.0 = 450.0 lbs
      - In Newtons: 450.0 * 4.448221615 = 2001.6997 N
    """
    res = lag_screw_withdrawal(Q(0.25, "inch"), Q(2.0, "inch"), 0.50)
    expected_n = 450.0 * 4.4482216152605
    assert abs(res.to("N").magnitude - expected_n) < 1e-3


def test_insert_pullout_hand_worked_and_safety_factor() -> None:
    """Hand check for threaded insert pull-out capacity and safety factor.

    From RAMPA catalogue:
      - M6 insert in hardwood: capacity = 4500 N per insert.
      - 4 inserts: total capacity = 4 * 4500 = 18000 N.
      - Applied tension load = 3000 N.
      - Safety factor = 18000 / 3000 = 6.0.
    """
    res = insert_pullout("M6", "hardwood", count=4, applied_load=Q(3000, "N"))
    assert res.single_capacity.to("N").magnitude == 4500.0
    assert res.capacity.to("N").magnitude == 18000.0
    assert res.count == 4
    assert res.safety_factor == pytest.approx(6.0)

    # Alias check: white-oak maps to hardwood
    res_oak = insert_pullout("M6", "white-oak", count=1)
    assert res_oak.capacity.to("N").magnitude == 4500.0

    # Softwood and MDF checks
    res_pine = insert_pullout("M8", "pine", count=2)
    assert res_pine.capacity.to("N").magnitude == 8400.0  # 2 * 4200 N

    res_mdf = insert_pullout("M4", "mdf", count=1)
    assert res_mdf.capacity.to("N").magnitude == 1100.0


def test_insert_pullout_input_validation() -> None:
    """insert_pullout validates inputs and rejects invalid keys/counts/loads."""
    with pytest.raises(KeyError, match="unknown insert"):
        insert_pullout("M99", "hardwood")

    with pytest.raises(KeyError, match="unknown insert .* or substrate"):
        insert_pullout("M6", "titanium")

    with pytest.raises(ValueError, match="count must be >= 1"):
        insert_pullout("M6", "hardwood", count=0)

    with pytest.raises(ValueError, match="applied_load cannot be negative"):
        insert_pullout("M6", "hardwood", count=1, applied_load=Q(-100, "N"))


# --- 3. Joint moment capacity and frame racking -------------------------------------


def test_joint_moment_capacity_welded_hand_worked() -> None:
    """Hand check for welded corner moment capacity before yield.

    Formula: M = Z * sigma_y * eta.
    Given:
      - 50 x 50 x 3 mm square tube (outer 50 mm, wall 3 mm)
      - I = (50^4 - 44^4) / 12 = 208492 mm4
      - Z = I / (h/2) = 208492 / 25 = 8339.68 mm3 = 8.33968e-6 m3
      - Material: Mild steel, yield strength sigma_y = 250 MPa = 2.5e8 Pa
      - Weld efficiency: 1.0 (full penetration)
    Worked:
      - M = 8.33968e-6 * 2.5e8 = 2084.92 N*m
    """
    z = Q(8339.68, "mm**3")
    ys = Q(250, "MPa")
    res = joint_moment_capacity("welded", section_modulus=z, yield_strength=ys)
    assert res.to("N*m").magnitude == pytest.approx(2084.92, rel=1e-4)

    # Weld efficiency derating (e.g. 0.8 for fillet weld)
    res_eff = joint_moment_capacity(
        "welded", section_modulus=z, yield_strength=ys, weld_efficiency=0.8
    )
    assert res_eff.to("N*m").magnitude == pytest.approx(2084.92 * 0.8, rel=1e-4)


def test_joint_moment_capacity_bolted_hand_worked() -> None:
    """Hand check for bolted corner moment capacity before yield.

    Formula: M = (F_bolt / max(|y_i|)) * sum(y_i^2).
    Given:
      - 2 bolts spaced 150 mm apart (y = +/- 75 mm = +/- 0.075 m)
      - Bolt tensile capacity F_bolt = 4000 N (4 kN)
    Worked:
      - max_y = 0.075 m
      - sum(y_i^2) = 2 * (0.075^2) = 0.01125 m2
      - M = (4000 / 0.075) * 0.01125 = 4000 * 0.15 = 600 N*m
    """
    res = joint_moment_capacity(
        "bolted",
        bolt_capacity=Q(4, "kN"),
        bolt_distances=(Q(-75, "mm"), Q(75, "mm")),
    )
    assert res.to("N*m").magnitude == pytest.approx(600.0, rel=1e-5)

    # Spacing shortcut with 2 bolts
    res_spacing = joint_moment_capacity(
        "bolted", bolt_capacity=Q(4, "kN"), bolt_spacing=Q(150, "mm"), bolt_count=2
    )
    assert res_spacing.to("N*m").magnitude == pytest.approx(600.0, rel=1e-5)


def test_frame_racking_rigid_and_semi_rigid() -> None:
    """Hand check for unbraced portal frame racking sway (Roark Table 8.2).

    Given:
      - Lateral racking load P = 100 N
      - Column height H = 0.75 m (750 mm)
      - Top beam span L = 1.2 m (1200 mm)
      - Young's modulus E = 200 GPa = 2e11 Pa
      - Moment of inertia I_c = I_b = 73365.33 mm4 = 7.336533e-8 m4
      - E * I = 2e11 * 7.336533e-8 = 14673.067 N*m2
    Rigid frame worked:
      - Column sway: delta_col = P * H^3 / (6 * E * I_c)
        = 100 * 0.75^3 / (6 * 14673.067) = 42.1875 / 88038.4 = 0.479194 mm
      - Beam sway: delta_beam = P * H^2 * L / (12 * E * I_b)
        = 100 * 0.75^2 * 1.2 / (12 * 14673.067) = 67.5 / 176076.8 = 0.383355 mm
      - Total rigid sway = 0.479194 + 0.383355 = 0.86255 mm
    Semi-rigid frame worked:
      - Corner spring stiffness K_theta = 5000 N*m/rad
      - Joint sway: delta_joint = P * H^2 / (2 * K_theta)
        = 100 * 0.75^2 / (2 * 5000) = 56.25 / 10000 = 0.005625 m = 5.625 mm
      - Total sway = 0.86255 + 5.625 = 6.48755 mm
    """
    h = Q(750, "mm")
    span = Q(1200, "mm")
    e = Q(200, "GPa")
    i_sec = Q(73365.33, "mm**4")
    load = Q(100, "N")

    # Rigid corners
    sway_rigid = frame_racking(load, height=h, span=span, e_modulus=e, i_column=i_sec, i_beam=i_sec)
    assert sway_rigid.to("mm").magnitude == pytest.approx(0.862598, rel=1e-3)

    # Semi-rigid corners via PortalFrame dataclass
    frame = PortalFrame(
        height=h,
        span=span,
        e_modulus=e,
        i_column=i_sec,
        i_beam=i_sec,
        joint_stiffness=Q(5000, "N*m"),
    )
    sway_semi = frame_racking(frame, load)
    assert sway_semi.to("mm").magnitude == pytest.approx(6.487598, rel=1e-3)

    # Fixed base portal frame
    sway_fixed = frame_racking(
        load, height=h, span=span, e_modulus=e, i_column=i_sec, i_beam=i_sec, base_fixity="fixed"
    )
    # Fixed base should be significantly stiffer than pinned base
    assert sway_fixed.to("mm").magnitude < sway_rigid.to("mm").magnitude


# --- 4. Wood creep and wood movement ------------------------------------------------


def test_wood_creep_deflection_factors() -> None:
    """Hand check for wood creep deflection by load duration and moisture.

    Eurocode 5 Table 3.2:
      - Instantaneous: k_def = 0.0 (multiplier = 1.0)
      - Sustained, dry (indoor): k_def = 0.60 (multiplier = 1.60)
      - Sustained, damp (covered exterior): k_def = 0.80 (multiplier = 1.80)
      - Sustained, wet (exterior/cycling): k_def = 2.00 (multiplier = 3.00)
    """
    elastic = Q(2.5, "mm")

    # Instantaneous live load
    inst = wood_creep_deflection(elastic, load_duration="instantaneous")
    assert inst.to("mm").magnitude == pytest.approx(2.5)

    # Sustained indoor load
    sust_dry = wood_creep_deflection(elastic, load_duration="sustained", moisture="dry")
    assert sust_dry.to("mm").magnitude == pytest.approx(2.5 * 1.60)

    # Sustained damp load
    sust_damp = wood_creep_deflection(elastic, load_duration="sustained", moisture="damp")
    assert sust_damp.to("mm").magnitude == pytest.approx(2.5 * 1.80)

    # Sustained wet load
    sust_wet = wood_creep_deflection(elastic, load_duration="sustained", moisture="wet")
    assert sust_wet.to("mm").magnitude == pytest.approx(2.5 * 3.00)

    with pytest.raises(ValueError, match="unknown load_duration"):
        wood_creep_deflection(elastic, load_duration="infinite")


def test_wood_movement_hand_worked() -> None:
    """Hand check for across-grain wood dimensional movement.

    Formula (USDA Wood Handbook Ch. 4 & 13):
      Delta_W = W * C * Delta_M
    Given:
      - Tabletop width W = 800 mm
      - Species: White oak (Quercus alba), tangential C = 0.00365, radial C = 0.00180
      - Humidity swing: 30% to 70% RH (typical dry indoor winter to humid summer)
      - Delta_M = 6.9 % moisture content change
    Worked:
      - Tangential (flat-sawn): Delta_W = 800 * 0.00365 * 6.9 = 20.148 mm
      - Radial (quarter-sawn): Delta_W = 800 * 0.00180 * 6.9 = 9.936 mm
    """
    w = Q(800, "mm")

    # Tangential flat-sawn movement
    mov_tan = wood_movement(w, "white-oak", (30, 70), delta_mc=6.9, grain_direction="tangential")
    assert mov_tan.to("mm").magnitude == pytest.approx(20.148, rel=1e-4)

    # Radial quarter-sawn movement
    mov_rad = wood_movement(w, "white-oak", (30, 70), delta_mc=6.9, grain_direction="radial")
    assert mov_rad.to("mm").magnitude == pytest.approx(9.936, rel=1e-4)

    # Plywood check: cross-laminated panel has negligible movement
    mov_ply = wood_movement(w, "baltic-birch-plywood", (30, 70), delta_mc=6.9)
    assert mov_ply.to("mm").magnitude == pytest.approx(800 * 0.00015 * 6.9, rel=1e-4)

    # MDF check
    mov_mdf = wood_movement(w, "mdf", (30, 70), delta_mc=6.9)
    assert mov_mdf.to("mm").magnitude == pytest.approx(800 * 0.00050 * 6.9, rel=1e-4)

    with pytest.raises(KeyError, match="unknown wood species"):
        wood_movement(w, "balsa-tree", (30, 70))

    with pytest.raises(ValueError, match="unknown grain_direction"):
        wood_movement(w, "white-oak", (30, 70), grain_direction="diagonal")


# --- 5. Fatigue and load cases ------------------------------------------------------


def test_fatigue_margin_steel_goodman_hand_worked() -> None:
    """Hand check for steel fatigue safety factor via Modified Goodman.

    Shigley 11th ed. Section 6-11:
      1 / n_f = sigma_a / S_e + sigma_m / S_ut
    Given:
      - Material: Mild steel, S_ut = 400 MPa
      - Endurance limit: S'_e = 0.5 * 400 = 200 MPa
      - Marin factor = 0.8 -> S_e = 160 MPa
      - Stress: alternating sigma_a = 50 MPa, mean sigma_m = 100 MPa
      - Cycles: 10^6 (infinite life, S_f = S_e = 160 MPa)
    Worked:
      - 1 / n_f = 50 / 160 + 100 / 400 = 0.3125 + 0.2500 = 0.5625
      - n_f = 1 / 0.5625 = 1.777778
    """
    sigma_a = Q(50, "MPa")
    sigma_m = Q(100, "MPa")
    n = fatigue_margin(
        sigma_a,
        sigma_m,
        "mild-steel",
        1000000,
        ultimate_strength=Q(400, "MPa"),
        marin_factor=0.8,
    )
    assert n == pytest.approx(1.777778, rel=1e-4)

    # Pure alternating stress (zero mean stress): n = S_e / sigma_a = 160 / 50 = 3.20
    n_alt = fatigue_margin(
        sigma_a,
        Q(0, "MPa"),
        "mild-steel",
        1000000,
        ultimate_strength=Q(400, "MPa"),
        marin_factor=0.8,
    )
    assert n_alt == pytest.approx(3.20, rel=1e-4)

    # Compressive mean stress (compressive mean does not reduce fatigue endurance)
    n_comp = fatigue_margin(
        sigma_a,
        Q(-50, "MPa"),
        "mild-steel",
        1000000,
        ultimate_strength=Q(400, "MPa"),
        marin_factor=0.8,
    )
    assert n_comp == pytest.approx(3.20, rel=1e-4)


def test_fatigue_margin_missing_sn_failure() -> None:
    """Non-ferrous materials without an endurance limit fail loudly when sn_strength is missing."""
    with pytest.raises(ValueError, match="material 'aluminum-6061-t6' has no endurance limit"):
        fatigue_margin(Q(40, "MPa"), Q(20, "MPa"), "aluminum-6061-t6", 500000)

    with pytest.raises(ValueError, match="material 'pla-printed' has no endurance limit"):
        fatigue_margin(Q(15, "MPa"), Q(5, "MPa"), "pla-printed", 100000)

    # Providing sn_strength evaluates correctly
    n_al = fatigue_margin(
        Q(40, "MPa"),
        Q(0, "MPa"),
        "aluminum-6061-t6",
        500000,
        sn_strength=Q(80, "MPa"),
    )
    assert n_al == pytest.approx(2.0, rel=1e-4)


def test_factor_of_safety_defaults_and_loosening_refusal() -> None:
    """factor_of_safety provides cited defaults and strictly refuses loosening (W1)."""
    # Static yield default is 1.5
    assert factor_of_safety("yield", "static") == 1.5

    # Sustained yield default is 2.0
    assert factor_of_safety("yield", "sustained") == 2.0

    # Cyclic buckling default is 3.0
    assert factor_of_safety("buckling", "cyclic") == 3.0

    # Human-applied edge load tip-over default is 2.0
    assert factor_of_safety("tip_over", "edge_load") == 2.0

    # Tightening is allowed (e.g. required 2.5 on static yield)
    assert factor_of_safety("yield", "static", required=2.5) == 2.5

    # Loosening is strictly refused
    with pytest.raises(ValueError, match="safety factors may only be tightened"):
        factor_of_safety("yield", "static", required=1.2)

    with pytest.raises(ValueError, match="safety factors may only be tightened"):
        factor_of_safety("buckling", "cyclic", required=2.0)

    # Unknown check/load combination raises KeyError
    with pytest.raises(KeyError, match="unknown load case"):
        factor_of_safety("flying_carpet", "static")


# --- 6. Unit errors -----------------------------------------------------------------


def test_unit_errors_on_bare_numbers() -> None:
    """Every public function refuses bare numbers with UnitError."""
    # wood_screw_withdrawal
    with pytest.raises(UnitError):
        wood_screw_withdrawal(5, Q(25, "mm"), 0.68)
    with pytest.raises(UnitError):
        wood_screw_withdrawal(Q(5, "mm"), 25, 0.68)

    # lag_screw_withdrawal
    with pytest.raises(UnitError):
        lag_screw_withdrawal(6, Q(50, "mm"), 0.50)
    with pytest.raises(UnitError):
        lag_screw_withdrawal(Q(6, "mm"), 50, 0.50)

    # insert_pullout
    with pytest.raises(UnitError):
        insert_pullout("M6", "hardwood", applied_load=500)

    # joint_moment_capacity
    with pytest.raises(UnitError):
        joint_moment_capacity("welded", section_modulus=10000, yield_strength=Q(250, "MPa"))
    with pytest.raises(UnitError):
        joint_moment_capacity("welded", section_modulus=Q(10000, "mm**3"), yield_strength=250)
    with pytest.raises(UnitError):
        joint_moment_capacity("bolted", bolt_capacity=5000, bolt_spacing=Q(100, "mm"))

    # frame_racking
    with pytest.raises(UnitError):
        frame_racking(
            100,
            height=Q(750, "mm"),
            span=Q(1200, "mm"),
            e_modulus=Q(200, "GPa"),
            i_column=Q(75000, "mm**4"),
            i_beam=Q(75000, "mm**4"),
        )

    # wood_creep_deflection
    with pytest.raises(UnitError):
        wood_creep_deflection(2.5)

    # wood_movement
    with pytest.raises(UnitError):
        wood_movement(800, "white-oak", (30, 70))

    # fatigue_margin
    with pytest.raises(UnitError):
        fatigue_margin(50, Q(100, "MPa"), "mild-steel", 1000000)
    with pytest.raises(UnitError):
        fatigue_margin(Q(50, "MPa"), 100, "mild-steel", 1000000)
