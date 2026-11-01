"""The screen runner (F8, F10, F15): every installed screen on one card, then the rules.

Installed screens, in order: the system's generic screens (:mod:`.generic`), the screens
installed domains register (``Domain.screens``) and the product's own pack
(``model/screens/*.py``, loaded fresh per product root by :mod:`napkin2factory.core.packs`).
They run phase by phase (``measure``, ``estimate``, ``total``, ``check``; see
:mod:`.base`). Between ``measure`` and ``estimate`` a card number of the wrong kind for a
field some screen declares is left out with one note. Then the ``concept-v0`` pack's rules
run on what the screens found, and each screen's own rows follow in phase order.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from napkin2factory.concepts.screens.base import (
    PHASES,
    CardField,
    ScreenValues,
    fields_of,
    phase_of,
)
from napkin2factory.concepts.screens.generic import GENERIC_SCREENS
from napkin2factory.core.domain import Screen
from napkin2factory.core.model.concepts import ConceptCard, RuleRow, Screening


def installed_screens(root: Path | None = None) -> list[Screen]:
    """The generic screens, the domains' and (with ``root``) the product's own, in order."""
    from napkin2factory.core.registry import registry

    screens = [*GENERIC_SCREENS, *registry().screens()]
    if root is not None:
        from napkin2factory.core.packs import product_screens

        screens += product_screens(root)
    return screens


def declared_fields(screens: list[Screen]) -> list[CardField]:
    """Every field the screens declare, once each (first declaration wins), in order."""
    seen: dict[str, CardField] = {}
    for s in screens:
        for f in fields_of(s):
            seen.setdefault(f.name, f)
    return list(seen.values())


def generic_fields() -> list[CardField]:
    """The fields the system's generic screens read: the system's own words (F9)."""
    return declared_fields(list(GENERIC_SCREENS))


def card_fields(root: Path | None = None) -> list[CardField]:
    """The fields every screen installed for ``root`` reads (``n2f concept new``/``lint``)."""
    return declared_fields(installed_screens(root))


def wrong_kind_notes(card: ConceptCard, fields: list[CardField]) -> list[str]:
    """One note per card number of the wrong kind: screening leaves it out (C8, S-096)."""
    notes = []
    for f in fields:
        wrong = f.wrong_kind(f.raw(card))
        if wrong is not None:
            shown, kind, example = wrong
            notes.append(
                f"{f.words} on the card ({shown}) is not {kind}, so screening leaves it out: "
                f"give it like {example}"
            )
    return notes


def run_screens(
    card: ConceptCard,
    massing: Any,
    root: Path | None = None,
    *,
    screens: list[Screen] | None = None,
    now: dt.datetime | None = None,
) -> Screening:
    """Screen one card: labelled numbers, rule rows and a verdict.

    Args:
        card: the concept card.
        massing: the composed :class:`~napkin2factory.concepts.massing.MassingResult`, or
            ``None``.
        root: the product folder; its ``model/screens/`` pack runs too.
        screens: run exactly these instead of the installed ones (tests).
        now: the timestamp to record (default: now, to the second).
    """
    from napkin2factory.rulepacks.concept_checks import run_concept_rules

    chosen = screens if screens is not None else installed_screens(root)
    values = ScreenValues()
    own_rows: dict[str, list[RuleRow]] = {p: [] for p in PHASES}
    for phase in PHASES:
        if phase == "estimate":
            values.notes += wrong_kind_notes(card, declared_fields(chosen))
        for s in chosen:
            if phase_of(s) == phase:
                own_rows[phase] += list(s.run(card, massing, values))
    rules = run_concept_rules(
        card, values.computed.raw, values.estimate.raw, massing, values.shared
    )
    for phase in PHASES:
        rules += own_rows[phase]
    red = any(r.status == "fail" for r in rules)
    stamp = (now or dt.datetime.now()).replace(microsecond=0)
    return Screening(
        given=values.given.out,
        computed=values.computed.out,
        estimates=values.estimate.out,
        rules=rules,
        verdict="red" if red else "green",
        at=stamp,
        notes=values.notes,
    )


def screens_key(root: Path | None) -> str | None:
    """The hash of the product's own screens (``model/screens/``), or None without one (F10).

    A concept build records it; a build that finds it changed re-screens every card with a
    fresh timestamp even when the numbers come out the same (the screens changed, so the
    old screening is not the one these screens would give).
    """
    from napkin2factory.core.packs import screens_hash

    return screens_hash(root) if root is not None else None


__all__ = [
    "card_fields",
    "declared_fields",
    "generic_fields",
    "installed_screens",
    "run_screens",
    "screens_key",
    "wrong_kind_notes",
]
