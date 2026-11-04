"""The table's own napkin-stage screens (F8, F10): what the generic ones leave out.

The generic screens (fits the space, total mass, cost band, lift class, ``structural``) read
the rough shapes. A table's card needs three things more, and only a table needs them, so they
live here (SPEC.md sections 3 and 4.0):

* **hardware** — every card has a bought-in set: 4 levelling glides and one threaded insert and
  one screw with washer for each fixing of the top (8 on the pine and trestle cards; the apron
  frame card has one per fixing tab, 6). Its mass joins the total mass; its price joins the
  cost band (the cost bands price by weight, so a bought-in set is added to the band
  afterwards, with a row of its own against the budget).
* **cross rail** — the apron frame card has a tube under the middle of the top, welded between
  the long rails. The oak top is stiff along its grain and soft across it, so the load at the
  middle reaches the long rails through that tube, and the tube's dip adds to the top's sag
  (SPEC.md section 4.1; the generic screen has no such member).
* **mass limit** — ``site.mass_limit`` held against the total mass.
* **supports** — the generic ``structural`` screen understands a frame with a top and a column
  with an arm. The frame kit refuses bare legs (a frame is a weldment with rails), and a trestle
  (two plate ends carrying a top) is no frame, so the cards that stand on four corner legs or on
  two trestle ends are judged here: the top's sag, its stress and the tip-over factor come from
  the same calc kit functions the generic screen uses, so the three cards are judged by the same
  physics (S-221).
"""

from __future__ import annotations

from typing import Any

from napkin2factory.calckit import joints, structural
from napkin2factory.concepts.screens import TO_CHECK, ScreenValues, fmt, reads
from napkin2factory.concepts.screens.base import sig
from napkin2factory.concepts.screens.generic import BUDGET, MASS_LIMIT
from napkin2factory.concepts.screens.structural import (
    EDGE_LOAD,
    EDGE_OFFSET,
    MAX_DEFLECTION,
    POINT_LOAD,
)
from napkin2factory.core.domain import Screen
from napkin2factory.core.model.concepts import ConceptCard, RuleRow
from napkin2factory.core.units import Quantity

Qty = Any

#: The bought-in set of a card: (what, kg each, USD each). SPEC.md section 4.0, "the spec's
#: estimates, US, 2026-11", still [verify] against a supplier catalogue (S-221).
GLIDE = ("levelling glide", 0.080, 4.00)
INSERT = ("M8 threaded insert", 0.010, 1.50)
SCREW = ("M8 screw with washer", 0.020, 1.00)
#: Fixings of the top on a card with no frame tabs to count (the pine and trestle cards).
DEFAULT_FIXINGS = 8
HARDWARE_REF = "SPEC.md section 4.0 hardware set [verify]"


def fixings(card: ConceptCard) -> int:
    """Fixings of the top: one per mounting tab of the card's frame, else 8 (SPEC.md 4.0, 3.4)."""
    for call in card.massing:
        if call.kit == "frame" and call.args.get("mounting_tabs"):
            return len(call.args["mounting_tabs"])
    return DEFAULT_FIXINGS


def hardware(card: ConceptCard) -> tuple[float, float, str]:
    """Mass (kg), price (USD) and words of a card's hardware: 4 glides, n inserts, n screws."""
    n = fixings(card)
    kg = GLIDE[1] * 4 + (INSERT[1] + SCREW[1]) * n
    usd = GLIDE[2] * 4 + (INSERT[2] + SCREW[2]) * n
    return kg, usd, f"the hardware set (4 glides, {n} inserts, {n} screws)"


G = 9.80665  # m/s^2, the value calckit.structural uses


def _mm(q: Qty) -> str:
    """A length with three significant figures (``fmt`` rounds a length to whole millimetres)."""
    return f"{sig(float(q.to('mm').magnitude))} mm"


