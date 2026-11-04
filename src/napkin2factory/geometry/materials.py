"""Material density table for mass estimates.

Values are nominal handbook densities read from the shared calc-kit table
(``calckit/data/materials.yaml``, W2); a part may override with ``material.density``.
Sources are noted per row; unusual materials are flagged ``[verify]`` in DECISIONS.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napkin2factory.core.units import Quantity

#: The shared table (the calc kit's): massing, screening and part masses read one number (W2).
SHARED_TABLE = Path(__file__).resolve().parents[1] / "calckit" / "data" / "materials.yaml"

#: Default fallback density (kg/m3) when no material is declared (mild steel).
DEFAULT_DENSITY = 7850.0

_CACHE: tuple[Path, int, list[dict[str, Any]]] | None = None


def _load_rows(table: Path | None = None) -> list[dict[str, Any]]:
    global _CACHE
    target = table or SHARED_TABLE
    try:
        mtime = target.stat().st_mtime_ns
    except OSError:
        mtime = 0
    if _CACHE is not None and _CACHE[0] == target and _CACHE[1] == mtime:
        return _CACHE[2]
    from napkin2factory.core.yamlio import read_yaml

    rows = list(read_yaml(target)["rows"])
    _CACHE = (target, mtime, rows)
    return rows


def _match_row(material: Any, table: Path | None = None) -> dict[str, Any] | None:
    """The row in ``materials.yaml`` that ``material`` matches (first match wins), or ``None``."""
    if material is None:
        return None
    name = str(getattr(material, "name", material)).lower()
    spec = str(getattr(material, "spec", "") or "").lower()
    rows = _load_rows(table)
    # 1. Match material name against keywords or row name
    for row in rows:
        keywords = [str(k).lower() for k in row.get("keywords", [])]
        row_name = str(row.get("name", "")).lower()
        if any(kw in name for kw in keywords) or (row_name and row_name in name):
            return row
    # 2. If name did not match, check spec against keywords or row name
    if spec:
        for row in rows:
            keywords = [str(k).lower() for k in row.get("keywords", [])]
            row_name = str(row.get("name", "")).lower()
            if any(kw in spec for kw in keywords) or (row_name and row_name in spec):
                return row
    return None


def density_is_assumed(material: Any) -> bool:
    """Whether the density for ``material`` is assumed rather than known.

    Returns True when :func:`density_kg_m3` would fall back to :data:`DEFAULT_DENSITY`
    (mild steel) because no material is declared, or the material matches no known entry
    in ``materials.yaml`` and declares no explicit density (S-186).
    """
    if material is None:
        return True
    declared = getattr(material, "density", None)
    if declared is not None:
        return False
    return _match_row(material) is None


def density_kg_m3(material: Any) -> tuple[float, str]:
    """Density (kg/m³) and its source for a :class:`Material` or a name string."""
    if material is None:
        return DEFAULT_DENSITY, "no material declared; assumed mild steel"
    declared = getattr(material, "density", None)
    if declared is not None:
        return float(Quantity(declared).to("kg/m**3").magnitude), "declared on the part"
    row = _match_row(material)
    if row is not None:
        rho = float(row["density"])
        src = f"{row['name']} {rho / 1000:g} g/cm³ (calckit/data/materials.yaml)"
        if row.get("verify"):
            src += " [verify]"
        return rho, src
    name = str(getattr(material, "name", material)).lower()
    return DEFAULT_DENSITY, f"unknown material {name!r}; assumed mild steel"


def density_input(material: Any, table: Path | None = None) -> str:
    """What a part's mass reads outside the geometry package: its shared density row.

    A part whose density comes from :data:`SHARED_TABLE` (``calckit/data/materials.yaml``)
    gets ``"<row name>: <density>"``, read from the file now, so the part rule's key moves
    when that density is edited and the parts of other materials keep theirs (S-129). A
    density declared on the part, or held in this module, is already in the part's own file
    or the geometry package hash: ``"package"``.
    """
    if material is None or getattr(material, "density", None) is not None:
        return "package"
    row = _match_row(material, table)
    if row is None:
        return "package"
    return f"{row['name']}: {row['density']}"
