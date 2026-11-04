"""The test stand's own napkin screens: what the package's generic screens do not do yet (F10).

Three small things, each computed from the card and the numbers of SPEC.md, none a constant
standing in for a result:

* the bought-in parts, which a card cannot draw (a stepper actuator is no rough shape): their
  mass and their cost per item join the rough shapes' (SPEC section 4.6 and 4.7);
* the cost of what is bought by the metre (the extruded frame) or by the square metre (the
  routed polycarbonate): the package's cost screen prices per kilogram and per item only, so
  those pieces are priced here with the same band table (B-0211);
* a failing row when the total mass is over ``site.mass_limit``: the generic lift-class row
  only warns.
"""

from __future__ import annotations

from typing import Any

from napkin2factory.calckit import mass_cost
from napkin2factory.concepts.screens import fmt, reads
from napkin2factory.concepts.screens.generic import BUDGET, MASS_LIMIT, cost_region
from napkin2factory.core.domain import Screen
from napkin2factory.core.model.concepts import RuleRow
from napkin2factory.core.units import Quantity

#: The bought-in parts: (name, mass in kg, priced as a controls item). SPEC.md section 4.6
#: gives each mass as an allowance [verify against the chosen catalogue part]; section 4.7
#: prices the first nine as ``cots-controls`` items and leaves the hinges, feet and
#: fasteners out (no band on file).
BOUGHT_IN: tuple[tuple[str, float, bool], ...] = (
    ("actuator", 4.00, True),
    ("load cell", 0.35, True),
    ("power supply", 0.60, True),
    ("controller", 0.40, True),
    ("E-stop", 0.15, True),
    ("upper limit switch", 0.05, True),
    ("lower limit switch", 0.05, True),
    ("mains inlet", 0.08, True),
    ("guard interlock", 0.15, True),
    ("hinges", 0.10, False),
    ("feet", 0.10, False),
    ("fasteners, plugs and wiring", 0.60, False),
)


@reads(phase="estimate")
def bought_in(card: Any, massing: Any, values: Any) -> list[RuleRow]:
    """Add the bought-in parts' mass and the cost of the priced ones (SPEC.md 4.6, 4.7)."""
    total = sum(kg for _, kg, _ in BOUGHT_IN)
    values.mass_items.append(
        (Quantity(total, "kg"), "the bought-in parts (an allowance each)", "SPEC.md 4.6 [verify]")
    )
    values.cost_items += [(name, "cots-controls", None) for name, _, priced in BOUGHT_IN if priced]
    return []


def _extent(piece: Any) -> tuple[float, float]:
    """The longest side, and the area of the biggest face, of a piece's bounding box (mm, mm2)."""
    a, b, c = sorted(piece.size, reverse=True)
    return a, a * b


@reads(MASS_LIMIT, BUDGET, phase="total")
def by_length_and_area(card: Any, massing: Any, values: Any) -> list[RuleRow]:
    """Price the pieces bought by the metre or the square metre; judge the mass limit."""
    rows: list[RuleRow] = []
    region, _ = cost_region(card, values)  # the card's or the product's region (gate I, B2)
    low = high = 0.0
    priced: list[str] = []
    for piece in [] if massing is None else massing.pieces:
        band = mass_cost.cost_band(piece.process_class, region=region)
        if not band.known or band.unit not in ("per_m", "per_m2"):
            continue
        longest, face = _extent(piece)
        est = mass_cost.cost_estimate(
            piece.process_class,
            length=Quantity(longest, "mm"),
            area=Quantity(face, "mm**2"),
            region=region,
        )
        if est.low is None or est.high is None:
            continue
        low += float(est.low.to("USD").magnitude)
        high += float(est.high.to("USD").magnitude)
        priced.append(piece.name)
    old_low, old_high = values.estimate.raw.get("cost_low"), values.estimate.raw.get("cost_high")
    if old_low is not None and not old_low.check("[currency]"):
        values.notes.append(
            "the pieces bought by the metre or the square metre are priced in USD and the cost "
            "bands are in another currency, so they are not added (nothing is converted)"
        )
        priced = []
    budget = BUDGET.quantity(card)
    if priced and old_low is not None and old_high is not None:
        new_low = old_low + Quantity(low, "USD")
        new_high = old_high + Quantity(high, "USD")
        # the generic cost screen noted these pieces as left out: they are counted below
        values.notes[:] = [n for n in values.notes if not n.startswith("the cost leaves out")]
        values.notes.append(
            "the cost row above counts what the package prices, per kilogram and per item; the "
            f"cost band and the budget row below also count the {', '.join(priced)}, priced here "
            "per metre or per square metre (the package's cost screen does not yet do that)"
        )
        words = (
            f"{values.estimate.out['cost_low'].source}; with the {', '.join(priced)} priced here "
            "per metre or per square metre"
        )
        for name, value in (("cost_low", new_low), ("cost_high", new_high)):
            values.estimate.add(
                name, value, fmt(value, "USD"), words, "mass_cost.cost_estimate [verify]"
            )
        if budget is not None:
            rows.append(_budget_row(new_low, new_high, budget))
    mass = values.estimate.raw.get("total_mass", values.computed.raw.get("mass"))
    limit = MASS_LIMIT.quantity(card)
    if mass is not None and limit is not None:
        over = float(mass.to("kg").magnitude) > float(limit.to("kg").magnitude)
        side = "over" if over else "within"
        words = f"total mass {fmt(mass, 'kg')} (estimate), {side} the {fmt(limit, 'kg')} limit"
        rows.append(
            RuleRow(
                id="mass-limit",
                title="Total mass within the limit",
                severity="fail",
                status="fail" if over else "pass",
                message=words + " on the card",
                relies_on=["given", "estimate"],
            )
        )
    return rows


def _budget_row(low: Any, high: Any, budget: Any) -> RuleRow:
    """The budget held against the completed band.

    Pass when the high end fits, fail when even the low end is over, else a warning: the
    generic rule's own test (S-207).
    """
    lo, hi, bud = (fmt(q, "USD") for q in (low, high, budget))
    title = "Within the budget, counting the frame and the guard"
    if high <= budget:
        status, msg = "pass", f"the cost, {lo} to {hi}, is within the {bud} budget"
    elif low > budget:
        status, msg = "fail", f"even the low end of the cost, {lo}, is over the {bud} budget"
    else:
        status, msg = "warn", f"the {bud} budget sits inside the cost band, {lo} to {hi}"
    severity = "warn" if status == "warn" else "fail"
    return RuleRow(
        id="cost-vs-budget-complete",
        title=title,
        severity=severity,
        status=status,
        message=msg,
        relies_on=["given", "estimate"],
    )


SCREENS = (
    Screen("bought-in", bought_in, title="The bought-in parts"),
    Screen(
        "by-length-and-area", by_length_and_area, title="Cost by the metre and the square metre"
    ),
)
