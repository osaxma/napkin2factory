"""Bolt-pattern math shared with interfaces (decision D16), plus a ``hole_pattern`` plate.

Both parties of a ``bolt-pattern`` interface place their holes with
:func:`centers_from_spec`, so the two hole sets line up by construction.  The
``hole_pattern`` generator builds a plate carrying one such pattern.
"""

from __future__ import annotations

import math
from typing import Any, Literal, NamedTuple

from build123d import (
    Align,
    Box,
    BuildPart,
    BuildSketch,
    Cylinder,
    Location,
    Plane,
    Rectangle,
    extrude,
)

from napkin2factory.core.frames import frame_basis  # one basis for holes, place_by and checks (P1)
from napkin2factory.core.frames import norm as _norm
from napkin2factory.core.model.interfaces import BoltPatternSpec, Frame
from napkin2factory.core.units import mm
from napkin2factory.geometry.features import (
    Dim,
    Features,
    FlatPattern,
    Hole,
    HolePattern,
    PartResult,
    Vec3,
    polygon_area,
)
from napkin2factory.geometry.kit import KitArgs, KitContext
from napkin2factory.geometry.kit._common import Count, Length, massing_result, require_positive

Vec2 = tuple[float, float]


def _q_mm(q: Any) -> float:
    """A pint quantity (or bare number) in mm; dimensionless magnitudes are taken as mm."""
    if getattr(q, "dimensionless", False):
        return float(q.magnitude)
    return float(mm(q))


def centers_2d(
    pattern: str, count: int, spacing: list[float] | None, pitch_circle: float | None
) -> list[Vec2]:
    """Hole centres of a pattern in its own 2D frame, centred on the origin.

    * ``rect``: count 1 → the origin; 2 → ``(±dx/2, 0)``; 4 → ``(±dx/2, ±dy/2)``; other even
      counts → two rows at ``±dy/2`` of ``count/2`` columns along x at pitch ``dx``.
      A single spacing value means ``dy = dx``.  Ordered row by row (y, then x ascending).
    * ``circle``: ``count`` points on a circle of diameter ``pitch_circle``, the first on +x,
      counter-clockwise.
    * ``line``: ``count`` points along x at pitch ``spacing[0]``, centred.

    Args:
        pattern: ``rect`` | ``circle`` | ``line``.
        count: number of holes.
        spacing: ``[dx, dy]`` for rect, ``[pitch]`` for line (mm).
        pitch_circle: pitch-circle diameter for circle (mm).

    Returns:
        The centres, in mm.

    Raises:
        ValueError: on a missing spacing/pitch circle or an impossible count.
    """
    if count < 0:
        raise ValueError(f"count must not be negative, got {count}")
    if count == 0:
        return []
    if pattern == "circle":
        if pitch_circle is None or pitch_circle <= 0:
            raise ValueError("a circle pattern needs a positive pitch_circle")
        r = pitch_circle / 2
        return [
            (r * math.cos(2 * math.pi * i / count), r * math.sin(2 * math.pi * i / count))
            for i in range(count)
        ]
    if count == 1:
        return [(0.0, 0.0)]
    if not spacing:
        raise ValueError(f"a {pattern} pattern of {count} holes needs spacing")
    dx = spacing[0]
    if dx <= 0:
        raise ValueError(f"spacing must be positive, got {dx}")
    if pattern == "line":
        return [((i - (count - 1) / 2) * dx, 0.0) for i in range(count)]
    if pattern != "rect":
        raise ValueError(f"unknown pattern {pattern!r}; use rect, circle or line")
    if count == 2:
        return [(-dx / 2, 0.0), (dx / 2, 0.0)]
    if count % 2:
        raise ValueError(f"a rect pattern needs 1, 2 or an even count, got {count}")
    dy = spacing[1] if len(spacing) > 1 else dx
    if dy <= 0:
        raise ValueError(f"spacing must be positive, got {dy}")
    cols = count // 2
    xs = [(i - (cols - 1) / 2) * dx for i in range(cols)]
    return [(x, y) for y in (-dy / 2, dy / 2) for x in xs]


def to_3d(points: list[Vec2], frame: Frame | None = None) -> list[Vec3]:
    """Map 2D pattern points into 3D: ``origin + x·X̂ + y·Ŷ``.

    Args:
        points: 2D centres in the frame plane.
        frame: the interface frame.

    Returns:
        3D centres.
    """
    o, ex, ey, _ = frame_basis(frame)
    return [
        (
            o[0] + px * ex[0] + py * ey[0],
            o[1] + px * ex[1] + py * ey[1],
            o[2] + px * ex[2] + py * ey[2],
        )
        for px, py in points
    ]


def spec_mm(spec: BoltPatternSpec) -> tuple[float, list[float] | None, float | None]:
    """``(diameter, spacing, pitch_circle)`` of a bolt-pattern spec, in mm."""
    spacing = [_q_mm(s) for s in spec.spacing] if spec.spacing is not None else None
    pc = _q_mm(spec.pitch_circle) if spec.pitch_circle is not None else None
    return _q_mm(spec.diameter), spacing, pc


