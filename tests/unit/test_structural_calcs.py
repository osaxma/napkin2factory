"""Unit and property tests for calckit/structural.py (W1, Track A §3.1).

Includes:
- Handbook reference cases verification (all pass, public coverage, citations)
- Hand checks with step-by-step worked arithmetic in comments
- Wrong-unit input checks raising UnitError
- Hypothesis properties (deflection scales with F and L³, buckling scales with 1/L²)
"""

from __future__ import annotations

import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from napkin2factory.calckit import _cases, structural
from napkin2factory.calckit.structural import (
    K_FACTORS,
    K_FACTORS_THEORETICAL,
    beam_bending_stress,
    beam_deflection_cantilever,
    beam_deflection_simply_supported,
    check_euler_slenderness,
    euler_buckling_load,
    fastener_group_shear,
    rect_section,
    rect_tube_section,
    round_tube_section,
    tip_over_safety_factor,
    yield_safety_factor,
)
from napkin2factory.core.units import Quantity as Q
from napkin2factory.core.units import UnitError

FAST = settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])


# --- reference cases ----------------------------------------------------------------


def test_every_structural_function_has_a_case_and_every_case_passes() -> None:
    """Every public function must have at least one reference case and all must pass."""
    assert structural.CASES, "structural.CASES must not be empty"
    uncovered = _cases.uncovered(structural)
    assert uncovered == [], f"uncovered public functions: {uncovered}"
    for case, outcome in _cases.run_pack(structural):
        assert outcome.ok, (case.fn, outcome.message, outcome.expected, outcome.actual)
        assert case.source.strip(), f"{case.fn} has empty source"


def test_structural_has_external_handbook_cases_with_sources() -> None:
    """Published handbook cases must have external=True, source > 40 chars,
    and no 'hand computation'.
    """
    external = [c for c in structural.CASES if c.external]
    assert len(external) >= 6, f"expected at least 6 external cases, got {len(external)}"
    for c in external:
        assert not c.source.lower().startswith("hand computation"), c.source
        assert len(c.source) > 40, f"source citation too brief: {c.source!r}"


# --- hand checks with worked numbers in comments -------------------------------------


def test_hand_check_rect_section() -> None:
    """Hand check for solid rectangular section properties.

    Worked computation:
      b = 50 mm = 0.05 m
      h = 100 mm = 0.1 m
      I_x = b * h^3 / 12 = 0.05 * 0.1^3 / 12 = 0.05 * 0.001 / 12 = 5e-5 / 12 ≈ 4.166667e-6 m^4
      Z_x = b * h^2 / 6 = 0.05 * 0.1^2 / 6 = 0.05 * 0.01 / 6 = 5e-4 / 6 ≈ 8.333333e-5 m^3
      A = b * h = 0.05 * 0.1 = 0.005 m^2 = 5000 mm^2
      I_y = h * b^3 / 12 = 0.1 * 0.05^3 / 12 = 0.1 * 1.25e-4 / 12 ≈ 1.041667e-6 m^4
      Z_y = h * b^2 / 6 = 0.1 * 0.05^2 / 6 = 0.1 * 0.0025 / 6 ≈ 4.166667e-5 m^3
    """
    sec = rect_section(Q(50, "mm"), Q(100, "mm"))
    assert float(sec.I.to("m**4").magnitude) == pytest.approx(5e-5 / 12.0, rel=1e-9)
    assert float(sec.Z.to("m**3").magnitude) == pytest.approx(5e-4 / 6.0, rel=1e-9)
    assert float(sec.A.to("mm**2").magnitude) == pytest.approx(5000.0, rel=1e-9)
    assert float(sec.Iy.to("m**4").magnitude) == pytest.approx(1.25e-5 / 12.0, rel=1e-9)
    assert float(sec.Zy.to("m**3").magnitude) == pytest.approx(2.5e-4 / 6.0, rel=1e-9)
    # Tuple unpacking check: (I, Z, A)
    i, z, a = sec
    assert i == sec.I and z == sec.Z and a == sec.A


