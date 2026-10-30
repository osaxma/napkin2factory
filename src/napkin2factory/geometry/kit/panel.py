"""``panel``: a flat sheet with explicit holes and rectangular cutouts (doors, lids, covers).

Origin at the panel centre; width along X, height along Y, thickness along +Z from 0.
Hole and cutout centres are given in panel coordinates (from the centre).  The panel is
its own flat pattern; rounded corners are sampled into the outline polygons, and the
developed area is computed analytically.
"""

from __future__ import annotations

import math

from build123d import (
    Axis,
    BuildPart,
    BuildSketch,
    Circle,
    Locations,
    Mode,
    Rectangle,
    RectangleRounded,
    extrude,
    fillet,
)

from napkin2factory.geometry.features import (
    Cutout,
    Dim,
    Features,
    FlatPattern,
    Hole,
    PartResult,
    Vec2,
)
from napkin2factory.geometry.kit import KitArgs, KitContext
from napkin2factory.geometry.kit._common import Length, require_positive

_EPS = 1e-6


class HoleItem(KitArgs):
    """One round through-hole, centre from the panel centre."""

    center: tuple[Length, Length]
    diameter: Length
    label: str | None = None


class CutoutItem(KitArgs):
    """One rectangular (optionally rounded) through-opening, centre from the panel centre."""

    center: tuple[Length, Length]
    width: Length
    height: Length
    corner_radius: Length = 0.0
    label: str | None = None


class Args(KitArgs):
    """``panel`` arguments (lengths in any unit; converted to mm)."""

    width: Length
    height: Length
    thickness: Length
    corner_radius: Length = 0.0
    holes: list[HoleItem] = []
    cutouts: list[CutoutItem] = []
    process: str = "cut-sheet"


ARGS = Args


def rounded_rect(
    cx: float, cy: float, w: float, h: float, r: float, segments: int = 8
) -> list[Vec2]:
    """Polygon of a rectangle with rounded corners (arcs sampled), counter-clockwise.

    Args:
        cx: centre x.
        cy: centre y.
        w: width (X).
        h: height (Y).
        r: corner radius (0 gives the four corners).
        segments: line segments per quarter arc.

    Returns:
        The outline points.
    """
    hw, hh = w / 2, h / 2
    if r <= _EPS:
        return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]
    pts: list[Vec2] = []
    corners = [
        (hw - r, -hh + r, -90.0),
        (hw - r, hh - r, 0.0),
        (-hw + r, hh - r, 90.0),
        (-hw + r, -hh + r, 180.0),
    ]
    for ox, oy, start in corners:
        for i in range(segments + 1):
            t = math.radians(start + 90.0 * i / segments)
            pts.append((cx + ox + r * math.cos(t), cy + oy + r * math.sin(t)))
    return pts


def rounded_rect_area(w: float, h: float, r: float) -> float:
    """Exact area of a ``w`` × ``h`` rectangle with corner radius ``r``."""
    return w * h - (4 - math.pi) * r * r


def _inside_outline(a: Args, x: float, y: float, reach: float) -> bool:
    """Is a disc of radius ``reach`` at (x, y) strictly inside the (rounded) outline?"""
    hw, hh = a.width / 2, a.height / 2
    if abs(x) + reach >= hw - _EPS or abs(y) + reach >= hh - _EPS:
        return False
    r = a.corner_radius
    if r > _EPS and abs(x) > hw - r and abs(y) > hh - r:
        return math.hypot(abs(x) - (hw - r), abs(y) - (hh - r)) + reach < r - _EPS
    return True


def _edge_distance(a: Args, x: float, y: float, d: float) -> float:
    """Web between a hole and the nearest outline edge (corner arcs included)."""
    hw, hh = a.width / 2, a.height / 2
    r = a.corner_radius
    if r > _EPS and abs(x) > hw - r and abs(y) > hh - r:
        return r - math.hypot(abs(x) - (hw - r), abs(y) - (hh - r)) - d / 2
    return min(hw - abs(x), hh - abs(y)) - d / 2


def _rect_corners(c: CutoutItem) -> list[Vec2]:
    cx, cy = c.center
    hw, hh = c.width / 2, c.height / 2
    return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]


def _circle_hits_rect(x: float, y: float, rad: float, c: CutoutItem) -> bool:
    cx, cy = c.center
    qx = min(max(x, cx - c.width / 2), cx + c.width / 2)
    qy = min(max(y, cy - c.height / 2), cy + c.height / 2)
    return math.hypot(x - qx, y - qy) < rad + _EPS