def centers_from_spec(spec: BoltPatternSpec, frame: Frame | None = None) -> list[Vec3]:
    """3D hole centres of an interface bolt pattern (the D16 shared placement).

    Args:
        spec: the interface's bolt-pattern spec (pint quantities).
        frame: the interface frame (``None`` → origin, +Z normal).

    Returns:
        Hole centres in the first party's coordinates, mm.
    """
    _, spacing, pc = spec_mm(spec)
    return to_3d(centers_2d(spec.pattern, spec.count, spacing, pc), frame)


def pattern_feature(
    spec: BoltPatternSpec, frame: Frame | None, interface_uri: str | None
) -> HolePattern:
    """A :class:`HolePattern` for ``features.json`` from an interface spec.

    Args:
        spec: the bolt-pattern spec.
        frame: the interface frame.
        interface_uri: ``iface://<id>`` to tag the pattern with, if any.

    Returns:
        The pattern feature.
    """
    o, _, _, z = frame_basis(frame)
    return HolePattern(
        centers=centers_from_spec(spec, frame),
        diameter=_q_mm(spec.diameter),
        frame_origin=o,
        frame_normal=z,
        interface=interface_uri,
        label=interface_uri.removeprefix("iface://") if interface_uri else spec.pattern,
    )


def cut_pattern(
    shape: Any, centers_3d: list[Vec3], diameter: float, normal: Vec3, depth: float
) -> Any:
    """Subtract round holes along ``normal`` through each centre.

    Each cylinder is ``2·depth`` long and centred on its point, so it removes material
    within ``depth`` on either side of the pattern plane regardless of which way the
    normal points.

    Args:
        shape: the build123d solid to cut.
        centers_3d: hole centres.
        diameter: hole diameter, mm.
        normal: hole axis direction.
        depth: reach on each side of the centre, mm.

    Returns:
        The cut shape (a new object; ``label`` is carried over).
    """
    require_positive(diameter=diameter, depth=depth)
    z = _norm(normal)
    label = getattr(shape, "label", "")
    for c in centers_3d:
        cyl = Cylinder(diameter / 2, 2 * depth)
        shape = shape - cyl.moved(Location(Plane(origin=c, z_dir=z)))
    shape.label = label
    return shape


class Args(KitArgs):
    """``hole_pattern`` arguments (lengths in any unit; converted to mm)."""

    plate_width: Length
    plate_depth: Length
    thickness: Length
    pattern: Literal["rect", "circle", "line"] = "rect"
    count: Count = 4
    diameter: Length | None = None
    spacing: list[Length] | None = None
    pitch_circle: Length | None = None
    interface: str | None = None  # iface id; its spec and frame override the args above
    process: str = "cut-sheet"


ARGS = Args


def _iface_lookup(ctx: KitContext, ref: str) -> Any:
    iface_id = ref.removeprefix("iface://")
    for key in (iface_id, ref, f"iface://{iface_id}"):
        if key in ctx.interfaces:
            return iface_id, ctx.interfaces[key]
    return iface_id, None


class _Resolved(NamedTuple):
    """The pattern as placed on the plate, after validation."""

    centers: list[Vec3]
    diameter: float
    origin: Vec3
    normal: Vec3
    pattern: str
    spacing: list[float] | None
    pitch_circle: float | None
    iface_uri: str | None
    notes: list[str]


def _resolve(a: Args, ctx: KitContext) -> _Resolved:
    """Resolve the pattern (from the args or the interface) and check it fits the plate.

    Raises:
        ValueError: on missing pattern data, holes off the plate or overlapping holes.
    """
    require_positive(plate_width=a.plate_width, plate_depth=a.plate_depth, thickness=a.thickness)
    notes: list[str] = []
    iface_uri: str | None = None
    iface = None
    if a.interface:
        iface_id, iface = _iface_lookup(ctx, a.interface)
        if iface is None:
            notes.append(f"interface {a.interface!r} not in context; used the pattern args")
        elif not isinstance(getattr(iface, "spec", None), BoltPatternSpec):
            raise ValueError(f"interface {iface_id!r} is not a bolt-pattern interface")
        else:
            iface_uri = f"iface://{iface_id}"
    if iface is not None:
        spec: BoltPatternSpec = iface.spec
        frame: Frame = iface.frame
        diameter, spacing, pitch_circle = spec_mm(spec)
        pattern, count = spec.pattern, spec.count
    else:
        if a.diameter is None:
            raise ValueError("hole_pattern needs a diameter (or an interface)")
        frame = Frame()
        diameter, spacing, pitch_circle = a.diameter, a.spacing, a.pitch_circle
        pattern, count = a.pattern, a.count
    require_positive(diameter=diameter)
    origin, _, _, normal = frame_basis(frame)
    if abs(abs(normal[2]) - 1.0) > 1e-9:
        raise ValueError(f"hole_pattern plate needs a frame normal along ±Z, got {normal}")
    centers = to_3d(centers_2d(pattern, count, spacing, pitch_circle), frame)

    hw, hd = a.plate_width / 2, a.plate_depth / 2
    for x, y, _ in centers:
        if min(hw - abs(x), hd - abs(y)) - diameter / 2 <= 0:
            raise ValueError(f"hole at ({x:.1f}, {y:.1f}) Ø{diameter:g} breaks the plate edge")
    for i in range(len(centers)):
        for j in range(i + 1, len(centers)):
            if math.dist(centers[i][:2], centers[j][:2]) <= diameter:
                raise ValueError(f"holes {i + 1} and {j + 1} overlap (Ø{diameter:g})")
    return _Resolved(
        centers, diameter, origin, normal, pattern, spacing, pitch_circle, iface_uri, notes
    )


