"""Bending and axial stress and yield factors of the frame (SPEC section 4.3)."""

from __future__ import annotations

from _stand import _beam_peak_stress, _column_section, _frame_stock

from napkin2factory.core.units import Quantity


def beam_bending_stress(P):  # noqa: N803
    """Peak bending stress of the crosshead and base beam, M / Z with M = F L / 4."""
    return _beam_peak_stress(P).stress.to("MPa")


def column_axial_stress(P):  # noqa: N803
    """Tension in each column: half the rated load over its section area."""
    return ((P["rated-load"] / 2) / _column_section(P).A).to("MPa")


def yield_factor(P):  # noqa: N803
    """The lower of the beams' and the columns' yield factors (the beams govern)."""
    _, sy = _frame_stock()
    beams = _beam_peak_stress(P).yield_factor
    columns = float((sy / column_axial_stress(P)).to("").magnitude)
    return Quantity(min(beams, columns), "")
