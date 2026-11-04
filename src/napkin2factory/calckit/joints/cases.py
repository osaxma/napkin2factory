"""Reference cases of the joints pack; see :mod:`napkin2factory.calckit._cases`."""

from __future__ import annotations

from napkin2factory.calckit._cases import Case
from napkin2factory.core.units import Quantity

# --- Reference cases (F17, W1) ------------------------------------------------------

_HAND = "hand computation: "


CASES: list[Case] = [
    Case(
        "insert_pullout",
        Quantity(4500.0, "N"),
        "RAMPA Tec technical documentation for Type SK/SKD threaded inserts in hardwood; "
        "verified pull-out resistance for M6 insert in beech/oak substrate",
        args=("M6", "hardwood", 1),
        pick="capacity",
        external=True,
        verify=True,
    ),
    Case(
        "insert_pullout",
        Quantity(18000.0, "N"),
        _HAND + "4 x M6 inserts in hardwood at 4500 N each = 18 000 N",
        args=("M6", "hardwood", 4),
        pick="capacity",
        verify=True,
    ),
    Case(
        "wood_screw_withdrawal",
        Quantity(250.3896 * 4.4482216152605, "N"),
        "ANSI/AWC NDS-2018 National Design Specification for Wood Construction Section 12.2.1: "
        "W = 2850 G^2 D (lbs/in); #10 screw D=0.190 in, white oak G=0.68, 1 in penetration",
        args=(Quantity(0.190, "inch"), Quantity(1.0, "inch"), 0.68),
        rel=1e-5,
        external=True,
    ),
    Case(
        "lag_screw_withdrawal",
        Quantity(450.0 * 4.4482216152605, "N"),
        "ANSI/AWC NDS-2018 National Design Specification for Wood Construction Section 12.2.1: "
        "W = 1800 G^1.5 D^0.75 (lbs/in); 1/4 in lag screw D=0.25 in, pine G=0.50, 2 in penetration",
        args=(Quantity(0.25, "inch"), Quantity(2.0, "inch"), 0.50),
        rel=1e-5,
        external=True,
    ),
    Case(
        "joint_moment_capacity",
        Quantity(2000.0, "N*m"),
        _HAND + "welded corner section modulus Z = 10000 mm3, yield strength = 200 MPa, "
        "efficiency = 1.0: M = 1e-5 m3 * 2e8 Pa = 2000 N*m",
        args=("welded",),
        kwargs={
            "section_modulus": Quantity(10000, "mm**3"),
            "yield_strength": Quantity(200, "MPa"),
        },
        rel=1e-6,
    ),
    Case(
        "joint_moment_capacity",
        Quantity(1000.0, "N*m"),
        _HAND
        + "bolted corner 2 bolts spaced 200 mm apart (y = +/- 100 mm), bolt tensile capacity 5 kN: "
        "M = 2 * 5000 N * 0.1 m = 1000 N*m",
        args=("bolted",),
        kwargs={
            "bolt_capacity": Quantity(5, "kN"),
            "bolt_distances": (Quantity(-100, "mm"), Quantity(100, "mm")),
        },
        rel=1e-6,
    ),
    Case(
        "frame_racking",
        Quantity(0.8625977, "mm"),
        "Roark's Formulas for Stress and Strain 8th ed. Table 8.2 Case 1: unbraced portal "
        "frame with pinned bases; P=100 N, H=0.75 m, L=1.2 m, EI=14673.067 N*m2: "
        "delta = 0.4792 + 0.3834 = 0.8626 mm",
        args=(
            Quantity(100, "N"),
            Quantity(750, "mm"),
            Quantity(1200, "mm"),
            Quantity(200, "GPa"),
            Quantity(73365.33, "mm**4"),
            Quantity(73365.33, "mm**4"),
        ),
        rel=1e-4,
        external=True,
    ),
    Case(
        "frame_racking",
        Quantity(6.4875977, "mm"),
        _HAND + "portal frame above with joint rotational stiffness K_theta = 5000 N*m/rad; "
        "delta_joint = P H^2 / (2 K) = 5.625 mm; total = 0.8626 + 5.625 = 6.4876 mm",
        args=(
            Quantity(100, "N"),
            Quantity(750, "mm"),
            Quantity(1200, "mm"),
            Quantity(200, "GPa"),
            Quantity(73365.33, "mm**4"),
            Quantity(73365.33, "mm**4"),
        ),
        kwargs={"joint_stiffness": Quantity(5000, "N*m")},
        rel=1e-4,
    ),
    Case(
        "wood_creep_deflection",
        Quantity(4.0, "mm"),
        "Eurocode 5 (EN 1995-1-1:2004) Table 3.2: k_def = 0.60 for solid timber service class 1; "
        "total = 2.5 mm * (1 + 0.60) = 4.0 mm",
        args=(Quantity(2.5, "mm"), "sustained", "dry"),
        rel=1e-6,
        external=True,
    ),
    Case(
        "wood_movement",
        Quantity(20.148, "mm"),
        "USDA Forest Products Laboratory Wood Handbook (FPL-GTR-190) Ch. 4 Table 4-4: white oak "
        "tangential C=0.00365; W=800 mm, Delta_M=6.9 %: Delta_W = 800 * 0.00365 * 6.9 = 20.148 mm",
        args=(Quantity(800, "mm"), "white-oak", (30, 70)),
        kwargs={"delta_mc": 6.9},
        rel=1e-4,
        external=True,
    ),
    Case(
        "fatigue_margin",
        1.7777777777777777,
        "Shigley Mechanical Engineering Design 11th ed. Section 6-11 Modified Goodman: "
        "steel Sut=400 MPa, Se=160 MPa, sigma_a=50 MPa, sigma_m=100 MPa: "
        "1/n = 50/160 + 100/400 = 0.5625 -> n = 1.7778",
        args=(
            Quantity(50, "MPa"),
            Quantity(100, "MPa"),
            "mild-steel",
            1000000,
        ),
        kwargs={
            "ultimate_strength": Quantity(400, "MPa"),
            "marin_factor": 0.8,
        },
        rel=1e-4,
        external=True,
    ),
    Case(
        "factor_of_safety",
        1.5,
        "AISC 360-16 Specification for Structural Steel Buildings Table 1-5: "
        "default static yield safety factor = 1.5",
        args=("yield", "static"),
        external=True,
    ),
    Case(
        "factor_of_safety",
        2.2,
        _HAND + "factor_of_safety tightened above default 1.5 to required 2.2",
        args=("yield", "static", 2.2),
        rel=1e-6,
    ),
]
