"""The generic ``structural`` screen: does a napkin card stand up under its loads? (W4, S-206).

Loads and limits are ``site`` fields of the card (the package's own words; a product's word
for one, a "throat" or an "overhang", stays in its folder, F9, F10); supports and sections are
read from the card's massing, never guessed:

* a **frame with a top**: the legs are the frame's member section and height; the top is the
  widest flat board (a ``block``, ``plate`` or ``panel`` call), one board across the frame's
  long side between the end legs (span = that side less one leg size, leg centre to centre).
  The two long top rails share that span with the top, so their stiffnesses add (E·I of the
  top + 2 · E·I of a rail) and the top takes its share of the moment. Checks: sag and yield of
  the top, buckling of one leg, tip-over under the edge load.
* a **column with an arm** (``tube`` or ``block`` calls, no frame): the arm reaches out from
  the column's centre line. Checks: tip deflection (arm bending plus column rotation), yield
  at the column foot, buckling of the column.

A check whose inputs are not on the card or in the massing is a row that says which one is
missing and that it was not run. Factors compare against ``calckit.joints.factor_of_safety``
(load kind ``cyclic`` once the card gives ``site.cycles``, else ``static``; tip-over uses
the edge-load row). The screen runs only when the card gives a point, distributed or edge load.
Fatigue and the rails' own stress are not checked here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from napkin2factory.calckit import joints, structural
from napkin2factory.concepts.screens.base import CardField, ScreenValues, fmt, reads, sig
from napkin2factory.core.domain import Screen
from napkin2factory.core.model.concepts import ConceptCard, RuleRow
from napkin2factory.core.units import Quantity

Qty = Any


def _site(key: str, unit: str, kind: str, example: str, words: str) -> CardField:
    # ``hint=False``: a new card's skeleton names these only when the card gives one, so a
    # product with no loads is never asked about them
    return CardField("site", key, unit, kind, example, words, hint=False)


POINT_LOAD = _site("point_load", "N", "a force", "1471.5 N", "the load at the centre of the top")
DISTRIBUTED_LOAD = _site("distributed_load", "N", "a force", "800 N", "the load spread over it")
EDGE_LOAD = _site("edge_load", "N", "a force", "490.5 N", "the downward load at an edge")
EDGE_OFFSET = _site(
    "edge_offset", "mm", "a length", "150 mm", "how far beyond the support the edge load acts"
)
MAX_DEFLECTION = _site("max_deflection", "mm", "a length", "2.5 mm", "the most it may sag")
CYCLES = _site("cycles", "", "a count", "100000", "how many times the load is applied")
FIELDS = (POINT_LOAD, DISTRIBUTED_LOAD, EDGE_LOAD, EDGE_OFFSET, MAX_DEFLECTION, CYCLES)

TITLES = {
    "structural-deflection": "Sag stays within the limit",
    "structural-yield": "Stress stays under yield",
    "structural-buckling": "Legs or column do not buckle",
    "structural-tip-over": "It does not tip over",
    "structural-support": "The massing shows what carries the load",
}
#: Effective length factors: unbraced frame legs sway laterally (AISC Table C-A-7.1 case f,
#: K = 2.0, SPEC §4); a column with an arm is a cantilever (case e, design K = 2.1).
LEG_ENDS, COLUMN_ENDS = 2.0, "fixed-free"


@dataclass
class _Ctx:
    card: ConceptCard
    massing: Any
    values: ScreenValues
    loads: dict[str, Qty | None]
    limit: Qty | None
    kind: str


@dataclass(frozen=True)
class _Stock:
    E: Qty
    yield_strength: Qty
    ref: str


def _mm(v: float) -> Qty:
    return Quantity(v, "mm")


def _len(q: Qty) -> str:
    return f"{sig(float(q.to('mm').magnitude))} mm"


def _row(rid: str, status: Any, message: str) -> RuleRow:
    relies: Any = [] if status == "skip" else ["computed"]
    return RuleRow(id=rid, title=TITLES[rid], status=status, message=message, relies_on=relies)


def _skip(rid: str, why: str) -> RuleRow:
    return _row(rid, "skip", f"not run: {why}")


def _stock(piece: Any) -> _Stock | str:
    """E and yield strength of a piece's material from the shared table, else the reason."""
    # the same keyword match the massing densities use (calckit/data/materials.yaml, W2)
    from napkin2factory.geometry.materials import material_row

    if piece.material is None:
        return f"the {piece.name} has no material"
    row = material_row(piece.material)
    if row is None or row.get("youngs_modulus") is None or row.get("yield_strength") is None:
        return f"no stiffness and strength on file for {piece.material}"
    return _Stock(
        Quantity(float(row["youngs_modulus"]), "Pa"),
        Quantity(float(row["yield_strength"]), "Pa"),
        f"{row['name']} in calckit/data/materials.yaml [verify]",
    )


