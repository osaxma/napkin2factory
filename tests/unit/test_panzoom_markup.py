"""M3b: drawings and wiring diagrams are preview cards that open a viewer (S-319, S-322)."""

from __future__ import annotations

import re

import pytest
from selectolax.lexbor import LexborHTMLParser

from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product
from napkin2factory.report.inline import bundle_viewer, bundle_workbench
from tests.conftest import EXAMPLES, FIXTURES, copy_product


@pytest.fixture(scope="module")
def wired(tmp_path_factory: pytest.TempPathFactory) -> str:
    """The electrical fixture's report: a wiring section with one diagram."""
    root = copy_product(
        FIXTURES / "electrical" / "minimal", tmp_path_factory.mktemp("pz") / "hb", git=False
    )
    run_build(load_product(root), quiet=True, render=False)
    return (root / "build/report/index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def table(tmp_path_factory: pytest.TempPathFactory) -> str:
    root = copy_product(
        EXAMPLES / "table", tmp_path_factory.mktemp("pzt") / "table", git=False, prebuilt=True
    )
    return (root / "build/report/index.html").read_text(encoding="utf-8")


def _check_card(card) -> None:
    """A card is a title and one real button around the static preview: no other control."""
    buttons = card.css("button")
    assert len(buttons) == 1
    b = buttons[0]
    assert b.attributes["type"] == "button" and "pz-open" in b.attributes["class"]
    assert b.attributes["aria-label"].startswith("Open ") and card.attributes["data-title"]
    assert "part://" not in card.attributes["data-title"] + b.attributes["aria-label"]
    assert b.css_first("svg") is not None
    assert not b.css("a"), "a link inside the button"  # captions stay outside it


def test_wiring_has_one_id_each_and_a_card_per_diagram(wired: str) -> None:
    assert wired.count('id="wiring"') == 1
    ids = re.findall(r'\bid="([^"]+)"', LexborHTMLParser(wired).css_first("section#wiring").html)
    assert len(ids) == len(set(ids)), "an id repeats inside the wiring section"
    cards = LexborHTMLParser(wired).css("section#wiring [data-pzcard]")
    assert cards
    for c in cards:
        _check_card(c)


def test_drawings_are_cards_with_no_click_toggle(table: str) -> None:
    cards = LexborHTMLParser(table).css("section#drawings [data-pzcard]")
    assert cards
    for c in cards:
        _check_card(c)
    # plain titles, never an identifier, in the caption and the card (N5, D17; S-323)
    for fig in LexborHTMLParser(table).css("section#drawings figure"):
        for v in fig.css("svg"):  # the sheet's own title block is the drawing itself
            v.decompose()
        assert "part://" not in fig.text()
    assert "Open " in cards[0].css_first("button").attributes["aria-label"]
    assert "onclick" not in LexborHTMLParser(table).css_first("section#drawings").html
    # the 3D callout stays a link in the caption, outside the button
    assert "data-show3d" in LexborHTMLParser(table).css_first("section#drawings figcaption").html


def test_script_is_inlined_with_and_without_a_model() -> None:
    for body in (bundle_viewer(), bundle_workbench()):
        assert "---- panzoom.js ----" in body and "data-pzcard" in body
