"""Johnson parabola for short columns, and the Euler/Johnson choice by slenderness (S-207)."""

from __future__ import annotations

import dataclasses
import math

from napkin2factory.calckit.structural._units import Qty, _m, _m2, _m4, _n, _pa
from napkin2factory.calckit.structural.columns import (
    BucklingResult,
    _resolve_k_factor,
    euler_buckling_load,
)
from napkin2factory.core.units import Quantity

_JOHNSON_SOURCE = (
    "Johnson parabola: Shigley's Mechanical Engineering Design, 11th ed., §4-12 "
    "(intermediate columns); AISC 360 Commentary Table C-A-7.1 for K"
)


def _column_terms(
    E: Qty,
    I_min: Qty,
    area: Qty,
    yield_strength: Qty,
    length: Qty,
    k_factor: float | str | Qty,
) -> tuple[float, float, float, float, float]:
    """SI floats (E, area, yield, slenderness, transition slenderness); refuses non-positives."""
    e_pa = _pa(E, "E")
    i_m4 = _m4(I_min, "I_min")
    a_m2 = _m2(area, "area")
    sy_pa = _pa(yield_strength, "yield_strength")
    l_m = _m(length, "length")
    k_val = _resolve_k_factor(k_factor)
    if min(e_pa, i_m4, a_m2, sy_pa, l_m) <= 0:
        raise ValueError("E, I_min, area, yield_strength and length must all be positive")
    slenderness = k_val * l_m / math.sqrt(i_m4 / a_m2)
    transition = math.sqrt(2.0 * math.pi**2 * e_pa / sy_pa)
    return e_pa, a_m2, sy_pa, slenderness, transition


def johnson_buckling_load(
    E: Qty,
    I_min: Qty,
    area: Qty,
    yield_strength: Qty,
    length: Qty,
    k_factor: float | str | Qty = 1.0,
    *,
    load: Qty | None = None,
) -> BucklingResult:
    r"""Critical load of a short (intermediate) column by the Johnson parabola.

    :math:`P_{cr} = A\left[\sigma_y - \frac{\sigma_y^2}{4\pi^2 E}
    \left(\frac{K L}{r}\right)^2\right]` with :math:`r = \sqrt{I_{\min}/A}`. It joins the
    Euler curve tangentially at :math:`\lambda_c = \sqrt{2\pi^2 E/\sigma_y}`, where
    :math:`\sigma_{cr} = \sigma_y/2`. Valid for :math:`\lambda \le \lambda_c`; a slenderer
    column is refused (use :func:`euler_buckling_load` or :func:`column_buckling_load`).

    Args:
        E: Young's modulus (pressure).
        I_min: minimum area moment of inertia (length⁴).
        area: cross-section area (length²).
        yield_strength: yield strength (pressure).
        length: unsupported length (length).
        k_factor: effective length factor K (float or end-condition string).
        load: applied compressive load (force, optional) for the safety factor.

    Returns:
        :class:`BucklingResult` with ``method == "johnson"``.

    Raises:
        ValueError: if the slenderness is above the Euler transition.
    """
    e_pa, a_m2, sy_pa, slenderness, transition = _column_terms(
        E, I_min, area, yield_strength, length, k_factor
    )
    if slenderness > transition:
        raise ValueError(
            f"slenderness ratio λ={slenderness:.1f} is above the transition "
            f"λ_c={transition:.1f}: the column buckles elastically; use "
            f"euler_buckling_load or column_buckling_load"
        )
    sigma_cr = sy_pa - (sy_pa * slenderness / (2.0 * math.pi)) ** 2 / e_pa
    p_cr = sigma_cr * a_m2
    sf: float | None = None
    if load is not None:
        p_applied = _n(load, "load")
        sf = p_cr / p_applied if p_applied > 0 else float("inf")
    return BucklingResult(
        critical_load=Quantity(p_cr, "N"),
        safety_factor=sf,
        slenderness=slenderness,
        critical_slenderness=transition,
        formula="P_cr = A * (S_y - (S_y * KL/r / (2*pi))^2 / E)",
        source=_JOHNSON_SOURCE,
        method="johnson",
    )


def column_buckling_load(
    E: Qty,
    I_min: Qty,
    area: Qty,
    yield_strength: Qty,
    length: Qty,
    k_factor: float | str | Qty = 1.0,
    *,
    load: Qty | None = None,
) -> BucklingResult:
    r"""Critical load of a column by Euler or Johnson, whichever its slenderness calls for.

    Slender columns (:math:`\lambda \ge \lambda_c = \sqrt{2\pi^2 E/\sigma_y}`) buckle
    elastically (Euler); shorter ones by the Johnson parabola (Shigley §4-12). The result's
    ``method`` field says which was used (``"euler"`` or ``"johnson"``).

    Args:
        E: Young's modulus (pressure).
        I_min: minimum area moment of inertia (length⁴).
        area: cross-section area (length²).
        yield_strength: yield strength (pressure).
        length: unsupported length (length).
        k_factor: effective length factor K (float or end-condition string).
        load: applied compressive load (force, optional) for the safety factor.

    Returns:
        :class:`BucklingResult` with slenderness, transition and ``method`` filled in.
    """
    _, _, _, slenderness, transition = _column_terms(
        E, I_min, area, yield_strength, length, k_factor
    )
    if slenderness <= transition:
        return johnson_buckling_load(E, I_min, area, yield_strength, length, k_factor, load=load)
    euler = euler_buckling_load(E, I_min, length, k_factor, load=load)
    return dataclasses.replace(
        euler, slenderness=slenderness, critical_slenderness=transition, method="euler"
    )
