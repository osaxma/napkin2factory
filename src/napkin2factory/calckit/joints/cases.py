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
        "hand computation with the formula of ANSI/AWC NDS-2018 National Design Specification for "
        "Wood Construction Section 12.2.1 [verify]: "
        "W = 2850 G^2 D (lbs/in); #10 screw D=0.190 in, white oak G=0.68, 1 in penetration",
        args=(Quantity(0.190, "inch"), Quantity(1.0, "inch"), 0.68),
        rel=1e-5,
    ),
    Case(
        "lag_screw_withdrawal",
        Quantity(450.0 * 4.4482216152605, "N"),
        "hand computation with the formula of ANSI/AWC NDS-2018 National Design Specification for "
        "Wood Construction Section 12.2.1 [verify]: "
        "W = 1800 G^1.5 D^0.75 (lbs/in); 1/4 in lag screw D=0.25 in, pine G=0.50, 2 in penetration",
        args=(Quantity(0.25, "inch"), Quantity(2.0, "inch"), 0.50),
        rel=1e-5,
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
        "hand computation with the formula of Roark's Formulas for Stress and Strain (the "
        "rigid-frame table, number to confirm) [verify]: "
        "unbraced portal frame with pinned bases, rederived by slope-deflection; P=100 N, H=0.75 "
        "m, L=1.2 m, EI=14673.067 N*m2: "
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
    ),
    Case(
        "frame_racking",
        Quantity(6.4875977, "mm"),
        _HAND + "portal frame above with joint rotational stiffness K_theta = 5000 N*m/rad; "
        "delta_joint = P H^2 / (2 K) = 5.625 mm (pinned bases: the whole column moment P H / 2 "
        "turns the joint); total = 0.8626 + 5.625 = 6.4876 mm",
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
        "frame_racking",
        Quantity(0.0297619, "mm"),
        _HAND + "fixed-base portal frame, rigid corners, slope-deflection (derivation in "
        "frames.py): P=100 N, h=L=1 m, E=200 GPa, I_c=I_b=1e-6 m^4, k=(I_b/L)/(I_c/h)=1: "
        "delta = P h^3 (3k+2)/(12 E I_c (6k+1)) = 100 x 5 / (12 x 2e5 x 7) m = 0.029762 mm "
        "(a 2D frame stiffness solve gives the same; gate I replaced (k+2) by (3k+2))",
        args=(
            Quantity(100, "N"),
            Quantity(1, "m"),
            Quantity(1, "m"),
            Quantity(200, "GPa"),
            Quantity(1e6, "mm**4"),
            Quantity(1e6, "mm**4"),
        ),
        kwargs={"base_fixity": "fixed"},
        rel=1e-5,
    ),
    Case(
        "frame_racking",
        Quantity(100 * 1.0**3 / (24 * 200e9 * 1e-6) * 1000, "mm"),
        _HAND + "fixed-base portal frame with a rigid beam (I_b = 1e9 I_c, k to infinity): two "
        "fixed-fixed columns each taking P/2: delta = P h^3 / (24 E I_c) = 100 / (24 x 2e5) m "
        "= 0.020833 mm",
        args=(
            Quantity(100, "N"),
            Quantity(1, "m"),
            Quantity(1, "m"),
            Quantity(200, "GPa"),
            Quantity(1e6, "mm**4"),
            Quantity(1e15, "mm**4"),
        ),
        kwargs={"base_fixity": "fixed"},
        rel=1e-6,
    ),
    Case(
        "frame_racking",
        Quantity(0.0818151, "mm"),
        _HAND + "fixed-base portal frame above (k=1) with corner springs K_theta = 5000 N*m/rad: "
        "E I_c/(h K) = 2e5 N*m2 / (1 m x 5000 N*m) = 40; r = 1/(1 + 1/(6k) + 40) = 0.024291; "
        "delta = P h^3/(24 E I_c) x (4 - 3 r) = 0.0208333 mm x 3.92713 = 0.081815 mm; a 2D "
        "frame stiffness solve with a spring between column and beam gives the same",
        args=(
            Quantity(100, "N"),
            Quantity(1, "m"),
            Quantity(1, "m"),
            Quantity(200, "GPa"),
            Quantity(1e6, "mm**4"),
            Quantity(1e6, "mm**4"),
        ),
        kwargs={"base_fixity": "fixed", "joint_stiffness": Quantity(5000, "N*m")},
        rel=1e-5,
    ),
    Case(
        "wood_creep_deflection",
        Quantity(4.0, "mm"),
        "hand computation with the formula of Eurocode 5 (EN 1995-1-1:2004) Table 3.2 [verify]: "
        "k_def = 0.60 for solid timber service class 1; "
        "total = 2.5 mm * (1 + 0.60) = 4.0 mm",
        args=(Quantity(2.5, "mm"), "sustained", "dry"),
        rel=1e-6,
    ),
    Case(
        "timber_k_def",
        0.60,
        "Eurocode 5 (EN 1995-1-1:2004) Table 3.2 [verify]: k_def = 0.60 for solid timber, service "
        "class 1",
        args=("sustained", "dry"),
        external=True,
        verify=True,
    ),
    Case(
        "composite_creep_deflection",
        Quantity(0.7537, "mm"),
        "EN 1995-1-1:2004 section 2.3.2.2, only the timber's modulus drops to E/(1+k_def), "
        "k_def = 0.60: white-oak top 800x30 (EI 2.214e10 N*mm^2) with two 50x50x1.5 steel "
        "rails (EI 4.5677e10 N*mm^2), elastic sag 0.6614 mm: 0.6614 * 6.7817e10 / "
        "(2.214e10/1.6 + 4.5677e10) = 0.7537 mm (independent hand calculation of the table "
        "benchmark)",
        args=(
            Quantity(0.661399803753192, "mm"),
            [
                (Quantity(2.214e10, "N*mm**2"), True),
                (Quantity(4.5677e10, "N*mm**2"), False),
            ],
        ),
        rel=1e-3,
        verify=True,
    ),
    Case(
        "equilibrium_moisture_content",
        6.2,
        "USDA Wood Handbook FPL-GTR-190 Table 4-2 [verify], 30 % RH at 70 degF (21.1 degC): 6.2 % "
        "(the Hailwood-Horrobin Eq. 4-5 gives 6.17)",
        args=(30,),
        kwargs={"temperature": Quantity(70, "degF")},
        abs=0.05,
        external=True,
    ),
    Case(
        "equilibrium_moisture_content",
        9.2,
        "USDA Wood Handbook FPL-GTR-190 Table 4-2 [verify], 50 % RH at 70 degF: 9.2 %",
        args=(50,),
        kwargs={"temperature": Quantity(70, "degF")},
        abs=0.05,
        external=True,
    ),
    Case(
        "equilibrium_moisture_content",
        13.1,
        "USDA Wood Handbook FPL-GTR-190 Table 4-2 [verify], 70 % RH at 70 degF: 13.1 %",
        args=(70,),
        kwargs={"temperature": Quantity(70, "degF")},
        abs=0.05,
        external=True,
    ),
    Case(
        "wood_movement",
        Quantity(7.05, "mm"),
        "Independent hand calculation of the table benchmark, FPL-GTR-190 Ch. 4: oak at a fixing "
        "280 mm from the fixed centreline, 30 % to 70 % RH at room temperature "
        "(6.9 points of moisture): 280 * 0.00365 * 6.9 = 7.05 mm",
        args=(Quantity(280, "mm"), "white-oak", (30, 70)),
        rel=0.01,
        verify=True,
    ),
    Case(
        "wood_movement",
        Quantity(20.148, "mm"),
        "hand computation with the formula of USDA Forest Products Laboratory Wood Handbook "
        "(FPL-GTR-190) Ch. 4 Table 4-4 [verify]: white oak "
        "tangential C=0.00365; W=800 mm, Delta_M=6.9 %: Delta_W = 800 * 0.00365 * 6.9 = 20.148 mm",
        args=(Quantity(800, "mm"), "white-oak", (30, 70)),
        kwargs={"delta_mc": 6.9},
        rel=1e-4,
    ),
    Case(
        "fatigue_margin",
        1.7777777777777777,
        "hand computation with the formula of Shigley Mechanical Engineering Design 11th ed. "
        "Section 6-11 Modified Goodman [verify]: "
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
    ),
    Case(
        "factor_of_safety",
        1.5,
        "hand computation with the formula of AISC 360-16 Specification for Structural Steel "
        "Buildings, Table 1-5 [verify]: "
        "default static yield safety factor = 1.5",
        args=("yield", "static"),
    ),
    Case(
        "factor_of_safety",
        2.2,
        _HAND + "factor_of_safety tightened above default 1.5 to required 2.2",
        args=("yield", "static", 2.2),
        rel=1e-6,
    ),
]
