"""M3b: preview cards and the drawing viewer in a browser, from ``file://`` (S-319, S-322, B-0176).

A prebuilt table (drawings) and the electrical fixture (a wiring diagram): a card is a title and a
static preview with no controls; clicking it opens a modal viewer with the drawing fitted and
centred; zoom changes the SVG's size, the pan arrows and the keys move it, the list switches
drawing, Escape returns focus to the card; the same at phone width.
"""

from __future__ import annotations

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


def _scale(page: Any) -> float:
    return float(page.locator(".pzv").get_attribute("data-pz-scale"))


def _open_page(browser: Any, url: str, errors: list[str], width: int = 1440) -> Any:
    page = browser.new_page(viewport={"width": width, "height": 844 if width < 600 else 900})
    page.set_default_timeout(15000)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(url + "#lens=drawings")
    page.locator("[data-pzcard]").first.wait_for(state="visible")
    return page


def _centred(page: Any) -> None:
    view = page.locator(".pzv-view").bounding_box()
    svg = page.locator(".pzv-view svg").bounding_box()
    assert abs((svg["x"] + svg["width"] / 2) - (view["x"] + view["width"] / 2)) <= 3
    assert abs((svg["y"] + svg["height"] / 2) - (view["y"] + view["height"] / 2)) <= 3
    assert svg["width"] <= view["width"] + 1 and svg["height"] <= view["height"] + 1


def _no_ids(page: Any) -> None:
    """No `part://` text shows in the open viewer or a card caption (N5, D17)."""
    # the sheet's own title block is the drawing, not page chrome, so svg text is left out
    shown = page.evaluate(
        "[...document.querySelectorAll('.pzv:not([hidden]), [data-pzcard], figcaption')].map(e => {"
        " const c = e.cloneNode(true); c.querySelectorAll('svg').forEach(v => v.remove());"
        " return c.textContent + ' ' + (e.getAttribute('data-title') || ''); }).join(' ')"
    )
    assert "part://" not in shown and "asm://" not in shown
    labels = page.evaluate(
        "[...document.querySelectorAll('.pzv [aria-label], [data-pzcard] [aria-label]')]"
        ".map(e => e.getAttribute('aria-label')).join(' ')"
    )
    assert "part://" not in labels


def _inside(page: Any) -> None:
    """The drawing's box lies fully inside the area the viewer leaves for it."""
    view = page.locator(".pzv-view").bounding_box()
    svg = page.locator(".pzv-view svg").bounding_box()
    assert svg["x"] >= view["x"] - 1 and svg["y"] >= view["y"] - 1
    assert svg["x"] + svg["width"] <= view["x"] + view["width"] + 1
    assert svg["y"] + svg["height"] <= view["y"] + view["height"] + 1


