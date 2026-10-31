"""Helpers shared by generators: quantity coercion, hole cutting, dimension callouts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BeforeValidator
from typing_extensions import Annotated

from napkin2factory.core.units import UnitError, parse_quantity
from napkin2factory.core.units import mm as _mm
from napkin2factory.geometry.features import Dim, Features, PartResult

if TYPE_CHECKING:
    from napkin2factory.geometry.kit import KitContext

MASSING_NOTE = "massing silhouette: features omitted"


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


def massing_result(
    shape: Any,
    process: str,
    dims: list[Dim],
    ctx: KitContext,
    props: dict[str, Any] | None = None,
) -> PartResult:
    """Wrap a silhouette solid as a massing-fidelity :class:`PartResult` (N3).

    Features carry only the process and ``extra = {"fidelity": "massing"}``; there is no
    flat pattern and no cut list.

    Args:
        shape: the silhouette solid, built from primitives in the full path's frame.
        process: the same process string the full path declares.
        dims: the overall dimension callouts.
        ctx: generator context (labels the shape with ``ctx.uri``).
        props: extra cheap scalars that still hold for the silhouette.

    Returns:
        The massing result.
    """
    shape.label = ctx.uri
    return PartResult(
        shape=shape,
        features=Features(process=process, extra={"fidelity": "massing"}),
        dims=dims,
        flat_pattern=None,
        cut_list=[],
        props={"fidelity": "massing", **(props or {})},
        notes=[MASSING_NOTE],
    )