def test_hand_check_rect_tube_section() -> None:
    """Hand check for hollow rectangular tube section (60x40x4 mm).

    Worked computation:
      Outer b = 60 mm, h = 40 mm, t = 4 mm
      Inner b1 = 60 - 2*4 = 52 mm, h1 = 40 - 2*4 = 32 mm
      A = 60*40 - 52*32 = 2400 - 1664 = 736 mm^2 = 7.36e-4 m^2
      I_x = (60 * 40^3 - 52 * 32^3) / 12
          = (60 * 64000 - 52 * 32768) / 12
          = (3840000 - 1703936) / 12 = 2136064 / 12 = 178005.333 mm^4
      Z_x = I_x / (h/2) = 178005.333 / 20 = 8900.267 mm^3
      I_y = (40 * 60^3 - 32 * 52^3) / 12
          = (40 * 216000 - 32 * 140608) / 12
          = (8640000 - 4499456) / 12 = 4140544 / 12 = 345045.333 mm^4
      Z_y = I_y / (b/2) = 345045.333 / 30 = 11501.511 mm^3
    """
    sec = rect_tube_section(Q(60, "mm"), Q(40, "mm"), Q(4, "mm"))
    assert float(sec.A.to("mm**2").magnitude) == pytest.approx(736.0, rel=1e-9)
    assert float(sec.Ix.to("mm**4").magnitude) == pytest.approx(2136064.0 / 12.0, rel=1e-9)
    assert float(sec.Iy.to("mm**4").magnitude) == pytest.approx(4140544.0 / 12.0, rel=1e-9)
    assert float(sec.Zx.to("mm**3").magnitude) == pytest.approx((2136064.0 / 12.0) / 20.0, rel=1e-9)
    assert float(sec.Zy.to("mm**3").magnitude) == pytest.approx((4140544.0 / 12.0) / 30.0, rel=1e-9)
    # Tuple unpacking check: (Ix, Iy, Zx, A)
    ix, iy, zx, a = sec
    assert ix == sec.Ix and iy == sec.Iy and zx == sec.Zx and a == sec.A


def test_hand_check_round_tube_section() -> None:
    """Hand check for round tube section (OD=50 mm, t=5 mm).

    Worked computation:
      OD = 50 mm = 0.05 m, t = 5 mm, ID = 40 mm = 0.04 m
      A = pi/4 * (50^2 - 40^2) = pi/4 * (2500 - 1600) = 900*pi/4 = 225*pi mm^2 ≈ 706.8583 mm^2
      I = pi/64 * (50^4 - 40^4) = pi/64 * (6250000 - 2560000) = 3690000*pi/64
        = 57656.25*pi mm^4 ≈ 181134.39 mm^4
      Z = I / (OD/2) = (57656.25*pi) / 25 = 2306.25*pi mm^3 ≈ 7245.3756 mm^3
    """
    sec = round_tube_section(Q(50, "mm"), Q(5, "mm"))
    assert float(sec.A.to("mm**2").magnitude) == pytest.approx(225.0 * math.pi, rel=1e-9)
    assert float(sec.I.to("mm**4").magnitude) == pytest.approx(57656.25 * math.pi, rel=1e-9)
    assert float(sec.Z.to("mm**3").magnitude) == pytest.approx(2306.25 * math.pi, rel=1e-9)
    # Tuple unpacking check: (I, Z, A)
    i, z, a = sec
    assert i == sec.I and z == sec.Z and a == sec.A