def _tube(shape: str, size: float, wall: float, size2: float | None = None) -> Any | str:
    if shape in ("round", "round-tube"):
        if wall <= 0 or wall >= size / 2:
            return "no section properties for a solid round bar"
        return structural.round_tube_section(_mm(size), _mm(wall))
    if shape not in ("square", "square-tube", "rect-tube"):
        return f"no section properties for a {shape}"
    if wall <= 0 or wall >= min(size, size2 or size) / 2:
        return structural.rect_section(_mm(size2 or size), _mm(size))
    return structural.rect_tube_section(_mm(size2 or size), _mm(size), _mm(wall))


def _piece_section(piece: Any, depth: int, across: int) -> Any | str:
    """Section of a tube or block piece bending with its ``depth`` axis in the plane."""
    a = piece.args
    if piece.kit == "tube":
        return _tube(a.shape, a.size, a.wall)
    if piece.kit == "block":
        return structural.rect_section(_mm(piece.size[across]), _mm(piece.size[depth]))
    return f"no section properties for a {piece.kit} call"


def _factor_row(
    rid: str, ctx: _Ctx, got: float, need: float, subject: str, how: str, case: str = ""
) -> RuleRow:
    """A factor against the factor it needs: one row, the value, the formula and the source."""
    ok = got >= need
    name = rid.removeprefix("structural-").replace("-", "_") + "_factor"
    ctx.values.computed.add(name, got, sig(got), "computed from the card and the massing", how)
    return _row(
        rid,
        "pass" if ok else "fail",
        f"{subject}: factor {sig(got)} (computed), {'at least' if ok else 'below'} the "
        f"{sig(need)} needed ({case or ctx.kind} case) — {how}",
    )


def _deflection_row(ctx: _Ctx, d: Qty, what: str, how: str) -> RuleRow:
    ctx.values.computed.add("deflection", d, _len(d), "computed from the card and the massing", how)
    if ctx.limit is None:
        msg = f"{what} {_len(d)} (computed), not judged: no max_deflection on the card — {how}"
        return _row("structural-deflection", "skip", msg)
    need = joints.factor_of_safety("deflection", ctx.kind)
    margin = float((ctx.limit / d).to("").magnitude) if float(d.magnitude) else math.inf
    ok = margin >= need
    return _row(
        "structural-deflection",
        "pass" if ok else "fail",
        f"{what} {_len(d)} (computed), {'within' if ok else 'beyond'} the {_len(ctx.limit)} "
        f"limit on the card (limit ÷ sag is {sig(margin)}, {sig(need)} needed, "
        f"{ctx.kind} case) — {how}",
    )


def _column_row(
    ctx: _Ctx, sec: Any, stock: _Stock, length_mm: float, load: Qty, ends: str | float, who: str
) -> RuleRow:
    """Buckling of one column by Euler or Johnson depending on slenderness (S-207, S-211)."""
    i_min, length = min(sec.Ix, sec.Iy), _mm(length_mm)
    res = structural.column_buckling_load(
        stock.E, i_min, sec.A, stock.yield_strength, length, ends, load=load
    )
    got = res.safety_factor or math.inf
    if isinstance(ends, (int, float)):
        k, ends_label = float(ends), "sway"
    else:
        k, ends_label = structural.K_FACTORS[ends], ends
    need = joints.factor_of_safety("buckling", ctx.kind)
    method_name = res.method.capitalize()
    formula_text = f"{method_name} ({res.formula})"
    how = f"{formula_text}; slenderness {sig(res.slenderness or 0)}, K {k:g} ({ends_label}); "
    how += f"{res.source}; {stock.ref}"
    if who == "one leg":
        subject = (
            f"the worst-loaded leg, taking a quarter of the weight plus the applied loads "
            f"({fmt(load, 'N')}), over {_len(length)}"
        )
    else:
        subject = f"{who} under {fmt(load, 'N')} over {_len(length)}"
    return _factor_row("structural-buckling", ctx, got, need, subject, how)


