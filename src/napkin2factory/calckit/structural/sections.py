"""Cross-section properties: solid rectangles, rectangular and round tubing (Roark Table 1)."""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass

from napkin2factory.calckit.structural._units import Qty, _m
from napkin2factory.core.units import Quantity

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
    source: str = "Roark's Formulas for Stress and Strain, 7th ed., Table 1, Case 1 [verify]"

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
    source: str = "Roark's Formulas for Stress and Strain, 7th ed., Table 1, Case 2 [verify]"

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
    source: str = "Roark's Formulas for Stress and Strain, 7th ed., Table 1, Case 12 [verify]"

    def __iter__(self) -> Iterator[Qty]:
        return iter((self.I, self.Z, self.A))

    def __len__(self) -> int:
        return 3

    def __getitem__(self, idx: int) -> Qty:
        return (self.I, self.Z, self.A)[idx]


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