def test_hand_check_simply_supported_point_and_uniform() -> None:
    """Hand check for simply supported beam deflections.

    Worked computation:
      F = 1000 N, L = 1.0 m, E = 200 GPa = 2e11 Pa, I = 1e-6 m^4
      1) Center point load:
         delta = F * L^3 / (48 * E * I)
               = 1000 * 1^3 / (48 * 2e11 * 1e-6)
               = 1000 / 9600000 = 1 / 9600 m ≈ 0.1041667 mm
      2) Uniform distributed load w = 1000 N/m:
         delta = 5 * w * L^4 / (384 * E * I)
               = 5 * 1000 * 1^4 / (384 * 2e11 * 1e-6)
               = 5000 / 76800000 = 5 / 76800 m ≈ 0.0651042 mm
      3) Total force W = 1000 N uniform load:
         w = W / L = 1000 N/m -> same deflection 5/76800 m
    """
    pt = beam_deflection_simply_supported(
        Q(1000, "N"), Q(1, "m"), Q(200, "GPa"), Q(1e-6, "m**4"), "point_center"
    )
    assert float(pt.deflection.to("mm").magnitude) == pytest.approx(1000.0 / 9600.0, rel=1e-9)
    assert pt.formula == "FL^3 / (48*E*I)"

    uni = beam_deflection_simply_supported(
        Q(1000, "N/m"), Q(1, "m"), Q(200, "GPa"), Q(1e-6, "m**4"), "uniform"
    )
    assert float(uni.deflection.to("mm").magnitude) == pytest.approx(5000.0 / 76800.0, rel=1e-9)
    assert uni.formula == "5*w*L^4 / (384*E*I)"

    # Total force representation of uniform load
    uni_tot = beam_deflection_simply_supported(
        Q(1000, "N"), Q(1, "m"), Q(200, "GPa"), Q(1e-6, "m**4"), "uniform"
    )
    assert float(uni_tot.deflection.to("mm").magnitude) == pytest.approx(
        float(uni.deflection.to("mm").magnitude), rel=1e-9
    )


def test_hand_check_cantilever_and_column_rotation() -> None:
    """Hand check for cantilever tip deflection with and without column rotation.

    Worked computation:
      F = 2000 N, La = 0.15 m, H = 0.4 m, E = 200 GPa = 2e11 Pa
      Ia = Ic = 4.706987e-7 m^4
      Arm bending:
        delta_arm = F * La^3 / (3 * E * Ia)
                  = 2000 * 0.15^3 / (3 * 2e11 * 4.706987e-7)
                  = 6.75 / 282419.22 ≈ 2.390064e-5 m = 0.023901 mm
      Column rotation tip displacement:
        theta = M * H / (E * Ic) = (F * La) * H / (E * Ic)
        delta_col = theta * La = F * La^2 * H / (E * Ic)
                  = 2000 * 0.15^2 * 0.4 / (2e11 * 4.706987e-7)
                  = 18.0 / 94139.74 ≈ 1.912051e-4 m = 0.191205 mm
      Total tip deflection:
        delta = delta_arm + delta_col ≈ 0.023901 + 0.191205 = 0.215106 mm
    """
    res = beam_deflection_cantilever(
        force=Q(2000, "N"),
        overhang=Q(150, "mm"),
        column_height=Q(400, "mm"),
        E=Q(200, "GPa"),
        I_arm=Q(4.706987e-7, "m**4"),
        I_col=Q(4.706987e-7, "m**4"),
    )
    assert float(res.deflection.to("mm").magnitude) == pytest.approx(0.2151057, rel=1e-4)
    assert res.value == res.deflection

    # Pure cantilever (H = 0)
    pure = beam_deflection_cantilever(
        force=Q(2000, "N"),
        overhang=Q(150, "mm"),
        column_height=Q(0, "mm"),
        E=Q(200, "GPa"),
        I_arm=Q(4.706987e-7, "m**4"),
    )
    assert float(pure.deflection.to("mm").magnitude) == pytest.approx(0.02390064, rel=1e-4)


def test_hand_check_bending_stress_and_yield_factor() -> None:
    """Hand check for bending stress sigma = M / Z and yield safety factor.

    Worked computation:
      M = 500 N*m
      Z = 1e-5 m^3
      sigma = 500 / 1e-5 = 5e7 Pa = 50 MPa
      yield_strength = 250 MPa
      yield_factor = 250 / 50 = 5.0
    """
    res = beam_bending_stress(Q(500, "N*m"), Q(1e-5, "m**3"), yield_strength=Q(250, "MPa"))
    assert float(res.stress.to("MPa").magnitude) == pytest.approx(50.0, rel=1e-9)
    assert res.yield_factor == pytest.approx(5.0, rel=1e-9)
    assert res.value == res.stress

    # Standalone yield_safety_factor function
    sf = yield_safety_factor(Q(50, "MPa"), Q(250, "MPa"))
    assert sf == pytest.approx(5.0, rel=1e-9)


