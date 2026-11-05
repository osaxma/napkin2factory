"""The generic ``structural`` screen: does a napkin card stand up under its loads? (W4, S-206).

Loads and limits are ``site`` fields of the card (the package's own words); supports and sections
are read from the card's massing, never guessed. Two kinds of shape:

* a **top on a stand** (:mod:`~napkin2factory.concepts.screens.structural_top`): a frame (with
  rails or bare legs), bare legs of tubes or blocks, or trestle ends under the widest flat board,
  with an optional cross member across a frame. Checks: sag and yield of the top, the cross
  member's yield, buckling of one leg, tip-over under the edge load.
* a **column with an arm** (``tube`` or ``block`` calls, no frame): the arm reaches out from
  the column's centre line. Checks: tip deflection (arm bending plus column rotation), yield
  at the column foot, buckling of the column.

A check whose inputs are not on the card or in the massing is a row that says which one is
missing and that it was not run. Factors compare against ``calckit.joints.factor_of_safety``
(load kind ``cyclic`` once the card gives ``site.cycles``, else ``static``; tip-over uses
the edge-load row). The screen runs only when the card gives a point, distributed or edge load.
Fatigue and the rails' own stress are not checked here. The values the screen adds to a card's
screening are listed in docs/napkin.md ("The structural screen").
"""

from __future__ import annotations

from typing import Any

from napkin2factory.calckit import structural
from napkin2factory.concepts.screens.base import ScreenValues, fmt, reads
from napkin2factory.concepts.screens.structural_base import (
    COLUMN_ENDS,
    CYCLES,
    DISTRIBUTED_LOAD,
    EDGE_LOAD,
    FIELDS,
    MAX_DEFLECTION,
    POINT_LOAD,
    Ctx,
    column_row,
    deflection_row,
    length_text,
    piece_section,
    skip_row,
    stock_of,
    yield_row,
)
from napkin2factory.concepts.screens.structural_top import judge
from napkin2factory.core.domain import Screen
from napkin2factory.core.model.concepts import ConceptCard, RuleRow
from napkin2factory.core.units import Quantity

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


def _cantilever(ctx: Ctx, col: Any, arm: Any) -> list[RuleRow]:
    tip, cstock, astock = ctx.loads["point_load"], stock_of(col), stock_of(arm)
    if tip is None:
        return [skip_row("structural-deflection", "give the load at the arm's tip (point_load)")]
    if isinstance(cstock, str):
        return [skip_row("structural-deflection", cstock)]
    if isinstance(astock, str):
        return [skip_row("structural-deflection", astock)]
    if col.material != arm.material:
        return [skip_row("structural-deflection", NOT_MODELLED)]
    ax = 0 if arm.size[0] >= arm.size[1] else 1
    centre = (col.bbox_min[ax] + col.bbox_max[ax]) / 2
    reach = Quantity(max(abs(arm.bbox_max[ax] - centre), abs(arm.bbox_min[ax] - centre)), "mm")
    height = Quantity((arm.bbox_min[2] + arm.bbox_max[2]) / 2 - col.bbox_min[2], "mm")
    s_col, s_arm = piece_section(col, ax, 1 - ax), piece_section(arm, 2, 1 - ax)
    if isinstance(s_col, str):
        return [skip_row("structural-deflection", s_col)]
    if isinstance(s_arm, str):
        return [skip_row("structural-deflection", s_arm)]
    if float(height.magnitude) <= 0 or float(reach.magnitude) <= 0:
        return [skip_row("structural-deflection", NOT_MODELLED)]
    try:
        res = structural.beam_deflection_cantilever(
            tip, reach, height, cstock.E, s_arm.Ix, s_col.Ix
        )
    except ValueError:  # a shape the formula cannot take is a skip, never a traceback (S-233)
        return [skip_row("structural-deflection", NOT_MODELLED)]
    how = (
        f"{res.formula} for an arm reaching {length_text(reach)} from the column's centre line, "
        f"{length_text(height)} above its foot; {res.source}; {cstock.ref}"
    )
    z = min(s_col.Zx, s_arm.Zx)
    return [
        deflection_row(ctx, res.deflection.to("mm"), "the arm's tip deflects", how),
        yield_row(
            ctx, float((tip * reach).to("N*m").magnitude), z, cstock, "the column", "M = F·reach"
        ),
        column_row(ctx, s_col, cstock, col.size[2], tip, COLUMN_ENDS, "the column"),
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
    ctx = Ctx(card, massing, values, loads, MAX_DEFLECTION.quantity(card), kind)
    rows = judge(ctx)
    if rows is not None:
        return rows
    pieces = [] if massing is None else massing.pieces
    pair = _column_and_arm(pieces)
    if isinstance(pair, str):
        return [skip_row("structural-deflection", pair)]
    if pair is not None:
        return _cantilever(ctx, *pair)
    why = (
        "the rough shapes show no frame with a top or column with an arm: nothing carries the load"
    )
    return [skip_row("structural-support", why)]


STRUCTURAL = Screen("structural", run, title="Stays up under load")

__all__ = ["FIELDS", "STRUCTURAL"]
