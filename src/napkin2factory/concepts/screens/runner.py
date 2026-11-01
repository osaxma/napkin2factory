"""The screen runner (F8, F10, F15): every installed screen on one card, then the rules.

Installed screens, in order: the system's generic screens (:mod:`.generic`), the screens
installed domains register (``Domain.screens``) and the product's own pack
(``model/screens/*.py``, loaded fresh per product root by :mod:`napkin2factory.core.packs`).
They run phase by phase (``measure``, ``estimate``, ``total``, ``check``; see
:mod:`.base`). Between ``measure`` and ``estimate`` a card number of the wrong kind for a
field some screen declares is left out with one note. Then the ``concept-v0`` pack's rules
run on what the screens found, and each screen's own rows follow in phase order.

The product's own words for what the generic rows name (``WORDS`` in its screens modules,
:func:`napkin2factory.core.packs.product_words`: a "recess", say) reach the rules as
``values.shared["space_words"]``; without them the rows say "the space" (S-137). A product
screen that fails while running is a plain error naming its file, the screen and the next
step (gate F, S-137); the system's and the domains' screens fail as code does.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from napkin2factory.concepts.screens.base import (
    PHASES,
    SPACE_WORDS,
    CardField,
    ScreenValues,
    fields_of,
    phase_of,
)
from napkin2factory.concepts.screens.generic import GENERIC_SCREENS
from napkin2factory.core.domain import Screen
from napkin2factory.core.errors import N2FError
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


def wrong_kind_notes(
    card: ConceptCard, fields: list[CardField], space: str = SPACE_WORDS
) -> list[str]:
    """One note per card number of the wrong kind: screening leaves it out (C8, S-096)."""
    notes = []
    for f in fields:
        wrong = f.wrong_kind(f.raw(card))
        if wrong is not None:
            shown, kind, example = wrong
            notes.append(
                f"{f.said(space)} on the card ({shown}) is not {kind}, so screening leaves it "
                f"out: give it like {example}"
            )
    return notes


def _product_file(screen: Screen, root: Path | None) -> str | None:
    """``model/screens/shelf.py`` when ``screen`` comes from the product's own pack, else None."""
    import sys

    if root is None:
        return None
    module = sys.modules.get(getattr(screen.run, "__module__", "") or "")
    file = getattr(module, "__file__", None)
    if not file:
        return None
    folder = (Path(root) / "model" / "screens").resolve()
    path = Path(file).resolve()
    return f"model/screens/{path.name}" if path.parent == folder else None


def _run_one(
    screen: Screen, card: ConceptCard, massing: Any, values: ScreenValues, root: Path | None
) -> list[RuleRow]:
    """One screen's rows; a product screen that fails says so in plain words (gate F)."""
    try:
        return list(screen.run(card, massing, values))
    except N2FError:
        raise
    except Exception as exc:
        file = _product_file(screen, root)
        if file is None:
            raise  # the system's or a domain's screen: a fault in installed code
        from napkin2factory.core.packs import move_out

        raise N2FError(
            f"{file}: the screen '{screen.title or screen.name}' failed while running on "
            f"{card.id} ({type(exc).__name__}: {exc}) → {move_out('screens')}, then run "
            f"`n2f concept build {card.id}` again"
        ) from exc


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
    from napkin2factory.core.packs import product_words
    from napkin2factory.rulepacks.concept_checks import run_concept_rules

    chosen = screens if screens is not None else installed_screens(root)
    values = ScreenValues()
    space = product_words(root).get("space", SPACE_WORDS)
    values.shared["space_words"] = space
    own_rows: dict[str, list[RuleRow]] = {p: [] for p in PHASES}
    for phase in PHASES:
        if phase == "estimate":
            values.notes += wrong_kind_notes(card, declared_fields(chosen), space)
        for s in chosen:
            if phase_of(s) == phase:
                own_rows[phase] += _run_one(s, card, massing, values, root)
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