def test_hand_check_euler_buckling_and_k_factors() -> None:
    """Hand check for Euler buckling P_cr = pi^2 * E * I / (K*L)^2 across end conditions.

    Worked computation:
      E = 200 GPa = 2e11 Pa, I = 1e-7 m^4, L = 1.0 m
      Base capacity (K = 1.0):
        P_cr = pi^2 * 2e11 * 1e-7 / 1^2 = 2e4 * pi^2 ≈ 197392.088 N
      Under P = 50 kN:
        FS = 197392.088 / 50000 ≈ 3.94784
    """
    # 1. Theoretical K = 1.0
    res_pinned = euler_buckling_load(
        Q(200, "GPa"),
        Q(1e-7, "m**4"),
        Q(1, "m"),
        k_factor="pinned-pinned",
        load=Q(50, "kN"),
    )
    expected_p = 2e4 * math.pi**2
    assert float(res_pinned.critical_load.to("N").magnitude) == pytest.approx(expected_p, rel=1e-6)
    assert res_pinned.safety_factor == pytest.approx(expected_p / 50000.0, rel=1e-6)

    # 2. Fixed-free (K = 2.1 design AISC Table C-A-7.1)
    res_cant = euler_buckling_load(
        Q(200, "GPa"),
        Q(1e-7, "m**4"),
        Q(1, "m"),
        k_factor="fixed-free",
    )
    expected_cant = expected_p / (K_FACTORS["fixed-free"] ** 2)
    assert float(res_cant.critical_load.to("N").magnitude) == pytest.approx(expected_cant, rel=1e-6)

    # 3. Fixed-pinned (K = 0.8 design AISC Table C-A-7.1)
    res_fp = euler_buckling_load(
        Q(200, "GPa"),
        Q(1e-7, "m**4"),
        Q(1, "m"),
        k_factor="fixed-pinned",
    )
    expected_fp = expected_p / (K_FACTORS["fixed-pinned"] ** 2)
    assert float(res_fp.critical_load.to("N").magnitude) == pytest.approx(expected_fp, rel=1e-6)

    # 4. Fixed-fixed (K = 0.65 design AISC Table C-A-7.1)
    res_ff = euler_buckling_load(
        Q(200, "GPa"),
        Q(1e-7, "m**4"),
        Q(1, "m"),
        k_factor="fixed-fixed",
    )
    expected_ff = expected_p / (K_FACTORS["fixed-fixed"] ** 2)
    assert float(res_ff.critical_load.to("N").magnitude) == pytest.approx(expected_ff, rel=1e-6)

    # 5. Theoretical K values directly
    res_theo = euler_buckling_load(
        Q(200, "GPa"),
        Q(1e-7, "m**4"),
        Q(1, "m"),
        k_factor=K_FACTORS_THEORETICAL["fixed-free"],
    )
    assert float(res_theo.critical_load.to("N").magnitude) == pytest.approx(
        expected_p / 4.0, rel=1e-6
    )


def test_hand_check_slenderness_rejection_johnson() -> None:
    """Slenderness check refuses inelastic column buckling, naming Johnson's formula.

    Worked computation:
      E = 200 GPa = 2e11 Pa, sigma_y = 250 MPa = 2.5e8 Pa
      lambda_c = sqrt(2 * pi^2 * E / sigma_y)
               = sqrt(2 * pi^2 * 2e11 / 2.5e8)
               = sqrt(1600 * pi^2) = 40 * pi ≈ 125.6637

      Case 1 (short column, lambda < lambda_c):
        I_min = 1e-7 m^4, A = 1e-4 m^2 -> r = sqrt(I/A) = sqrt(1e-3) ≈ 0.0316228 m
        L = 1.0 m, K = 1.0 -> lambda = 1.0 / 0.0316228 ≈ 31.62 < 125.66
        Must raise ValueError citing Johnson's formula.

      Case 2 (slender column, lambda >= lambda_c):
        L = 5.0 m, K = 1.0 -> lambda = 5.0 / 0.0316228 ≈ 158.11 >= 125.66
        Euler formula valid, passes.
    """
    # 1. Short column must be refused with mention of Johnson's formula
    with pytest.raises(ValueError, match="Johnson's formula"):
        check_euler_slenderness(
            length=Q(1, "m"),
            k_factor=1.0,
            I_min=Q(1e-7, "m**4"),
            area=Q(1e-4, "m**2"),
            E=Q(200, "GPa"),
            yield_strength=Q(250, "MPa"),
        )

    # Also verified via euler_buckling_load directly
    with pytest.raises(ValueError, match="Johnson's formula"):
        euler_buckling_load(
            E=Q(200, "GPa"),
            I_min=Q(1e-7, "m**4"),
            length=Q(1, "m"),
            k_factor=1.0,
            area=Q(1e-4, "m**2"),
            yield_strength=Q(250, "MPa"),
        )

    # 2. Long column passes
    lam = check_euler_slenderness(
        length=Q(5, "m"),
        k_factor=1.0,
        I_min=Q(1e-7, "m**4"),
        area=Q(1e-4, "m**2"),
        E=Q(200, "GPa"),
        yield_strength=Q(250, "MPa"),
    )
    assert lam == pytest.approx(5.0 / math.sqrt(1e-3), rel=1e-6)

    res = euler_buckling_load(
        E=Q(200, "GPa"),
        I_min=Q(1e-7, "m**4"),
        length=Q(5, "m"),
        k_factor=1.0,
        area=Q(1e-4, "m**2"),
        yield_strength=Q(250, "MPa"),
    )
    assert res.slenderness == pytest.approx(lam, rel=1e-6)
    assert res.critical_slenderness == pytest.approx(40.0 * math.pi, rel=1e-6)


