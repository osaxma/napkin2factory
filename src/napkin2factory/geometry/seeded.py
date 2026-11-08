"""Placement for an assembly that promotion seeded from a concept card (S-336).

``n2f concept promote`` writes, per seeded assembly, a geometry module whose ``build()`` calls
:func:`place_rows` with a table: one row per placed instance, saying per axis which face of the
product's overall box the instance keeps to and how far from it. The three overall sizes are
parameters, so changing one moves the instances that keep to its far face and (through the
parts' own expressions) stretches the pieces that span it.

A row is ``{"part": id, "label": name, "rz": degrees, "x": (anchor, mm), "y": ..., "z": ...}``
(or ``{"asm": id}`` for a sub-assembly, placed at the origin because its own table is in the
product's frame). Per axis the anchor is:

* ``"low"``: the instance's near face is ``mm`` above the box's low face;
* ``"high"``: the instance's far face is ``mm`` below the box's high face;
* ``"mid"``: the instance's centre is ``mm`` from the box's centre.

The box: ``x`` and ``y`` grow about the centre ``(cx, cy)``, ``z`` grows upward from ``floor``.
The numbers in a row are the card's own rough shapes, measured once at promotion; the part is
placed so its real extent (after the rotation) lands there, whatever its origin is.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from napkin2factory.geometry.assembly import AssemblyResult, place

#: The anchors a row may use on an axis.
ANCHORS: tuple[str, ...] = ("low", "high", "mid")
AXES: tuple[str, str, str] = ("x", "y", "z")


def box_of(
    P: Any,  # noqa: N803 — P is the recording accessor
    sizes: Mapping[str, str],
    centre: Sequence[float],
    floor: float,
) -> dict[str, tuple[float, float]]:
    """The overall box ``{axis: (low, high)}`` in mm from the three driving parameters.

    Args:
        P: the parameter accessor (each read is recorded).
        sizes: axis -> name of the parameter that holds the overall size along it.
        centre: ``(cx, cy)``, the centre of the box in plan.
        floor: the box's low face along ``z``.
    """
    out: dict[str, tuple[float, float]] = {}
    for axis, c in zip(("x", "y"), centre, strict=True):
        size = float(P.mm(sizes[axis]))
        out[axis] = (c - size / 2, c + size / 2)
    out["z"] = (floor, floor + float(P.mm(sizes["z"])))
    return out


def _rotated_extent(built: Any, rz: float) -> dict[str, tuple[float, float]]:
    """The built part's extent along each axis after turning it ``rz`` degrees about z."""
    pts = np.asarray(built.tess[0], dtype=float)
    a = np.radians(rz)
    c, s = np.cos(a), np.sin(a)
    x = pts[:, 0] * c - pts[:, 1] * s
    y = pts[:, 0] * s + pts[:, 1] * c
    z = pts[:, 2]
    return {
        "x": (float(x.min()), float(x.max())),
        "y": (float(y.min()), float(y.max())),
        "z": (float(z.min()), float(z.max())),
    }


def _shift(anchor: str, off: float, box: tuple[float, float], ext: tuple[float, float]) -> float:
    """How far to move the part along one axis so it keeps to its anchor."""
    if anchor == "low":
        return box[0] + off - ext[0]
    if anchor == "high":
        return box[1] - off - ext[1]
    if anchor == "mid":
        return (box[0] + box[1]) / 2 + off - (ext[0] + ext[1]) / 2
    raise ValueError(f"unknown anchor {anchor!r}; use one of {', '.join(ANCHORS)}")


def place_rows(
    P: Any,  # noqa: N803 — P is the recording accessor
    parts: Any,
    rows: Sequence[Mapping[str, Any]],
    *,
    sizes: Mapping[str, str],
    centre: Sequence[float],
    floor: float,
) -> AssemblyResult:
    """Place every row of a seeded assembly's table (see the module docstring).

    Args:
        P: the parameter accessor.
        parts: the assembly's built children (``parts[...]`` as in any geometry module).
        rows: one mapping per instance.
        sizes: axis -> name of the parameter that holds the overall size along it.
        centre: ``(cx, cy)``, the centre of the box in plan.
        floor: the box's low face along ``z``.

    Returns:
        The placements, in the assembly's (the product's) frame.
    """
    box = box_of(P, sizes, centre, floor)
    res = AssemblyResult()
    for row in rows:
        if "asm" in row:
            res.add(place(f"asm://{row['asm']}", parts[row["asm"]]))
            continue
        built = parts[row["part"]]
        rz = float(row.get("rz", 0.0))
        ext = _rotated_extent(built, rz)
        shift = [_shift(*row[axis], box[axis], ext[axis]) for axis in AXES]
        res.add(
            place(
                f"part://{row['part']}",
                built,
                translate=(shift[0], shift[1], shift[2]),
                rotate=(0.0, 0.0, rz),
                label=row.get("label"),
            )
        )
    return res
