"""Euler buckling, tip-over stability and fastener group shear."""

from __future__ import annotations

import math
from dataclasses import dataclass

from napkin2factory.calckit.structural._units import (
    _G_SI,
    Qty,
    _dimless,
    _kg,
    _m,
    _m2,
    _m4,
    _n,
    _pa,
)
from napkin2factory.core.units import Quantity


@dataclass(frozen=True)
class BucklingResult:
    r"""Euler elastic column buckling capacity and margin.

    Attributes:
        critical_load: Euler buckling load :math:`P_{cr}` (force).
        safety_factor: buckling safety factor :math:`P_{cr} / P`, or None.
        slenderness: column slenderness ratio :math:`\\lambda = K L / r`, or None.
        critical_slenderness: Euler/Johnson transition slenderness :math:`\\lambda_c`, or None.
        formula: governing formula text.
        source: published citation.
    """

    critical_load: Qty
    safety_factor: float | None
    slenderness: float | None
    critical_slenderness: float | None
    formula: str
    source: str

    @property
    def value(self) -> Qty:
        """The critical buckling load for screen cards."""
        return self.critical_load


@dataclass(frozen=True)
class TipOverResult:
    """Stability against tip-over under eccentric or edge loading.

    Attributes:
        safety_factor: restoring moment divided by overturning moment (dimensionless).
        restoring_moment: gravity moment about the tipping fulcrum (moment).
        overturning_moment: moment about the tipping fulcrum from edge load (moment).
        formula: governing formula text.
        source: published citation.
    """

    safety_factor: float
    restoring_moment: Qty
    overturning_moment: Qty
    formula: str
    source: str

    @property
    def value(self) -> float:
        """The tip-over safety factor for screen cards."""
        return self.safety_factor


@dataclass(frozen=True)
class ShearResult:
    r"""Direct shear stress on a group of fasteners.

    Attributes:
        shear_stress: nominal shear stress per fastener :math:`\\tau = V / (n A_s)` (pressure).
        safety_factor: safety factor :math:`\\tau_{\\text{allow}} / \\tau`, or None.
        formula: governing formula text.
        source: published citation.
    """

    shear_stress: Qty
    safety_factor: float | None
    formula: str
    source: str

    @property
    def value(self) -> Qty:
        """The shear stress quantity for screen cards."""
        return self.shear_stress


# --- column buckling and stability --------------------------------------------------

#: Effective length factor K per column end condition.
#: Theoretical values from Roark Table 15.1; design values from AISC Table C-A-7.1 /
#: Shigley Table 4-2.
K_FACTORS: dict[str, float] = {
    "pinned-pinned": 1.0,
    "fixed-free": 2.10,  # theoretical 2.0; design 2.10 (AISC Table C-A-7.1)
    "fixed-pinned": 0.80,  # theoretical 0.707; design 0.80 (AISC Table C-A-7.1)
    "fixed-fixed": 0.65,  # theoretical 0.5; design 0.65 (AISC Table C-A-7.1)
}


K_FACTORS_THEORETICAL: dict[str, float] = {
    "pinned-pinned": 1.0,
    "fixed-free": 2.0,
    "fixed-pinned": 1.0 / math.sqrt(2.0),
    "fixed-fixed": 0.5,
}


def _resolve_k_factor(k: float | int | str | Qty) -> float:
    if isinstance(k, str):
        key = k.strip().lower().replace("_", "-")
        if key in K_FACTORS:
            return K_FACTORS[key]
        valid = ", ".join(repr(x) for x in sorted(K_FACTORS))
        raise ValueError(f"unknown end condition {k!r}; expected one of: {valid}")
    if hasattr(k, "to"):
        return _dimless(k, "k_factor")
    if isinstance(k, (int, float)):
        val = float(k)
        if val <= 0:
            raise ValueError(f"k_factor must be positive, got {val}")
        return val
    raise TypeError(
        f"k_factor must be float, int, str, or dimensionless Quantity, got {type(k).__name__}"
    )


