"""Beam deflection (simply supported; cantilever with column rotation), flexure and yield margin."""

from __future__ import annotations

from dataclasses import dataclass

from napkin2factory.calckit.structural._units import Qty, _m, _m3, _m4, _n, _nm, _pa
from napkin2factory.core.units import Quantity, UnitError

# --- result dataclasses -------------------------------------------------------------


@dataclass(frozen=True)
class DeflectionResult:
    """Deflection of a loaded beam member.

    Attributes:
        deflection: elastic deflection (length).
        formula: governing formula text.
        source: published citation.
    """

    deflection: Qty
    formula: str
    source: str

    @property
    def value(self) -> Qty:
        """The deflection quantity for screen cards."""
        return self.deflection


@dataclass(frozen=True)
class BendingStressResult:
    r"""Bending stress and optional yield margin.

    Attributes:
        stress: nominal bending stress :math:`M / Z` (pressure).
        yield_factor: yield safety factor :math:`\\sigma_y / \\sigma_b` (dimensionless), or None.
        formula: governing formula text.
        source: published citation.
    """

    stress: Qty
    yield_factor: float | None
    formula: str
    source: str

    @property
    def value(self) -> Qty:
        """The bending stress quantity for screen cards."""
        return self.stress


# --- beam deflections ---------------------------------------------------------------


def beam_deflection_simply_supported(
    force: Qty,
    span: Qty,
    E: Qty,
    I: Qty,  # noqa: E741
    load_kind: str = "point_center",
) -> DeflectionResult:
    """Maximum deflection of a simply supported beam.

    Args:
        force: applied load. For ``point_center``, total point force (force).
            For ``uniform``, either total force on span (force) or distributed load (force/length).
        span: supported span length (length, L).
        E: Young's modulus of elasticity (pressure/stress, E).
        I: area moment of inertia about bending axis (length⁴, I).
        load_kind: ``"point_center"`` (FL³/48EI) or ``"uniform"`` (5wL⁴/384EI).

    Returns:
        :class:`DeflectionResult` with deflection, formula and citation.
    """
    l_m = _m(span, "span")
    e_pa = _pa(E, "E")
    i_m4 = _m4(I, "I")
    if l_m <= 0 or e_pa <= 0 or i_m4 <= 0:
        raise ValueError("span, modulus, and moment of inertia must be positive")

    kind = load_kind.strip().lower().replace("-", "_")
    if kind in ("point", "point_center", "center", "centre"):
        f_n = _n(force, "force")
        delta = f_n * l_m**3 / (48.0 * e_pa * i_m4)
        formula = "FL^3 / (48*E*I)"
        source = "Roark's Formulas for Stress and Strain, 7th ed., Table 8.1, Case 1d"
    elif kind in ("uniform", "distributed"):
        if not hasattr(force, "check"):
            raise UnitError(f"force must be a quantity, got {force!r}")
        if force.check("[force]"):
            w_total = float(force.to("N").magnitude)
            delta = 5.0 * w_total * l_m**3 / (384.0 * e_pa * i_m4)
        elif force.check("[force] / [length]"):
            w_per_m = float(force.to("N/m").magnitude)
            delta = 5.0 * w_per_m * l_m**4 / (384.0 * e_pa * i_m4)
        else:
            raise UnitError(
                f"uniform load must have units of force (total) or force/length, got {force.units}"
            )
        formula = "5*w*L^4 / (384*E*I)"
        source = "Roark's Formulas for Stress and Strain, 7th ed., Table 8.1, Case 1e"
    else:
        raise ValueError(f"unknown load_kind {load_kind!r}; expected 'point_center' or 'uniform'")

    return DeflectionResult(
        deflection=Quantity(delta, "m"),
        formula=formula,
        source=source,
    )


simply_supported_deflection = beam_deflection_simply_supported


