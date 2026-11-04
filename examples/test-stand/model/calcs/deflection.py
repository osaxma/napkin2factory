"""Frame deflection at the load axis under the rated load (SPEC section 4.3)."""

from __future__ import annotations

from _stand import _beam_section, _column_section, _frame_stock

from napkin2factory.calckit import structural


def frame_deflection(P):  # noqa: N803
    """Deflection at the load axis under the rated load.

    Two beams, each simply supported on the column centre lines and loaded at mid-span (Roark
    Table 8.1 case 1d), plus the stretch of the two columns, each carrying half the load in
    tension (Hooke's law). Shear deflection of the beams and joint compliance are not counted
    (SPEC section 4.3 states both).
    """
    e, _ = _frame_stock()
    f = P["rated-load"]
    per_beam = structural.beam_deflection_simply_supported(f, P["span"], e, _beam_section(P).Ix)
    stretch = (f / 2) * P["column-length"] / (e * _column_section(P).A)
    return (2 * per_beam.deflection + stretch).to("mm")
