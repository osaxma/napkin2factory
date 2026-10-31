"""``enclosure``: an open-top sheet-metal tray — a base with four walls bent up.

Frame: the base is centred on XY with its outer (bottom) face at ``z = 0``; walls rise to
``z = height``.  Front is the −Y wall, back +Y, left −X, right +X.  ``length``/``width``
are the outer tray dimensions measured over the walls; an optional ``flange`` lip is bent
outward at the top of every wall and adds ``flange`` beyond each wall's outer face, so
with a lip the bounding box is ``(length + 2·flange) × (width + 2·flange) × height``.

The solid is the union of the flat regions (base, four walls, four lips) and the bend
zones between them (annular sectors from :func:`bend_solid`).  Each wall is shortened at
both ends by ``relief`` (measured from the outer corner), leaving the corners open as on
a real folded tray; ``relief`` must be at least ``thickness + bend_radius`` so the bend
zones of adjacent walls cannot overlap.

Cutout coordinates are 2D, origin at the centre of the face's flat (planar) region:

* ``base``: world ``(x, y)``.
* walls: ``(u, v)`` seen from outside the tray, ``v`` up (+Z) and ``u`` to the right —
  front ``u = +X``, back ``u = −X``, left ``u = −Y``, right ``u = +Y``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from build123d import (
    Box,
    Location,
    Plane,
    Pos,
    Rectangle,
    RectangleRounded,
    Solid,
    Vector,
    extrude,
)
from pydantic import Field

from napkin2factory.geometry.features import (
    Bend,
    Cutout,
    Dim,
    Features,
    Flange,
    FlatPattern,
    PartResult,
    Relief,
    Vec2,
    Vec3,
    polygon_area,
)
from napkin2factory.geometry.kit import KitArgs, KitContext
from napkin2factory.geometry.kit._common import Length, massing_result, require_positive
from napkin2factory.geometry.kit._sheet import (
    bend_allowance,
    bend_solid,
    developed_tray,
    k_factor,
    place,
    rounded_rect,
    rounded_rect_area,
)

FaceName = Literal["base", "front", "back", "left", "right"]


class CutoutSpec(KitArgs):
    """A rectangular (optionally rounded) opening through one face."""

    face: FaceName
    center: tuple[Length, Length] = (0.0, 0.0)
    width: Length
    height: Length
    corner_radius: Length = 0.0
    label: str | None = None


class Args(KitArgs):
    """``enclosure`` arguments (lengths in any unit; converted to mm)."""

    length: Length  # X, outer
    width: Length  # Y, outer
    height: Length  # Z, outer incl. base
    thickness: Length
    bend_radius: Length | None = None  # inside radius; default = thickness
    flange: Length = 0.0  # outward lip width beyond the wall's outer face; 0 = no lip
    relief: Length | None = None  # corner gap from the outer corner; default t + r
    cutouts: list[CutoutSpec] = Field(default_factory=list)
    process: str = "sheet-metal"


ARGS = Args

_EPS = 1e-3  # mm of slack when deciding which region a 3D point lies on


@dataclass(frozen=True)
class _Wall:
    """Geometry of one wall: outward normal, face-right direction, offsets."""

    name: str
    n: Vector  # outward normal (horizontal)
    u: Vector  # face u direction (horizontal, seen from outside)
    half: float  # distance of the outer face from the tray centre
    span: float  # half the wall's length along u


def _walls(length: float, width: float, relief: float) -> list[_Wall]:
    """The four walls in front, back, left, right order."""
    ax, ay = length / 2 - relief, width / 2 - relief
    return [
        _Wall("front", Vector(0, -1, 0), Vector(1, 0, 0), width / 2, ax),
        _Wall("back", Vector(0, 1, 0), Vector(-1, 0, 0), width / 2, ax),
        _Wall("left", Vector(-1, 0, 0), Vector(0, -1, 0), length / 2, ay),
        _Wall("right", Vector(1, 0, 0), Vector(0, 1, 0), length / 2, ay),
    ]


def _box(center: Vector, along_u: float, along_n: float, along_z: float, w: _Wall) -> Solid:
    """An axis-aligned box sized in a wall's (u, n, z) directions."""
    sx = along_u if abs(w.u.X) > 0.5 else along_n
    sy = along_n if abs(w.u.X) > 0.5 else along_u
    box = Box(sx, sy, along_z)
    return box.located(Location(_vec(center))).solids()[0]


