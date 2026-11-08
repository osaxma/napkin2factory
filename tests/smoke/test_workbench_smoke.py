"""M3a: the workbench page in a browser, from ``file://`` (decisions V1, V2, V6, V8, S-232).

A prebuilt table report: the deep link and the old anchors, the tree and the inspector, an empty
pick of the 3D view, the lens tabs and Back, no sideways scroll at 390 px, and the tree and
inspector with WebGL switched off.  The tree and the inspector must not need WebGL, so only the
asserts that read the 3D view skip when the host has none.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

from tests.conftest import EXAMPLES, copy_product, real_page_errors

GL_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]
PRODUCT = "manifest://product"


@pytest.fixture(scope="module")
def report_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    root = copy_product(
        EXAMPLES / "table", tmp_path_factory.mktemp("wbs") / "table", git=False, prebuilt=True
    )
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


class Page:
    """A page on the report that collects its errors."""

    def __init__(self, browser: Any, url: str, width: int = 1280, height: int = 900) -> None:
        self.errors: list[str] = []
        self.page = browser.new_page(viewport={"width": width, "height": height})
        self.page.set_default_timeout(15000)
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        self.page.goto(url)
        self.page.wait_for_function("window.n2fWorkbench !== undefined")
        self.index: dict[str, Any] = self.page.evaluate("window.n2fWorkbench.index")

    def title(self) -> str:
        return str(self.page.text_content("#inspector-title")).strip()

    def visible_lens(self) -> list[str]:
        return list(
            self.page.eval_on_selector_all(
                ".lens", "els => els.filter(e => !e.hidden).map(e => e.dataset.lens)"
            )
        )

    def close(self, check: bool = True) -> None:
        self.page.close()
        if check:
            assert real_page_errors(self.errors) == [], self.errors


@pytest.fixture
def open_page(browser: Any, report_url: str) -> Iterator[Any]:
    opened: list[Page] = []

    def make(fragment: str = "", **kw: int) -> Page:
        pg = Page(browser, report_url + fragment, **kw)
        opened.append(pg)
        return pg

    yield make
    for pg in opened:
        pg.close()


def test_a_deep_link_opens_the_lens_and_the_entry(open_page: Any) -> None:
    pg = open_page("#lens=build&select=part://top-board")
    assert pg.visible_lens() == ["build"]
    assert pg.page.get_attribute("#tab-build", "aria-selected") == "true"
    assert pg.title() == pg.index["part://top-board"]["title"]
    assert pg.page.evaluate("window.n2fWorkbench.current()") == "part://top-board"
    # the encoded form reads the same (V6), and a select alone opens the workbench
    pg2 = open_page("#select=part%3A%2F%2Fapron-frame")
    assert pg2.visible_lens() == ["workbench"]
    assert pg2.title() == pg2.index["part://apron-frame"]["title"]
    assert (
        pg2.page.get_attribute('#tree li[data-uri="part://apron-frame"]', "aria-selected") == "true"
    )


def test_an_old_anchor_opens_its_lens_and_scrolls_to_it(open_page: Any) -> None:
    pg = open_page("#drawing-apron-frame")
    assert pg.visible_lens() == ["drawings"]
    top = pg.page.evaluate(
        "document.getElementById('drawing-apron-frame').getBoundingClientRect().top"
    )
    assert 0 <= top < 900
    assert pg.page.evaluate("window.n2fWorkbench.current()") == PRODUCT  # selection unchanged
    # #overview opens the workbench with the product; an unknown anchor opens the workbench
    pg.page.evaluate("location.hash = '#overview'")
    pg.page.wait_for_function("!document.getElementById('lens-workbench').hidden")
    assert pg.title() == pg.index[PRODUCT]["title"]
    pg.page.evaluate("location.hash = '#nothing-here'")
    pg.page.wait_for_function("!document.getElementById('lens-workbench').hidden")


def test_a_tree_click_selects_and_the_inspector_follows(open_page: Any) -> None:
    pg = open_page()
    assert pg.visible_lens() == ["workbench"]
    assert pg.title() == pg.index[PRODUCT]["title"]
    pg.page.click('#tree li[data-uri="part://apron-frame"] > .row')
    entry = pg.index["part://apron-frame"]
    assert pg.title() == entry["title"]
    assert (
        pg.page.get_attribute('#tree li[data-uri="part://apron-frame"]', "aria-selected") == "true"
    )
    assert pg.page.is_hidden("#inspector-product") and pg.page.is_visible("#inspector-entry")
    assert "part://apron-frame" in str(pg.page.text_content("#inspector-head"))
    # the address always links back to what is shown (V6)
    assert pg.page.evaluate("location.hash") == "#lens=workbench&select=part://apron-frame"
    # a "Go to" link reaches the Drawings lens
    pg.page.click("#inspector-entry a[href='#drawing-apron-frame']")
    pg.page.wait_for_function("document.getElementById('lens-workbench').hidden")
    assert pg.visible_lens() == ["drawings"]
    # an assembly's tree row selects it too
    pg.page.evaluate("location.hash = '#lens=workbench'")
    pg.page.click('#tree li[data-uri="asm://table"] > .row')
    assert pg.title() == pg.index["asm://table"]["title"]


def test_a_link_in_the_inspector_selects_its_target(open_page: Any) -> None:
    pg = open_page("#select=part://apron-frame")
    first = pg.page.locator("#inspector-entry ul.links a[href^='#lens=workbench&select=']").first
    uri = str(first.get_attribute("href")).split("select=", 1)[1]
    first.click()
    pg.page.wait_for_function(f"window.n2fWorkbench.current() === {json.dumps(uri)}")
    assert pg.title() == pg.index[uri]["title"]


def test_an_empty_pick_returns_to_the_product(open_page: Any) -> None:
    pg = open_page("#select=part://apron-frame")
    assert pg.title() != pg.index[PRODUCT]["title"]
    # what the viewer sends when the click lands on empty space (V3): uri null
    pg.page.evaluate(
        "document.getElementById('viewer').dispatchEvent("
        "new CustomEvent('n2f:select', {detail: {uri: null}}))"
    )
    assert pg.page.is_visible("#inspector-product")
    assert pg.title() == pg.index[PRODUCT]["title"]
    assert (
        pg.page.get_attribute('#tree li[data-uri="manifest://product"]', "aria-selected") == "true"
    )
    # and a pick of a part selects it, with no loop between the viewer and the page
    pg.page.evaluate(
        "document.getElementById('viewer').dispatchEvent("
        "new CustomEvent('n2f:select', {detail: {uri: 'part://top-board'}}))"
    )
    assert pg.title() == pg.index["part://top-board"]["title"]


def test_an_unknown_uri_gets_the_honest_answer(open_page: Any) -> None:
    pg = open_page("#select=part://not-in-this-product")
    assert (
        str(pg.page.text_content("#inspector-empty")).strip()
        == "This build records nothing for part://not-in-this-product."
    )


def test_a_pick_in_the_viewer_selects_the_part(open_page: Any) -> None:
    pg = open_page()
    pg.page.evaluate("window.n2fViewerReady")
    if pg.page.evaluate("window.n2fViewer.glState") == "unavailable":
        pytest.skip("WebGL unavailable on this host (S-232)")
    pg.page.evaluate("window.n2fViewer.select('part://top-board')")
    assert pg.title() == pg.index["part://top-board"]["title"]
    # a part the inspector selects is the viewer's selection too (no second event loop)
    pg.page.click('#tree li[data-uri="part://cross-rail"] > .row')
    assert pg.title() == pg.index["part://cross-rail"]["title"]
    assert pg.page.evaluate("window.n2fViewer.nodes().includes('part://cross-rail')")


def test_the_tabs_change_the_lens_and_back_returns(open_page: Any) -> None:
    pg = open_page()
    pg.page.click("#tab-verification")
    assert pg.visible_lens() == ["verification"]
    pg.page.click("#tab-history")
    assert pg.visible_lens() == ["history"]
    pg.page.go_back()
    pg.page.wait_for_function("!document.getElementById('lens-verification').hidden")
    assert pg.visible_lens() == ["verification"]
    # the requirements filter still works, now inside the Checks lens
    pg.page.check("#req-open-only")
    assert "only-open" in str(pg.page.get_attribute("#req-table", "class"))


def test_nothing_scrolls_sideways_on_a_phone(open_page: Any) -> None:
    pg = open_page(width=390, height=844)
    lenses = pg.page.eval_on_selector_all("[role=tab]", "els => els.map(e => e.dataset.lensTab)")
    assert len(lenses) == 5
    for lens in lenses:
        pg.page.evaluate(f"location.hash = '#lens={lens}'")
        pg.page.wait_for_function(f"!document.getElementById('lens-{lens}').hidden")
        width = pg.page.evaluate("document.documentElement.scrollWidth")
        assert width <= 390, (lens, width)
    # the lens tabs sit at the bottom edge on a phone
    box = pg.page.eval_on_selector("[role=tablist]", "e => e.getBoundingClientRect().bottom")
    assert abs(box - 844) < 2


def test_the_tree_and_inspector_work_without_webgl(browser: Any, report_url: str) -> None:
    from playwright.sync_api import Error

    try:
        bare = browser.browser_type.launch(args=["--disable-3d-apis", "--disable-gpu"])
    except Error as exc:
        pytest.skip(f"Playwright Chromium unavailable: {exc}")
    try:
        pg = Page(bare, report_url)
        pg.page.click('#tree li[data-uri="part://top-board"] > .row')
        assert pg.title() == pg.index["part://top-board"]["title"]
        pg.page.click('#tree li[data-uri="manifest://product"] > .row')
        assert pg.title() == pg.index[PRODUCT]["title"]
        # no WebGL context at all: the pane says so (the console may carry the browser's complaint)
        pg.page.wait_for_selector("#model.off", state="attached")
        assert "cannot show the 3D view" in str(pg.page.text_content("#viewer"))
        pg.close(check=False)
    finally:
        bare.close()


def test_the_index_in_the_page_is_the_workbenchs_index(open_page: Any) -> None:
    pg = open_page()
    raw = pg.page.evaluate("document.getElementById('inspector-index').textContent")
    assert json.loads(raw) == pg.index