def check_euler_slenderness(
    length: Qty,
    k_factor: float | str | Qty,
    I_min: Qty,
    area: Qty,
    E: Qty,
    yield_strength: Qty,
) -> float:
    r"""Check that column slenderness is in the Euler range and refuse inelastic buckling.

    Computes column slenderness :math:`\\lambda = \\frac{K L}{r}` with radius of gyration
    :math:`r = \\sqrt{I_{\\min} / A}`. Refuses slenderness below the Euler transition
    limit :math:`\\lambda_c = \\sqrt{\\frac{2 \\pi^2 E}{\\sigma_y}}`, naming Johnson's
    formula as not covered (Shigley §4-11).

    Returns:
        Slenderness ratio :math:`\\lambda` (float).

    Raises:
        ValueError: if :math:`\\lambda < \\lambda_c`.
    """
    l_m = _m(length, "length")
    k_val = _resolve_k_factor(k_factor)
    i_m4 = _m4(I_min, "I_min")
    a_m2 = _m2(area, "area")
    e_pa = _pa(E, "E")
    sy_pa = _pa(yield_strength, "yield_strength")

    if l_m <= 0 or i_m4 <= 0 or a_m2 <= 0 or e_pa <= 0 or sy_pa <= 0:
        raise ValueError("length, I_min, area, E, and yield_strength must all be positive")

    r = math.sqrt(i_m4 / a_m2)
    le = k_val * l_m
    slenderness = le / r
    crit_slenderness = math.sqrt(2.0 * math.pi**2 * e_pa / sy_pa)

    if slenderness < crit_slenderness:
        raise ValueError(
            f"slenderness ratio \u03bb={slenderness:.1f} is below the Euler limit "
            f"\u03bb_c={crit_slenderness:.1f} (inelastic buckling range; "
            f"Johnson's formula is not covered)"
        )
    return slenderness


def euler_buckling_load(
    E: Qty,
    I_min: Qty,
    length: Qty,
    k_factor: float | str | Qty = 1.0,
    *,
    load: Qty | None = None,
    area: Qty | None = None,
    yield_strength: Qty | None = None,
) -> BucklingResult:
    r"""Critical Euler column buckling load and optional safety factor.

    Calculates :math:`P_{cr} = \\frac{\\pi^2 E I_{\\min}}{(K L)^2}`.
    When ``area`` and ``yield_strength`` are provided, checks that slenderness
    is in the Euler elastic range and refuses inelastic columns, naming Johnson's
    formula as not covered (Shigley §4-11).

    Args:
        E: Young's modulus of elasticity (pressure/stress).
        I_min: minimum area moment of inertia of column section (length⁴).
        length: unsupported column length (length, L).
        k_factor: effective length factor K (float, or end-condition string, e.g. "pinned-pinned").
        load: applied compressive axial load (force, optional).
        area: cross-sectional area (length², optional; enables slenderness check).
        yield_strength: yield strength (pressure/stress, optional; enables slenderness check).

    Returns:
        :class:`BucklingResult` with critical load, safety factor, and slenderness.
    """
    e_pa = _pa(E, "E")
    i_m4 = _m4(I_min, "I_min")
    l_m = _m(length, "length")
    k_val = _resolve_k_factor(k_factor)

    if e_pa <= 0 or i_m4 <= 0 or l_m <= 0:
        raise ValueError("E, I_min, and length must be positive")

    slenderness: float | None = None
    crit_slenderness: float | None = None

    if area is not None and yield_strength is not None:
        slenderness = check_euler_slenderness(
            length=length,
            k_factor=k_factor,
            I_min=I_min,
            area=area,
            E=E,
            yield_strength=yield_strength,
        )
        sy_pa = _pa(yield_strength, "yield_strength")
        crit_slenderness = math.sqrt(2.0 * math.pi**2 * e_pa / sy_pa)

    le = k_val * l_m
    p_cr = math.pi**2 * e_pa * i_m4 / (le**2)

    sf: float | None = None
    if load is not None:
        p_applied = _n(load, "load")
        sf = p_cr / p_applied if p_applied > 0 else float("inf")

    return BucklingResult(
        critical_load=Quantity(p_cr, "N"),
        safety_factor=sf,
        slenderness=slenderness,
        critical_slenderness=crit_slenderness,
        formula="P_cr = pi^2 * E * I / (K*L)^2",
        source="Euler column buckling: Roark Table 15.1; AISC Table C-A-7.1",
    )


