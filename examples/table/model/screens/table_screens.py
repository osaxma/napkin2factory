"""The table's own napkin-stage screens (F8, F10): what the generic ones leave out.

The generic screens (fits the space, total mass, cost band, lift class, ``structural``) read
the rough shapes, and the ``structural`` one judges the top on its legs, trestle ends or frame,
with the cross member under it (S-235). A table's card needs two things more, and only a table
needs them, so they live here (SPEC.md sections 3 and 4.0):

* **hardware** — every card has a bought-in set: 4 levelling glides and one threaded insert and
  one screw with washer for each fixing of the top (8 on the pine and trestle cards; the apron
  frame card has one per fixing tab, 6). Its mass joins the total mass; its price joins the
  cost band (the cost bands price by weight, so a bought-in set is added to the band
  afterwards, with a row of its own against the budget).
* **mass limit** — ``site.mass_limit`` held against the total mass.
"""

from __future__ import annotations

from typing import Any

from napkin2factory.concepts.screens import TO_CHECK, ScreenValues, fmt, reads
from napkin2factory.concepts.screens.generic import BUDGET, MASS_LIMIT
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


SCREENS = (
    Screen("hardware-mass", hardware_mass, title="Hardware mass"),
    Screen("hardware-cost", hardware_cost, title="Hardware cost"),
    Screen("mass-limit", mass_limit, title="Mass limit"),
)
