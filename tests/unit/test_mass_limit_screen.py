"""S-233 (B-0234): the generic ``mass-limit`` screen fails a card on ``site.mass_limit``."""

from __future__ import annotations

import copy
from typing import Any

import pytest
import yaml

from napkin2factory.concepts.massing import compose
from napkin2factory.concepts.screening import screen
from napkin2factory.concepts.screens import GENERIC_SCREENS, run_screens
from napkin2factory.concepts.screens.mass_limit import MARGIN
from napkin2factory.core.domain import Screen
from napkin2factory.core.model import ConceptCard, Screening
from napkin2factory.core.units import Quantity
from tests.conftest import FIXTURES


def _screened(limit: str | None, screens: list[Screen] | None = None) -> Screening:
    # the made-up column-and-arm card: two 60 x 60 x 4 mm steel tubes, about 11.5 kg
    data: dict[str, Any] = yaml.safe_load((FIXTURES / "structural" / "column-arm.yaml").read_text())
    data = copy.deepcopy(data)
    data["site"] = {} if limit is None else {"mass_limit": limit}
    card = ConceptCard.model_validate(data)
    massing = compose(card, write=False)
    if screens is None:
        return screen(card, massing)
    return run_screens(card, massing, screens=screens)


def _mass() -> float:
    return float(_screened(None).computed["mass"].value.split()[0])


def test_a_card_over_its_mass_limit_fails() -> None:
    m = _mass()
    s = _screened(f"{m / 2:.1f} kg")
    row = s.rule("mass-limit")
    assert row is not None and row.status == "fail" and row.severity == "fail"
    assert "(computed)" in row.message and "over the" in row.message
    assert s.verdict == "red"


def test_within_the_margin_is_amber_not_red() -> None:
    m = _mass()
    s = _screened(f"{m / (1 - MARGIN / 2):.2f} kg")  # the mass is 5 % below the limit
    row = s.rule("mass-limit")
    assert row is not None and row.status == "warn" and row.severity == "warn"
    assert "within 10% of the" in row.message
    assert s.verdict == "green"


def test_well_under_the_limit_passes_and_the_limit_is_a_given() -> None:
    s = _screened(f"{_mass() * 3:.0f} kg")
    row = s.rule("mass-limit")
    assert row is not None and row.status == "pass" and "within the" in row.message
    assert s.given["mass_limit"].label == "given"


def test_no_limit_on_the_card_gives_no_row() -> None:
    assert _screened(None).rule("mass-limit") is None


def test_the_total_mass_a_screen_added_is_what_is_held_to_the_limit() -> None:
    def extra(card: Any, massing: Any, values: Any) -> list[Any]:
        values.mass_items.append((Quantity(500.0, "kg"), "a heavy part", "test"))
        return []

    extra.phase = "estimate"  # type: ignore[attr-defined]
    s = _screened(f"{_mass() * 3:.0f} kg", [*GENERIC_SCREENS, Screen("heavy", extra)])
    row = s.rule("mass-limit")
    assert row is not None and row.status == "fail" and "(estimate)" in row.message


def test_a_products_own_mass_limit_row_replaces_the_generic_one() -> None:
    from napkin2factory.core.model.concepts import RuleRow

    def own(card: Any, massing: Any, values: Any) -> list[RuleRow]:
        return [RuleRow(id="mass-limit", status="pass", message="its own words")]

    s = _screened("1 kg", [*GENERIC_SCREENS, Screen("own", own)])
    rows = [r for r in s.rules if r.id == "mass-limit"]
    assert [r.message for r in rows] == ["its own words"]


@pytest.mark.parametrize("name", [s.name for s in GENERIC_SCREENS])
def test_the_generic_screens_are_registered_once(name: str) -> None:
    assert [s.name for s in GENERIC_SCREENS].count(name) == 1


def test_an_unknown_material_is_named_with_the_known_ones_not_silently_steel() -> None:
    # B-0236 (S-233): "zzzz" was weighed as mild steel with no word to the owner
    data: dict[str, Any] = yaml.safe_load((FIXTURES / "structural" / "column-arm.yaml").read_text())
    data["massing"][1]["material"] = "zzzz"
    card = ConceptCard.model_validate(copy.deepcopy(data))
    s = screen(card, compose(card, write=False))
    (note,) = [n for n in s.notes if "does not know" in n]
    assert "arm" in note and "weighed as mild steel" in note
    assert "aluminum-6063-t5" in note and "walnut" in note  # the known materials
    assert not [n for n in _screened(None).notes if "does not know" in n]
