"""A card number of the wrong kind (``power: 3 kg``) is a lint error and a screening note.

Before, screening fed it to the calc kit and stopped with a unit traceback.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from napkin2factory.core import concepts as cm
from tests.unit.test_screening import KILN, KILN_ROOT, _card, _screen


def test_lint_names_the_number_and_the_kind_it_should_be(tmp_path: Path) -> None:
    # the power and the touch limit are read by the kiln's own screens (F8, F10)
    shutil.copytree(KILN_ROOT / "model" / "screens", tmp_path / "model" / "screens")
    d = tmp_path / "concepts"
    d.mkdir()
    (d / "C-001.yaml").write_text(
        "id: C-001\ntitle: t\nenvelope: {power: 3 kg, door_swing: 110 degree}\n"
        "site: {alcove_width: 800 mm, touch_limit: 2 m}\n"
    )
    problems = cm.lint_concepts(tmp_path)
    found = {(p.rule, p.message, p.hint) for p in problems.errors}
    assert found == {
        (
            "C8-number-kinds",
            "envelope.power is 3 kg, which is not a power",
            "give it as a power with its unit, like 2.5 kW",
        ),
        (
            "C8-number-kinds",
            "site.touch_limit is 2 m, which is not a temperature",
            "give it as a temperature with its unit, like 60 degC",
        ),
    }


def test_lint_flags_a_word_where_a_number_belongs(tmp_path: Path) -> None:
    d = tmp_path / "concepts"
    d.mkdir()
    (d / "C-001.yaml").write_text("id: C-001\ntitle: t\nsite: {alcove_width: wide}\n")
    (err,) = cm.lint_concepts(tmp_path).errors
    assert err.message == "site.alcove_width is wide, which is not a length"


def test_the_shipped_cards_are_the_right_kinds() -> None:
    from tests.conftest import EXAMPLES

    for product in ("kiln", "bracket", "enclosure"):
        assert not [
            p for p in cm.lint_concepts(EXAMPLES / product).items if p.rule == "C8-number-kinds"
        ]


@pytest.mark.parametrize("power", ["3 kg", "5 h"])
def test_screening_leaves_a_wrong_power_out_with_a_note(power: str) -> None:
    s = _screen(_card(KILN, envelope={**KILN["envelope"], "power": power}))
    assert "power" not in s.given and "heat_up_time" not in s.estimates
    assert "current" not in s.estimates
    rules = {r.id: r for r in s.rules}
    assert rules["circuit-available"].status == "skip"
    assert any(
        n.startswith(f"the power on the card ({power}) is not a power") and "like 2.5 kW" in n
        for n in s.notes
    ), s.notes
    assert not any("no power on the card" in n for n in s.notes)  # said once, not twice


def test_screening_skips_a_wrong_alcove_instead_of_failing() -> None:
    s = _screen(_card(KILN, site={"width": "3 kg"}))
    assert {r.id: r.status for r in s.rules}["fits-site-width"] == "skip"
    assert any(n.startswith("the alcove width on the card (3 kg) is not a length") for n in s.notes)


def test_a_force_given_as_a_mass_is_accepted_by_lint(tmp_path: Path) -> None:
    """B-0321 (S-336): a mass (e.g. 150 kg or 330 lb) given on a force field is accepted."""
    d = tmp_path / "concepts"
    d.mkdir()
    (d / "C-001.yaml").write_text(
        "id: C-001\ntitle: t\nsite: {point_load: 150 kg, edge_load: 330 lb}\n"
    )
    problems = cm.lint_concepts(tmp_path)
    assert not [p for p in problems.errors if p.rule == "C8-number-kinds"]


def test_a_force_given_a_length_or_bare_number_is_refused_by_lint(tmp_path: Path) -> None:
    """B-0321: a length or bare number on a force field is still refused."""
    d = tmp_path / "concepts"
    d.mkdir()
    (d / "C-001.yaml").write_text(
        "id: C-001\ntitle: t\nsite: {point_load: 330 mm, edge_load: 50}\n"
    )
    errors = [p for p in cm.lint_concepts(tmp_path).errors if p.rule == "C8-number-kinds"]
    messages = {p.message for p in errors}
    assert "site.point_load is 330 mm, which is not a force" in messages
    assert "site.edge_load is 50, which is not a force" in messages


def test_force_field_quantity_converts_mass_at_standard_gravity() -> None:
    """Checklist 1: quantity() returns force = mass * STANDARD_GRAVITY."""
    from napkin2factory.calckit.structural import STANDARD_GRAVITY
    from napkin2factory.concepts.screens.structural_base import POINT_LOAD
    from napkin2factory.core.model.concepts import ConceptCard
    from napkin2factory.core.units import ureg

    card = ConceptCard.model_validate(
        {
            "id": "C-001",
            "title": "t",
            "site": {"point_load": "150 kg"},
        }
    )
    q = POINT_LOAD.quantity(card)
    expected = (ureg("150 kg") * STANDARD_GRAVITY).to("N")
    assert q is not None
    assert abs(q.magnitude - expected.magnitude) < 1e-6
    assert str(q.units) == "newton"

    # A length or bare number returns None
    card_len = ConceptCard.model_validate(
        {
            "id": "C-002",
            "title": "t",
            "site": {"point_load": "150 mm"},
        }
    )
    assert POINT_LOAD.quantity(card_len) is None

    card_bare = ConceptCard.model_validate(
        {
            "id": "C-003",
            "title": "t",
            "site": {"point_load": 150},
        }
    )
    assert POINT_LOAD.quantity(card_bare) is None


def test_screening_given_value_records_mass_as_weight() -> None:
    """Checklist 2: screen given value says '150 kg, read as 1471 N (its weight)'."""
    from napkin2factory.concepts.massing import compose
    from napkin2factory.concepts.screening import screen
    from napkin2factory.core.model import ConceptCard

    card = ConceptCard.model_validate(
        {
            "id": "C-001",
            "title": "t",
            "site": {"point_load": "150 kg"},
            "massing": [
                {
                    "kit": "block",
                    "as": "top",
                    "role": "body",
                    "material": "mild steel",
                    "args": {"length": "1000 mm", "width": "500 mm", "height": "20 mm"},
                }
            ],
        }
    )
    s = screen(card, compose(card, write=False))
    assert "point_load" in s.given
    assert s.given["point_load"].value == "150 kg, read as 1471 N (its weight)"
    assert s.given["point_load"].ref == "site.point_load"