@reads(phase="estimate")
def hardware_mass(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """Add the hardware set's mass to the rough shapes' mass (the total-mass screen reads it).

    The glide stems drawn in the picture (pieces named ``glide-*``, so the table stands at its
    real height) are part of the set: they are weighed once, as shapes.
    """
    drawn = sum(
        p.mass or 0.0
        for p in (massing.pieces if massing is not None else [])
        if p.name.startswith("glide")
    )
    set_kg, _, words = hardware(card)
    kg = Quantity(set_kg - drawn, "kg")
    values.mass_items.append((kg, words, HARDWARE_REF))
    return []


@reads(BUDGET, phase="check")
def hardware_cost(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """Add the hardware set's price to the cost band and hold the result against the budget."""
    low, high = values.estimate.raw.get("cost_low"), values.estimate.raw.get("cost_high")
    if low is None or high is None:
        return []
    if not low.check("[currency]"):  # the cost bands are not in USD (an EU product, gate I B2)
        values.notes.append(
            "the hardware set is priced in USD and the cost bands are in another currency, so "
            "it is not added (nothing is converted)"
        )
        return []
    _, set_usd, set_words = hardware(card)
    add = Quantity(set_usd, "USD")
    low, high = low + add, high + add
    words = f"rough cost of the rough shapes from the cost bands, plus {set_words}; {TO_CHECK}"
    ref = f"mass_cost.cost_estimate + {HARDWARE_REF}"
    values.estimate.add("cost_low", low, fmt(low, "USD"), words, ref)
    values.estimate.add("cost_high", high, fmt(high, "USD"), words, ref)
    budget = BUDGET.quantity(card)
    if budget is None:
        return []
    lo, hi, bud = fmt(low, "USD"), fmt(high, "USD"), fmt(budget, "USD")
    if high <= budget:
        status, msg = (
            "pass",
            f"with the hardware the cost, {lo} to {hi}, is within the {bud} budget",
        )
    elif low > budget:
        status = "fail"
        msg = f"with the hardware even the low end of the cost, {lo}, is over the {bud} budget"
    else:
        status, msg = (
            "warn",
            f"with the hardware the {bud} budget sits inside the cost band, {lo} to {hi}",
        )
    return [
        RuleRow(
            id="hardware-cost-vs-budget",
            title="Within the budget with the hardware",
            severity="warn" if status == "warn" else "fail",
            status=status,  # type: ignore[arg-type]
            message=msg,
            relies_on=["given", "estimate"],
        )
    ]


@reads(MASS_LIMIT, phase="check")
def mass_limit(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """The total mass (with the hardware) held against ``site.mass_limit``."""
    limit = MASS_LIMIT.quantity(card)
    mass = values.estimate.raw.get("total_mass") or values.computed.raw.get("mass")
    if limit is None or mass is None:
        return []
    values.given.add("mass_limit", limit, fmt(limit, "kg"), "on the card", "site.mass_limit")
    got, lim = fmt(mass, "kg"), fmt(limit, "kg")
    ok = float(mass.to("kg").magnitude) <= float(limit.to("kg").magnitude)
    msg = f"the table weighs {got} (estimate), " + (
        f"within the {lim} limit on the card" if ok else f"over the {lim} limit on the card"
    )
    return [
        RuleRow(
            id="mass-limit",
            title="Total mass within the limit",
            severity="fail",
            status="pass" if ok else "fail",
            message=msg,
            relies_on=["given", "estimate"],
        )
    ]


def _stock(piece: Any) -> tuple[Qty, Qty, str] | str:
    """E, yield strength and source of a piece's material, else the reason it has none."""
    from napkin2factory.geometry.materials import material_row

    row = material_row(piece.material) if piece.material else None
    if row is None or row.get("youngs_modulus") is None or row.get("yield_strength") is None:
        return f"no stiffness and strength on file for {piece.material}"
    return (
        Quantity(float(row["youngs_modulus"]), "Pa"),
        Quantity(float(row["yield_strength"]), "Pa"),
        f"{row['name']} in calckit/data/materials.yaml [verify]",
    )


def _row(rid: str, title: str, ok: bool, msg: str) -> RuleRow:
    return RuleRow(
        id=rid,
        title=title,
        severity="fail",
        status="pass" if ok else "fail",
        message=msg,
        relies_on=["computed"],
    )


@reads(POINT_LOAD, EDGE_LOAD, EDGE_OFFSET, MAX_DEFLECTION, phase="check")
def supports(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """A top on legs or trestle ends (no frame): its sag and stress between them, and tip-over.

    The supports are the pieces named ``leg-*`` or ``upright-*`` and the top is the piece named
    ``top``. The top is a simply supported beam between the supports' centre lines along its long
    side (Roark Table 8.1, cases 1d and 1e, its own weight a uniform load, as the generic screen
    does for a frame). Tip-over is about the glide line, ``edge_offset`` in from the top's edge,
    with the table's whole weight (rough shapes and hardware) at the plan centre. A card with a
    frame is the generic screen's and gives no rows here.
    """
    if massing is None or any(p.kit == "frame" for p in massing.pieces):
        return []
    top = massing.piece("top")
    ends = [p for p in massing.pieces if p.name.startswith(("leg", "upright"))]
    point, edge, offset = (
        POINT_LOAD.quantity(card),
        EDGE_LOAD.quantity(card),
        EDGE_OFFSET.quantity(card),
    )
    limit = MAX_DEFLECTION.quantity(card)
    if top is None or len(ends) < 2 or point is None:
        return []
    stock = _stock(top)
    if isinstance(stock, str):
        return []
    young, yield_strength, ref = stock
    ax = 0 if top.size[0] >= top.size[1] else 1
    centres = [(p.bbox_min[ax] + p.bbox_max[ax]) / 2 for p in ends]
    span = Quantity(max(centres) - min(centres), "mm")
    section = structural.rect_section(Quantity(top.size[1 - ax], "mm"), Quantity(top.size[2], "mm"))
    weight = Quantity((top.mass or 0.0) * G, "N")
    sag_p = structural.beam_deflection_simply_supported(point, span, young, section.I)
    sag_w = structural.beam_deflection_simply_supported(weight, span, young, section.I, "uniform")
    sag = (sag_p.deflection + sag_w.deflection).to("mm")
    how = (
        f"{sag_p.formula} + {sag_w.formula} on the {sig(top.size[1 - ax])} mm wide, "
        f"{sig(top.size[2])} mm thick top over a {sig(float(span.magnitude))} mm span between the "
        f"supports, self weight {fmt(weight, 'N')}; {sag_p.source}; {ref}"
    )
    values.computed.add("deflection", sag, _mm(sag), "computed from the card and the massing", how)
    rows: list[RuleRow] = []
    if limit is not None:
        need = joints.factor_of_safety("deflection", "static")
        margin = float((limit / sag).to("").magnitude)
        ok = margin >= need
        rows.append(
            _row(
                "table-sag",
                "Sag stays within the limit",
                ok,
                f"the top sags {_mm(sag)} (computed), {'within' if ok else 'beyond'} the "
                f"{_mm(limit)} limit on the card (limit ÷ sag is {sig(margin)}, "
                f"{sig(need)} needed, static case) — {how}",
            )
        )
    moment = float(point.to("N").magnitude) * float(span.to("m").magnitude) / 4
    moment += float(weight.to("N").magnitude) * float(span.to("m").magnitude) / 8
    res = structural.beam_bending_stress(Quantity(moment, "N*m"), section.Z, yield_strength)
    need = joints.factor_of_safety("yield", "static")
    got = res.yield_factor or float("inf")
    values.computed.add(
        "yield_factor", got, sig(got), "computed from the card and the massing", res.formula
    )
    rows.append(
        _row(
            "table-yield",
            "Stress stays under yield",
            got >= need,
            f"the top carries {fmt(res.stress.to('MPa'), 'MPa')} of bending stress "
            f"({sig(moment)} N·m): factor {sig(got)} (computed), "
            f"{'at least' if got >= need else 'below'} the {sig(need)} needed — "
            f"M = F·L/4 + W·L/8; {res.formula}; {res.source}; {ref}",
        )
    )
    if edge is not None and offset is not None and massing.mass is not None:
        across = 1 - ax  # the glide line runs along the long side; the edge load acts across it
        kg = massing.mass + sum(float(q.to("kg").magnitude) for q, _, _ in values.mass_items)
        centre = sum(
            (p.mass or 0.0) * (p.bbox_min[across] + p.bbox_max[across]) / 2 for p in massing.pieces
        )
        centre /= massing.mass
        line = (top.bbox_max[across] - top.bbox_min[across]) / 2 - float(offset.to("mm").magnitude)
        arm = Quantity(line - abs(centre), "mm")
        tip = structural.tip_over_safety_factor(Quantity(kg, "kg"), arm, edge, offset)
        need = joints.factor_of_safety("tip_over", "edge_load")
        values.computed.add(
            "tip_over_factor",
            tip.safety_factor,
            sig(tip.safety_factor),
            "computed from the card and the massing",
            tip.formula,
        )
        rows.append(
            _row(
                "table-tip-over",
                "It does not tip over",
                tip.safety_factor >= need,
                f"{fmt(Quantity(kg, 'kg'), 'kg')} (rough shapes and hardware) with its centre "
                f"{_mm(arm)} inside the glide line, under {fmt(edge, 'N')} acting "
                f"{_mm(offset)} beyond it: factor {sig(tip.safety_factor)} (computed), "
                f"{'at least' if tip.safety_factor >= need else 'below'} the {sig(need)} needed "
                f"(edge load case) — {tip.formula}; {tip.source}",
            )
        )
    return rows


@reads(POINT_LOAD, MAX_DEFLECTION, phase="check")
def cross_rail(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """The tube under the middle of the top: its dip adds to the top's sag, and its own stress.

    The piece named ``cross-rail`` is a square tube between the frame's two long rails; the
    centre load stands over it and it carries the whole load to them as a simply supported beam
    (Roark Table 8.1, case 1e). The oak on top is given no share. The generic screen's sag (the
    top and the long rails along the length) is kept as it is and the dip is added to it, so
    both figures stay in the card (SPEC.md section 4.1). A card without that piece gives no rows.
    """
    if massing is None:
        return []
    cross, frame = (
        massing.piece("cross-rail"),
        next((p for p in massing.pieces if p.kit == "frame"), None),
    )
    point = POINT_LOAD.quantity(card)
    along = values.computed.raw.get("deflection")
    if cross is None or frame is None or point is None or along is None:
        return []
    stock = _stock(cross)
    if isinstance(stock, str):
        return []
    young, yield_strength, ref = stock
    ax = 0 if frame.size[0] >= frame.size[1] else 1
    span = Quantity(frame.size[1 - ax] - frame.args.member.size, "mm")  # long rail to long rail
    tube = structural.rect_tube_section(
        Quantity(cross.args.size, "mm"),
        Quantity(cross.args.size, "mm"),
        Quantity(cross.args.wall, "mm"),
    )
    dip = structural.beam_deflection_simply_supported(point, span, young, tube.Ix)
    dip_mm = dip.deflection.to("mm")
    total = (along + dip_mm).to("mm")
    how = (
        f"the top's sag along the length {_mm(along)} + the cross rail's dip {_mm(dip_mm)}: "
        f"{dip.formula} on the {sig(cross.args.size)} mm square tube over the {_mm(span)} between "
        f"the long rails; {dip.source}; {ref}"
    )
    values.computed.add(
        "cross_rail_dip", dip_mm, _mm(dip_mm), "computed from the card and the massing", how
    )
    values.computed.add(
        "sag_with_cross_rail", total, _mm(total), "computed from the card and the massing", how
    )
    rows: list[RuleRow] = []
    limit = MAX_DEFLECTION.quantity(card)
    if limit is not None:
        need = joints.factor_of_safety("deflection", "static")
        margin = float((limit / total).to("").magnitude)
        ok = margin >= need
        rows.append(
            _row(
                "table-cross-rail",
                "The cross rail carries the centre load",
                ok,
                f"with the cross rail's dip the top sags {_mm(total)} in all (computed), "
                f"{'within' if ok else 'beyond'} the {_mm(limit)} limit on the card "
                f"(limit ÷ sag is {sig(margin)}, {sig(need)} needed, static case) — {how}",
            )
        )
    moment = Quantity(float(point.to("N").magnitude) * float(span.to("m").magnitude) / 4, "N*m")
    res = structural.beam_bending_stress(moment, tube.Zx, yield_strength)
    need = joints.factor_of_safety("yield", "static")
    got = res.yield_factor or float("inf")
    rows.append(
        _row(
            "table-cross-rail-yield",
            "The cross rail stays under yield",
            got >= need,
            f"the cross rail carries {fmt(res.stress.to('MPa'), 'MPa')} of bending stress "
            f"({sig(float(moment.magnitude))} N·m): factor {sig(got)} (computed), "
            f"{'at least' if got >= need else 'below'} the {sig(need)} needed — M = F·L/4; "
            f"{res.formula}; {res.source}; {ref}",
        )
    )
    return rows


SCREENS = (
    Screen("hardware-mass", hardware_mass, title="Hardware mass"),
    Screen("hardware-cost", hardware_cost, title="Hardware cost"),
    Screen("mass-limit", mass_limit, title="Mass limit"),
    Screen("supports", supports, title="A top on legs or trestle ends stands up"),
    Screen("cross-rail", cross_rail, title="The cross rail carries the centre load"),
)
