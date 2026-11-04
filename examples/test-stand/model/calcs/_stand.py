"""Shared pieces of the stand's calcs: the frame sections and the aluminium's stiffness.

Not a calc itself (no public function, no reference case). The sections come from
``calckit.structural`` (Roark Table 1) and the stiffness and yield strength from the shared
materials table (``calckit/data/materials.yaml``, row aluminum-6063-t5, ASM Handbook Vol 2 /
MatWeb [verify]), the one source the napkin screen reads too (W2).
"""

from __future__ import annotations

from napkin2factory.calckit import structural
from napkin2factory.core.units import Quantity
from napkin2factory.geometry.materials import material_row

FRAME_MATERIAL = "aluminum-6063-t5"


def _frame_stock() -> tuple[Quantity, Quantity]:
    """Young's modulus and yield strength of the frame aluminium, from the shared table."""
    row = material_row(FRAME_MATERIAL)
    if row is None or row.get("youngs_modulus") is None or row.get("yield_strength") is None:
        raise ValueError(f"no stiffness and strength on file for {FRAME_MATERIAL}")
    return Quantity(float(row["youngs_modulus"]), "Pa"), Quantity(
        float(row["yield_strength"]), "Pa"
    )


def _beam_section(P):  # noqa: N803
    """The crosshead and base beam: rectangular hollow section, width x height x wall."""
    return structural.rect_tube_section(P["beam-width"], P["beam-height"], P["beam-wall"])


def _column_section(P):  # noqa: N803
    """A column: square hollow section."""
    return structural.rect_tube_section(P["column-size"], P["column-size"], P["column-wall"])


def _beam_peak_stress(P):  # noqa: N803
    """Bending stress at mid-span of a beam carrying the whole rated load: M = F L / 4, M / Z."""
    _, sy = _frame_stock()
    moment = (P["rated-load"] * P["span"] / 4).to("N*m")
    return structural.beam_bending_stress(moment, _beam_section(P).Zx, sy)