def _yield_row(ctx: _Ctx, moment_nm: float, z: Qty, stock: _Stock, who: str, how: str) -> RuleRow:
    res = structural.beam_bending_stress(Quantity(moment_nm, "N*m"), z, stock.yield_strength)
    got = res.yield_factor or math.inf
    need = joints.factor_of_safety("yield", ctx.kind)
    stress = fmt(res.stress.to("MPa"), "MPa")
    subject = f"{who} carries {stress} of bending stress ({sig(moment_nm)} N·m)"
    detail = f"{how}; {res.formula}; {res.source}; {stock.ref}"
    return _factor_row("structural-yield", ctx, got, need, subject, detail)


# --- a frame with a top -------------------------------------------------------------------


def _find_top(pieces: list[Any], frame: Any) -> Any | None:
    boards = [p for p in pieces if p is not frame and p.kit in ("block", "plate", "panel")]
    boards = [p for p in boards if p.size[2] <= 0.25 * min(p.size[0], p.size[1])]
    return max(boards, key=lambda p: p.size[0] * p.size[1], default=None)


def _table(ctx: _Ctx, frame: Any) -> list[RuleRow]:
    rows: list[RuleRow] = []
    pieces = ctx.massing.pieces
    point, spread, edge = (ctx.loads[k] for k in ("point_load", "distributed_load", "edge_load"))
    leg = frame.args.member.size
    ax = 0 if frame.size[0] >= frame.size[1] else 1  # the span runs along the long side
    span = Quantity(frame.size[ax] - leg, "mm")
    m = frame.args.member
    sec, stock = _tube(str(m.profile), m.size, m.wall, getattr(m, "size2", None)), _stock(frame)
    top = _find_top(pieces, frame)
    if point is not None or spread is not None:
        topstock = _stock(top) if top is not None else "the massing has no flat top board"
        if isinstance(topstock, str):
            rows += [_skip("structural-deflection", topstock), _skip("structural-yield", topstock)]
        else:
            rows += _top_rows(ctx, top, topstock, span, 1 - ax, _rail_stiffness(frame, stock))
    if ctx.massing.without_material:
        msg = "some rough shapes have no material, so no weight"
        rows.append(_skip("structural-buckling", msg))
    elif isinstance(sec, str):
        rows.append(_skip("structural-buckling", sec))
    elif isinstance(stock, str):
        rows.append(_skip("structural-buckling", stock))
    else:
        total_weight = Quantity((ctx.massing.mass or 0.0) * 9.80665, "N")
        leg_weight = total_weight / 4
        sp4 = spread / 4 if spread is not None else None
        applied = sum((q for q in (point, sp4, edge) if q is not None), Quantity(0.0, "N"))
        vertical = leg_weight + applied
        rows.append(_column_row(ctx, sec, stock, frame.size[2], vertical, LEG_ENDS, "one leg"))
    if edge is not None:
        rows.append(_tip_row(ctx, frame, edge, 1 - ax, leg))
    return rows


def _rail_stiffness(frame: Any, stock: _Stock | str) -> Qty | None:
    """E·I of the two long top rails, which share the top's span, else None (S-206)."""
    if isinstance(stock, str) or not frame.args.top_rails:
        return None
    m = getattr(frame.args, "rail_member", None) or frame.args.member
    sec = _tube(str(m.profile), m.size, m.wall, getattr(m, "size2", None))
    return None if isinstance(sec, str) else 2 * stock.E * sec.Ix