def test_hand_check_tip_over_safety_factor() -> None:
    """Hand check for tip-over safety factor: restoring moment / overturning moment.

    Worked computation:
      mass = 40 kg, g = 9.80665 m/s^2, cg_x = 0.3 m
      edge_load = 200 N, overhang_x = 0.15 m
      M_restoring = 40 * 9.80665 * 0.3 = 117.6798 N*m
      M_overturning = 200 * 0.15 = 30.0 N*m
      FS = 117.6798 / 30.0 = 3.92266
    """
    res = tip_over_safety_factor(
        mass=Q(40, "kg"),
        cg_x=Q(300, "mm"),
        edge_load=Q(200, "N"),
        overhang_x=Q(150, "mm"),
    )
    assert float(res.restoring_moment.to("N*m").magnitude) == pytest.approx(117.6798, rel=1e-6)
    assert float(res.overturning_moment.to("N*m").magnitude) == pytest.approx(30.0, rel=1e-6)
    assert res.safety_factor == pytest.approx(117.6798 / 30.0, rel=1e-6)
    assert res.value == res.safety_factor


def test_hand_check_fastener_group_shear() -> None:
    """Hand check for direct fastener group shear stress and safety factor.

    Worked computation:
      V = 10 kN = 10000 N, n = 4 bolts
      A_s = 58 mm^2 = 5.8e-5 m^2 (M10 coarse bolt stress area)
      tau = V / (n * A_s) = 10000 / (4 * 5.8e-5) = 10000 / 2.32e-4 ≈ 43103448.28 Pa ≈ 43.103 MPa
      tau_allow = 120 MPa = 1.2e8 Pa
      FS = 120 / 43.103448 ≈ 2.784
    """
    res = fastener_group_shear(
        shear_force=Q(10, "kN"),
        count=4,
        bolt_area=Q(58, "mm**2"),
        shear_strength=Q(120, "MPa"),
    )
    assert float(res.shear_stress.to("MPa").magnitude) == pytest.approx(43.103448, rel=1e-5)
    assert res.safety_factor == pytest.approx(120.0 / 43.103448, rel=1e-5)
    assert res.value == res.shear_stress


# --- wrong-unit input checks raising UnitError ---------------------------------------


