"""M3b: pan/zoom frames in a browser, from ``file://`` (S-319, B-0176).

A prebuilt table (drawings) and the electrical fixture (a wiring diagram): the drawing starts fitted
to its frame, zoom changes the transform, Reset returns to fit, a plain wheel does not zoom (no
scroll trap), the keys work, and the wiring frame is no wider than its column.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest

from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES, FIXTURES, copy_product, real_page_errors

GL_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]


@pytest.fixture(scope="module")
def table_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    root = copy_product(
        EXAMPLES / "table", tmp_path_factory.mktemp("pzs") / "table", git=False, prebuilt=True
    )
    return (root / "build/report/index.html").as_uri()


@pytest.fixture(scope="module")
def wired_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    root = copy_product(
        FIXTURES / "electrical" / "minimal", tmp_path_factory.mktemp("pzw") / "hb", git=False
    )
    run_build(load_product(root), quiet=True, render=False)
    return (root / "build/report/index.html").as_uri()


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    pytest.importorskip("playwright")
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(args=GL_ARGS)
        except Error as exc:  # browser not installed: logged in BACKLOG.md (B-0001)
            pytest.skip(f"Playwright Chromium unavailable: {exc}")
        yield b
        b.close()


def _scale(frame: Any) -> float:
    return float(frame.get_attribute("data-pz-scale"))


def _open(browser: Any, url: str, sel: str, errors: list[str]) -> tuple[Any, Any]:
    page = browser.new_page(viewport={"width": 1100, "height": 900})
    page.set_default_timeout(15000)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(url + "#lens=drawings")
    frame = page.locator(sel).first
    frame.wait_for(state="visible")
    page.wait_for_function("(s) => document.querySelector(s).classList.contains('pz-on')", arg=sel)
    return page, frame


def test_drawing_fits_zooms_and_resets(browser: Any, table_url: str) -> None:
    errors: list[str] = []
    page, frame = _open(browser, table_url, "section#drawings .pz", errors)
    try:
        fit = _scale(frame)
        view = frame.locator(".pz-view")
        box = view.bounding_box()
        svg = frame.locator(".pz-stage svg").bounding_box()
        assert (
            svg["width"] <= box["width"] + 1 and svg["height"] <= box["height"] + 1
        )  # whole drawing
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        frame.get_by_role("button", name="Zoom in").click()
        assert _scale(frame) > fit * 1.4
        # drag pans
        x0 = frame.locator(".pz-stage").evaluate("e => e.style.transform")
        view.hover()
        page.mouse.down()
        page.mouse.move(
            box["x"] + box["width"] / 2 + 60, box["y"] + box["height"] / 2 + 40, steps=4
        )
        page.mouse.up()
        assert frame.locator(".pz-stage").evaluate("e => e.style.transform") != x0
        # a plain wheel is left to the page; ctrl + wheel zooms
        s1 = _scale(frame)
        page.mouse.wheel(0, 100)
        assert _scale(frame) == s1
        page.keyboard.down("Control")
        page.mouse.wheel(0, -200)
        page.keyboard.up("Control")
        assert _scale(frame) > s1
        frame.get_by_role("button", name="Reset to fit the width").click()
        assert _scale(frame) == pytest.approx(fit, rel=1e-3)
        assert frame.locator(".pz-stage").evaluate("e => e.style.transform") != ""
        # keys, with the frame focused
        view.focus()
        page.keyboard.press("+")
        assert _scale(frame) > fit
        page.keyboard.press("ArrowLeft")
        page.keyboard.press("0")
        assert _scale(frame) == pytest.approx(fit, rel=1e-3)
        # double click zooms in, and out again
        view.dblclick()
        assert _scale(frame) > fit * 2
        view.dblclick()
        assert _scale(frame) == pytest.approx(fit, rel=1e-3)
        assert real_page_errors(errors) == []
    finally:
        page.close()


def test_wiring_diagram_fits_its_column(browser: Any, wired_url: str) -> None:
    errors: list[str] = []
    page, frame = _open(browser, wired_url, "section#wiring .pz", errors)
    try:
        col = page.locator("section#wiring").bounding_box()["width"]
        fw = frame.bounding_box()["width"]
        assert fw <= col  # B-0176: the frame is never wider than the column
        svg = frame.locator(".pz-stage svg").bounding_box()
        assert svg["width"] <= fw + 1  # the whole diagram shows, no sideways scroll
        assert re.match(r"^[0-9.]+$", frame.get_attribute("data-pz-scale"))
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert real_page_errors(errors) == []
    finally:
        page.close()
