"""Material density table for mass estimates.

Values are nominal handbook densities; a part may override with ``material.density``.
Sources are noted per row; unusual materials are flagged ``[verify]`` in DECISIONS.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napkin2factory.core.units import Quantity

#: The shared table (the calc kit's): massing, screening and part masses read one number.
SHARED_TABLE = Path(__file__).resolve().parents[1] / "calckit" / "data" / "materials.yaml"
#: Density key → the name of the shared row it was read from.
_SHARED_ROWS: dict[str, str] = {}


def _shared_row(name: str, table: Path | None = None) -> dict[str, Any]:
    # read the file itself: importing the calckit package here would import mass_cost,
    # which imports this module
    from napkin2factory.core.yamlio import read_yaml

    rows = read_yaml(table or SHARED_TABLE)["rows"]
    return dict(next(r for r in rows if r["name"] == name))


def _shared(name: str, keys: tuple[str, ...]) -> list[tuple[str, float, str]]:
    """Density rows from ``calckit/data/materials.yaml``, the table screening reads too.

    One row per material keeps the massing, concept screening and the calc kit on the same
    number (review gate A, C4).
    """
    row = _shared_row(name)
    rho = float(row["density"])
    src = f"{row['name']} {rho / 1000:g} g/cm³ (calckit/data/materials.yaml) [verify]"
    _SHARED_ROWS.update(dict.fromkeys(keys, name))
    return [(key, rho, src) for key in keys]


#: Lower-case substring → density in kg/m³.  First match wins, so order matters.
DENSITIES: list[tuple[str, float, str]] = [
    ("stainless", 7900.0, "AISI 304, ~7.9 g/cm³ (Matweb)"),
    *_shared("mild steel", ("mild steel", "steel")),
    ("aluminium", 2700.0, "Al 2.70 g/cm³ (handbook)"),
    ("aluminum", 2700.0, "Al 2.70 g/cm³ (handbook)"),
    ("brass", 8500.0, "CuZn ~8.5 g/cm³ (handbook)"),
    ("copper", 8960.0, "Cu 8.96 g/cm³ (handbook)"),
    *_shared("K-23 insulating firebrick", ("k23", "firebrick")),
    *_shared("ceramic fiber board (Kaowool 1260)", ("ceramic fiber", "fiber board")),
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


def _match(material: Any) -> str | None:
    """The :data:`DENSITIES` key a named material matches (first match wins), or ``None``."""
    name = str(getattr(material, "name", material)).lower()
    spec = str(getattr(material, "spec", "") or "").lower()
    return next((key for key, _, _ in DENSITIES if key in name or key in spec), None)


def density_kg_m3(material: Any) -> tuple[float, str]:
    """Density (kg/m³) and its source for a :class:`Material` or a name string."""
    if material is None:
        return DEFAULT_DENSITY, "no material declared; assumed mild steel"
    declared = getattr(material, "density", None)
    if declared is not None:
        return float(Quantity(declared).to("kg/m**3").magnitude), "declared on the part"
    key = _match(material)
    for k, rho, src in DENSITIES:
        if k == key:
            return rho, src
    name = str(getattr(material, "name", material)).lower()
    return DEFAULT_DENSITY, f"unknown material {name!r}; assumed mild steel"


def density_input(material: Any, table: Path | None = None) -> str:
    """What a part's mass reads outside the geometry package: its shared density row.

    A part whose density comes from :data:`SHARED_TABLE` (``calckit/data/materials.yaml``)
    gets ``"<row name>: <density>"``, read from the file now, so the part rule's key moves
    when that density is edited and the parts of other materials keep theirs (S-129).  A
    density declared on the part, or held in this module, is already in the part's own file
    or the geometry package hash: ``"package"``.
    """
    if material is None or getattr(material, "density", None) is not None:
        return "package"
    row_name = _SHARED_ROWS.get(_match(material) or "")
    if row_name is None:
        return "package"
    return f"{row_name}: {_shared_row(row_name, table)['density']}"
