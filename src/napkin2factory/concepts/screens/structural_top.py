"""The structural screen's cases for a top on a stand (W4, S-206, S-235).

A card's massing is read, never guessed. The top is the widest flat board (a ``block``,
``plate`` or ``panel`` call); what carries it is the first of these that fits:

* a **frame** (one ``frame`` call): its four legs at the corners, with or without rails. The
  top spans the frame's long side between the legs; with top rails the two long rails share
  that span (their stiffness adds to the top's). A tube or block across the frame's width that
  the top rests on is a **cross member**: the centre load reaches the long rails through it, and
  its dip adds to the sag along the length.
* **bare legs**: three or more upright tubes or blocks under the top, reaching up to it. The
  top spans between the outermost leg lines along its long side.
* **trestle ends**: two or more upright plates (thin, tall ``block`` or ``panel`` calls), or two
  or more frames, under the top. The top spans between the ends along the plates' normal.

Checks: sag and yield of the top; the cross member's yield; buckling of the worst-loaded leg
(trestle ends' own strength is not judged here); tip-over about the feet. The leg carries a
share of the weight plus the centre load and the load's share of any spread load; the edge load
belongs to tip-over alone (B-0217, SPEC section 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from napkin2factory.calckit import joints, structural
from napkin2factory.concepts.screens.base import fmt
from napkin2factory.concepts.screens.structural_base import (
    EDGE_OFFSET,
    LEG_ENDS,
    Ctx,
    Stock,
    column_row,
    deflection_row,
    factor_row,
    length_text,
    mm,
    piece_section,
    skip_row,
    stock_of,
    total_kg,
    tube_section,
    yield_row,
)
from napkin2factory.core.model.concepts import RuleRow
from napkin2factory.core.units import Quantity

Qty = Any
G = 9.80665  # m/s^2, the value calckit.structural uses
#: Shape-reading tolerances (S-235), not engineering numbers: a support "reaches up to" the top
#: when its upper end is within this share of its height of the top's underside; a cross member
#: spans the frame when it is at least this share of the frame's width.
REACH, SPANS = 0.15, 0.7


@dataclass
class Stand:
    """What carries the top: where its supports are along the span, and what buckles."""

    kind: str  # "frame", "legs" or "trestles"
    axis: int  # the span runs along this plan axis (0 = x, 1 = y)
    lo: float  # the supports' lines along the span, outermost first and last
    hi: float
    frame: Any | None = None  # the one frame ("frame")
    posts: list[Any] = field(default_factory=list)  # the legs ("legs")

    @property
    def span(self) -> float:
        """The span in mm between the outermost support lines."""
        return self.hi - self.lo


def _centre(p: Any, axis: int) -> float:
    return float((p.bbox_min[axis] + p.bbox_max[axis]) / 2)


def find_top(pieces: list[Any]) -> Any | None:
    """The widest flat board in the massing, else None."""
    boards = [p for p in pieces if p.kit in ("block", "plate", "panel")]
    boards = [p for p in boards if p.size[2] <= 0.25 * min(p.size[0], p.size[1])]
    return max(boards, key=lambda p: p.size[0] * p.size[1], default=None)


def _under(p: Any, top: Any) -> bool:
    """The piece stands under the top (its plan centre inside the top's) and reaches up to it."""
    inside = all(top.bbox_min[a] - 1 <= _centre(p, a) <= top.bbox_max[a] + 1 for a in (0, 1))
    reach = top.bbox_min[2] - p.bbox_max[2] <= REACH * p.size[2]
    return bool(inside and reach and top.bbox_min[2] >= p.bbox_min[2])


def _post(p: Any) -> bool:
    return bool(p.kit in ("tube", "block") and p.size[2] >= 2 * max(p.size[0], p.size[1]))


def _plate(p: Any) -> bool:
    """A thin, tall board standing on edge."""
    thin, wide = min(p.size[0], p.size[1]), max(p.size[0], p.size[1])
    return bool(p.kit in ("block", "plate", "panel") and thin <= 0.25 * min(wide, p.size[2]))


def _frame_stand(frame: Any) -> Stand:
    ax = 0 if frame.size[0] >= frame.size[1] else 1  # the span runs along the long side
    leg = float(frame.args.member.size)
    return Stand("frame", ax, frame.bbox_min[ax] + leg / 2, frame.bbox_max[ax] - leg / 2, frame)


def _spread(centres: list[float]) -> bool:
    return bool(centres) and max(centres) - min(centres) > 1.0


def find_stand(pieces: list[Any], top: Any | None) -> Stand | None:
    """What carries the top, in the order frame, bare legs, trestle ends; else None."""
    frames = [p for p in pieces if p.kit == "frame"]
    if len(frames) == 1 or (frames and top is None):
        return _frame_stand(frames[0])
    if top is None:
        return None
    ends = [p for p in frames if _under(p, top)]
    if len(ends) >= 2:  # trestle ends made of frames: the span is where they stand apart
        ax = max(
            (0, 1),
            key=lambda a: max(_centre(p, a) for p in ends) - min(_centre(p, a) for p in ends),
        )
        cs = [_centre(p, ax) for p in ends]
        return Stand("trestles", ax, min(cs), max(cs)) if _spread(cs) else None
    posts = [p for p in pieces if _post(p) and _under(p, top)]
    top_ax = 0 if top.size[0] >= top.size[1] else 1
    if len(posts) >= 3 and all(_spread([_centre(p, a) for p in posts]) for a in (0, 1)):
        cs = [_centre(p, top_ax) for p in posts]
        return Stand("legs", top_ax, min(cs), max(cs), posts=posts)
    plates = [p for p in pieces if _plate(p) and _under(p, top)]
    if len(plates) >= 2:  # the plates' normal (their thin side) is the span
        ax = 0 if plates[0].size[0] < plates[0].size[1] else 1
        cs = [_centre(p, ax) for p in plates]
        if all((0 if p.size[0] < p.size[1] else 1) == ax for p in plates) and _spread(cs):
            return Stand("trestles", ax, min(cs), max(cs))
    return None


def _rails(frame: Any, stock: Stock | str) -> tuple[Qty, Qty] | None:
    """E·I and weight of the frame's two long top rails, which share the top's span (S-206)."""
    if isinstance(stock, str) or not frame.args.top_rails:
        return None
    m = getattr(frame.args, "rail_member", None) or frame.args.member
    sec = tube_section(str(m.profile), m.size, m.wall, getattr(m, "size2", None))
    if isinstance(sec, str):
        return None
    ax = 0 if frame.size[0] >= frame.size[1] else 1
    length = Quantity(frame.size[ax] - 2 * frame.args.member.size, "mm")  # cut between the legs
    weight = 2 * Quantity(stock.density, "kg/m^3") * sec.A * length * Quantity(G, "m/s^2")
    return 2 * stock.E * sec.Ix, weight.to("N")


def _cross_member(pieces: list[Any], frame: Any, top: Any | None, ax: int) -> Any | None:
    """The tube or block across the frame's width that the top rests on, else None."""
    if top is None or not frame.args.top_rails:
        return None
    rail = (getattr(frame.args, "rail_member", None) or frame.args.member).size
    across = 1 - ax
    found = [
        p
        for p in pieces
        if p is not top
        and p.kit in ("tube", "block")
        and p.size[across] >= SPANS * frame.size[across]
        and p.size[across] >= 2 * max(p.size[ax], p.size[2])
        and top.bbox_min[2] - rail - 1 <= p.bbox_max[2] <= top.bbox_min[2] + 1
        and frame.bbox_min[ax] < _centre(p, ax) < frame.bbox_max[ax]
    ]
    return min(found, key=lambda p: abs(_centre(p, ax) - _centre(frame, ax)), default=None)


def judge(ctx: Ctx) -> list[RuleRow] | None:
    """Rows for a card whose top stands on a frame, bare legs or trestle ends; None if not."""
    pieces = [] if ctx.massing is None else ctx.massing.pieces
    top = find_top(pieces)
    st = find_stand(pieces, top)
    if st is None:
        return None
    rows: list[RuleRow] = []
    point, spread, edge = (ctx.loads[k] for k in ("point_load", "distributed_load", "edge_load"))
    if point is not None or spread is not None:
        if top is None:
            why = "the massing has no flat top board"
            rows += [skip_row("structural-deflection", why), skip_row("structural-yield", why)]
        else:
            rows += _top_rows(
                ctx,
                st,
                top,
                _cross_member(pieces, st.frame, top, st.axis) if st.frame is not None else None,
            )
    rows += _legs_rows(ctx, st)
    if edge is not None:
        rows.append(_tip_row(ctx, st, top, edge))
    return rows


def _top_rows(ctx: Ctx, st: Stand, top: Any, cross: Any | None) -> list[RuleRow]:
    """Sag and yield of the top as a simply supported beam; with a cross member, its dip too."""
    stock = stock_of(top)
    if isinstance(stock, str):
        return [skip_row("structural-deflection", stock), skip_row("structural-yield", stock)]
    point, spread = ctx.loads["point_load"], ctx.loads["distributed_load"]
    across = 1 - st.axis
    section = structural.rect_section(mm(top.size[across]), mm(top.size[2]))
    span = mm(st.span)
    frame_stock = stock_of(st.frame) if st.frame is not None else "no frame"
    rails = _rails(st.frame, frame_stock) if st.frame is not None else None
    ei_top = stock.E * section.I
    share = 1.0 if rails is None else float((ei_top / (ei_top + rails[0])).to("").magnitude)
    stiff = section.I / share  # the top's I scaled so E·I is the top and the rails together
    # what stands on the beam: the cross member's weight is a point load at the middle, the top's
    # and the long rails' weights are spread along it (SPEC section 4.1)
    centre = point if point is not None else Quantity(0.0, "N")
    uniform = Quantity((top.mass or 0.0) * G, "N")
    weights = [f"self weight of the top {fmt(uniform, 'N')}"]
    if rails is not None:
        uniform = uniform + rails[1]
        weights.append(f"of the two long rails {fmt(rails[1], 'N')}")
    if spread is not None:
        uniform = uniform + spread
        weights.append(f"distributed load {fmt(spread, 'N')}")
    if cross is not None:
        cross_n = Quantity((cross.mass or 0.0) * G, "N")
        centre = centre + cross_n
        weights.append(f"the cross member's weight {fmt(cross_n, 'N')} at the middle")
    parts, moment = [], 0.0
    span_m = float(span.to("m").magnitude)
    if centre.magnitude > 0:
        parts.append(structural.beam_deflection_simply_supported(centre, span, stock.E, stiff))
        moment += float(centre.to("N").magnitude) * span_m / 4  # Roark T8.1 case 2a [verify]
    parts.append(
        structural.beam_deflection_simply_supported(uniform, span, stock.E, stiff, "uniform")
    )
    moment += float(uniform.to("N").magnitude) * span_m / 8  # Roark T8.1 case 2e [verify]
    along = sum((p.deflection.to("mm") for p in parts), mm(0.0))
    shared = ", with the two long top rails sharing it (E·I of top + rails)" if rails else ""
    how = (
        f"{' + '.join(p.formula for p in parts)} on the {length_text(mm(top.size[across]))} wide, "
        f"{length_text(mm(top.size[2]))} thick top over a {length_text(span)} span between its "
        f"supports{shared}, {', '.join(weights)}; {parts[0].source}; {stock.ref}"
    )
    ctx.values.computed.add(
        "deflection_along", along, length_text(along), "computed from the card and the massing", how
    )
    out: list[RuleRow] = []
    dip = None
    total, what = along, "the top sags"
    if cross is not None and point is not None:
        dip_rows = _cross_dip(ctx, st, cross, point)
        if isinstance(dip_rows, str):
            out.append(skip_row("structural-deflection", dip_rows))
        else:
            dip, dip_how, cross_rows = dip_rows
            total = (along + dip).to("mm")
            what = "the top sags (along its length plus the cross member's dip)"
            how = (
                f"the sag along the length {length_text(along)} + the cross member's dip "
                f"{length_text(dip)}: {how}; {dip_how}"
            )
            out += cross_rows
    if not any(r.id == "structural-deflection" for r in out):
        out.insert(0, deflection_row(ctx, total, what, how))
    yield_how = "M = F·L/4 + W·L/8, the top's share" if centre.magnitude > 0 else "M = W·L/8"
    out.insert(1, yield_row(ctx, moment * share, section.Z, stock, "the top", yield_how))
    return out


def _cross_dip(ctx: Ctx, st: Stand, cross: Any, point: Qty) -> tuple[Qty, str, list[RuleRow]] | str:
    """The cross member's dip under the whole centre load and its own stress, else why not."""
    stock = stock_of(cross)
    if isinstance(stock, str):
        return stock
    ax, frame = st.axis, st.frame
    assert frame is not None  # a cross member belongs to a frame
    sec = piece_section(cross, 2, ax)
    if isinstance(sec, str):
        return sec
    rail = (getattr(frame.args, "rail_member", None) or frame.args.member).size
    span = mm(frame.size[1 - ax] - rail)  # long rail to long rail, centre to centre
    dip = structural.beam_deflection_simply_supported(point, span, stock.E, sec.Ix)
    ctx.values.computed.add(
        "cross_member_dip",
        dip.deflection.to("mm"),
        length_text(dip.deflection),
        "computed from the card and the massing",
        dip.formula,
    )
    how = (
        f"the cross member's dip: {dip.formula} on the {length_text(mm(cross.size[2]))} deep "
        f"member over the {length_text(span)} between the long rails, the top given no share; "
        f"{dip.source}; {stock.ref}"
    )
    moment = float(point.to("N").magnitude) * float(span.to("m").magnitude) / 4
    row = yield_row(
        ctx,
        moment,
        sec.Zx,
        stock,
        "the cross member",
        "M = F·L/4",
        rid="structural-cross-member",
        name="cross_member_yield_factor",
    )
    return dip.deflection.to("mm"), how, [row]


def _legs_rows(ctx: Ctx, st: Stand) -> list[RuleRow]:
    """Buckling of the worst-loaded leg; trestle ends' own strength is noted as not judged."""
    point, spread = ctx.loads["point_load"], ctx.loads["distributed_load"]
    if st.kind == "trestles":
        ctx.values.notes.append(
            "the trestle ends' own strength is not judged here: only the top's sag and the tip-over"
        )
        return []
    if ctx.massing.without_material:
        return [skip_row("structural-buckling", "some rough shapes have no material, so no weight")]
    if st.frame is not None:
        leg, m = st.frame, st.frame.args.member
        sec, n = tube_section(str(m.profile), m.size, m.wall, getattr(m, "size2", None)), 4
    else:
        leg, n = max(st.posts, key=lambda p: p.size[2]), len(st.posts)
        sec = piece_section(leg, 0, 1)
    stock = stock_of(leg)
    if isinstance(sec, str):
        return [skip_row("structural-buckling", sec)]
    if isinstance(stock, str):
        return [skip_row("structural-buckling", stock)]
    frac = "a quarter" if n == 4 else f"1/{n}"
    share = f"{frac} of the weight"
    load: Qty = Quantity(total_kg(ctx) * G, "N") / n
    if point is not None:
        load, share = load + point, share + " plus the centre load"
    if spread is not None:
        load, share = load + spread / n, share + f" plus {frac} of the spread load"
    return [column_row(ctx, sec, stock, leg.size[2], load, LEG_ENDS, "one leg", share)]


def _foot_lines(pieces: list[Any], axis: int) -> tuple[float, float]:
    """The outermost floor contacts along ``axis`` (S-235).

    A foot taller than it is wide stands on a point at its centre (a glide, a leg), a flat one on
    its edge (a foot bar), a frame on its legs' centre lines.
    """
    floor = min(p.bbox_min[2] for p in pieces)
    lows, highs = [], []
    for p in (p for p in pieces if p.bbox_min[2] <= floor + 1.0):
        if p.kit == "frame":
            half = float(p.args.member.size) / 2
            lows.append(p.bbox_min[axis] + half)
            highs.append(p.bbox_max[axis] - half)
        elif p.size[2] >= max(p.size[0], p.size[1]):
            lows.append(_centre(p, axis))
            highs.append(_centre(p, axis))
        else:
            lows.append(p.bbox_min[axis])
            highs.append(p.bbox_max[axis])
    return min(lows), max(highs)


def _tip_row(ctx: Ctx, st: Stand, top: Any | None, edge: Qty) -> RuleRow:
    """Tip-over about the nearer foot line: the whole weight at its centre against the edge load."""
    offset = EDGE_OFFSET.quantity(ctx.card)
    if offset is None:
        return skip_row("structural-tip-over", "give how far beyond the support the edge load acts")
    if ctx.massing.without_material:
        return skip_row("structural-tip-over", "some rough shapes have no material, so no weight")
    pieces, axis = ctx.massing.pieces, 1 - st.axis
    moments = [((p.mass or 0.0), _centre(p, axis)) for p in pieces]
    extra = total_kg(ctx) - float(ctx.massing.mass or 0.0)  # the hardware, at the top's middle
    moments.append((extra, _centre(top, axis) if top is not None else 0.0))
    total = sum(m for m, _ in moments)
    cg = sum(m * c for m, c in moments) / total
    lo, hi = _foot_lines(pieces, axis)
    cg_x = min(cg - lo, hi - cg)  # the nearer foot line is the one it tips over
    res = structural.tip_over_safety_factor(
        Quantity(total, "kg"), Quantity(max(cg_x, 0.0), "mm"), edge, offset
    )
    what = "the rough shapes' weight" + (" and the hardware" if extra > 0 else "")
    line = "foot line" if st.kind == "trestles" else "leg line"
    subject = (
        f"{fmt(Quantity(total, 'kg'), 'kg')} ({what}) with its centre "
        f"{length_text(Quantity(cg_x, 'mm'))} inside the {line}, under {fmt(edge, 'N')} acting "
        f"{length_text(offset)} beyond it"
    )
    need = joints.factor_of_safety("tip_over", "edge_load")
    how = f"{res.formula}; {res.source}"
    return factor_row(
        "structural-tip-over", ctx, res.safety_factor, need, subject, how, "edge load"
    )


__all__ = ["Stand", "find_stand", "find_top", "judge"]
