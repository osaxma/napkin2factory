"""``bracket_l``: a sheet-metal L bracket — two legs joined by one 90° bend.

Frame: the outer corner of the L (the virtual sharp of the outer mould lines) is the
origin.  The horizontal leg runs along +X (``z ∈ [0, t]``), the vertical leg along +Z
(``x ∈ [0, t]``), and the width is along Y centred on 0.  The bend is a quarter annulus
of inside radius ``bend_radius`` whose centre is at ``x = z = bend_radius + thickness``.

The solid is one L cross-section (straight legs plus inner/outer arcs) in the XZ plane,
extruded ±width/2 along Y, with holes subtracted.  The flat pattern is a strip
``flat_vertical + bend_allowance + flat_horizontal`` long, vertical leg first.

Aesthetics (N7): a part with a styling role that leaves ``bend_radius`` unset gets
``thickness × style.radius_scale`` instead of ``thickness``.
"""

from __future__ import annotations

import math

from build123d import (
    Box,
    BuildLine,
    BuildPart,
    BuildSketch,
    CenterArc,
    Cylinder,
    Line,
    Location,
    Locations,
    Mode,
    Plane,
    Pos,
    extrude,
    make_face,
)

from napkin2factory.geometry.features import (
    Bend,
    Dim,
    Features,
    Flange,
    FlatPattern,
    Hole,
    PartResult,
    Vec2,
    Vec3,
    polygon_area,
)
from napkin2factory.geometry.kit import KitArgs, KitContext
from napkin2factory.geometry.kit._common import (
    Count,
    Length,
    apply_style_defaults,
    massing_result,
    require_positive,
)
from napkin2factory.geometry.kit._sheet import bend_allowance, developed_l, k_factor


class HoleSpec(KitArgs):
    """Holes in each leg: a row across the width at ``inset`` from the leg's free end."""

    diameter: Length
    spacing: Length | None = None  # centre-to-centre across the width; default width / count
    inset: Length | None = None  # from the free end; default: middle of the leg's flat
    count: Count = 2  # per leg


class Args(KitArgs):
    """``bracket_l`` arguments (lengths in any unit; converted to mm)."""

    length: Length  # horizontal leg, outer
    height: Length  # vertical leg, outer
    width: Length
    thickness: Length
    bend_radius: Length | None = None  # inside radius; default = thickness
    holes: HoleSpec | None = None
    process: str = "sheet-metal"


ARGS = Args

_EPS = 1e-3  # mm of slack when deciding which region a 3D point lies on


def _row(count: int, spacing: float) -> list[float]:
    """Y positions of ``count`` holes ``spacing`` apart, centred on 0."""
    return [-spacing * (count - 1) / 2 + spacing * i for i in range(count)]


_Rows = list[tuple[str, float, list[float]]]


