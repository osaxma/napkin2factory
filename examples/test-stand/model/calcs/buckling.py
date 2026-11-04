"""Column buckling with the rated load reversed (a pull test), SPEC section 4.3."""

from __future__ import annotations

from _stand import _column_section, _frame_stock

from napkin2factory.calckit import structural
from napkin2factory.core.units import Quantity

#: Effective length factor of the sway mode, the base beam rigid on the console and the top
#: free to sway: the fixed-free design value (AISC Table C-A-7.1, case e).
K_SWAY = 2.1


def buckling_factor(P):  # noqa: N803
    """Buckling factor of one column under half the rated load, in compression.

    Euler or Johnson by slenderness, K = 2.1 (Roark Table 15.1, AISC Table C-A-7.1;
    ``structural.column_buckling_load``).
    """
    e, sy = _frame_stock()
    sec = _column_section(P)
    res = structural.column_buckling_load(
        e, min(sec.Ix, sec.Iy), sec.A, sy, P["column-length"], K_SWAY, load=P["rated-load"] / 2
    )
    return Quantity(float(res.safety_factor), "")