def test_wrong_unit_inputs_raise_unit_error() -> None:
    """Inputs with bare numbers or mismatched dimensions must raise UnitError."""
    # 1. Bare numbers
    with pytest.raises(UnitError):
        rect_section(50, Q(100, "mm"))  # type: ignore[arg-type]
    with pytest.raises(UnitError):
        rect_tube_section(Q(60, "mm"), 40, Q(4, "mm"))  # type: ignore[arg-type]
    with pytest.raises(UnitError):
        round_tube_section(Q(50, "mm"), 5)  # type: ignore[arg-type]
    with pytest.raises(UnitError):
        beam_deflection_simply_supported(1000, Q(1, "m"), Q(200, "GPa"), Q(1e-6, "m**4"))  # type: ignore[arg-type]
    with pytest.raises(UnitError):
        beam_deflection_cantilever(Q(500, "N"), 0.5, None, Q(200, "GPa"), Q(1e-6, "m**4"))  # type: ignore[arg-type]
    with pytest.raises(UnitError):
        beam_bending_stress(500, Q(1e-5, "m**3"))  # type: ignore[arg-type]
    with pytest.raises(UnitError):
        yield_safety_factor(50, Q(250, "MPa"))  # type: ignore[arg-type]
    with pytest.raises(UnitError):
        euler_buckling_load(200, Q(1e-7, "m**4"), Q(1, "m"))  # type: ignore[arg-type]
    with pytest.raises(UnitError):
        tip_over_safety_factor(40, Q(0.3, "m"), Q(200, "N"), Q(0.15, "m"))  # type: ignore[arg-type]
    with pytest.raises(UnitError):
        fastener_group_shear(10000, 4, Q(58, "mm**2"))  # type: ignore[arg-type]

    # 2. Incompatible unit dimensions (e.g. temperature or time for length/force)
    with pytest.raises(UnitError):
        rect_section(Q(50, "degC"), Q(100, "mm"))
    with pytest.raises(UnitError):
        beam_deflection_simply_supported(
            Q(1000, "second"), Q(1, "m"), Q(200, "GPa"), Q(1e-6, "m**4")
        )
    with pytest.raises(UnitError):
        beam_bending_stress(Q(500, "kg"), Q(1e-5, "m**3"))
    with pytest.raises(UnitError):
        tip_over_safety_factor(Q(40, "meter"), Q(0.3, "m"), Q(200, "N"), Q(0.15, "m"))
    with pytest.raises(UnitError):
        fastener_group_shear(Q(10, "kN"), 4, Q(58, "degC"))


def test_invalid_parameters_raise_value_error() -> None:
    """Non-positive dimensions, unknown end conditions, and zero bolt counts raise ValueError."""
    with pytest.raises(ValueError, match="must be positive"):
        rect_section(Q(-50, "mm"), Q(100, "mm"))
    with pytest.raises(ValueError, match="must be less than outer width"):
        rect_tube_section(Q(20, "mm"), Q(20, "mm"), Q(12, "mm"))
    with pytest.raises(ValueError, match="must be less than outer diameter"):
        round_tube_section(Q(20, "mm"), Q(12, "mm"))
    with pytest.raises(ValueError, match="unknown load_kind"):
        beam_deflection_simply_supported(
            Q(100, "N"), Q(1, "m"), Q(200, "GPa"), Q(1e-6, "m**4"), "triangular"
        )
    with pytest.raises(ValueError, match="unknown end condition"):
        euler_buckling_load(Q(200, "GPa"), Q(1e-7, "m**4"), Q(1, "m"), k_factor="unsupported-free")
    with pytest.raises(ValueError, match="count must be at least 1"):
        fastener_group_shear(Q(10, "kN"), 0, Q(58, "mm**2"))


# --- hypothesis property tests ------------------------------------------------------


@FAST
@given(
    force=st.floats(10.0, 50000.0),
    span=st.floats(0.1, 10.0),
    E=st.floats(10.0, 500.0),  # GPa
    I=st.floats(1e-8, 1e-4),  # m^4
)
def test_simply_supported_deflection_linear_in_force(
    force: float, span: float, E: float, I: float
) -> None:
    """Deflection is strictly linear in applied force: delta(2*F) = 2 * delta(F)."""
    d1 = beam_deflection_simply_supported(Q(force, "N"), Q(span, "m"), Q(E, "GPa"), Q(I, "m**4"))
    d2 = beam_deflection_simply_supported(
        Q(2.0 * force, "N"), Q(span, "m"), Q(E, "GPa"), Q(I, "m**4")
    )
    v1 = float(d1.deflection.to("m").magnitude)
    v2 = float(d2.deflection.to("m").magnitude)
    assert v2 == pytest.approx(2.0 * v1, rel=1e-9)