def _validate(a: Args) -> tuple[float, float, float, float, _Rows]:
    """Check the legs and holes fit; return ``(r, big_r, flat_h, flat_v, rows)``.

    ``rows`` holds ``(leg, inset, ys)`` per leg carrying holes.

    Raises:
        ValueError: on non-positive sizes, a leg too short for the bend, or holes that
            overlap, break an edge or reach into the bend zone.
    """
    r = a.thickness if a.bend_radius is None else a.bend_radius
    t, w = a.thickness, a.width
    require_positive(length=a.length, height=a.height, width=w, thickness=t, bend_radius=r)
    big_r = r + t  # outside bend radius; the bend tangent lines sit at x = big_r, z = big_r
    flat_h, flat_v = a.length - big_r, a.height - big_r
    for name, leg_len, flat in (("length", a.length, flat_h), ("height", a.height, flat_v)):
        if flat < t:
            raise ValueError(
                f"{name} {leg_len:g} mm is too short: a leg needs at least bend_radius + "
                f"2 × thickness = {big_r + t:g} mm to leave a flat after the bend"
            )

    # holes: (leg, inset, ys) per leg
    rows: _Rows = []
    h = a.holes
    if h is not None and h.count > 0:
        require_positive(hole_diameter=h.diameter)
        spacing = h.spacing if h.spacing is not None else w / h.count
        if h.count > 1 and spacing <= h.diameter:
            raise ValueError(
                f"hole spacing {spacing:g} mm is not larger than the hole diameter "
                f"{h.diameter:g} mm: the holes overlap"
            )
        ys = _row(h.count, spacing)
        if max(abs(y) for y in ys) + h.diameter / 2 >= w / 2:
            raise ValueError(
                f"{h.count} holes of {h.diameter:g} mm at {spacing:g} mm spacing break the "
                f"side edges of a {w:g} mm wide bracket"
            )
        for leg, flat in (("horizontal", flat_h), ("vertical", flat_v)):
            inset = h.inset if h.inset is not None else flat / 2
            if inset - h.diameter / 2 <= 0:
                raise ValueError(
                    f"{leg} leg hole at inset {inset:g} mm breaks the free end "
                    f"(diameter {h.diameter:g} mm)"
                )
            if flat - inset - h.diameter / 2 < 0:
                raise ValueError(
                    f"{leg} leg hole at inset {inset:g} mm cuts into the bend zone: its edge "
                    f"is {flat - inset - h.diameter / 2:g} mm past the bend tangent line"
                )
            rows.append((leg, inset, ys))
    return r, big_r, flat_h, flat_v, rows


def _styled(a: Args, ctx: KitContext) -> tuple[Args, list[str]]:
    """Scale the default bend radius by ``style.radius_scale`` (opted-in parts only)."""
    style = ctx.styled
    if style is None or style.radius_scale == 1.0:
        return a, []
    return apply_style_defaults(a, {"bend_radius": a.thickness * style.radius_scale}, _validate)


def _overall_dims(a: Args) -> list[Dim]:
    hw = a.width / 2
    return [
        Dim("length", a.length, (0, -hw, 0), (a.length, -hw, 0), view="front"),
        Dim("height", a.height, (0, -hw, 0), (0, -hw, a.height), view="front"),
        Dim("width", a.width, (a.length, -hw, 0), (a.length, hw, 0), view="top"),
    ]


def massing(a: Args, ctx: KitContext) -> PartResult:
    """Silhouette (N3): two leg boxes fused at a sharp corner; no bend radius, no holes.

    Same frame as :func:`generate`: the horizontal leg at ``z ∈ [0, t]``, the vertical
    leg at ``x ∈ [0, t]``, width centred on Y.
    """
    _validate(a)
    t, w = a.thickness, a.width
    horizontal = Pos(a.length / 2, 0, t / 2) * Box(a.length, w, t)
    vertical = Pos(t / 2, 0, a.height / 2) * Box(t, w, a.height)
    shape = horizontal.fuse(vertical).clean()
    return massing_result(shape, a.process, _overall_dims(a), ctx)


