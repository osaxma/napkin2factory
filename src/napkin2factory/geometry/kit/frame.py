"""``frame``: a welded stand of square-tube or angle members, like a table base.

Four vertical legs stand at the corners of the footprint and span the full height.  A
rectangle of top rails joins the leg tops (flush with ``z = height``) and, optionally, a
second rectangle of bottom rails sits at ``bottom_rail_height`` (floor to rail underside).
Rails are cut to fit *between* the legs (``length - 2*size`` along X, ``width - 2*size``
along Y) and sit in line with the legs, so their outer faces are flush with the legs' outer
faces.  The whole weldment is one custom part: every member is built as its own solid and
the lot is fused into a single solid.

Coordinates: origin at the centre of the footprint on the floor (``z = 0``), X along
``length``, Y along ``width``, Z up to ``height``.

Member joins.  A rail cut to its true length only *touches* the legs, and a boolean fuse of
merely touching solids is fragile (it can leave several solids or slivers).  Each rail's
end therefore runs :data:`JOIN_OVERLAP` (0.01 mm) into the leg it meets, and only the part
of its section that lands inside solid leg material is extended:

* square tube: the whole ring section is extended; it lands inside the leg's wall, which is
  a solid slab ``wall`` thick across the full leg face.
* angle: only the rail's vertical (outside) flange is extended; it lands inside the leg
  flange lying in the same outer plane.  The horizontal flange stops at the true cut.

Because every extension is swallowed by leg material, the fused volume equals the analytic
sum of the true-length member volumes exactly, and the cut list reports the true cut length.

Angle orientation.  An angle is an L section of two legs ``size`` long and ``wall`` thick.
Legs put the outside corner of the L at the frame's outer vertical edge (one flange on each
outer face).  Rails put the outside corner at the frame's outer edge of the rail band: a
vertical flange in the outer face and a horizontal flange along the rail's top (for top
rails that is the frame's top edge; bottom rails use the same orientation so the horizontal
flange can carry a shelf).

Overhang (N7 aesthetics).  With ``overhang > 0`` the top rails become a ring that sits *on*
the legs and reaches ``overhang`` beyond them on every side, like a table top: the X rails
run the full ``length + 2·overhang``, the Y rails fit between them, and the legs stop under
the ring (``height − size``).  The ring must still land on the legs' outer walls, so
``overhang ≤ size − wall``; square tube only.  Each leg top runs :data:`JOIN_OVERLAP` up
into the ring.  A part with a styling role that leaves ``overhang`` unset takes
``style.overhang`` (skipped with a note when it does not fit this frame).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from build123d import Box, Pos, Shape

from napkin2factory.geometry.features import CutItem, Dim, Features, Member, PartResult
from napkin2factory.geometry.kit import KitArgs, KitContext
from napkin2factory.geometry.kit._common import (
    Length,
    apply_style_defaults,
    massing_result,
    require_positive,
    style_length,
)

JOIN_OVERLAP = 0.01  # mm a rail end runs into the leg it is welded to (see module docstring)


class MemberSpec(KitArgs):
    """The stock every member is cut from."""

    profile: Literal["square-tube", "angle"] = "square-tube"
    size: Length  # outer side of the tube, or leg length of the angle
    wall: Length  # tube wall, or angle leg thickness


class Args(KitArgs):
    """``frame`` arguments (lengths in any unit; converted to mm)."""

    length: Length  # outer X
    width: Length  # outer Y
    height: Length  # outer Z
    member: MemberSpec
    top_rails: bool = True
    bottom_rails: bool = True
    bottom_rail_height: Length | None = None  # floor to rail underside; default = member size
    overhang: Length = 0.0  # top ring beyond the legs on every side; 0 = rails between legs
    process: str = "welding"


ARGS = Args


@dataclass
class _Piece:
    """One member before solid modelling: axis, centre line, cut length, angle corner."""

    label: str
    kind: str  # leg | rail-x | rail-y
    axis: int  # 0 = X, 1 = Y, 2 = Z
    center: tuple[float, float, float]
    length: float  # true cut length
    corner: tuple[float, float]  # sign of the outside corner in the two cross-section axes
    extend: bool  # rail ends run JOIN_OVERLAP into the legs
    extend_top: bool = False  # the top end runs JOIN_OVERLAP up into the overhanging ring


def profile_name(m: MemberSpec) -> str:
    """Stock description used in members and the cut list, e.g. ``square-tube 25x25x2``."""
    return f"{m.profile} {m.size:g}x{m.size:g}x{m.wall:g}"


def section_area(m: MemberSpec) -> float:
    """Cross-section area of the stock, mm²."""
    s, w = m.size, m.wall
    if m.profile == "square-tube":
        return s * s - (s - 2 * w) ** 2
    return 2 * s * w - w * w


def validate(a: Args) -> float:
    """Check the frame can be built; return the resolved bottom rail height."""
    m = a.member
    require_positive(length=a.length, width=a.width, height=a.height, size=m.size, wall=m.wall)
    if m.size < 2 * m.wall + 0.5:
        raise ValueError(f"member size {m.size:g} must be at least 2*wall + 0.5 (wall {m.wall:g})")
    for name, v in (("length", a.length), ("width", a.width)):
        if v <= 2 * m.size + 10:
            raise ValueError(
                f"frame {name} {v:g} must exceed 2*size + 10 = {2 * m.size + 10:g} "
                "to leave room for rails between the legs"
            )
    if a.height <= m.size:
        raise ValueError(f"frame height {a.height:g} must exceed member size {m.size:g}")
    if not (a.top_rails or a.bottom_rails):
        raise ValueError("a frame needs top_rails or bottom_rails: bare legs are not a weldment")
    if a.overhang < 0:
        raise ValueError(f"overhang must not be negative, got {a.overhang:g}")
    if a.overhang > 0:
        if not a.top_rails:
            raise ValueError("an overhang needs top rails: the ring is what overhangs")
        if m.profile != "square-tube":
            raise ValueError("an overhang needs square-tube members (an angle ring has no floor)")
        if a.overhang > m.size - m.wall + 1e-9:
            raise ValueError(
                f"overhang {a.overhang:g} must not exceed size − wall = {m.size - m.wall:g} "
                "so the top ring still sits on the legs"
            )
    hb = m.size if a.bottom_rail_height is None else a.bottom_rail_height
    if a.bottom_rails:
        if hb < 0:
            raise ValueError(f"bottom_rail_height {hb:g} must not be negative")
        if hb + m.size >= a.height - m.size:
            raise ValueError(
                f"bottom rails at {hb:g} (top {hb + m.size:g}) collide with the top rails "
                f"(underside {a.height - m.size:g})"
            )
    return hb


def pieces(a: Args, bottom_height: float) -> list[_Piece]:
    """Lay out legs and rails (centre lines, true cut lengths) in frame coordinates."""
    s = a.member.size
    hx, hy = a.length / 2, a.width / 2
    cx, cy = hx - s / 2, hy - s / 2  # leg centre lines
    o = a.overhang
    out: list[_Piece] = []
    corners = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    leg_h = a.height - s if o > 0 else a.height
    for i, (sx, sy) in enumerate(corners, 1):
        center = (sx * cx, sy * cy, leg_h / 2)
        out.append(_Piece(f"leg-{i}", "leg", 2, center, leg_h, (sx, sy), False, o > 0))
    levels: list[tuple[str, float]] = []
    if a.top_rails and o > 0:
        z, rx, ry = a.height - s / 2, hx + o - s / 2, hy + o - s / 2
        for i, sy in enumerate((-1, 1), 1):  # full-length X rails of the ring
            out.append(
                _Piece(
                    f"top-rail-x-{i}",
                    "rail-x",
                    0,
                    (0.0, sy * ry, z),
                    a.length + 2 * o,
                    (sy, 1),
                    False,
                )
            )
        for i, sx in enumerate((-1, 1), 1):  # Y rails between them
            out.append(
                _Piece(
                    f"top-rail-y-{i}",
                    "rail-y",
                    1,
                    (sx * rx, 0.0, z),
                    a.width + 2 * o - 2 * s,
                    (sx, 1),
                    True,
                )
            )
    elif a.top_rails:
        levels.append(("top", a.height - s / 2))
    if a.bottom_rails:
        levels.append(("bottom", bottom_height + s / 2))
    for level, z in levels:
        for i, sy in enumerate((-1, 1), 1):  # rails along X, cross section (Y, Z)
            out.append(
                _Piece(
                    f"{level}-rail-x-{i}",
                    "rail-x",
                    0,
                    (0.0, sy * cy, z),
                    a.length - 2 * s,
                    (sy, 1),
                    True,
                )
            )
        for i, sx in enumerate((-1, 1), 1):  # rails along Y, cross section (X, Z)
            out.append(
                _Piece(
                    f"{level}-rail-y-{i}",
                    "rail-y",
                    1,
                    (sx * cx, 0.0, z),
                    a.width - 2 * s,
                    (sx, 1),
                    True,
                )
            )
    return out


def _box(axis: int, along: float, u: float, v: float, center: tuple[float, float, float]) -> Shape:
    """An axis-aligned box ``along`` long on ``axis`` with cross section ``u`` × ``v``."""
    cross = [i for i in range(3) if i != axis]
    size = [0.0, 0.0, 0.0]
    size[axis], size[cross[0]], size[cross[1]] = along, u, v
    return Pos(*center) * Box(*size)


def _solid_span(p: _Piece) -> tuple[float, tuple[float, float, float]]:
    """Modelled length and centre of a member, join extensions included."""
    if p.extend_top:
        c = list(p.center)
        c[p.axis] += JOIN_OVERLAP / 2
        return p.length + JOIN_OVERLAP, (c[0], c[1], c[2])
    return p.length + (2 * JOIN_OVERLAP if p.extend else 0.0), p.center


def member_solid(p: _Piece, m: MemberSpec) -> Shape:
    """Model one member as a solid along its axis (see the module docstring for joins)."""
    s, w = m.size, m.wall
    ext = p.length + (2 * JOIN_OVERLAP if p.extend else 0.0)
    if m.profile == "square-tube":
        ext, center = _solid_span(p)
        outer = _box(p.axis, ext, s, s, center)
        inner = _box(p.axis, ext + 2, s - 2 * w, s - 2 * w, center)
        return outer - inner
    cross = [i for i in range(3) if i != p.axis]
    cu, cv = p.corner
    # flange thin along the first cross axis (for rails: the vertical flange in the outer face)
    c1 = list(p.center)
    c1[cross[0]] += cu * (s - w) / 2
    f1 = _box(p.axis, ext, w, s, (c1[0], c1[1], c1[2]))
    # flange thin along the second cross axis (for rails: the horizontal flange, true length)
    c2 = list(p.center)
    c2[cross[1]] += cv * (s - w) / 2
    f2 = _box(p.axis, p.length, s, w, (c2[0], c2[1], c2[2]))
    return f1 + f2


def _endpoints(p: _Piece) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    a, b = list(p.center), list(p.center)
    a[p.axis] -= p.length / 2
    b[p.axis] += p.length / 2
    return (a[0], a[1], a[2]), (b[0], b[1], b[2])


def _overall_dims(a: Args) -> list[Dim]:
    hx, hy = a.length / 2, a.width / 2
    return [
        Dim("length", a.length, (-hx, -hy, 0), (hx, -hy, 0), view="front"),
        Dim("width", a.width, (hx, -hy, 0), (hx, hy, 0), view="right"),
        Dim("height", a.height, (hx, -hy, 0), (hx, -hy, a.height), view="front"),
    ]


def massing(a: Args, ctx: KitContext) -> PartResult:
    """Silhouette (N3): every member a solid ``size × size`` box where :func:`pieces` puts it.

    Members are not hollow and angles are not L sections; rail ends run
    :data:`JOIN_OVERLAP` into the (solid) legs so the fuse is robust and the volume exact.
    No member features and no cut list.

    The silhouette overstates the metal several times over, so the props carry what the
    stock really holds (S-087): ``section_area`` × ``total_member_length`` =
    ``material_volume``, the same volume the full build's fused weldment has (see the module
    docstring). The massing composer weighs a frame by ``material_volume``, not the boxes.
    """
    hb = validate(a)
    s = a.member.size
    layout = pieces(a, hb)
    boxes = []
    for p in layout:
        ext, center = _solid_span(p)
        boxes.append(_box(p.axis, ext, s, s, center))
    shape = boxes[0].fuse(*boxes[1:]).clean()
    area = section_area(a.member)
    total = sum(p.length for p in layout)
    props = {"section_area": area, "total_member_length": total, "material_volume": area * total}
    return massing_result(shape, a.process, _overall_dims(a), ctx, props)


def generate(a: Args, ctx: KitContext) -> PartResult:
    """Build the frame as one fused weldment. Origin at the footprint centre on the floor."""
    notes: list[str] = []
    if ctx.styled is not None:
        a, notes = apply_style_defaults(a, {"overhang": style_length(ctx, "overhang")}, validate)
    hb = validate(a)
    m = a.member
    layout = pieces(a, hb)
    solids = [member_solid(p, m) for p in layout]
    shape = solids[0].fuse(*solids[1:]).clean()
    shape.label = ctx.uri

    prof = profile_name(m)
    feats = Features(process=a.process, thickness=m.wall)
    for p in layout:
        start, end = _endpoints(p)
        feats.members.append(Member(prof, p.length, start, end, label=p.label))
    rails = [p for p in layout if p.kind != "leg"]
    feats.extra = {
        "member_count": len(layout),
        "weld_joints": 2 * len(rails),  # each rail end is welded to one leg
        "profile": m.profile,
        "join_overlap": JOIN_OVERLAP,
    }
    if a.overhang > 0:
        feats.extra["overhang"] = a.overhang

    groups: dict[float, list[_Piece]] = {}
    for p in layout:
        groups.setdefault(round(p.length, 6), []).append(p)
    cut_list = [
        CutItem(
            description=" + ".join(sorted({p.kind for p in ps})),
            length=ps[0].length,
            qty=len(ps),
            profile=prof,
            width=m.size,
            thickness=m.wall,
        )
        for _, ps in sorted(groups.items(), reverse=True)
    ]

    hx, hy, s = a.length / 2, a.width / 2, m.size
    dims = _overall_dims(a) + [
        Dim("member", s, (hx - s, -hy, a.height), (hx, -hy, a.height), view="top"),
    ]
    if a.bottom_rails:
        dims.append(Dim("bottom_rail_height", hb, (0, -hy, 0), (0, -hy, hb), view="front"))
    total = sum(p.length for p in layout)
    return PartResult(
        shape=shape,
        features=feats,
        dims=dims,
        cut_list=cut_list,
        props={"total_member_length": total, "section_area": section_area(m)},
        notes=notes,
    )