def _top_rows(
    ctx: _Ctx, top: Any, stock: _Stock, span: Qty, across: int, rails: Qty | None
) -> list[RuleRow]:
    point, spread = ctx.loads["point_load"], ctx.loads["distributed_load"]
    section = structural.rect_section(_mm(top.size[across]), _mm(top.size[2]))
    ei_top = stock.E * section.I
    share = 1.0 if rails is None else float((ei_top / (ei_top + rails)).to("").magnitude)
    stiff = section.I / share  # the top's I scaled so E·I is the top and the rails together
    parts: list[Any] = []
    moment = 0.0
    span_m = float(span.to("m").magnitude)
    if point is not None:
        parts.append(structural.beam_deflection_simply_supported(point, span, stock.E, stiff))
        moment += (
            float(point.to("N").magnitude) * span_m / 4
        )  # Roark T8.1 case 2a (simply supported, centre load) [verify]: F·L/4
    # Self weight: the top's own weight is added as a uniform load on the span (S-211)
    top_weight_n = float(top.mass or 0.0) * 9.80665
    top_weight = Quantity(top_weight_n, "N")
    uniform_load = top_weight + (spread if spread is not None else Quantity(0.0, "N"))
    parts.append(
        structural.beam_deflection_simply_supported(uniform_load, span, stock.E, stiff, "uniform")
    )
    moment += (
        float(uniform_load.to("N").magnitude) * span_m / 8
    )  # Roark T8.1 case 2e (simply supported, uniform load) [verify]: W·L/8
    d = sum((p.deflection.to("mm") for p in parts), _mm(0.0))
    shared = (
        "" if rails is None else ", with the two long top rails sharing it (E·I of top + rails)"
    )
    weight_desc = f", self weight {fmt(top_weight, 'N')}"
    if spread is not None:
        weight_desc += f" + distributed load {fmt(spread, 'N')}"
    how = (
        f"{' + '.join(p.formula for p in parts)} on the {_len(_mm(top.size[across]))} wide, "
        f"{_len(_mm(top.size[2]))} thick top over a {_len(span)} span between its supports"
        f"{shared}{weight_desc}; {parts[0].source}; {stock.ref}"
    )
    yield_desc = (
        "M = F·L/4 + W·L/8, the top's share" if point is not None else "M = W·L/8, the top's share"
    )
    return [
        _deflection_row(ctx, d, "the top sags", how),
        _yield_row(ctx, moment * share, section.Z, stock, "the top", yield_desc),
    ]


def _tip_row(ctx: _Ctx, frame: Any, edge: Qty, axis: int, leg: float) -> RuleRow:
    offset = EDGE_OFFSET.quantity(ctx.card)
    if offset is None:
        return _skip("structural-tip-over", "give how far beyond the support the edge load acts")
    pieces = ctx.massing.pieces
    if ctx.massing.without_material:
        return _skip("structural-tip-over", "some rough shapes have no material, so no weight")
    masses = [(p.mass or 0.0, (p.bbox_min[axis] + p.bbox_max[axis]) / 2) for p in pieces]
    total = sum(m for m, _ in masses)
    cg = sum(m * c for m, c in masses) / total
    lo, hi = frame.bbox_min[axis] + leg / 2, frame.bbox_max[axis] - leg / 2
    cg_x = min(cg - lo, hi - cg)  # the nearer leg line is the one it tips over
    res = structural.tip_over_safety_factor(
        Quantity(total, "kg"), Quantity(max(cg_x, 0.0), "mm"), edge, offset
    )
    need = joints.factor_of_safety("tip_over", "edge_load")
    subject = (
        f"{fmt(Quantity(total, 'kg'), 'kg')} (the rough shapes' weight) with its centre "
        f"{_len(Quantity(cg_x, 'mm'))} inside the leg line, under {fmt(edge, 'N')} acting "
        f"{_len(offset)} beyond it"
    )
    how = f"{res.formula}; {res.source}"
    return _factor_row(
        "structural-tip-over", ctx, res.safety_factor, need, subject, how, "edge load"
    )


# --- a column with an arm -----------------------------------------------------------------


#: What the screen says of a shape that is not one column with one arm (gate I wording).
NOT_MODELLED = (
    "this card's shape is not one the structural screen models: it takes one column and one arm "
    "of the same material"
)


def _column_and_arm(pieces: list[Any]) -> tuple[Any, Any] | str | None:
    """The one column and its arm, else the owner's reason this shape is not one (S-233).

    A second upright at least half as tall as the first makes a portal or a gantry, whose
    stiffness is the two uprights and their bridges together: reading its tallest upright and
    some bridge as a cantilever gave a wrong sag, or a negative column height (B-0235). An
    arm is a piece above the column's foot; a foot or base under it carries nothing out.
    """
    flat = [p for p in pieces if p.kit in ("tube", "block")]
    cols = [p for p in flat if p.size[2] >= 2 * max(p.size[0], p.size[1])]
    if not cols:
        return None
    col = max(cols, key=lambda p: p.size[2])
    if any(p is not col and p.size[2] >= 0.5 * col.size[2] for p in cols):
        return (
            f"{NOT_MODELLED}; this card has two upright columns (a gantry or a portal), so its "
            "sag is unknown here"
        )
    cx = [(col.bbox_min[i] + col.bbox_max[i]) / 2 for i in (0, 1)]

    def reach(p: Any) -> float:
        a = 0 if p.size[0] >= p.size[1] else 1
        return float(max(abs(p.bbox_max[a] - cx[a]), abs(p.bbox_min[a] - cx[a])))

    arms = [
        p
        for p in flat
        if p is not col
        and max(p.size[0], p.size[1]) >= p.size[2]
        and (p.bbox_min[2] + p.bbox_max[2]) / 2 > col.bbox_min[2]
    ]
    return (col, max(arms, key=reach)) if arms else None