def _overall_dims(a: Args) -> list[Dim]:
    hw, hd = a.plate_width / 2, a.plate_depth / 2
    return [
        Dim("width", a.plate_width, (-hw, -hd, 0), (hw, -hd, 0), view="top"),
        Dim("depth", a.plate_depth, (hw, -hd, 0), (hw, hd, 0), view="top"),
        Dim("thickness", a.thickness, (hw, -hd, 0), (hw, -hd, a.thickness), view="front"),
    ]


def massing(a: Args, ctx: KitContext) -> PartResult:
    """Silhouette (N3): the plate as a box, no holes; the pattern is still validated.

    The plate is always centred on the origin; an interface frame moves only the holes,
    so the silhouette is the same with or without one.
    """
    res = _resolve(a, ctx)
    shape = Box(
        a.plate_width, a.plate_depth, a.thickness, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    result = massing_result(shape, a.process, _overall_dims(a), ctx)
    result.notes.extend(res.notes)
    return result


def generate(a: Args, ctx: KitContext) -> PartResult:
    """Build a plate (origin at its centre, Z up through the thickness) carrying one pattern.

    With ``interface`` naming an interface in ``ctx.interfaces``, that interface's spec and
    frame place the holes (the frame normal must be along ±Z) and the pattern is tagged
    ``iface://<id>``; otherwise the pattern args are used with the frame at the origin.

    Args:
        a: validated arguments.
        ctx: generator context.

    Returns:
        The plate with the pattern, its holes, dims and flat pattern.

    Raises:
        ValueError: on missing pattern data, holes off the plate or overlapping holes.
    """
    res = _resolve(a, ctx)
    centers, diameter, origin, normal = res.centers, res.diameter, res.origin, res.normal
    pattern, spacing, pitch_circle = res.pattern, res.spacing, res.pitch_circle
    iface_uri, notes = res.iface_uri, res.notes
    hw, hd = a.plate_width / 2, a.plate_depth / 2

    with BuildPart() as bp:
        with BuildSketch():
            Rectangle(a.plate_width, a.plate_depth)
        extrude(amount=a.thickness)
    shape = bp.part
    shape.label = ctx.uri
    if centers:
        reach = a.thickness + abs(origin[2]) + 1.0
        shape = cut_pattern(shape, centers, diameter, normal, reach)

    feats = Features(process=a.process, thickness=a.thickness)
    feats.patterns.append(
        HolePattern(
            centers=centers,
            diameter=diameter,
            frame_origin=origin,
            frame_normal=normal,
            interface=iface_uri,
            label=iface_uri.removeprefix("iface://") if iface_uri else pattern,
        )
    )
    for i, (x, y, z) in enumerate(centers):
        feats.holes.append(
            Hole(
                center=(x, y, z),
                diameter=diameter,
                axis=normal,
                edge_distance=min(hw - abs(x), hd - abs(y)) - diameter / 2,
                interface=iface_uri,
                label=f"H{i + 1}",
            )
        )

    outline = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    flat = FlatPattern(
        outline=outline,
        holes=[((x, y), diameter) for x, y, _ in centers],
        thickness=a.thickness,
    )
    flat.area = polygon_area(outline) - len(centers) * math.pi * (diameter / 2) ** 2

    dims = _overall_dims(a)
    if centers:
        c0 = centers[0]
        dims.append(Dim("hole", diameter, c0, c0, view="top", kind="diameter"))
        if pattern == "circle" and pitch_circle:
            dims.append(
                Dim(
                    "pitch_circle",
                    pitch_circle,
                    (origin[0] - pitch_circle / 2, origin[1], 0),
                    (origin[0] + pitch_circle / 2, origin[1], 0),
                    view="top",
                    kind="diameter",
                )
            )
        elif spacing and len(centers) > 1:
            c1 = centers[1]
            dims.append(Dim("spacing_x", spacing[0], c0, c1, view="top"))
            if pattern == "rect" and len(centers) >= 4:
                dy = spacing[1] if len(spacing) > 1 else spacing[0]
                dims.append(Dim("spacing_y", dy, c0, centers[len(centers) // 2], view="top"))
    return PartResult(
        shape=shape,
        features=feats,
        dims=dims,
        flat_pattern=flat,
        props={"developed_area": flat.area},
        notes=notes,
    )
