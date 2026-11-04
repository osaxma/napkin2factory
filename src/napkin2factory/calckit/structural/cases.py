"""Reference cases of the structural pack; see :mod:`napkin2factory.calckit._cases`."""

from __future__ import annotations

import math

from napkin2factory.calckit._cases import Case
from napkin2factory.core.units import Quantity

# --- reference cases ----------------------------------------------------------------

_HAND = "hand computation: "


#: Every public function's reference cases; external ones come from published handbooks.
CASES: list[Case] = [
    # rect_section
    Case(
        "rect_section",
        Quantity(4.166666666666667e-6, "m**4"),
        "Roark's Formulas for Stress and Strain, 7th ed., Table 1, Case 1 (Solid Rectangle): "
        "b=50 mm, h=100 mm, I = b*h^3/12 = 4.16667e-6 m^4",
        args=(Quantity(50, "mm"), Quantity(100, "mm")),
        pick="I",
        external=True,
    ),
    Case(
        "rect_section",
        Quantity(8.333333333333333e-5, "m**3"),
        _HAND + "solid rectangle 50x100 mm: Z = b*h^2/6 = 0.05 * 0.1^2 / 6 = 8.33333e-5 m^3",
        args=(Quantity(50, "mm"), Quantity(100, "mm")),
        pick="Z",
        rel=1e-6,
    ),
    Case(
        "rect_section",
        Quantity(5000, "mm**2"),
        _HAND + "solid rectangle 50x100 mm: A = 50 * 100 = 5000 mm^2",
        args=(Quantity(50, "mm"), Quantity(100, "mm")),
        pick="A",
        rel=1e-12,
    ),
    # rect_tube_section
    Case(
        "rect_tube_section",
        Quantity(178005.33333333334, "mm**4"),
        "Roark's Formulas for Stress and Strain, 7th ed., Table 1, Case 2 (Hollow Rectangle): "
        "60x40x4 mm tube, Ix = (60*40^3 - 52*32^3)/12 = 178005.33 mm^4",
        args=(Quantity(60, "mm"), Quantity(40, "mm"), Quantity(4, "mm")),
        pick="Ix",
        external=True,
    ),
    Case(
        "rect_tube_section",
        Quantity(345045.33333333335, "mm**4"),
        _HAND + "60x40x4 mm tube: Iy = (40*60^3 - 32*52^3)/12 = 345045.33 mm^4",
        args=(Quantity(60, "mm"), Quantity(40, "mm"), Quantity(4, "mm")),
        pick="Iy",
        rel=1e-6,
    ),
    Case(
        "rect_tube_section",
        Quantity(8900.266666666667, "mm**3"),
        _HAND + "60x40x4 mm tube: Zx = Ix / (h/2) = 178005.333 / 20 = 8900.27 mm^3",
        args=(Quantity(60, "mm"), Quantity(40, "mm"), Quantity(4, "mm")),
        pick="Zx",
        rel=1e-6,
    ),
    Case(
        "rect_tube_section",
        Quantity(736, "mm**2"),
        _HAND + "60x40x4 mm tube: A = 60*40 - 52*32 = 736 mm^2",
        args=(Quantity(60, "mm"), Quantity(40, "mm"), Quantity(4, "mm")),
        pick="A",
        rel=1e-12,
    ),
    # round_tube_section
    Case(
        "round_tube_section",
        Quantity(57656.25 * math.pi, "mm**4"),
        "Roark's Formulas for Stress and Strain, 7th ed., Table 1, Case 12 (Hollow Circle): "
        "OD=50 mm, t=5 mm, I = pi*(50^4 - 40^4)/64 = 181134.39 mm^4",
        args=(Quantity(50, "mm"), Quantity(5, "mm")),
        pick="I",
        external=True,
    ),
    Case(
        "round_tube_section",
        Quantity(57656.25 * math.pi / 25.0, "mm**3"),
        _HAND + "round tube OD=50 mm, t=5 mm: Z = I / (D/2) = 181134.39 / 25 = 7245.38 mm^3",
        args=(Quantity(50, "mm"), Quantity(5, "mm")),
        pick="Z",
        rel=1e-6,
    ),
    Case(
        "round_tube_section",
        Quantity(225.0 * math.pi, "mm**2"),
        _HAND + "round tube OD=50 mm, t=5 mm: A = pi/4 * (50^2 - 40^2) = 225*pi mm^2",
        args=(Quantity(50, "mm"), Quantity(5, "mm")),
        pick="A",
        rel=1e-12,
    ),
    # beam_deflection_simply_supported
    Case(
        "beam_deflection_simply_supported",
        Quantity(1000.0 / (48.0 * 200e9 * 1e-6), "m"),
        "Roark's Formulas for Stress and Strain, 7th ed., Table 8.1, Case 1d (Center Load): "
        "F=1000 N, L=1 m, E=200 GPa, I=1e-6 m^4, delta = FL^3/(48EI) = 0.104167 mm",
        args=(
            Quantity(1000, "N"),
            Quantity(1, "m"),
            Quantity(200, "GPa"),
            Quantity(1e-6, "m**4"),
        ),
        pick="deflection",
        external=True,
    ),
    Case(
        "beam_deflection_simply_supported",
        Quantity(5000.0 / (384.0 * 200e9 * 1e-6), "m"),
        "Roark's Formulas for Stress and Strain, 7th ed., Table 8.1, Case 1e (Uniform Load): "
        "w=1000 N/m, L=1 m, E=200 GPa, I=1e-6 m^4, delta = 5wL^4/(384EI) = 0.065104 mm",
        args=(
            Quantity(1000, "N/m"),
            Quantity(1, "m"),
            Quantity(200, "GPa"),
            Quantity(1e-6, "m**4"),
        ),
        kwargs={"load_kind": "uniform"},
        pick="deflection",
        external=True,
    ),
    # beam_deflection_cantilever
    Case(
        "beam_deflection_cantilever",
        Quantity(500.0 * 0.5**3 / (3.0 * 200e9 * 1e-6), "m"),
        "Roark's Formulas for Stress and Strain, 7th ed., Table 8.1, "
        "Case 1a (Cantilever Tip Load): F=500 N, L=0.5 m, E=200 GPa, "
        "I=1e-6 m^4, delta = FL^3/(3EI) = 0.104167 mm",
        args=(
            Quantity(500, "N"),
            Quantity(0.5, "m"),
            None,
            Quantity(200, "GPa"),
            Quantity(1e-6, "m**4"),
        ),
        pick="deflection",
        external=True,
    ),
    Case(
        "beam_deflection_cantilever",
        Quantity(2.1510574185794713e-4, "m"),
        _HAND + "cantilever with column rotation (Track A §3.1): F=2000 N, La=0.15 m, H=0.4 m, "
        "E=200 GPa, Ia=Ic=4.706987e-7 m^4; delta = delta_arm + delta_col = 0.2151 mm",
        args=(
            Quantity(2000, "N"),
            Quantity(150, "mm"),
            Quantity(400, "mm"),
            Quantity(200, "GPa"),
            Quantity(4.706987e-7, "m**4"),
            Quantity(4.706987e-7, "m**4"),
        ),
        pick="deflection",
        rel=1e-5,
    ),
    # beam_bending_stress
    Case(
        "beam_bending_stress",
        Quantity(50, "MPa"),
        _HAND + "bending stress: M=500 N*m, Z=1e-5 m^3, sigma = 500 / 1e-5 = 50 MPa",
        args=(Quantity(500, "N*m"), Quantity(1e-5, "m**3")),
        pick="stress",
        rel=1e-12,
    ),
    Case(
        "beam_bending_stress",
        5.0,
        _HAND + "bending stress yield factor: sigma=50 MPa, sigma_y=250 MPa, FS = 250 / 50 = 5.0",
        args=(Quantity(500, "N*m"), Quantity(1e-5, "m**3")),
        kwargs={"yield_strength": Quantity(250, "MPa")},
        pick="yield_factor",
        rel=1e-12,
    ),
    # yield_safety_factor
    Case(
        "yield_safety_factor",
        5.0,
        _HAND + "yield safety factor: sigma=50 MPa, sigma_y=250 MPa, FS = 5.0",
        args=(Quantity(50, "MPa"), Quantity(250, "MPa")),
        rel=1e-12,
    ),
    # check_euler_slenderness
    Case(
        "check_euler_slenderness",
        5.0 / math.sqrt(1e-3),
        _HAND + "slenderness check: L=5 m, K=1.0, I=1e-7 m^4, A=1e-4 m^2, "
        "r=sqrt(1e-3) m; lambda = 158.11",
        args=(
            Quantity(5, "m"),
            1.0,
            Quantity(1e-7, "m**4"),
            Quantity(1e-4, "m**2"),
            Quantity(200, "GPa"),
            Quantity(250, "MPa"),
        ),
        rel=1e-6,
    ),
    # euler_buckling_load
    Case(
        "euler_buckling_load",
        Quantity(math.pi**2 * 200e9 * 1e-7 / 1.0**2, "N"),
        "Roark's Formulas for Stress and Strain, 7th ed., Table 15.1, "
        "Case 1 (Euler Column Buckling): pinned-pinned K=1, L=1 m, "
        "E=200 GPa, I=1e-7 m^4, P_cr = pi^2*E*I/(KL)^2 = 197.392 kN",
        args=(
            Quantity(200, "GPa"),
            Quantity(1e-7, "m**4"),
            Quantity(1, "m"),
            "pinned-pinned",
        ),
        pick="critical_load",
        external=True,
    ),
    # tip_over_safety_factor
    Case(
        "tip_over_safety_factor",
        (40.0 * 9.80665 * 0.3) / (200.0 * 0.15),
        _HAND + "tip-over factor: mass=40 kg, cg_x=0.3 m, edge_load=200 N, "
        "overhang_x=0.15 m; FS = 3.92266",
        args=(
            Quantity(40, "kg"),
            Quantity(0.3, "m"),
            Quantity(200, "N"),
            Quantity(0.15, "m"),
        ),
        pick="safety_factor",
        rel=1e-6,
    ),
    # fastener_group_shear
    Case(
        "fastener_group_shear",
        Quantity(10000.0 / (4.0 * 5.8e-5), "Pa"),
        "Shigley's Mechanical Engineering Design, 11th ed., §8-5 (Bolted Shear Connections): "
        "V=10 kN, n=4 bolts, As=58 mm^2, tau = V/(n*As) = 43.103 MPa",
        args=(
            Quantity(10, "kN"),
            4,
            Quantity(58, "mm**2"),
        ),
        kwargs={"shear_strength": Quantity(120, "MPa")},
        pick="shear_stress",
        external=True,
    ),
    Case(
        "fastener_group_shear",
        120e6 / (10000.0 / (4.0 * 5.8e-5)),
        _HAND + "fastener group shear safety factor: tau=43.103 MPa, allowable=120 MPa, FS = 2.784",
        args=(
            Quantity(10, "kN"),
            4,
            Quantity(58, "mm**2"),
        ),
        kwargs={"shear_strength": Quantity(120, "MPa")},
        pick="safety_factor",
        rel=1e-6,
    ),
    # aliases
    Case(
        "rect_section_inertia",
        Quantity(4.166666666666667e-6, "m**4"),
        _HAND + "rect_section_inertia alias for rect_section: I = 4.16667e-6 m^4",
        args=(Quantity(50, "mm"), Quantity(100, "mm")),
        pick="I",
        rel=1e-12,
    ),
    Case(
        "tube_section_inertia",
        Quantity(178005.33333333334, "mm**4"),
        _HAND + "tube_section_inertia alias for rect_tube_section: Ix = 178005.33 mm^4",
        args=(Quantity(60, "mm"), Quantity(40, "mm"), Quantity(4, "mm")),
        pick="Ix",
        rel=1e-12,
    ),
    Case(
        "simply_supported_deflection",
        Quantity(1000.0 / (48.0 * 200e9 * 1e-6), "m"),
        _HAND + "simply_supported_deflection alias: delta = FL^3/(48EI)",
        args=(
            Quantity(1000, "N"),
            Quantity(1, "m"),
            Quantity(200, "GPa"),
            Quantity(1e-6, "m**4"),
        ),
        pick="deflection",
        rel=1e-12,
    ),
    Case(
        "cantilever_deflection",
        Quantity(500.0 * 0.5**3 / (3.0 * 200e9 * 1e-6), "m"),
        _HAND + "cantilever_deflection alias: delta = FL^3/(3EI)",
        args=(
            Quantity(500, "N"),
            Quantity(0.5, "m"),
            None,
            Quantity(200, "GPa"),
            Quantity(1e-6, "m**4"),
        ),
        pick="deflection",
        rel=1e-12,
    ),
    Case(
        "euler_buckling",
        Quantity(math.pi**2 * 200e9 * 1e-7 / 1.0**2, "N"),
        _HAND + "euler_buckling alias for euler_buckling_load: P_cr = 197.392 kN",
        args=(
            Quantity(200, "GPa"),
            Quantity(1e-7, "m**4"),
            Quantity(1, "m"),
            "pinned-pinned",
        ),
        pick="critical_load",
        rel=1e-12,
    ),
]
