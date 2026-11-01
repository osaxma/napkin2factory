"""Interface frame math shared by the hole cutter, ``place_by`` and the alignment check (P1, P3).

One basis for one frame, everywhere: the holes are cut with :func:`frame_basis`
(``geometry/kit/hole_pattern.py`` re-exports it), ``geometry/assembly.py::place_by`` places
parts with it and ``core/checks/interface.py`` checks the placed frames with it (S-106).
It lives in ``core`` so the check runs without importing the CAD kernel.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from napkin2factory.core.model.interfaces import Frame

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]  # x, y, z, w


def norm(v: Vec3) -> Vec3:
    """``v`` scaled to unit length.

    Raises:
        ValueError: for the zero vector.
    """
    n = math.sqrt(dot(v, v))
    if n < 1e-12:
        raise ValueError(f"cannot normalise the zero vector {v}")
    return (v[0] / n, v[1] / n, v[2] / n)


def cross(a: Vec3, b: Vec3) -> Vec3:
    """``a × b``."""
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a: Vec3, b: Vec3) -> float:
    """``a · b``."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def sub(a: Vec3, b: Vec3) -> Vec3:
    """``a − b``."""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add_scaled(a: Vec3, b: Vec3, s: float) -> Vec3:
    """``a + s·b``."""
    return (a[0] + s * b[0], a[1] + s * b[1], a[2] + s * b[2])


def length(v: Vec3) -> float:
    """Euclidean length of ``v``."""
    return math.sqrt(dot(v, v))


def angle_deg(a: Vec3, b: Vec3) -> float:
    """Angle between two unit vectors, in degrees."""
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(a, b)))))


def frame_basis(frame: Frame | None = None) -> tuple[Vec3, Vec3, Vec3, Vec3]:
    """Orthonormal basis of an interface frame.

    ``Ẑ`` is the normalised frame normal; ``X̂`` is ``frame.x_axis`` (made perpendicular to
    ``Ẑ``) or, when absent, the global axis least aligned with ``Ẑ`` (ties → X, then Y)
    made perpendicular by Gram–Schmidt; ``Ŷ = Ẑ × X̂``.

    Args:
        frame: the frame (``None`` → origin with +Z normal); its origin must be numbers
            (resolved through ``geometry/accessors.py::resolve_interface``).

    Returns:
        ``(origin, X̂, Ŷ, Ẑ)``.

    Raises:
        ValueError: on a zero normal or an x_axis parallel to the normal.
    """
    frame = frame or Frame()
    origin: Vec3 = (float(frame.origin[0]), float(frame.origin[1]), float(frame.origin[2]))
    z = norm((float(frame.normal[0]), float(frame.normal[1]), float(frame.normal[2])))
    if frame.x_axis is not None:
        seed: Vec3 = (float(frame.x_axis[0]), float(frame.x_axis[1]), float(frame.x_axis[2]))
    else:
        axes: list[Vec3] = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
        seed = min(axes, key=lambda e: abs(dot(e, z)))
    d = dot(seed, z)
    x_raw = (seed[0] - d * z[0], seed[1] - d * z[1], seed[2] - d * z[2])
    if math.sqrt(dot(x_raw, x_raw)) < 1e-9:
        raise ValueError(f"frame x_axis {seed} is parallel to the normal {z}")
    x = norm(x_raw)
    y = cross(z, x)
    return origin, x, y, z


def quat_rotate(q: Sequence[float], v: Vec3) -> Vec3:
    """Rotate ``v`` by the unit quaternion ``q`` = (x, y, z, w), as ``instances.json`` stores it."""
    x, y, z, w = (float(c) for c in q)
    u: Vec3 = (x, y, z)
    uv = cross(u, v)
    uuv = cross(u, uv)
    return (
        v[0] + 2 * (w * uv[0] + uuv[0]),
        v[1] + 2 * (w * uv[1] + uuv[1]),
        v[2] + 2 * (w * uv[2] + uuv[2]),
    )


@dataclass(frozen=True)
class WorldFrame:
    """An interface frame moved into an assembly's coordinates by one occurrence."""

    origin: Vec3
    x_axis: Vec3
    normal: Vec3

    def to_dict(self) -> dict[str, list[float]]:
        """JSON form (mm and unit vectors, rounded for evidence)."""
        return {
            "origin": [round(c, 3) + 0.0 for c in self.origin],
            "normal": [round(c, 4) + 0.0 for c in self.normal],
            "x_axis": [round(c, 4) + 0.0 for c in self.x_axis],
        }


def world_frame(
    frame: Frame, translation: Sequence[float], rotation: Sequence[float]
) -> WorldFrame:
    """``frame`` (in a part's coordinates) as placed by ``translation`` and ``rotation``.

    Args:
        frame: the party's resolved frame.
        translation: the occurrence's translation (mm).
        rotation: the occurrence's rotation as a quaternion (x, y, z, w).
    """
    o, x, _, z = frame_basis(frame)
    t: Vec3 = (float(translation[0]), float(translation[1]), float(translation[2]))
    ro = quat_rotate(rotation, o)
    return WorldFrame(
        origin=(ro[0] + t[0], ro[1] + t[1], ro[2] + t[2]),
        x_axis=quat_rotate(rotation, x),
        normal=quat_rotate(rotation, z),
    )
