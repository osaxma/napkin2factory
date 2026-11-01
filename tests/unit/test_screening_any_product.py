"""The napkin stage for any product (gate F, B3 and B4; gate E, C8 and C13; S-137).

A product with no door and no alcove (a wall shelf) is screened, sketched and promoted in
words that name neither: "the space" and its width alone. The kiln keeps its own words,
which its screens pack gives (``WORDS = {"space": "alcove"}``), so its shipped cards screen
exactly as recorded. A product's own screen or rule-pack check that fails while running is
one plain error naming the file and the next step, not a traceback.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from napkin2factory.concepts.massing import compose
from napkin2factory.concepts.screening import same_screening, screen
from napkin2factory.core import concepts as cm
from napkin2factory.core.errors import N2FError
from napkin2factory.core.model import ConceptCard, Screening
from tests.conftest import EXAMPLES

#: Words a shelf's napkin stage must not say (an oven's, a door's, an alcove's).
FOREIGN = re.compile(r"\b(door|doors|alcove|oven|kiln|chamber|hinge)\b", re.IGNORECASE)


def _shelf(width: str = "800 mm") -> ConceptCard:
    """A wall shelf: one board, no door, a space to fit."""
    return ConceptCard.model_validate(
        {
            "id": "C-001",
            "title": "Wall shelf",
            "site": {"width": width, "depth": "300 mm"},
            "massing": [
                {
                    "kit": "block",
                    "as": "body",
                    "material": "mild steel",
                    "args": {"length": "600 mm", "width": "250 mm", "height": "20 mm"},
                }
            ],
        }
    )


def _said(s: Screening) -> str:
    """Every owner-facing word of a screening: rows, values' sources, notes."""
    rows = [f"{r.title}: {r.message}" for r in s.rules]
    values = [v.source for part in (s.given, s.computed, s.estimates) for v in part.values()]
    return "\n".join([*rows, *values, *s.notes])


def _row(s: Screening, rid: str) -> Any:
    return next(r for r in s.rules if r.id == rid)


def test_a_shelf_that_does_not_fit_says_the_space_and_no_door() -> None:
    card = _shelf("500 mm")
    s = screen(card, compose(card, write=False))
    width = _row(s, "fits-site-width")
    assert width.status == "fail" and width.title == "Fits the space width"
    assert width.message == "it is 600 mm wide but the space is 500 mm wide"
    assert not FOREIGN.search(_said(s)), _said(s)


def test_a_shelf_that_fits_says_the_space_and_no_door() -> None:
    card = _shelf()
    s = screen(card, compose(card, write=False))
    assert _row(s, "fits-site-width").message == "600 mm wide fits the 800 mm space"
    assert _row(s, "fits-site-depth").title == "Fits the space depth"
    assert _row(s, "fits-site-height").message == "no space height on the card"
    assert s.verdict == "green" and not FOREIGN.search(_said(s)), _said(s)


def test_the_kiln_cards_screen_exactly_as_shipped() -> None:
    """The kiln's pack gives "alcove": its board and screening do not move (S-137)."""
    root = EXAMPLES / "kiln"
    for cid, card in sorted(cm.load_concepts(root).items()):
        again = screen(card, compose(card, write=False), root)
        assert same_screening(card.screening, again), cid
    c1 = cm.load_concepts(root)["C-001"]
    assert c1.screening is not None
    assert _row(c1.screening, "fits-site-width").title == "Fits the alcove with the door open"


def _pack(root: Path, name: str, body: str) -> None:
    folder = root / "model" / "screens"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(body, encoding="utf-8")


def test_a_product_pack_names_the_space_its_own_way(tmp_path: Path) -> None:
    _pack(tmp_path, "words.py", 'SCREENS = ()\nWORDS = {"space": "recess"}\n')
    card = _shelf("500 mm")
    s = screen(card, compose(card, write=False), tmp_path)
    width = _row(s, "fits-site-width")
    assert width.title == "Fits the recess width"
    assert width.message == "it is 600 mm wide but the recess is 500 mm wide"