def _vec(v: Vector) -> tuple[float, float, float]:
    return (float(v.X), float(v.Y), float(v.Z))


@dataclass(frozen=True)
class _Layout:
    """Validated sizes the solid, features and flat pattern are built from."""

    t: float
    r: float
    big_r: float
    relief: float
    f: float
    lip: bool
    z_top: float  # top of the straight wall
    wall_flat: float


def _validate(a: Args) -> _Layout:
    """Check the tray (walls, reliefs, lip, height, cutouts) can be built.

    Raises:
        ValueError: on non-positive sizes, a lip too short to bend, reliefs too small, no
            wall left between the reliefs, too low a height, or a cutout off its face.
    """
    t = a.thickness
    r = t if a.bend_radius is None else a.bend_radius
    big_r = r + t
    relief = big_r if a.relief is None else a.relief
    f = a.flange
    require_positive(length=a.length, width=a.width, height=a.height, thickness=t, bend_radius=r)
    if f < 0:
        raise ValueError(f"flange must not be negative, got {f}")
    lip = f > 0
    if lip and f - r < t:
        raise ValueError(
            f"flange {f:g} mm is too short: a lip needs at least bend_radius + thickness "
            f"= {big_r:g} mm"
        )
    if relief < big_r - 1e-9:
        raise ValueError(
            f"relief {relief:g} mm is smaller than thickness + bend_radius = {big_r:g} mm: "
            "the bends of adjacent walls would collide"
        )
    for name, size in (("length", a.length), ("width", a.width)):
        if size / 2 - relief < t:
            raise ValueError(
                f"{name} {size:g} mm leaves no wall between the corner reliefs "
                f"(relief {relief:g} mm at each end)"
            )
    z_top = a.height - (t + r if lip else 0.0)  # top of the straight wall
    wall_flat = z_top - big_r
    if wall_flat < 1.0:
        need = big_r + 1 + (big_r if lip else 0.0)
        raise ValueError(
            f"height {a.height:g} mm is too low: it must exceed {need:g} mm "
            "(thickness + bend_radius + 1, plus the lip bend if any)"
        )
    base_l, base_w = a.length - 2 * big_r, a.width - 2 * big_r
    by_name = {w.name: w for w in _walls(a.length, a.width, relief)}

    # cutout validation, before any modelling
    for i, c in enumerate(a.cutouts):
        tag = c.label or f"#{i + 1}"
        require_positive(cutout_width=c.width, cutout_height=c.height)
        if c.corner_radius < 0 or c.corner_radius * 2 >= min(c.width, c.height):
            raise ValueError(
                f"cutout {tag}: corner_radius {c.corner_radius:g} mm must be below half the "
                f"smaller side ({min(c.width, c.height) / 2:g} mm)"
            )
        if c.face == "base":
            hu, hv = base_l / 2, base_w / 2
        else:
            hu, hv = by_name[c.face].span, wall_flat / 2
        cu, cv = c.center
        if abs(cu) + c.width / 2 > hu + 1e-9 or abs(cv) + c.height / 2 > hv + 1e-9:
            raise ValueError(
                f"cutout {tag} ({c.width:g} × {c.height:g} mm at {cu:g}, {cv:g}) is outside "
                f"the flat region of the {c.face} face ({2 * hu:g} × {2 * hv:g} mm)"
            )
    return _Layout(t, r, big_r, relief, f, lip, z_top, wall_flat)


def _overall_dims(a: Args) -> list[Dim]:
    hl, hw = a.length / 2, a.width / 2
    return [
        Dim("length", a.length, (-hl, -hw, 0), (hl, -hw, 0), view="front"),
        Dim("width", a.width, (hl, -hw, 0), (hl, hw, 0), view="top"),
        Dim("height", a.height, (hl, -hw, 0), (hl, -hw, a.height), view="front"),
    ]


def _inner_props(a: Args) -> dict[str, float]:
    t = a.thickness
    return {
        "inner_length": a.length - 2 * t,
        "inner_width": a.width - 2 * t,
        "inner_height": a.height - t,
    }