def _cantilever(ctx: _Ctx, col: Any, arm: Any) -> list[RuleRow]:
    tip, cstock, astock = ctx.loads["point_load"], _stock(col), _stock(arm)
    if tip is None:
        return [_skip("structural-deflection", "give the load at the arm's tip (point_load)")]
    if isinstance(cstock, str):
        return [_skip("structural-deflection", cstock)]
    if isinstance(astock, str):
        return [_skip("structural-deflection", astock)]
    if col.material != arm.material:
        return [_skip("structural-deflection", NOT_MODELLED)]
    ax = 0 if arm.size[0] >= arm.size[1] else 1
    centre = (col.bbox_min[ax] + col.bbox_max[ax]) / 2
    reach = Quantity(max(abs(arm.bbox_max[ax] - centre), abs(arm.bbox_min[ax] - centre)), "mm")
    height = Quantity((arm.bbox_min[2] + arm.bbox_max[2]) / 2 - col.bbox_min[2], "mm")
    s_col, s_arm = _piece_section(col, ax, 1 - ax), _piece_section(arm, 2, 1 - ax)
    if isinstance(s_col, str):
        return [_skip("structural-deflection", s_col)]
    if isinstance(s_arm, str):
        return [_skip("structural-deflection", s_arm)]
    if float(height.magnitude) <= 0 or float(reach.magnitude) <= 0:
        return [_skip("structural-deflection", NOT_MODELLED)]
    try:
        res = structural.beam_deflection_cantilever(
            tip, reach, height, cstock.E, s_arm.Ix, s_col.Ix
        )
    except ValueError:  # a shape the formula cannot take is a skip, never a traceback (S-233)
        return [_skip("structural-deflection", NOT_MODELLED)]
    how = (
        f"{res.formula} for an arm reaching {_len(reach)} from the column's centre line, "
        f"{_len(height)} above its foot; {res.source}; {cstock.ref}"
    )
    z = min(s_col.Zx, s_arm.Zx)
    return [
        _deflection_row(ctx, res.deflection.to("mm"), "the arm's tip deflects", how),
        _yield_row(
            ctx, float((tip * reach).to("N*m").magnitude), z, cstock, "the column", "M = F·reach"
        ),
        _column_row(ctx, s_col, cstock, col.size[2], tip, COLUMN_ENDS, "the column"),
    ]


@reads(*FIELDS, phase="check")
def run(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """Sag, yield, buckling and tip-over of the card's frame and top, or its column and arm."""
    loads = {f.key: f.quantity(card) for f in (POINT_LOAD, DISTRIBUTED_LOAD, EDGE_LOAD)}
    if all(q is None for q in loads.values()):
        return []  # no load on the card: nothing to check, no row
    for key, q in loads.items():
        if q is not None:
            values.given.add(key, q, fmt(q, "N"), "on the card", f"site.{key}")
    cycles = CYCLES.quantity(card)
    cyclic = cycles is not None and float(cycles.magnitude) > 0
    if cyclic:
        values.notes.append(
            "the card gives a cycle count, so the cyclic safety factors apply; the endurance "
            "check itself is not part of this screen"
        )
    kind = "cyclic" if cyclic else "static"
    ctx = _Ctx(card, massing, values, loads, MAX_DEFLECTION.quantity(card), kind)
    pieces = [] if massing is None else massing.pieces
    frame = next((p for p in pieces if p.kit == "frame"), None)
    if frame is not None:
        return _table(ctx, frame)
    pair = _column_and_arm(pieces)
    if isinstance(pair, str):
        return [_skip("structural-deflection", pair)]
    if pair is not None:
        return _cantilever(ctx, *pair)
    why = (
        "the rough shapes show no frame with a top or column with an arm: nothing carries the load"
    )
    return [_skip("structural-support", why)]


STRUCTURAL = Screen("structural", run, title="Stays up under load")

__all__ = ["FIELDS", "STRUCTURAL"]
