"""``frame``: a welded stand of square/rect/round tube, angle or T-slot members (S-202).

Four vertical legs stand at the corners of the footprint and span the full height. A
rectangle of top rails joins the leg tops (flush with ``z = height``, or recessed by
``apron_offset_top``) and, optionally, a second rectangle of bottom rails sits at
``bottom_rail_height`` (floor to rail underside). Rails are cut to fit *between* the
legs and sit in line with the legs, so their outer faces are flush with the legs' outer
faces. Optional ``mounting_tabs`` (slotted plates) fuse to the inside faces of top rails.
The whole weldment is one custom part: every member is built as its own solid and the
lot is fused into a single solid.

Coordinates: origin at the centre of the footprint on the floor (``z = 0``), X along
``length``, Y along ``width``, Z up to ``height``.

Member joins. Each rail's end runs :data:`JOIN_OVERLAP` (0.01 mm) into the leg it meets.
Because every extension is swallowed by leg material, the fused volume equals the
analytic sum of the true-length member volumes and mounting tabs minus slots, and the
cut list reports the true cut length.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from build123d import Box, Circle, Pos, Shape, SlotOverall, extrude

from napkin2factory.geometry.features import CutItem, Dim, Features, Member, PartResult
from napkin2factory.geometry.kit import KitArgs, KitContext
from napkin2factory.geometry.kit._common import (
    Length,
    apply_style_defaults,
    massing_result,
    require_positive,
    style_length,
)
from napkin2factory.geometry.kit._profiles import (
    ProfileKind,
    profile_name,
    round_tube_solid,
    section_area,
    t_slot_solid,
    validate_member,
)

JOIN_OVERLAP = 0.01  # mm a rail end runs into the leg it is welded to


class MemberSpec(KitArgs):
    """The stock every member is cut from."""

    profile: ProfileKind = "square-tube"
    size: Length  # outer side, OD, angle leg, or rect-tube height
    wall: Length = 0.0  # tube wall, or angle leg thickness
    size2: Length | None = None  # rect-tube width (required for rect-tube)
    slot_width: Length | None = None  # t-slot groove width (required for t-slot)
    slot_depth: Length | None = None  # t-slot groove depth (required for t-slot)


class TabSpec(KitArgs):
    """A mounting tab fused to the inside face of a top rail."""

    x: Length  # centre X, frame coordinates
    y: Length  # centre Y, frame coordinates
    width: Length  # dimension across the rail (inward into frame)
    length: Length  # dimension along the rail
    thickness: Length  # tab plate thickness
    slot_length: Length  # through slot length (long axis across the rail)
    slot_width: Length  # through slot width (short axis along the rail)
    rail: Literal["x", "y"] = "x"  # rail the tab is attached to


class Args(KitArgs):
    """``frame`` arguments (lengths in any unit; converted to mm)."""

    length: Length  # outer X
    width: Length  # outer Y
    height: Length  # outer Z
    member: MemberSpec
    rail_member: MemberSpec | None = None  # stock for rails; legs keep member
    top_rails: bool = True
    bottom_rails: bool = True
    bottom_rail_height: Length | None = None  # floor to rail underside; default = member size
    apron_offset_top: Length = 0.0  # top rails set down from frame top
    overhang: Length = 0.0  # top ring beyond the legs on every side; 0 = rails between legs
    mounting_tabs: list[TabSpec] = []
    process: str = "welding"


ARGS = Args

__all__ = [
    "ARGS",
    "Args",
    "JOIN_OVERLAP",
    "MemberSpec",
    "ProfileKind",
    "TabSpec",
    "generate",
    "massing",
    "member_solid",
    "pieces",
    "profile_name",
    "section_area",
    "validate",
    "validate_member",
]


@dataclass
class _Piece:
    """One member before solid modelling: axis, centre line, cut length, angle corner."""

    label: str
    kind: str  # leg | rail-x | rail-y
    axis: int  # 0 = X, 1 = Y, 2 = Z
    center: tuple[float, float, float]
    length: float  # true cut length
    corner: tuple[float, float]  # sign of the outside corner in cross-section axes
    extend: bool  # rail ends run JOIN_OVERLAP into the legs
    extend_top: bool = False  # the top end runs JOIN_OVERLAP up into overhanging ring
    member: MemberSpec | None = None


def validate(a: Args) -> float:
    """Check the frame can be built; return the resolved bottom rail height."""
    validate_member(a.member, "member")
    if a.rail_member is not None:
        validate_member(a.rail_member, "rail_member")
    rail_m = a.rail_member or a.member
    m = a.member
    require_positive(length=a.length, width=a.width, height=a.height)

    leg_sx = m.size
    leg_sy = m.size2 if m.profile == "rect-tube" and m.size2 is not None else m.size
    rail_hz = rail_m.size
    for name, v, leg_s in (("length", a.length, leg_sx), ("width", a.width, leg_sy)):
        if v <= 2 * leg_s + 10:
            raise ValueError(
                f"frame {name} {v:g} must exceed 2*size + 10 = {2 * leg_s + 10:g} "
                "to leave room for rails between the legs"
            )
    if a.height <= rail_hz:
        raise ValueError(f"frame height {a.height:g} must exceed member size {rail_hz:g}")
    if not (a.top_rails or a.bottom_rails):
        raise ValueError("a frame needs top_rails or bottom_rails: bare legs are not a weldment")
    if a.apron_offset_top < 0:
        raise ValueError(f"apron_offset_top must not be negative, got {a.apron_offset_top:g}")
    if a.overhang < 0:
        raise ValueError(f"overhang must not be negative, got {a.overhang:g}")
    if a.overhang > 0:
        if a.apron_offset_top > 0:
            raise ValueError("overhang cannot be combined with apron_offset_top")
        if not a.top_rails:
            raise ValueError("an overhang needs top rails: the ring is what overhangs")
        if m.profile != "square-tube":
            raise ValueError("an overhang needs square-tube members (an angle ring has no floor)")
        if a.overhang > m.size - m.wall + 1e-9:
            raise ValueError(
                f"overhang {a.overhang:g} must not exceed size − wall = {m.size - m.wall:g} "
                "so the top ring still sits on the legs"
            )
    if a.top_rails and a.apron_offset_top + rail_hz >= a.height:
        raise ValueError(
            f"apron_offset_top ({a.apron_offset_top:g}) + rail height ({rail_hz:g}) "
            f"must be < frame height ({a.height:g})"
        )
    hb = rail_hz if a.bottom_rail_height is None else a.bottom_rail_height
    if a.bottom_rails:
        if hb < 0:
            raise ValueError(f"bottom_rail_height {hb:g} must not be negative")
        top_underside = a.height - a.apron_offset_top - rail_hz if a.top_rails else a.height
        if hb + rail_hz >= top_underside:
            raise ValueError(
                f"bottom rails at {hb:g} (top {hb + rail_hz:g}) collide with the top rails "
                f"(underside {top_underside:g})"
            )
    for idx, tab in enumerate(a.mounting_tabs, 1):
        if not a.top_rails:
            raise ValueError("mounting_tabs require top_rails")
        require_positive(
            **{
                f"tab[{idx}].width": tab.width,
                f"tab[{idx}].length": tab.length,
                f"tab[{idx}].thickness": tab.thickness,
                f"tab[{idx}].slot_length": tab.slot_length,
                f"tab[{idx}].slot_width": tab.slot_width,
            }
        )
        if tab.slot_length < tab.slot_width:
            raise ValueError(
                f"tab[{idx}] slot_length {tab.slot_length:g} "
                f"must be >= slot_width {tab.slot_width:g}"
            )
        if tab.slot_length > tab.width:
            raise ValueError(
                f"tab[{idx}] slot_length {tab.slot_length:g} "
                f"must not exceed tab width {tab.width:g}"
            )
        if tab.slot_width > tab.length:
            raise ValueError(
                f"tab[{idx}] slot_width {tab.slot_width:g} "
                f"must not exceed tab length {tab.length:g}"
            )
    return hb


def pieces(a: Args, bottom_height: float) -> list[_Piece]:
    """Lay out legs and rails (centre lines, true cut lengths) in frame coordinates."""
    m = a.member
    rail_m = a.rail_member or m
    leg_sx = m.size
    leg_sy = m.size2 if m.profile == "rect-tube" and m.size2 is not None else m.size
    hx, hy = a.length / 2, a.width / 2
    cx, cy = hx - leg_sx / 2, hy - leg_sy / 2
    o = a.overhang
    out: list[_Piece] = []
    corners = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    leg_h = a.height - rail_m.size if o > 0 else a.height
    for i, (sx, sy) in enumerate(corners, 1):
        center = (sx * cx, sy * cy, leg_h / 2)
        out.append(_Piece(f"leg-{i}", "leg", 2, center, leg_h, (sx, sy), False, o > 0, member=m))

    rail_hz = rail_m.size
    is_rect = rail_m.profile == "rect-tube" and rail_m.size2 is not None
    rail_wx = rail_m.size2 if is_rect else rail_m.size
    rail_wy = rail_wx
    levels: list[tuple[str, float]] = []
    if a.top_rails and o > 0:
        z, rx, ry = a.height - rail_hz / 2, hx + o - rail_hz / 2, hy + o - rail_hz / 2
        for i, sy in enumerate((-1, 1), 1):
            out.append(
                _Piece(
                    f"top-rail-x-{i}",
                    "rail-x",
                    0,
                    (0.0, sy * ry, z),
                    a.length + 2 * o,
                    (sy, 1),
                    False,
                    member=rail_m,
                )
            )
        for i, sx in enumerate((-1, 1), 1):
            out.append(
                _Piece(
                    f"top-rail-y-{i}",
                    "rail-y",
                    1,
                    (sx * rx, 0.0, z),
                    a.width + 2 * o - 2 * rail_hz,
                    (sx, 1),
                    True,
                    member=rail_m,
                )
            )
    elif a.top_rails:
        levels.append(("top", a.height - a.apron_offset_top - rail_hz / 2))
    if a.bottom_rails:
        levels.append(("bottom", bottom_height + rail_hz / 2))

    for level, z in levels:
        for i, sy in enumerate((-1, 1), 1):
            out.append(
                _Piece(
                    f"{level}-rail-x-{i}",
                    "rail-x",
                    0,
                    (0.0, sy * (hy - rail_wy / 2), z),
                    a.length - 2 * leg_sx,
                    (sy, 1),
                    True,
                    member=rail_m,
                )
            )
        for i, sx in enumerate((-1, 1), 1):
            out.append(
                _Piece(
                    f"{level}-rail-y-{i}",
                    "rail-y",
                    1,
                    (sx * (hx - rail_wx / 2), 0.0, z),
                    a.width - 2 * leg_sy,
                    (sx, 1),
                    True,
                    member=rail_m,
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
    """Model one member as a solid along its axis (see module docstring for joins)."""
    s, w = m.size, m.wall
    ext, center = _solid_span(p)
    if m.profile == "square-tube":
        outer = _box(p.axis, ext, s, s, center)
        inner = _box(p.axis, ext + 2, s - 2 * w, s - 2 * w, center)
        return outer - inner
    if m.profile == "rect-tube":
        s2 = m.size2 if m.size2 is not None else s
        u = s2 if p.kind != "leg" else s
        v = s if p.kind != "leg" else s2
        outer = _box(p.axis, ext, u, v, center)
        inner = _box(p.axis, ext + 2, u - 2 * w, v - 2 * w, center)
        return outer - inner
    if m.profile == "round-tube":
        return round_tube_solid(p.axis, ext, s, w, center)
    if m.profile == "t-slot":
        sw = m.slot_width or 0.0
        sd = m.slot_depth or 0.0
        return t_slot_solid(p.axis, ext, s, sw, sd, center, _box)
    # angle
    cross = [i for i in range(3) if i != p.axis]
    cu, cv = p.corner
    c1 = list(p.center)
    c1[cross[0]] += cu * (s - w) / 2
    f1 = _box(p.axis, ext, w, s, (c1[0], c1[1], c1[2]))
    c2 = list(p.center)
    c2[cross[1]] += cv * (s - w) / 2
    f2 = _box(p.axis, p.length, s, w, (c2[0], c2[1], c2[2]))
    return f1 + f2


def _tab_volume(tab: TabSpec) -> float:
    if abs(tab.slot_length - tab.slot_width) < 1e-9:
        slot_area = (math.pi / 4) * (tab.slot_width**2)
    else:
        slot_area = (tab.slot_length - tab.slot_width) * tab.slot_width + (math.pi / 4) * (
            tab.slot_width**2
        )
    return (tab.width * tab.length - slot_area) * tab.thickness


def _tab_solid(tab: TabSpec, z_top: float) -> Shape:
    tc = tab.thickness
    zc = z_top - tc / 2
    if tab.rail == "x":
        sy = 1 if tab.y >= 0 else -1
        cy = tab.y + sy * JOIN_OVERLAP / 2
        plate = Pos(tab.x, cy, zc) * Box(tab.length, tab.width + JOIN_OVERLAP, tc)
        if abs(tab.slot_length - tab.slot_width) < 1e-9:
            slot_sk = Circle(tab.slot_width / 2)
        else:
            slot_sk = SlotOverall(tab.slot_length, tab.slot_width, rotation=90)
    else:
        sx = 1 if tab.x >= 0 else -1
        cx = tab.x + sx * JOIN_OVERLAP / 2
        plate = Pos(cx, tab.y, zc) * Box(tab.width + JOIN_OVERLAP, tab.length, tc)
        if abs(tab.slot_length - tab.slot_width) < 1e-9:
            slot_sk = Circle(tab.slot_width / 2)
        else:
            slot_sk = SlotOverall(tab.slot_length, tab.slot_width)
    slot_cut = Pos(tab.x, tab.y, zc - (tc + 2) / 2) * extrude(slot_sk, amount=tc + 2)
    return plate - slot_cut


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
    """Silhouette (N3): members as solid boxes where pieces puts them."""
    hb = validate(a)
    layout = pieces(a, hb)
    boxes = []
    rail_m = a.rail_member or a.member
    for p in layout:
        ext, center = _solid_span(p)
        pm = p.member or a.member
        s = pm.size
        s2 = pm.size2 if pm.profile == "rect-tube" and pm.size2 is not None else s
        u = s2 if p.kind != "leg" else s
        v = s if p.kind != "leg" else s2
        boxes.append(_box(p.axis, ext, u, v, center))
    z_top = a.height - a.apron_offset_top
    for tab in a.mounting_tabs:
        boxes.append(_tab_solid(tab, z_top))
    shape = boxes[0].fuse(*boxes[1:]).clean()

    total_leg_len = sum(p.length for p in layout if p.kind == "leg")
    total_rail_len = sum(p.length for p in layout if p.kind != "leg")
    total_len = total_leg_len + total_rail_len
    mat_vol = (
        section_area(a.member) * total_leg_len
        + section_area(rail_m) * total_rail_len
        + sum(_tab_volume(t) for t in a.mounting_tabs)
    )
    props: dict[str, Any] = {
        "section_area": section_area(a.member),
        "total_member_length": total_len,
        "material_volume": mat_vol,
    }
    if a.mounting_tabs:
        props["tab_count"] = len(a.mounting_tabs)
    return massing_result(shape, a.process, _overall_dims(a), ctx, props)


def generate(a: Args, ctx: KitContext) -> PartResult:
    """Build the frame as one fused weldment. Origin at footprint centre on floor."""
    notes: list[str] = []
    if ctx.styled is not None:
        a, notes = apply_style_defaults(a, {"overhang": style_length(ctx, "overhang")}, validate)
    hb = validate(a)
    m = a.member
    rail_m = a.rail_member or m
    layout = pieces(a, hb)
    solids = [member_solid(p, p.member or m) for p in layout]

    z_top = a.height - a.apron_offset_top
    for tab in a.mounting_tabs:
        solids.append(_tab_solid(tab, z_top))

    shape = solids[0].fuse(*solids[1:]).clean()
    shape.label = ctx.uri

    feats = Features(process=a.process, thickness=m.wall)
    for p in layout:
        start, end = _endpoints(p)
        pm = p.member or m
        feats.members.append(Member(profile_name(pm), p.length, start, end, label=p.label))
    rails = [p for p in layout if p.kind != "leg"]
    feats.extra = {
        "member_count": len(layout),
        "weld_joints": 2 * len(rails),
        "profile": m.profile,
        "join_overlap": JOIN_OVERLAP,
    }
    if a.rail_member is not None:
        feats.extra["rail_profile"] = a.rail_member.profile
    if a.overhang > 0:
        feats.extra["overhang"] = a.overhang
    if a.apron_offset_top > 0:
        feats.extra["apron_offset_top"] = a.apron_offset_top
    if a.mounting_tabs:
        feats.extra["tab_count"] = len(a.mounting_tabs)

    groups: dict[tuple[float, str], list[_Piece]] = {}
    for p in layout:
        pm = p.member or m
        groups.setdefault((round(p.length, 6), profile_name(pm)), []).append(p)
    cut_list = [
        CutItem(
            description=" + ".join(sorted({p.kind for p in ps})),
            length=ps[0].length,
            qty=len(ps),
            profile=p_name,
            width=(ps[0].member or m).size,
            thickness=(ps[0].member or m).wall,
        )
        for (_, p_name), ps in sorted(groups.items(), key=lambda item: (-item[0][0], item[0][1]))
    ]

    hx, hy, s = a.length / 2, a.width / 2, m.size
    dims = _overall_dims(a) + [
        Dim("member", s, (hx - s, -hy, a.height), (hx, -hy, a.height), view="top"),
    ]
    if a.bottom_rails:
        dims.append(Dim("bottom_rail_height", hb, (0, -hy, 0), (0, -hy, hb), view="front"))

    total_leg_len = sum(p.length for p in layout if p.kind == "leg")
    total_rail_len = sum(p.length for p in layout if p.kind != "leg")
    total = total_leg_len + total_rail_len
    mat_vol = (
        section_area(m) * total_leg_len
        + section_area(rail_m) * total_rail_len
        + sum(_tab_volume(t) for t in a.mounting_tabs)
    )

    props: dict[str, Any] = {
        "total_member_length": total,
        "section_area": section_area(m),
        "material_volume": mat_vol,
    }
    if a.rail_member is not None:
        props["rail_section_area"] = section_area(rail_m)
    if a.mounting_tabs:
        props["tab_count"] = len(a.mounting_tabs)
        props["mounting_tabs"] = [
            {
                "center": (t.x, t.y, z_top),
                "rail": t.rail,
                "slot_length": t.slot_length,
                "slot_width": t.slot_width,
                "thickness": t.thickness,
                "width": t.width,
                "length": t.length,
            }
            for t in a.mounting_tabs
        ]
        for t in a.mounting_tabs:
            notes.append(
                f"mounting tab on rail-{t.rail} at ({t.x:g}, {t.y:g}, {z_top:g}) "
                f"with slot {t.slot_length:g}x{t.slot_width:g}"
            )

    return PartResult(
        shape=shape,
        features=feats,
        dims=dims,
        cut_list=cut_list,
        props=props,
        notes=notes,
    )