def beam_deflection_cantilever(
    force: Qty,
    overhang: Qty,
    column_height: Qty | None,
    E: Qty,
    I_arm: Qty,
    I_col: Qty | None = None,
) -> DeflectionResult:
    r"""Tip deflection of a cantilever arm including support column rotation.

    Total tip deflection is the sum of arm bending :math:`\\frac{F L_a^3}{3 E I_a}`
    and column rotation under moment :math:`M = F L_a`, rotating the arm tip by
    :math:`\\theta L_a = \\frac{F L_a^2 H}{E I_c}` (Track A §3.1).

    Args:
        force: downward point load at the tip (force, F).
        overhang: cantilever arm length (length, L_a).
        column_height: height of vertical support column (length, H), or None / 0.
        E: Young's modulus of elasticity (pressure/stress).
        I_arm: moment of inertia of cantilever arm (length⁴, I_a).
        I_col: moment of inertia of column (length⁴, I_c); defaults to ``I_arm``.

    Returns:
        :class:`DeflectionResult` with total deflection, formula and citation.
    """
    f_n = _n(force, "force")
    la_m = _m(overhang, "overhang")
    e_pa = _pa(E, "E")
    ia_m4 = _m4(I_arm, "I_arm")
    if la_m <= 0 or e_pa <= 0 or ia_m4 <= 0:
        raise ValueError("overhang, modulus, and I_arm must be positive")

    h_m = _m(column_height, "column_height") if column_height is not None else 0.0
    if h_m < 0:
        raise ValueError("column_height must be non-negative")

    delta_arm = f_n * la_m**3 / (3.0 * e_pa * ia_m4)

    if h_m > 0:
        ic_m4 = _m4(I_col, "I_col") if I_col is not None else ia_m4
        if ic_m4 <= 0:
            raise ValueError("I_col must be positive")
        delta_col = f_n * (la_m**2) * h_m / (e_pa * ic_m4)
        total = delta_arm + delta_col
        formula = "FL_a^3 / (3*E*I_a) + FL_a^2*H / (E*I_c)"
        source = (
            "Roark's Formulas for Stress and Strain, 7th ed., "
            "Table 8.1, Cases 1a & 3a (Track A §3.1)"
        )
    else:
        total = delta_arm
        formula = "FL^3 / (3*E*I)"
        source = "Roark's Formulas for Stress and Strain, 7th ed., Table 8.1, Case 1a"

    return DeflectionResult(
        deflection=Quantity(total, "m"),
        formula=formula,
        source=source,
    )


cantilever_deflection = beam_deflection_cantilever


# --- bending stress and yield factor ------------------------------------------------


def beam_bending_stress(
    moment: Qty,
    section_modulus: Qty,
    yield_strength: Qty | None = None,
) -> BendingStressResult:
    r"""Nominal bending stress and yield safety factor.

    Args:
        moment: bending moment :math:`M` (moment).
        section_modulus: section modulus :math:`Z` about bending axis (length³).
        yield_strength: material yield strength :math:`\\sigma_y` (pressure/stress, optional).

    Returns:
        :class:`BendingStressResult` with stress and yield factor.
    """
    m_nm = _nm(moment, "moment")
    z_m3 = _m3(section_modulus, "section_modulus")
    if z_m3 <= 0:
        raise ValueError(f"section_modulus must be positive, got {z_m3} m³")

    sigma = m_nm / z_m3
    yf: float | None = None
    if yield_strength is not None:
        sy_pa = _pa(yield_strength, "yield_strength")
        if sy_pa <= 0:
            raise ValueError(f"yield_strength must be positive, got {sy_pa} Pa")
        yf = sy_pa / abs(sigma) if sigma != 0 else float("inf")

    return BendingStressResult(
        stress=Quantity(sigma, "Pa"),
        yield_factor=yf,
        formula="\u03c3 = M / Z, FS = \u03c3_y / \u03c3",
        source="Roark's Formulas for Stress and Strain, 7th ed., Chapter 8, Section 8.1",
    )


def yield_safety_factor(stress: Qty, yield_strength: Qty) -> float:
    r"""Yield safety factor, :math:`FS_y = \\sigma_y / \\sigma`.

    Args:
        stress: applied stress (pressure/stress).
        yield_strength: material yield strength (pressure/stress).

    Returns:
        dimensionless safety factor (float).
    """
    s_pa = abs(_pa(stress, "stress"))
    sy_pa = _pa(yield_strength, "yield_strength")
    if sy_pa <= 0:
        raise ValueError("yield_strength must be positive")
    if s_pa == 0:
        return float("inf")
    return sy_pa / s_pa
