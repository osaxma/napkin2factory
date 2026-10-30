"""Helpers shared by generators: quantity coercion, hole cutting, dimension callouts."""

from __future__ import annotations

from typing import Any

from pydantic import BeforeValidator
from typing_extensions import Annotated

from napkin2factory.core.units import UnitError, parse_quantity
from napkin2factory.core.units import mm as _mm


def _length_mm(v: Any) -> float:
    """Accept a pint quantity, a '15 mm' string, or a bare number (millimetres)."""
    if hasattr(v, "to"):
        return float(_mm(v))
    if isinstance(v, bool):
        raise ValueError("expected a length")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            q = parse_quantity(v)
        except UnitError as exc:
            raise ValueError(str(exc)) from exc
        if q.dimensionless:
            return float(q.magnitude)
        return float(_mm(q))
    raise ValueError(f"expected a length, got {v!r}")


def _angle_deg(v: Any) -> float:
    if hasattr(v, "to"):
        return float(v.to("degree").magnitude)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        q = parse_quantity(v)
        return float(q.magnitude if q.dimensionless else q.to("degree").magnitude)
    raise ValueError(f"expected an angle, got {v!r}")


def _count(v: Any) -> int:
    if hasattr(v, "magnitude"):
        v = v.magnitude
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"expected a count, got {v!r}")
    if int(v) != v or v < 0:
        raise ValueError(f"expected a non-negative integer, got {v!r}")
    return int(v)


Length = Annotated[float, BeforeValidator(_length_mm)]
Angle = Annotated[float, BeforeValidator(_angle_deg)]
Count = Annotated[int, BeforeValidator(_count)]


def require_positive(**values: float) -> None:
    """Raise ``ValueError`` naming the first non-positive argument."""
    for k, v in values.items():
        if not v > 0:
            raise ValueError(f"{k} must be positive, got {v}")