def test_card_opens_viewer_fitted_and_centred(browser: Any, table_url: str) -> None:
    errors: list[str] = []
    page = _open_page(browser, table_url, errors)
    try:
        card = page.locator("section#drawings [data-pzcard]").first
        assert card.locator("button").count() == 1  # the preview itself, nothing else
        assert page.locator(".pzv").is_hidden()
        opener = card.locator("button.pz-open")
        opener.click()
        dlg = page.get_by_role("dialog")
        dlg.wait_for(state="visible")
        assert dlg.get_attribute("aria-modal") == "true"
        assert page.evaluate("document.activeElement.closest('.pzv') !== null")
        page.wait_for_function("document.querySelector('.pzv-view svg')")
        _centred(page)
        _no_ids(page)
        # the viewer's own svg repeats no id of the page
        assert page.evaluate(
            "[...document.querySelectorAll('.pzv [id]')].every("
            "e => document.querySelectorAll('[id=\"' + e.id + '\"]').length === 1)"
        )
        fit = _scale(page)
        for name in ("Zoom in", "Zoom out", "Fit", "Close"):
            assert dlg.get_by_role("button", name=name, exact=True).count() == 1
        before = page.locator(".pzv-view svg").bounding_box()["width"]
        dlg.get_by_role("button", name="Zoom in").click()
        assert _scale(page) > fit * 1.4
        assert page.locator(".pzv-view svg").bounding_box()["width"] > before * 1.4
        # zoom is the svg's own size, never a CSS transform (S-322: sharp lines)
        assert (
            page.evaluate("getComputedStyle(document.querySelector('.pzv-view svg')).transform")
            == "none"
        )
        # pan arrows and keys move it
        left0 = page.locator(".pzv-view svg").bounding_box()["x"]
        dlg.get_by_role("button", name="Pan right").click()
        assert page.locator(".pzv-view svg").bounding_box()["x"] < left0
        x1 = page.locator(".pzv-view svg").bounding_box()["x"]
        page.locator(".pzv-view").focus()
        page.keyboard.press("ArrowLeft")
        assert page.locator(".pzv-view svg").bounding_box()["x"] > x1
        # drag pans
        box = page.locator(".pzv-view").bounding_box()
        y0 = page.locator(".pzv-view svg").bounding_box()["y"]
        page.mouse.move(box["x"] + 300, box["y"] + 300)
        page.mouse.down()
        page.mouse.move(box["x"] + 300, box["y"] + 360, steps=4)
        page.mouse.up()
        assert page.locator(".pzv-view svg").bounding_box()["y"] != y0
        # wheel zooms (a modal: no page to scroll), keys zoom and fit
        s1 = _scale(page)
        page.mouse.wheel(0, -300)
        assert _scale(page) > s1
        page.keyboard.press("0")
        assert _scale(page) == pytest.approx(fit, rel=1e-3)
        _centred(page)
        page.keyboard.press("+")
        assert _scale(page) > fit
        dlg.get_by_role("button", name="Fit").click()
        page.locator(".pzv-view").dblclick()
        assert _scale(page) > fit * 2
        page.locator(".pzv-view").dblclick()
        assert _scale(page) == pytest.approx(fit, rel=1e-3)
        # a window resize at fit refits and recentres
        page.set_viewport_size({"width": 1000, "height": 700})
        page.wait_for_function("document.querySelector('.pzv-view').clientWidth < 1000")
        page.wait_for_timeout(100)
        _centred(page)
        # Escape closes and focus returns to the card that opened it
        page.keyboard.press("Escape")
        assert page.locator(".pzv").is_hidden()
        assert opener.evaluate("e => e === document.activeElement")
        # Enter on the focused card opens it again; Close closes
        page.keyboard.press("Enter")
        dlg.wait_for(state="visible")
        dlg.get_by_role("button", name="Close").click()
        assert page.locator(".pzv").is_hidden()
        assert opener.evaluate("e => e === document.activeElement")
        assert real_page_errors(errors) == []
    finally:
        page.close()


def test_sidebar_lists_every_drawing_and_switches(browser: Any, table_url: str) -> None:
    errors: list[str] = []
    page = _open_page(browser, table_url, errors)
    try:
        n = page.locator("[data-pzcard]").count()
        assert n > 1
        page.locator("section#drawings [data-pzcard] button.pz-open").first.click()
        dlg = page.get_by_role("dialog")
        toggle = dlg.get_by_role("button", name="Drawings", exact=True)
        assert toggle.get_attribute("aria-expanded") == "true"  # wide: starts open
        _no_ids(page)
        page.screenshot(path="/private/tmp/claude-503/m3b3-sidebar.png")
        entries = dlg.locator(".pzv-side button")
        assert entries.count() == n
        assert dlg.locator(".pzv-side [aria-current=true]").count() == 1
        entries.nth(1).click()
        assert entries.nth(1).get_attribute("aria-current") == "true"
        assert entries.nth(0).get_attribute("aria-current") is None
        assert dlg.locator(".pzv-title").inner_text() == entries.nth(1).inner_text()
        _centred(page)
        toggle.click()
        assert toggle.get_attribute("aria-expanded") == "false"
        assert dlg.locator(".pzv-side").is_hidden()
        page.wait_for_timeout(100)
        _centred(page)
        assert real_page_errors(errors) == []
    finally:
        page.close()


