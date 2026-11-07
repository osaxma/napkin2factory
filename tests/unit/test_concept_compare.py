"""M3a: ``n2f concept compare`` — one table, a row per value, a column per card (R11)."""

from __future__ import annotations

from pathlib import Path

import pytest

from napkin2factory.concepts.compare import compare, render_text
from napkin2factory.concepts.fork import fork_from_model
from napkin2factory.core import concepts as cm
from tests.conftest import EXAMPLES, copy_product

pytestmark = pytest.mark.xdist_group("test_concept_compare")


@pytest.fixture
def table(tmp_path: Path) -> Path:
    """A fresh tracked copy of the built table (C-002 promoted)."""
    return copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)


def test_compare_returns_rows_and_columns(table: Path) -> None:
    data = compare(table)
    ids = [c["id"] for c in data["cards"]]
    assert "C-002" in ids
    keys = [r["key"] for r in data["rows"]]
    for key in ("width", "cost", "verdict"):
        assert key in keys
    assert "cost_low" not in keys and "cost_high" not in keys  # one cost row (B-0292)
    verdict = next(r for r in data["rows"] if r["key"] == "verdict")
    assert verdict["cells"]["C-002"]["value"] == "holds up"


def test_compare_text_shares_the_rows(table: Path) -> None:
    text = render_text(compare(table))
    assert "width" in text
    assert "holds up" in text
    assert "C-002" in text


def test_compare_marks_a_forked_column(table: Path) -> None:
    fork_from_model(table)
    data = compare(table)
    col = next(c for c in data["cards"] if c["origin"] == "built")
    assert col["id"] == "C-004"
    text = render_text(data)
    assert "from the built design" in text
    # the forked card's computed cost joins the strip rows.
    cost = next(r for r in data["rows"] if r["key"] == "cost")
    assert cost["cells"]["C-004"]["label"] == "estimate"


def test_compare_shows_a_parked_cards_figures_when_parked(table: Path) -> None:
    cm.update_card_status(
        table,
        "C-003",
        "parked",
        {"reason": "set aside", "at": "2026-11-06"},
        built={
            "event": "parked",
            "checkpoint": "abc",
            "number": 5,
            "mass": "23.1 kg",
            "cost": "180 USD",
            "at": "2026-11-06",
        },
    )
    data = compare(table, ["C-003"])
    mass = next(r for r in data["rows"] if r["key"] == "total_mass")
    assert mass["cells"]["C-003"]["value"] == "23.1 kg"
    assert mass["cells"]["C-003"]["parked"] is True
    cost = next(r for r in data["rows"] if r["key"] == "cost")
    assert cost["cells"]["C-003"]["value"] == "180 USD"
    assert "when parked" in render_text(data)


def test_compare_heads_columns_with_titles_and_groups_thousands(table: Path) -> None:
    fork_from_model(table)
    data = compare(table)
    text = render_text(data)
    for col in data["cards"]:
        assert col["title"][:6] in text  # id and title head each column (B-0292)
    cost = next(r for r in data["rows"] if r["key"] == "cost")
    for cell in cost["cells"].values():
        assert not any(tok.isdigit() and len(tok) >= 4 for tok in cell["value"].split())


def test_grouped_numbers() -> None:
    from napkin2factory.concepts.compare import _grouped

    assert _grouped("13965 USD") == "13,965 USD"
    assert _grouped("1,017 USD") == "1,017 USD"
    assert _grouped("23.1 kg") == "23.1 kg"
    assert _grouped("750 mm") == "750 mm"
