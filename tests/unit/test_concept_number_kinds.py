"""A card number of the wrong kind (``power: 3 kg``) is a lint error and a screening note.

Before, screening fed it to the calc kit and stopped with a unit traceback.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from napkin2factory.core import concepts as cm
from tests.unit.test_screening import KILN, _card, _screen


def test_lint_names_the_number_and_the_kind_it_should_be(tmp_path: Path) -> None:
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
    s = _screen(_card(KILN, site={"alcove_width": "3 kg"}))
    assert {r.id: r.status for r in s.rules}["fits-site-width"] == "skip"
    assert any(n.startswith("the alcove width on the card (3 kg) is not a length") for n in s.notes)
