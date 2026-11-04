r"""Envelope-grade structural mechanics: member sections, beams, buckling, and shear.

Pure functions taking and returning pint quantities from the shared registry
(:mod:`napkin2factory.core.units`), backed by handbook reference cases (Roark, Shigley,
AISC). Used by the generic ``structural`` napkin screen
(:mod:`napkin2factory.concepts.screens.structural`) and product-level sizing calcs (W1).

Method and physics (one source for screening and product calcs; W1):

* **Cross-section geometry.** Geometric properties of solid rectangles, hollow rectangular
  tubing, and circular tubing (Roark Table 1): area moment of inertia :math:`I`, section
  modulus :math:`Z = I / c`, and cross-sectional area :math:`A`.
* **Beam deflection.**
  - Simply supported: center point load :math:`\delta = \frac{F L^3}{48 E I}`
    (Roark Table 8.1 Case 1d) and uniform distributed load :math:`\delta = \frac{5 w L^4}{384 E I}`
    (Roark Table 8.1 Case 1e).
  - Cantilever with column rotation: tip deflection under end point load combined with the
    rotation of a vertical support column under moment :math:`M = F L_a`:
    :math:`\delta = \frac{F L_a^3}{3 E I_a} + \frac{F L_a^2 H}{E I_c}`
    (Roark Table 8.1 Cases 1a & 3a; Track A §3.1).
* **Bending stress and yield margin.** Flexure formula :math:`\sigma_b = \frac{M}{Z}` and
  yield safety factor :math:`FS_y = \frac{\sigma_y}{\sigma_b}` (Roark §8.1; Shigley §1-10).
* **Column stability (Euler buckling).** Critical elastic buckling load
  :math:`P_{cr} = \frac{\pi^2 E I_{\min}}{(K L)^2}` with effective length factor :math:`K`
  per end condition (AISC Table C-A-7.1; Shigley Table 4-2). A slenderness check verifies
  that :math:`\lambda = \frac{K L}{r} \ge \lambda_c = \sqrt{\frac{2 \pi^2 E}{\sigma_y}}`;
  slenderness below :math:`\lambda_c` falls in the inelastic range and is refused, naming
  Johnson's parabolic formula as not covered (Shigley §4-11).
* **Tip-over safety factor.** Ratio of gravity restoring moment to overturning moment
  :math:`FS = \frac{m g x_{\text{cg}}}{F_{\text{edge}} x_{\text{overhang}}}` (Track A §3.1).
* **Fastener group shear.** Direct shear stress per fastener :math:`\tau = \frac{V}{n A_s}`
  and safety factor against allowable shear strength
  :math:`FS = \frac{\tau_{\text{allow}}}{\tau}` (Shigley §8-5).

Every public function takes and returns pint quantities from the shared registry
(:mod:`napkin2factory.core.units`); floats are used only inside, in SI units.
Results suitable for concept screens carry the formula and published source.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from napkin2factory.calckit._cases import Case
from napkin2factory.core.units import Quantity, UnitError

#: A pint quantity from the shared registry (pint is untyped for mypy).
Qty = Any

#: Standard acceleration of gravity, m/s² (ISO 80000-3; CODATA).
STANDARD_GRAVITY = Quantity(9.80665, "m/s**2")
_G_SI = 9.80665


# --- unit conversion and boundary checks ---------------------------------------------


def _si(q: Qty, unit: str, example: str) -> float:
    """``q`` in ``unit`` as a float; bare number or wrong dimension raises UnitError."""
    if not hasattr(q, "to"):
        raise UnitError(
            f"structural expects a quantity like {example!r}, got the bare number {q!r}"
        )
    try:
        return float(q.to(unit).magnitude)
    except Exception as exc:
        raise UnitError(f"structural expects a quantity in {unit} ({example}): {exc}") from exc


def _m(q: Qty, name: str = "length") -> float:
    return _si(q, "m", f"{name}=100 mm")


def _m2(q: Qty, name: str = "area") -> float:
    return _si(q, "m**2", f"{name}=50 mm**2")


def _m3(q: Qty, name: str = "section modulus") -> float:
    return _si(q, "m**3", f"{name}=10000 mm**3")


def _m4(q: Qty, name: str = "moment of inertia") -> float:
    return _si(q, "m**4", f"{name}=1e6 mm**4")


def _n(q: Qty, name: str = "force") -> float:
    return _si(q, "N", f"{name}=1000 N")


def _nm(q: Qty, name: str = "moment") -> float:
    return _si(q, "N*m", f"{name}=150 N*m")


def _pa(q: Qty, name: str = "stress/modulus") -> float:
    return _si(q, "Pa", f"{name}=200 GPa")


def _kg(q: Qty, name: str = "mass") -> float:
    return _si(q, "kg", f"{name}=25 kg")


def _dimless(q: Qty, name: str = "dimensionless") -> float:
    return _si(q, "dimensionless", f"{name}=Quantity(1.0, '')")


# --- section dataclasses ------------------------------------------------------------


@dataclass(frozen=True)
class RectSection:
    """Properties of a solid rectangular cross-section.

    Attributes:
        I: strong-axis area moment of inertia :math:`I_x = b h^3 / 12` (length⁴).
        Z: strong-axis section modulus :math:`Z_x = b h^2 / 6` (length³).
        A: cross-sectional area :math:`A = b h` (length²).
        Ix: alias for ``I``.
        Iy: weak-axis area moment of inertia :math:`I_y = h b^3 / 12` (length⁴).
        Zx: alias for ``Z``.
        Zy: weak-axis section modulus :math:`Z_y = h b^2 / 6` (length³).
        formula: summary of governing formulas.
        source: handbook citation.
    """

    I: Qty  # noqa: E741
    Z: Qty
    A: Qty
    Ix: Qty
    Iy: Qty
    Zx: Qty
    Zy: Qty
    formula: str = "I = b*h^3/12, Z = b*h^2/6, A = b*h"
    source: str = "Roark's Formulas for Stress and Strain, 7th ed., Table 1, Case 1"

    def __iter__(self) -> Iterator[Qty]:
        return iter((self.I, self.Z, self.A))

    def __len__(self) -> int:
        return 3

    def __getitem__(self, idx: int) -> Qty:
        return (self.I, self.Z, self.A)[idx]


@dataclass(frozen=True)
class RectTubeSection:
    """Properties of a hollow rectangular cross-section (b × h × t).

    Attributes:
        Ix: strong-axis area moment of inertia (length⁴).
        Iy: weak-axis area moment of inertia (length⁴).
        Zx: strong-axis section modulus :math:`I_x / (h/2)` (length³).
        Zy: weak-axis section modulus :math:`I_y / (b/2)` (length³).
        A: cross-sectional area :math:`b h - (b-2t)(h-2t)` (length²).
        I: alias for strong-axis ``Ix``.
        Z: alias for strong-axis ``Zx``.
        formula: summary of governing formulas.
        source: handbook citation.
    """

    Ix: Qty
    Iy: Qty
    Zx: Qty
    Zy: Qty
    A: Qty
    I: Qty  # noqa: E741
    Z: Qty
    formula: str = "Ix = (b*h^3 - b1*h1^3)/12, Zx = Ix/(h/2), A = b*h - b1*h1"
    source: str = "Roark's Formulas for Stress and Strain, 7th ed., Table 1, Case 2"

    def __iter__(self) -> Iterator[Qty]:
        return iter((self.Ix, self.Iy, self.Zx, self.A))

    def __len__(self) -> int:
        return 4

    def __getitem__(self, idx: int) -> Qty:
        return (self.Ix, self.Iy, self.Zx, self.A)[idx]


@dataclass(frozen=True)
class RoundTubeSection:
    r"""Properties of a hollow circular cross-section (OD × t).

    Attributes:
        I: area moment of inertia :math:`\\pi (D^4 - d^4) / 64` (length⁴).
        Z: section modulus :math:`\\pi (D^4 - d^4) / (32 D)` (length³).
        A: cross-sectional area :math:`\\pi (D^2 - d^2) / 4` (length²).
        Ix: alias for ``I``.
        Iy: alias for ``I``.
        Zx: alias for ``Z``.
        Zy: alias for ``Z``.
        formula: summary of governing formulas.
        source: handbook citation.
    """

    I: Qty  # noqa: E741
    Z: Qty
    A: Qty
    Ix: Qty
    Iy: Qty
    Zx: Qty
    Zy: Qty
    formula: str = "I = pi*(D^4 - d^4)/64, Z = pi*(D^4 - d^4)/(32*D), A = pi*(D^2 - d^2)/4"
    source: str = "Roark's Formulas for Stress and Strain, 7th ed., Table 1, Case 12"

    def __iter__(self) -> Iterator[Qty]:
        return iter((self.I, self.Z, self.A))

    def __len__(self) -> int:
        return 3

    def __getitem__(self, idx: int) -> Qty:
        return (self.I, self.Z, self.A)[idx]


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


# --- sections -----------------------------------------------------------------------


def rect_section(width: Qty, height: Qty) -> RectSection:
    """Geometric properties of a solid rectangular cross-section.

    Args:
        width: section width (length, horizontal dimension b).
        height: section height (length, vertical dimension h, bending axis).

    Returns:
        :class:`RectSection` with I, Z, A for both axes.
    """
    b = _m(width, "width")
    h = _m(height, "height")
    if b <= 0 or h <= 0:
        raise ValueError(f"dimensions must be positive, got width={b} m, height={h} m")
    a = b * h
    ix = b * h**3 / 12.0
    iy = h * b**3 / 12.0
    zx = b * h**2 / 6.0
    zy = h * b**2 / 6.0
    return RectSection(
        I=Quantity(ix, "m**4"),
        Z=Quantity(zx, "m**3"),
        A=Quantity(a, "m**2"),
        Ix=Quantity(ix, "m**4"),
        Iy=Quantity(iy, "m**4"),
        Zx=Quantity(zx, "m**3"),
        Zy=Quantity(zy, "m**3"),
    )


rect_section_inertia = rect_section


def rect_tube_section(width: Qty, height: Qty, thickness: Qty) -> RectTubeSection:
    """Geometric properties of a hollow rectangular cross-section (b × h × t).

    Args:
        width: outer section width (length, b).
        height: outer section height (length, h).
        thickness: uniform wall thickness (length, t).

    Returns:
        :class:`RectTubeSection` with Ix, Iy, Zx, Zy, A.
    """
    b = _m(width, "width")
    h = _m(height, "height")
    t = _m(thickness, "thickness")
    if b <= 0 or h <= 0 or t <= 0:
        raise ValueError(f"dimensions must be positive, got b={b}, h={h}, t={t}")
    if 2.0 * t >= b or 2.0 * t >= h:
        raise ValueError(
            f"wall thickness (2*t = {2 * t * 1e3:.2f} mm) must be less than outer width "
            f"({b * 1e3:.2f} mm) and height ({h * 1e3:.2f} mm)"
        )
    bi = b - 2.0 * t
    hi = h - 2.0 * t
    a = b * h - bi * hi
    ix = (b * h**3 - bi * hi**3) / 12.0
    iy = (h * b**3 - hi * bi**3) / 12.0
    zx = ix / (h / 2.0)
    zy = iy / (b / 2.0)
    return RectTubeSection(
        Ix=Quantity(ix, "m**4"),
        Iy=Quantity(iy, "m**4"),
        Zx=Quantity(zx, "m**3"),
        Zy=Quantity(zy, "m**3"),
        A=Quantity(a, "m**2"),
        I=Quantity(ix, "m**4"),
        Z=Quantity(zx, "m**3"),
    )


tube_section_inertia = rect_tube_section


def round_tube_section(outer_diameter: Qty, thickness: Qty) -> RoundTubeSection:
    """Geometric properties of a hollow circular cross-section (OD × t).

    Args:
        outer_diameter: outer diameter (length, D).
        thickness: uniform wall thickness (length, t).

    Returns:
        :class:`RoundTubeSection` with I, Z, A.
    """
    d_out = _m(outer_diameter, "outer_diameter")
    t = _m(thickness, "thickness")
    if d_out <= 0 or t <= 0:
        raise ValueError(f"dimensions must be positive, got OD={d_out}, t={t}")
    if 2.0 * t >= d_out:
        raise ValueError(
            f"wall thickness (2*t = {2 * t * 1e3:.2f} mm) must be less than "
            f"outer diameter ({d_out * 1e3:.2f} mm)"
        )
    d_in = d_out - 2.0 * t
    a = math.pi / 4.0 * (d_out**2 - d_in**2)
    i = math.pi / 64.0 * (d_out**4 - d_in**4)
    z = i / (d_out / 2.0)
    return RoundTubeSection(
        I=Quantity(i, "m**4"),
        Z=Quantity(z, "m**3"),
        A=Quantity(a, "m**2"),
        Ix=Quantity(i, "m**4"),
        Iy=Quantity(i, "m**4"),
        Zx=Quantity(z, "m**3"),
        Zy=Quantity(z, "m**3"),
    )


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

__all__ = [
    "CASES",
    "K_FACTORS",
    "K_FACTORS_THEORETICAL",
    "STANDARD_GRAVITY",
    "BendingStressResult",
    "BucklingResult",
    "DeflectionResult",
    "RectSection",
    "RectTubeSection",
    "RoundTubeSection",
    "ShearResult",
    "TipOverResult",
    "beam_bending_stress",
    "beam_deflection_cantilever",
    "beam_deflection_simply_supported",
    "cantilever_deflection",
    "check_euler_slenderness",
    "euler_buckling",
    "euler_buckling_load",
    "fastener_group_shear",
    "rect_section",
    "rect_section_inertia",
    "rect_tube_section",
    "round_tube_section",
    "simply_supported_deflection",
    "tip_over_safety_factor",
    "tube_section_inertia",
    "yield_safety_factor",
]
