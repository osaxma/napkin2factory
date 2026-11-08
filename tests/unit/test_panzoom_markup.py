"""M3b: drawings and wiring diagrams sit in pan/zoom frames; one id each (B-0180, S-319)."""

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


def _frames(html: str) -> list:
    return LexborHTMLParser(html).css("div.pz[data-panzoom]")


def _check_frame(frame) -> None:
    assert [b.attributes["data-pz"] for b in frame.css("button")] == ["in", "out", "fit", "full"]
    for b in frame.css("button"):
        assert b.attributes.get("aria-label") and b.text(strip=True)  # words, not only icons
        assert b.attributes["type"] == "button"
    view = frame.css_first(".pz-view")
    assert view.attributes["role"] == "group" and view.attributes["tabindex"] == "0"
    assert view.attributes["aria-label"]
    assert view.css_first(".pz-stage svg") is not None


def test_wiring_has_one_id_each_and_a_frame_per_diagram(wired: str) -> None:
    assert wired.count('id="wiring"') == 1
    ids = re.findall(r'\bid="([^"]+)"', LexborHTMLParser(wired).css_first("section#wiring").html)
    assert len(ids) == len(set(ids)), "an id repeats inside the wiring section"
    frames = LexborHTMLParser(wired).css("section#wiring div.pz[data-panzoom]")
    assert frames
    for f in frames:
        _check_frame(f)


def test_drawings_sit_in_frames_with_no_click_toggle(table: str) -> None:
    frames = LexborHTMLParser(table).css("section#drawings div.pz[data-panzoom]")
    assert frames
    for f in frames:
        _check_frame(f)
    assert "onclick" not in LexborHTMLParser(table).css_first("section#drawings").html


def test_script_is_inlined_with_and_without_a_model() -> None:
    for body in (bundle_viewer(), bundle_workbench()):
        assert "---- panzoom.js ----" in body and "data-panzoom" in body