def massing(a: Args, ctx: KitContext) -> PartResult:
    """Silhouette (N3): the outer box minus the open-top cavity, walls and base ``t`` thick.

    No bends, reliefs, lip or cutouts: with a ``flange`` the silhouette stays
    ``length × width × height`` (the lip is a feature, not massing).  Same frame as
    :func:`generate`: base centred on XY, bottom face at ``z = 0``.
    """
    lay = _validate(a)
    t = lay.t
    outer = Pos(0, 0, a.height / 2) * Box(a.length, a.width, a.height)
    reach = a.height - t + 1.0  # runs out through the open top
    cavity = Pos(0, 0, t + reach / 2) * Box(a.length - 2 * t, a.width - 2 * t, reach)
    shape = (outer - cavity).clean()
    return massing_result(shape, a.process, _overall_dims(a), ctx, _inner_props(a))


def generate(a: Args, ctx: KitContext) -> PartResult:
    """Build the tray (see the module docstring for the frame and face coordinates)."""
    lay = _validate(a)
    t, r, big_r, relief, f = lay.t, lay.r, lay.big_r, lay.relief, lay.f
    lip, z_top, wall_flat = lay.lip, lay.z_top, lay.wall_flat

    k = k_factor(r, t)
    ba = bend_allowance(r, t, 90.0, k)
    base_l, base_w = a.length - 2 * big_r, a.width - 2 * big_r
    walls = _walls(a.length, a.width, relief)
    by_name = {w.name: w for w in walls}
    zc = (big_r + z_top) / 2  # centre of each wall's flat region

    z = Vector(0, 0, 1)
    pieces: list[Solid] = []
    base = Box(base_l, base_w, t).located(Location((0, 0, t / 2))).solids()[0]
    for w in walls:
        face = w.n * w.half
        pieces.append(_box(face - w.n * (t / 2) + z * zc, 2 * w.span, t, wall_flat, w))
        e = w.n.cross(-z)
        axis = face - w.n * big_r + z * big_r
        pieces.append(
            place(bend_solid(r, t, 90.0, 2 * w.span), _vec(axis - e * w.span), _vec(w.n), _vec(e))
        )
        if lip:
            lip_flat = f - r
            centre = face + w.n * (r + lip_flat / 2) + z * (a.height - t / 2)
            pieces.append(_box(centre, 2 * w.span, lip_flat, t, w))
            e2 = (-w.n).cross(z)
            axis2 = face + w.n * r + z * (a.height - t - r)
            pieces.append(
                place(
                    bend_solid(r, t, 90.0, 2 * w.span),
                    _vec(axis2 - e2 * w.span),
                    _vec(-w.n),
                    _vec(e2),
                )
            )
    shape = base.fuse(*pieces).clean()

    for c in a.cutouts:
        cu, cv = c.center
        if c.face == "base":
            plane = Plane(origin=(cu, cv, t / 2))
        else:
            w = by_name[c.face]
            o = w.n * (w.half - t / 2) + z * (zc + cv) + w.u * cu
            plane = Plane(origin=_vec(o), x_dir=_vec(w.u), z_dir=_vec(w.n))
        profile = (
            RectangleRounded(c.width, c.height, c.corner_radius)
            if c.corner_radius > 0
            else Rectangle(c.width, c.height)
        )
        shape = shape - extrude(plane * profile, amount=t, both=True)
    shape.label = ctx.uri

    # features
    feats = Features(process=a.process, thickness=t)
    for w in walls:
        face = w.n * w.half
        s, e_ = face + w.u * -w.span, face + w.u * w.span
        feats.bends.append(
            Bend(start=_vec(s), end=_vec(e_), radius=r, k_factor=k, label=f"B-{w.name}")
        )
        feats.flanges.append(
            Flange(height=wall_flat, length=2 * w.span, bend=f"B-{w.name}", label=w.name)
        )
    if lip:
        for w in walls:
            inner = w.n * (w.half - t) + z * a.height
            feats.bends.append(
                Bend(
                    start=_vec(inner + w.u * -w.span),
                    end=_vec(inner + w.u * w.span),
                    radius=r,
                    direction="down",
                    k_factor=k,
                    label=f"L-{w.name}",
                )
            )
            feats.flanges.append(
                Flange(height=f - r, length=2 * w.span, bend=f"L-{w.name}", label=f"{w.name} lip")
            )
    for sx in (-1, 1):
        for sy in (-1, 1):
            feats.reliefs.append(
                Relief(at=(sx * a.length / 2, sy * a.width / 2, 0.0), width=relief, depth=relief)
            )
    for c in a.cutouts:
        feats.cutouts.append(
            Cutout(
                face=c.face,
                center=(c.center[0], c.center[1]),
                width=c.width,
                height=c.height,
                corner_radius=c.corner_radius,
                label=c.label,
            )
        )

    # flat pattern: base flat centred at the origin, walls unfolded outward
    flap = ba + wall_flat + ((ba + f - r) if lip else 0.0)
    outline = developed_tray(
        base_l, base_w, 2 * by_name["front"].span, 2 * by_name["left"].span, flap
    )
    bend_lines: list[tuple[Vec2, Vec2, float, str]] = []

    def flat_pt(w: _Wall, off: float, along: float) -> Vec2:
        """Point ``off`` outward from the base edge under wall ``w``, ``along`` its u."""
        bh = w.half - big_r
        return (w.n.X * (bh + off) + w.u.X * along, w.n.Y * (bh + off) + w.u.Y * along)

    for w in walls:
        for off, lbl in ((ba / 2, f"B-{w.name}"), (ba + wall_flat + ba / 2, f"L-{w.name}")):
            if lbl.startswith("L-") and not lip:
                continue
            bend_lines.append((flat_pt(w, off, -w.span), flat_pt(w, off, w.span), 90.0, lbl))
    flat_cuts: list[list[Vec2]] = []
    cut_area = 0.0
    for c in a.cutouts:
        poly = rounded_rect(c.center[0], c.center[1], c.width, c.height, c.corner_radius)
        if c.face != "base":
            w = by_name[c.face]
            poly = [flat_pt(w, ba + wall_flat / 2 + v, u) for u, v in poly]
            if _signed_area(poly) < 0:
                poly.reverse()
        flat_cuts.append(poly)
        cut_area += rounded_rect_area(c.width, c.height, c.corner_radius)
    fp = FlatPattern(outline=outline, cutouts=flat_cuts, bend_lines=bend_lines, thickness=t)
    fp.area = polygon_area(outline) - cut_area

    def flat_map(p: Vec3) -> Vec2 | None:
        """Map a point on the base, a wall or a lip to the flat; ``None`` on bends.

        Base points keep their (x, y).  A wall point at height ``z`` lands
        ``ba + (z − (t + r))`` outward from its base edge; a lip point at distance ``d``
        beyond the wall's outer face lands ``2·ba + wall_flat + (d − r)`` outward.  The
        along-wall coordinate is unchanged (flat X/Y equal the part's X/Y along the wall).
        """
        x, y, zz = p
        if -_EPS <= zz <= t + _EPS and abs(x) <= base_l / 2 + _EPS:
            if abs(y) <= base_w / 2 + _EPS:
                return (x, y)
        pv = Vector(x, y, 0)
        for w in walls:
            d, along = pv.dot(w.n) - w.half, pv.dot(w.u)  # d < 0 inside the outer face
            if abs(along) > w.span + _EPS:
                continue
            if -t - _EPS <= d <= _EPS and big_r - _EPS <= zz <= z_top + _EPS:
                return flat_pt(w, ba + zz - big_r, along)
            on_lip_z = a.height - t - _EPS <= zz <= a.height + _EPS
            if lip and on_lip_z and r - _EPS <= d <= f + _EPS:
                return flat_pt(w, 2 * ba + wall_flat + d - r, along)
        return None

    hw = a.width / 2
    c45 = math.cos(math.radians(45))
    dims = _overall_dims(a) + [
        Dim("thickness", t, (0, -hw, 0), (0, -hw, t), view="right"),
        Dim(
            "bend radius",
            r,
            (0, -hw + big_r, big_r),
            (0, -hw + big_r - r * c45, big_r - r * c45),
            view="right",
            kind="radius",
        ),
    ]
    if lip:
        dims.append(Dim("flange", f, (0, -hw, a.height), (0, -hw - f, a.height), view="right"))
    result = PartResult(
        shape=shape,
        features=feats,
        dims=dims,
        flat_pattern=fp,
        props={
            "developed_area": fp.area,
            **_inner_props(a),
            "bend_allowance": ba,
            "k_factor": k,
        },
    )
    result.flat_map = flat_map
    return result


def _signed_area(points: list[Vec2]) -> float:
    """Shoelace signed area (positive for counter-clockwise)."""
    s = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True):
        s += x1 * y2 - x2 * y1
    return s / 2
