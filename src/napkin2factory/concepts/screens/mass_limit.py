"""The generic ``mass-limit`` screen: does the card weigh no more than its site allows? (S-233).

``site.mass_limit`` is the heaviest the product may be (a lift a person can make, a shelf, a
vehicle). The row fails when the total mass is over it and warns when it is within
:data:`MARGIN` of it, because the mass is read off rough shapes. It holds the total mass when
a screen added to the rough shapes' (``values.estimate``), else the rough shapes' own mass
(``values.computed``). A product's own screen that writes a ``mass-limit`` row of its own
replaces this one (the runner keeps the later row of an id, S-233).
"""

from __future__ import annotations

from typing import Any

from napkin2factory.concepts.screens.base import CardField, ScreenValues, fmt, reads
from napkin2factory.core.domain import Screen
from napkin2factory.core.model.concepts import ConceptCard, Label, RuleRow

MASS_LIMIT = CardField("site", "mass_limit", "kg", "a mass", "40 kg", "the weight limit")
#: A mass within this share below the limit is amber: the mass is read off rough shapes, so a
#: card that close to the limit may go either way. A screening choice, not an engineering
#: figure (S-233).
MARGIN = 0.10

TITLE = "Total mass within the limit"


@reads(MASS_LIMIT, phase="check")
def mass_limit(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """The total mass (else the rough shapes') held against ``site.mass_limit``."""
    limit = MASS_LIMIT.quantity(card)
    if limit is None:
        return []  # no limit on the card (a wrong kind of number is noted by the runner)
    values.given.add("mass_limit", limit, fmt(limit, "kg"), "on the card", "site.mass_limit")
    mass, label = values.estimate.raw.get("total_mass"), "estimate"
    if mass is None:
        mass, label = values.computed.raw.get("mass"), "computed"
    if mass is None:
        return [
            RuleRow(
                id="mass-limit",
                title=TITLE,
                status="skip",
                message="not run: the rough shapes have no mass; give each a material",
            )
        ]
    got, lim = float(mass.to("kg").magnitude), float(limit.to("kg").magnitude)
    said = f"it weighs {fmt(mass, 'kg')} ({label}), "
    relies: list[Label] = ["given", label]  # type: ignore[list-item]
    lim_text = fmt(limit, "kg")
    if got > lim:
        status, severity, tail = "fail", "fail", f"over the {lim_text} limit on the card"
    elif got >= lim * (1 - MARGIN):
        status, severity = "warn", "warn"
        tail = f"within {MARGIN:.0%} of the {lim_text} limit on the card"
    else:
        status, severity, tail = "pass", "fail", f"within the {lim_text} limit on the card"
    return [
        RuleRow(
            id="mass-limit",
            title=TITLE,
            severity=severity,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            message=said + tail,
            relies_on=relies,
        )
    ]


MASS_LIMIT_SCREEN = Screen("mass-limit", mass_limit, title="Mass limit")

__all__ = ["MARGIN", "MASS_LIMIT", "MASS_LIMIT_SCREEN"]