def test_phone_sidebar_starts_collapsed_and_overlays(browser: Any, table_url: str) -> None:
    errors: list[str] = []
    page = _open_page(browser, table_url, errors, width=390)
    try:
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        _no_ids(page)
        page.screenshot(path="/private/tmp/claude-503/m3b3-lens.png")
        page.locator("section#drawings [data-pzcard] button.pz-open").first.click()
        dlg = page.get_by_role("dialog")
        dlg.wait_for(state="visible")
        page.wait_for_function("document.querySelector('.pzv-view svg')")
        toggle = dlg.get_by_role("button", name="Drawings", exact=True)
        assert toggle.get_attribute("aria-expanded") == "false"
        assert dlg.locator(".pzv-side").is_hidden()
        _centred(page)
        _inside(page)
        _no_ids(page)
        # the bar stays on one row, with touch-sized buttons
        tops = page.evaluate(
            "[...document.querySelectorAll('.pzv-bar button')]"
            ".filter(b => b.offsetParent).map(b => b.getBoundingClientRect().top)"
        )
        assert len(tops) >= 5 and max(tops) - min(tops) <= 2
        sizes = page.evaluate(
            "[...document.querySelectorAll('.pzv-bar button')].filter(b => b.offsetParent)"
            ".map(b => Math.min(b.offsetWidth, b.offsetHeight))"
        )
        assert min(sizes) >= 36
        for name in ("Zoom in", "Zoom out", "Fit", "Close", "Move the drawing"):
            assert dlg.get_by_role("button", name=name, exact=True).is_visible()
        page.screenshot(path="/private/tmp/claude-503/m3b3-phone.png")
        # the arrows sit behind Move
        assert dlg.get_by_role("button", name="Pan left").is_hidden()
        dlg.get_by_role("button", name="Move the drawing").click()
        assert dlg.get_by_role("button", name="Pan left").is_visible()
        dlg.get_by_role("button", name="Move the drawing").click()
        w0 = page.locator(".pzv-view").bounding_box()["width"]
        toggle.click()
        assert dlg.locator(".pzv-side").is_visible()
        assert page.locator(".pzv-view").bounding_box()["width"] == w0  # overlays, no squeeze
        page.screenshot(path="/private/tmp/claude-503/m3b3-phone-sidebar.png")
        dlg.locator(".pzv-side button").nth(1).click()
        assert dlg.locator(".pzv-side").is_hidden()  # picking one closes the overlay
        _centred(page)
        _inside(page)
        # rotating (a resize) at fit refits
        page.set_viewport_size({"width": 844, "height": 390})
        page.wait_for_timeout(200)
        _centred(page)
        _inside(page)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.keyboard.press("Escape")
        assert page.locator(".pzv").is_hidden()
        assert real_page_errors(errors) == []
    finally:
        page.close()


def test_wiring_card_opens_viewer(browser: Any, wired_url: str) -> None:
    errors: list[str] = []
    page = _open_page(browser, wired_url, errors)
    try:
        card = page.locator("section#wiring [data-pzcard]").first
        col = page.locator("section#wiring").bounding_box()["width"]
        assert card.bounding_box()["width"] <= col  # B-0176: never wider than the column
        assert card.locator("button").count() == 1
        card.locator("button.pz-open").click()
        dlg = page.get_by_role("dialog")
        dlg.wait_for(state="visible")
        page.wait_for_function("document.querySelector('.pzv-view svg')")
        _centred(page)
        assert dlg.locator(".pzv-title").inner_text() == card.get_attribute("data-title")
        page.keyboard.press("Escape")
        assert card.locator("button.pz-open").evaluate("e => e === document.activeElement")
        assert real_page_errors(errors) == []
    finally:
        page.close()
