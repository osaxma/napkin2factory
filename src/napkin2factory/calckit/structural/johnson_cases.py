"""Reference cases of the Johnson and Euler/Johnson column functions (S-207)."""

from __future__ import annotations

import math

from napkin2factory.calckit._cases import Case
from napkin2factory.core.units import Quantity

_HAND = "hand computation: "

JOHNSON_CASES: list[Case] = [
    Case(
        "johnson_buckling_load",
        Quantity(250e6 * 291e-6 / 2.0, "N"),
        "Shigley's Mechanical Engineering Design, 11th ed., §4-12: the Johnson parabola meets "
        "the Euler curve at lambda_c = sqrt(2 pi^2 E / S_y), where sigma_cr = S_y / 2; "
        "A = 291 mm^2, S_y = 250 MPa -> P_cr = 36 375 N",
        args=(
            Quantity(200, "GPa"),
            Quantity(114193.25, "mm**4"),
            Quantity(291, "mm**2"),
            Quantity(250, "MPa"),
            # lambda_c * r = 125.6637 * sqrt(114193.25 / 291) mm
            Quantity(125.66370614359172 * math.sqrt(114193.25 / 291.0), "mm"),
            1.0,
        ),
        pick="critical_load",
        rel=1e-6,
        external=True,
    ),
    Case(
        "johnson_buckling_load",
        Quantity(60578.0, "N"),
        _HAND + "independent worked benchmark (table leg): 50x50x1.5 mm tube, A=291 mm^2, "
        "I=114193.25 mm^4, K L = 2.0 x 720 mm, E=200 GPa, S_y=250 MPa: lambda = 72.69, "
        "sigma_cr = 250 - (250 x 72.69 / 2 pi)^2 / 200000 = 208.17 MPa, P_cr = 60 578 N",
        args=(
            Quantity(200, "GPa"),
            Quantity(114193.25, "mm**4"),
            Quantity(291, "mm**2"),
            Quantity(250, "MPa"),
            Quantity(720, "mm"),
            2.0,
        ),
        pick="critical_load",
        rel=1e-3,
        verify=True,
    ),
    Case(
        "column_buckling_load",
        "johnson",
        _HAND + "same table leg (lambda 72.7 < lambda_c 125.7): the Johnson curve is chosen",
        args=(
            Quantity(200, "GPa"),
            Quantity(114193.25, "mm**4"),
            Quantity(291, "mm**2"),
            Quantity(250, "MPa"),
            Quantity(720, "mm"),
            2.0,
        ),
        pick="method",
    ),
    Case(
        "column_buckling_load",
        Quantity(math.pi**2 * 200e9 * 1e-7 / 25.0, "N"),
        "Roark's Formulas for Stress and Strain, 7th ed., Table 15.1, Case 1: L=5 m, "
        "I=1e-7 m^4, A=1e-4 m^2 -> lambda = 158.1 > 125.7, so Euler: P_cr = pi^2 E I / L^2",
        args=(
            Quantity(200, "GPa"),
            Quantity(1e-7, "m**4"),
            Quantity(1e-4, "m**2"),
            Quantity(250, "MPa"),
            Quantity(5, "m"),
            1.0,
        ),
        pick="critical_load",
        external=True,
    ),
    Case(
        "column_buckling_load",
        "euler",
        _HAND + "the slender column above (lambda 158.1) is Euler",
        args=(
            Quantity(200, "GPa"),
            Quantity(1e-7, "m**4"),
            Quantity(1e-4, "m**2"),
            Quantity(250, "MPa"),
            Quantity(5, "m"),
            1.0,
        ),
        pick="method",
    ),
]