@FAST
@given(
    force=st.floats(10.0, 50000.0),
    span=st.floats(0.2, 5.0),
    scale=st.floats(1.1, 3.0),
    E=st.floats(10.0, 500.0),  # GPa
    I=st.floats(1e-8, 1e-4),  # m^4
)
def test_simply_supported_deflection_scales_with_span_cubed(
    force: float, span: float, scale: float, E: float, I: float
) -> None:
    """Deflection under point load scales with span cubed: delta(s*L) = s^3 * delta(L)."""
    d1 = beam_deflection_simply_supported(Q(force, "N"), Q(span, "m"), Q(E, "GPa"), Q(I, "m**4"))
    d2 = beam_deflection_simply_supported(
        Q(force, "N"), Q(span * scale, "m"), Q(E, "GPa"), Q(I, "m**4")
    )
    v1 = float(d1.deflection.to("m").magnitude)
    v2 = float(d2.deflection.to("m").magnitude)
    assert v2 == pytest.approx((scale**3) * v1, rel=1e-8)


@FAST
@given(
    force=st.floats(10.0, 10000.0),
    overhang=st.floats(0.05, 2.0),
    height=st.floats(0.0, 2.0),
    E=st.floats(50.0, 250.0),
    I=st.floats(1e-7, 1e-4),
)
def test_cantilever_deflection_linear_in_force(
    force: float, overhang: float, height: float, E: float, I: float
) -> None:
    """Cantilever tip deflection is linear in force: delta(2*F) = 2*delta(F)."""
    h_q = Q(height, "m") if height > 0 else None
    d1 = beam_deflection_cantilever(Q(force, "N"), Q(overhang, "m"), h_q, Q(E, "GPa"), Q(I, "m**4"))
    d2 = beam_deflection_cantilever(
        Q(2.0 * force, "N"), Q(overhang, "m"), h_q, Q(E, "GPa"), Q(I, "m**4")
    )
    v1 = float(d1.deflection.to("m").magnitude)
    v2 = float(d2.deflection.to("m").magnitude)
    assert v2 == pytest.approx(2.0 * v1, rel=1e-9)


@FAST
@given(
    E=st.floats(50.0, 400.0),
    I=st.floats(1e-8, 1e-4),
    length=st.floats(0.5, 10.0),
    scale=st.floats(1.1, 4.0),
)
def test_euler_buckling_inverse_quadratic_in_length(
    E: float, I: float, length: float, scale: float
) -> None:
    """Euler buckling load scales as 1/L²: P_cr(s*L) = P_cr(L) / s²."""
    b1 = euler_buckling_load(Q(E, "GPa"), Q(I, "m**4"), Q(length, "m"))
    b2 = euler_buckling_load(Q(E, "GPa"), Q(I, "m**4"), Q(length * scale, "m"))
    p1 = float(b1.critical_load.to("N").magnitude)
    p2 = float(b2.critical_load.to("N").magnitude)
    assert p2 == pytest.approx(p1 / (scale**2), rel=1e-9)


@FAST
@given(
    moment=st.floats(10.0, 10000.0),
    Z=st.floats(1e-6, 1e-2),
)
def test_bending_stress_linear_in_moment(moment: float, Z: float) -> None:
    """Bending stress is linear in moment: sigma(2*M) = 2 * sigma(M)."""
    s1 = beam_bending_stress(Q(moment, "N*m"), Q(Z, "m**3"))
    s2 = beam_bending_stress(Q(2.0 * moment, "N*m"), Q(Z, "m**3"))
    v1 = float(s1.stress.to("Pa").magnitude)
    v2 = float(s2.stress.to("Pa").magnitude)
    assert v2 == pytest.approx(2.0 * v1, rel=1e-9)


@FAST
@given(
    force=st.floats(100.0, 50000.0),
    count=st.integers(1, 10),
    area=st.floats(10.0, 500.0),
)
def test_fastener_shear_inversely_proportional_to_count(
    force: float, count: int, area: float
) -> None:
    """Fastener shear stress halves when fastener count doubles: tau(2*n) = tau(n)/2."""
    s1 = fastener_group_shear(Q(force, "N"), count, Q(area, "mm**2"))
    s2 = fastener_group_shear(Q(force, "N"), 2 * count, Q(area, "mm**2"))
    v1 = float(s1.shear_stress.to("Pa").magnitude)
    v2 = float(s2.shear_stress.to("Pa").magnitude)
    assert v2 == pytest.approx(v1 / 2.0, rel=1e-9)