def _validate(a: Args) -> None:
    require_positive(width=a.width, height=a.height, thickness=a.thickness)
    if a.corner_radius < 0 or a.corner_radius >= min(a.width, a.height) / 2:
        raise ValueError(
            f"corner_radius {a.corner_radius} must be in [0, {min(a.width, a.height) / 2})"
        )
    for i, h in enumerate(a.holes):
        name = h.label or f"H{i + 1}"
        require_positive(**{f"hole {name} diameter": h.diameter})
        if not _inside_outline(a, h.center[0], h.center[1], h.diameter / 2):
            raise ValueError(
                f"hole {name} at ({h.center[0]:g}, {h.center[1]:g}) Ø{h.diameter:g} "
                f"is not inside the {a.width:g}×{a.height:g} panel"
            )
    for i, c in enumerate(a.cutouts):
        name = c.label or f"C{i + 1}"
        require_positive(**{f"cutout {name} width": c.width, f"cutout {name} height": c.height})
        if c.corner_radius < 0 or c.corner_radius > min(c.width, c.height) / 2 + _EPS:
            raise ValueError(f"cutout {name} corner_radius {c.corner_radius} does not fit")
        if not all(_inside_outline(a, x, y, 0.0) for x, y in _rect_corners(c)):
            raise ValueError(
                f"cutout {name} at ({c.center[0]:g}, {c.center[1]:g}) {c.width:g}×{c.height:g} "
                f"is not inside the {a.width:g}×{a.height:g} panel"
            )
    for i, h1 in enumerate(a.holes):
        for j in range(i + 1, len(a.holes)):
            h2 = a.holes[j]
            gap = math.dist(h1.center, h2.center) - (h1.diameter + h2.diameter) / 2
            if gap < _EPS:
                raise ValueError(f"holes {i + 1} and {j + 1} overlap")
        for j, c in enumerate(a.cutouts):
            if _circle_hits_rect(h1.center[0], h1.center[1], h1.diameter / 2, c):
                raise ValueError(f"hole {i + 1} overlaps cutout {j + 1}")
    for i, c1 in enumerate(a.cutouts):
        for j in range(i + 1, len(a.cutouts)):
            c2 = a.cutouts[j]
            if (
                abs(c1.center[0] - c2.center[0]) < (c1.width + c2.width) / 2 + _EPS
                and abs(c1.center[1] - c2.center[1]) < (c1.height + c2.height) / 2 + _EPS
            ):
                raise ValueError(f"cutouts {i + 1} and {j + 1} overlap")


def generate(a: Args, ctx: KitContext) -> PartResult:
    """Build the panel. Origin at the panel centre, Z up through the thickness.

    Args:
        a: validated arguments.
        ctx: generator context (labels the shape with ``ctx.uri``).

    Returns:
        The solid with holes, cutouts, dims and the flat pattern.

    Raises:
        ValueError: on non-positive sizes, a hole or cutout outside the panel, or overlaps.
    """
    _validate(a)
    with BuildPart() as bp:
        with BuildSketch():
            Rectangle(a.width, a.height)
        extrude(amount=a.thickness)
        if a.corner_radius > 0.01:
            fillet(bp.edges().filter_by(Axis.Z), radius=a.corner_radius)
        if a.holes or a.cutouts:
            with BuildSketch():
                for h in a.holes:
                    with Locations(h.center):
                        Circle(h.diameter / 2)
                for c in a.cutouts:
                    with Locations(c.center):
                        if c.corner_radius > 0.01:
                            RectangleRounded(c.width, c.height, c.corner_radius)
                        else:
                            Rectangle(c.width, c.height)
            extrude(amount=a.thickness, mode=Mode.SUBTRACT)
    shape = bp.part
    shape.label = ctx.uri

    feats = Features(process=a.process, thickness=a.thickness)
    for i, h in enumerate(a.holes):
        feats.holes.append(
            Hole(
                center=(h.center[0], h.center[1], 0.0),
                diameter=h.diameter,
                edge_distance=_edge_distance(a, h.center[0], h.center[1], h.diameter),
                label=h.label or f"H{i + 1}",
            )
        )
    for i, c in enumerate(a.cutouts):
        feats.cutouts.append(
            Cutout(
                face="base",
                center=(c.center[0], c.center[1]),
                width=c.width,
                height=c.height,
                corner_radius=c.corner_radius,
                label=c.label or f"C{i + 1}",
            )
        )

    outline = rounded_rect(0.0, 0.0, a.width, a.height, a.corner_radius)
    flat = FlatPattern(
        outline=outline,
        holes=[((h.center[0], h.center[1]), h.diameter) for h in a.holes],
        cutouts=[
            rounded_rect(c.center[0], c.center[1], c.width, c.height, c.corner_radius)
            for c in a.cutouts
        ],
        thickness=a.thickness,
    )
    flat.area = (
        rounded_rect_area(a.width, a.height, a.corner_radius)
        - sum(math.pi * (h.diameter / 2) ** 2 for h in a.holes)
        - sum(rounded_rect_area(c.width, c.height, c.corner_radius) for c in a.cutouts)
    )

    hw, hh = a.width / 2, a.height / 2
    dims = [
        Dim("width", a.width, (-hw, -hh, 0), (hw, -hh, 0), view="top"),
        Dim("height", a.height, (hw, -hh, 0), (hw, hh, 0), view="top"),
        Dim("thickness", a.thickness, (hw, -hh, 0), (hw, -hh, a.thickness), view="front"),
    ]
    seen: set[float] = set()
    for h in a.holes:
        key = round(h.diameter, 6)
        if key in seen:
            continue
        seen.add(key)
        p = (h.center[0], h.center[1], 0.0)
        dims.append(Dim(f"hole Ø{h.diameter:g}", h.diameter, p, p, view="top", kind="diameter"))
    return PartResult(
        shape=shape,
        features=feats,
        dims=dims,
        flat_pattern=flat,
        props={"developed_area": flat.area},
    )