euler_buckling = euler_buckling_load


def tip_over_safety_factor(
    mass: Qty,
    cg_x: Qty,
    edge_load: Qty,
    overhang_x: Qty,
) -> TipOverResult:
    r"""Safety factor against tipping under an eccentric or edge downward load.

    Evaluates restoring gravity moment against overturning moment about the tipping
    fulcrum: :math:`FS = \frac{m g x_{\text{cg}}}{F_{\text{edge}} x_{\text{overhang}}}`.

    Args:
        mass: total supported mass (mass, m).
        cg_x: horizontal distance from tipping pivot to center of gravity (length).
        edge_load: vertical downward load applied at overhang (force).
        overhang_x: horizontal distance from tipping pivot to edge load (length).

    Returns:
        :class:`TipOverResult` with safety factor, restoring and overturning moments.
    """
    m_kg = _kg(mass, "mass")
    x_cg_m = _m(cg_x, "cg_x")
    f_edge_n = _n(edge_load, "edge_load")
    x_oh_m = _m(overhang_x, "overhang_x")

    if m_kg < 0 or x_cg_m < 0 or f_edge_n < 0 or x_oh_m < 0:
        raise ValueError("mass, cg_x, edge_load, and overhang_x must be non-negative")

    m_restoring = m_kg * _G_SI * x_cg_m
    m_overturning = f_edge_n * x_oh_m

    if m_overturning == 0:
        sf = float("inf")
    elif m_restoring == 0:
        sf = 0.0
    else:
        sf = m_restoring / m_overturning

    return TipOverResult(
        safety_factor=sf,
        restoring_moment=Quantity(m_restoring, "N*m"),
        overturning_moment=Quantity(m_overturning, "N*m"),
        formula="FS = (mass * g * cg_x) / (edge_load * overhang_x)",
        source="Static equilibrium, restoring vs overturning moment (Track A §3.1)",
    )


def fastener_group_shear(
    shear_force: Qty,
    count: int,
    bolt_area: Qty,
    shear_strength: Qty | None = None,
) -> ShearResult:
    r"""Direct nominal shear stress and allowable safety factor for a fastener group.

    Evaluates :math:`\tau = \frac{V}{n A_s}` and
    :math:`FS_{\text{shear}} = \frac{\tau_{\text{allow}}}{\tau}`.

    Args:
        shear_force: total shear force on the fastener group (force, V).
        count: number of shear-resisting fasteners (int, n >= 1).
        bolt_area: shear or tensile stress area per fastener (area, A_s).
        shear_strength: allowable shear strength of fastener material (pressure/stress, optional).

    Returns:
        :class:`ShearResult` with shear stress and safety factor.
    """
    v_n = _n(shear_force, "shear_force")
    if count < 1:
        raise ValueError(f"count must be at least 1, got {count}")
    as_m2 = _m2(bolt_area, "bolt_area")
    if as_m2 <= 0:
        raise ValueError(f"bolt_area must be positive, got {as_m2} m²")

    tau = v_n / (count * as_m2)
    sf: float | None = None
    if shear_strength is not None:
        tau_allow = _pa(shear_strength, "shear_strength")
        if tau_allow <= 0:
            raise ValueError(f"shear_strength must be positive, got {tau_allow} Pa")
        sf = tau_allow / tau if tau > 0 else float("inf")

    return ShearResult(
        shear_stress=Quantity(tau, "Pa"),
        safety_factor=sf,
        formula="\u03c4 = V / (n * A_s), FS = \u03c4_allow / \u03c4",
        source="Shigley's Mechanical Engineering Design, 11th ed., §8-5, bolted shear",
    )
