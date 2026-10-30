"""Material density table for mass estimates.

Values are nominal handbook densities; a part may override with ``material.density``.
Sources are noted per row; unusual materials are flagged ``[verify]`` in DECISIONS.md.
"""

from __future__ import annotations

from typing import Any

from napkin2factory.core.units import Quantity

#: Lower-case substring → density in kg/m³.  First match wins, so order matters.
DENSITIES: list[tuple[str, float, str]] = [
    ("stainless", 7900.0, "AISI 304, ~7.9 g/cm³ (Matweb)"),
    ("mild steel", 7850.0, "carbon steel 7.85 g/cm³ (handbook)"),
    ("steel", 7850.0, "carbon steel 7.85 g/cm³ (handbook)"),
    ("aluminium", 2700.0, "Al 2.70 g/cm³ (handbook)"),
    ("aluminum", 2700.0, "Al 2.70 g/cm³ (handbook)"),
    ("brass", 8500.0, "CuZn ~8.5 g/cm³ (handbook)"),
    ("copper", 8960.0, "Cu 8.96 g/cm³ (handbook)"),
    ("k23", 480.0, "insulating firebrick K23 ~0.48 g/cm³ [verify]"),
    ("firebrick", 480.0, "insulating firebrick ~0.48 g/cm³ [verify]"),
    ("ceramic fiber", 300.0, "ceramic fiber board ~0.30 g/cm³ (vendor range 0.25–0.35) [verify]"),
    ("fiber board", 300.0, "ceramic fiber board ~0.30 g/cm³ [verify]"),
    ("kanthal", 7100.0, "Kanthal A1 7.10 g/cm³ (Kanthal datasheet)"),
    ("plywood", 600.0, "softwood plywood ~0.6 g/cm³"),
    ("mdf", 750.0, "MDF ~0.75 g/cm³"),
    ("acrylic", 1180.0, "PMMA 1.18 g/cm³"),
    ("pla", 1240.0, "PLA 1.24 g/cm³"),
    ("abs", 1040.0, "ABS 1.04 g/cm³"),
    ("nylon", 1150.0, "PA6 1.15 g/cm³"),
    ("rubber", 1100.0, "elastomer ~1.1 g/cm³"),
    ("glass", 2500.0, "soda-lime glass 2.5 g/cm³"),
]
DEFAULT_DENSITY = 7850.0


def density_kg_m3(material: Any) -> tuple[float, str]:
    """Density (kg/m³) and its source for a :class:`Material` or a name string."""
    if material is None:
        return DEFAULT_DENSITY, "no material declared; assumed mild steel"
    declared = getattr(material, "density", None)
    if declared is not None:
        return float(Quantity(declared).to("kg/m**3").magnitude), "declared on the part"
    name = str(getattr(material, "name", material)).lower()
    spec = str(getattr(material, "spec", "") or "").lower()
    for key, rho, src in DENSITIES:
        if key in name or key in spec:
            return rho, src
    return DEFAULT_DENSITY, f"unknown material {name!r}; assumed mild steel"
