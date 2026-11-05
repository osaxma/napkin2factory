"""The test stand's own napkin screens: what the package's generic screens do not do yet (F10).

Two small things, each computed from the card and the numbers of SPEC.md, none a constant
standing in for a result:

* the bought-in parts, which a card cannot draw (a stepper actuator is no rough shape): their
  mass and their cost per item join the rough shapes' (SPEC section 4.6 and 4.7);
* a failing row when the total mass is over ``site.mass_limit``: the generic lift-class row
  only warns.

What is bought by the metre (the extruded frame) or the square metre (the routed
polycarbonate) is priced by the package's own cost screen (B-0211, S-230).
"""

from __future__ import annotations

from typing import Any

from napkin2factory.concepts.screens import fmt, reads
from napkin2factory.concepts.screens.generic import MASS_LIMIT
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


@reads(MASS_LIMIT, phase="total")
def mass_limit(card: Any, massing: Any, values: Any) -> list[RuleRow]:
    """Judge the total mass against ``site.mass_limit``."""
    rows: list[RuleRow] = []
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


SCREENS = (
    Screen("bought-in", bought_in, title="The bought-in parts"),
    Screen("mass-limit", mass_limit, title="Total mass within the limit"),
)
