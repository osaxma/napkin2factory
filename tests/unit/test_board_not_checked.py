"""Gate J, B1 (S-226): a card whose structural check did not run is no all-clear.

The two fixture cards are made-up: four bare legs, three of them outside the pine top's outline
(so the structural screen cannot name them as its support; legs under the top are judged since
S-235) and a pair of plate feet under an oak top (nothing the screen can name as the support).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from napkin2factory.cli.concept import screening_block, screening_line
from napkin2factory.concepts.board import gather_card, not_checked_line, render_board
from napkin2factory.concepts.massing import compose
from napkin2factory.concepts.screening import screen
from napkin2factory.core.model import ConceptCard, StyleFile
from tests.conftest import FIXTURES

pytestmark = pytest.mark.xdist_group("test_board_not_checked")

SHAPE_LINE = (
    "not checked: the structural screen does not model this shape — sag and tip-over are unknown"
)


def _card(name: str, drop: tuple[str, ...] = ()) -> ConceptCard:
    data = yaml.safe_load((FIXTURES / "structural" / f"{name}.yaml").read_text())
    data["site"] = {k: v for k, v in data["site"].items() if k not in drop}
    card = ConceptCard.model_validate(data)
    card.screening = screen(card, compose(card, write=False))
    return card


def _page(tmp_path: Path, card: ConceptCard) -> str:
    data = {
        "product": "t",
        "cards": [gather_card(tmp_path, card, StyleFile().resolved())],
        "notes": [],
    }
    return render_board(data)


@pytest.mark.parametrize("name", ["bare-legs", "trestle"])
def test_the_board_says_not_checked_and_never_all_clear(tmp_path: Path, name: str) -> None:
    card = _card(name)
    assert card.screening is not None and card.screening.verdict == "green"
    page = _page(tmp_path, card)
    assert SHAPE_LINE in page
    assert "holds up in screening" not in page
    assert "screening found no limitations" not in page
    assert "no problems found, but not fully checked" in page
    assert re.search(r'<article class="concept green exploring notchecked"', page)


def test_the_command_line_views_say_it_too() -> None:
    card = _card("bare-legs")
    assert card.screening is not None
    line = screening_line(card)
    assert "holds up" not in line and SHAPE_LINE in line
    block = "\n".join(screening_block(card.screening, card))
    assert "holds up" not in block and SHAPE_LINE in block


def test_a_card_with_every_check_run_still_holds_up(tmp_path: Path) -> None:
    data = yaml.safe_load((FIXTURES / "structural" / "stiff-apron.yaml").read_text())
    card = ConceptCard.model_validate(data)
    card.screening = screen(card, compose(card, write=False))
    assert not_checked_line(card.screening.rules, card) is None
    page = _page(tmp_path, card)
    assert "holds up in screening" in page and "not checked" not in page


def test_a_missing_input_is_asked_for_not_blamed_on_the_shape(tmp_path: Path) -> None:
    card = _card("stiff-apron", drop=("edge_offset",))
    assert card.screening is not None
    line = not_checked_line(card.screening.rules, card)
    assert line is not None and "does not model this shape" not in line
    assert line.startswith("not checked: tip-over is unknown")