def generate(a: Args, ctx: KitContext) -> PartResult:
    """Build the L bracket (see the module docstring for the frame)."""
    a, notes = _styled(a, ctx)
    r, big_r, flat_h, flat_v, rows = _validate(a)
    t, w = a.thickness, a.width
    h = a.holes
    k = k_factor(r, t)
    ba = bend_allowance(r, t, 90.0, k)

    with BuildPart() as bp:
        with BuildSketch(Plane.XZ):  # sketch (u, v) = world (x, z)
            with BuildLine():
                Line((big_r, 0), (a.length, 0))
                Line((a.length, 0), (a.length, t))
                Line((a.length, t), (big_r, t))
                CenterArc((big_r, big_r), r, 270, -90)  # inner arc → (t, big_r)
                Line((t, big_r), (t, a.height))
                Line((t, a.height), (0, a.height))
                Line((0, a.height), (0, big_r))
                CenterArc((big_r, big_r), big_r, 180, 90)  # outer arc → (big_r, 0)
            make_face()
        extrude(amount=w / 2, both=True)
        if h is not None:
            for leg, inset, ys in rows:
                if leg == "horizontal":
                    locs = [Location((a.length - inset, y, t / 2)) for y in ys]
                else:
                    locs = [Location((t / 2, y, a.height - inset), (0, 90, 0)) for y in ys]
                with Locations(*locs):
                    Cylinder(h.diameter / 2, 3 * t, mode=Mode.SUBTRACT)
    shape = bp.part
    if shape is None:
        raise ValueError("bracket_l produced no solid")
    shape.label = ctx.uri

    feats = Features(process=a.process, thickness=t)
    feats.bends.append(
        Bend(start=(0.0, -w / 2, 0.0), end=(0.0, w / 2, 0.0), radius=r, k_factor=k, label="B1")
    )
    feats.flanges.append(Flange(height=flat_h, length=w, bend="B1", label="horizontal"))
    feats.flanges.append(Flange(height=flat_v, length=w, bend="B1", label="vertical"))

    developed = flat_v + ba + flat_h
    outline, bend_x = developed_l(flat_v, ba, flat_h, w)

    def flat_map(p: Vec3) -> Vec2 | None:
        """Map a point on a leg (part frame) to the flat; ``None`` in the bend zone.

        The flat strip runs along +X from the vertical leg's free end (``x = 0``) to the
        horizontal leg's free end (``x = developed``); flat Y is the part's Y.
        """
        x, y, z = p
        if abs(y) > w / 2 + _EPS:
            return None
        if -_EPS <= z <= t + _EPS and big_r - _EPS <= x <= a.length + _EPS:
            return (developed - (a.length - x), y)
        if -_EPS <= x <= t + _EPS and big_r - _EPS <= z <= a.height + _EPS:
            return (a.height - z, y)
        return None

    flat_holes: list[tuple[tuple[float, float], float]] = []
    n = 0
    for leg, inset, ys in rows:
        d = h.diameter if h is not None else 0.0
        flat = flat_h if leg == "horizontal" else flat_v
        for y in ys:
            n += 1
            if leg == "horizontal":
                center, axis = (a.length - inset, y, 0.0), (0.0, 0.0, 1.0)
            else:
                center, axis = (0.0, y, a.height - inset), (1.0, 0.0, 0.0)
            mapped = flat_map(center)
            if mapped is None:  # cannot happen: holes were validated to lie on the flats
                raise ValueError(f"hole H{n} at {center} is not on a leg flat")
            flat_holes.append((mapped, d))
            feats.holes.append(
                Hole(
                    center=center,
                    diameter=d,
                    axis=axis,
                    edge_distance=min(inset, w / 2 - abs(y)) - d / 2,
                    bend_distance=flat - inset,
                    label=f"H{n}",
                )
            )
    fp = FlatPattern(
        outline=outline,
        holes=flat_holes,
        bend_lines=[((bend_x, -w / 2), (bend_x, w / 2), 90.0, "B1")],
        thickness=t,
    )
    fp.area = polygon_area(outline) - sum(math.pi * (d / 2) ** 2 for _, d in flat_holes)

    hw = w / 2
    c45 = math.cos(math.radians(45))
    dims = _overall_dims(a) + [
        Dim("thickness", t, (a.length, -hw, 0), (a.length, -hw, t), view="front"),
        Dim(
            "bend radius",
            r,
            (big_r, -hw, big_r),
            (big_r - r * c45, -hw, big_r - r * c45),
            view="front",
            kind="radius",
        ),
    ]
    if h is not None and rows:
        _, inset, ys = rows[0]
        x0 = a.length - inset
        dims.append(
            Dim("hole", h.diameter, (x0, ys[0], 0), (x0, ys[0], 0), view="top", kind="diameter")
        )
        dims.append(Dim("hole inset", inset, (a.length, ys[0], 0), (x0, ys[0], 0), view="top"))
    result = PartResult(
        shape=shape,
        features=feats,
        dims=dims,
        flat_pattern=fp,
        props={"developed_length": developed, "bend_allowance": ba, "k_factor": k},
        notes=notes,
    )
    result.flat_map = flat_map
    return result