@pytest.mark.parametrize(
    "words",
    ['{"room": "recess"}', '{"space": 3}', '"recess"'],
)
def test_a_wrong_words_entry_names_its_file(tmp_path: Path, words: str) -> None:
    from napkin2factory.core.packs import product_words

    _pack(tmp_path, "words.py", f"SCREENS = ()\nWORDS = {words}\n")
    with pytest.raises(N2FError, match=r"model/screens/words\.py: WORDS .*space \(the space"):
        product_words(tmp_path)


SAG = """
from napkin2factory.core.domain import Screen

def sag(card, massing, values):
    return [1 / 0]

SCREENS = (Screen("board-sag", sag, title="Board sag"),)
"""


def test_a_product_screen_that_fails_is_a_plain_error(tmp_path: Path) -> None:
    """Gate F, B4: one line naming the file, the screen and the next step."""
    _pack(tmp_path, "shelf.py", SAG)
    card = _shelf()
    with pytest.raises(N2FError) as caught:
        screen(card, compose(card, write=False), tmp_path)
    said = str(caught.value)
    assert said.startswith("model/screens/shelf.py: the screen 'Board sag' failed while running")
    assert "(ZeroDivisionError: division by zero)" in said
    assert "move it out of model/screens/" in said
    assert "`n2f concept build C-001`" in said


def test_a_system_screen_that_fails_stays_a_fault_in_code() -> None:
    """Only a product's own screen is said in owner words; installed code fails as code."""
    from napkin2factory.concepts.screens import run_screens
    from napkin2factory.core.domain import Screen

    def broken(card: Any, massing: Any, values: Any) -> list[Any]:
        raise ZeroDivisionError("division by zero")

    card = _shelf()
    with pytest.raises(ZeroDivisionError):
        run_screens(card, None, screens=[Screen("broken", broken)])


SHOP = """
from napkin2factory.rulepacks.checks import RuleSkip

def hole_edge(part, features, params, product):
    return params["no_such_key"]

def unsure(part, features, params, product):
    raise RuleSkip("no holes yet")

CHECKS = {"hole_edge": hole_edge, "unsure": unsure}
"""


def test_a_product_rule_check_that_fails_is_a_plain_error(tmp_path: Path) -> None:
    """Gate F, concern 5: the file, the check and the next step; its signals pass through."""
    from types import SimpleNamespace

    from napkin2factory.core.packs import pack_checks
    from napkin2factory.rulepacks.checks import RuleSkip

    folder = tmp_path / "model" / "rulepacks"
    folder.mkdir(parents=True)
    (folder / "shop.py").write_text(SHOP, encoding="utf-8")
    checks, _ = pack_checks(tmp_path)
    part = SimpleNamespace(uri="part://shelf-board")
    with pytest.raises(N2FError) as caught:
        checks["hole_edge"](part, {}, {}, None)
    said = str(caught.value)
    assert said.startswith(
        "model/rulepacks/shop.py: the check 'hole_edge' failed while running on "
        "part://shelf-board (KeyError: 'no_such_key')"
    )
    assert "move it out of model/rulepacks/" in said and "`n2f check`" in said
    with pytest.raises(RuleSkip, match="no holes yet"):
        checks["unsure"](part, {}, {}, None)


def _reads(text: str) -> str:
    """The skeleton's "screens read" comment lines."""
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        if "screens read:" in line:
            out.append(line)
            out += [x for x in lines[i + 1 : i + 3] if x.startswith("#     ")]
    return "\n".join(out)


def test_a_new_card_suggests_no_door_unless_it_names_one() -> None:
    """Gate F, B3: the skeleton's hints; the door's fields only once the card has a door."""
    fields = cm.screen_fields()
    blank = cm.render_card({"id": "C-001", "title": "Wall shelf"}, fields)
    assert "width (a length, like 800 mm)" in _reads(blank)
    assert not FOREIGN.search(blank), blank
    with_door = cm.render_card(
        {"id": "C-002", "title": "Cabinet", "layout": {"door": "hinged-left"}}, fields
    )
    assert "door (like hinged-left)" in _reads(with_door)
