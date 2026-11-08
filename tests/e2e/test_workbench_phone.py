"""M4: the workbench on a phone, 390 x 844 with touch (decision V8, S-324; Track C 3.5).

A prebuilt table report: the dock and the bottom sheets (parts list, inspector, 3D controls), the
focus rules, the touch targets, the compact top bar, and that nothing scrolls sideways.  The sheets
and the dock must not need WebGL, so only the 3D pane's own checks need it (none here do).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from tests.conftest import EXAMPLES, copy_product, real_page_errors

GL_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]
PRODUCT = "manifest://product"
W, H = 390, 844
SHEETS = {"tree": "#tree", "inspector": "#inspector", "view": "#view-panel"}


@pytest.fixture(scope="module")
def report_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    root = copy_product(
        EXAMPLES / "table", tmp_path_factory.mktemp("wbp") / "table", git=False, prebuilt=True
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


class Phone:
    """A phone-sized page on the report that collects its errors."""

    def __init__(self, browser: Any, url: str, width: int = W, height: int = H) -> None:
        self.errors: list[str] = []
        phone = width < 768
        self.ctx = browser.new_context(
            viewport={"width": width, "height": height}, has_touch=phone, is_mobile=phone
        )
        self.page = self.ctx.new_page()
        self.page.set_default_timeout(15000)
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        self.page.goto(url)
        self.page.wait_for_function("window.n2fWorkbench !== undefined")
        self.index: dict[str, Any] = self.page.evaluate("window.n2fWorkbench.index")

    def sheet(self) -> str:
        return str(self.page.get_attribute(".wb", "data-sheet"))

    def open(self, name: str) -> None:
        self.page.tap(f"[data-sheet-open={name}]")
        self.page.wait_for_selector(SHEETS[name], state="visible")

    def title(self) -> str:
        return str(self.page.text_content("#inspector-title")).strip()

    def size(self, selector: str) -> tuple[float, float]:
        box = self.page.eval_on_selector(
            selector, "e => { const r = e.getBoundingClientRect(); return [r.width, r.height]; }"
        )
        return float(box[0]), float(box[1])

    def close(self, check: bool = True) -> None:
        self.ctx.close()
        if check:
            assert real_page_errors(self.errors) == [], self.errors


@pytest.fixture
def phone(browser: Any, report_url: str) -> Iterator[Any]:
    opened: list[Phone] = []

    def make(fragment: str = "", **kw: int) -> Phone:
        pg = Phone(browser, report_url + fragment, **kw)
        opened.append(pg)
        return pg

    yield make
    for pg in opened:
        pg.close()


def test_the_dock_is_the_only_panel_chrome_and_desktop_has_none(phone: Any) -> None:
    pg = phone()
    names = pg.page.eval_on_selector_all(
        ".dock [data-sheet-open]", "els => els.map(e => e.dataset.sheetOpen)"
    )
    assert names == ["tree", "inspector", "view"]
    assert pg.page.get_attribute(".dock", "role") == "group"
    assert pg.sheet() == "none"
    for sel in SHEETS.values():
        assert pg.page.is_hidden(sel), sel
    assert pg.page.text_content("#dock-details").strip() == "Product"
    # the 3D pane takes the screen, whatever WebGL does
    assert pg.size("#model")[1] >= 0.55 * H
    # a wide screen shows neither the dock nor a sheet head, and its three panes as before
    wide = phone(width=1440, height=900)
    assert wide.page.is_hidden(".dock") and wide.page.is_hidden(".sheet-head")
    assert wide.page.is_visible("#tree") and wide.page.is_visible("#inspector")
    assert wide.page.is_hidden(".hdr-toggle") and wide.page.is_visible("#hdr-vitals")


def test_parts_sheet_then_a_part_shows_its_inspector(phone: Any) -> None:
    pg = phone()
    pg.open("tree")
    assert pg.sheet() == "tree"
    assert pg.page.get_attribute("[data-sheet-open=tree]", "aria-expanded") == "true"
    assert pg.size('#tree li[data-uri="part://apron-frame"] > .row')[1] >= 44
    pg.page.tap('#tree li[data-uri="part://apron-frame"] > .row')
    pg.page.wait_for_selector("#tree", state="hidden")
    title = pg.index["part://apron-frame"]["title"]
    assert pg.sheet() == "inspector"
    assert pg.page.is_visible("#inspector")
    assert pg.page.text_content("#inspector-sheet-title").strip() == title
    assert title in pg.page.text_content("[data-sheet-open=inspector]")
    assert pg.page.get_attribute("[data-sheet-open=inspector]", "aria-expanded") == "true"
    assert pg.page.get_attribute("[data-sheet-open=tree]", "aria-expanded") == "false"
    # focus moves into the sheet, to its Close button
    assert pg.page.evaluate("document.activeElement.hasAttribute('data-sheet-close')")
    # the viewer's click on empty space (what it sends: uri null) closes it and shows the product
    pg.page.evaluate(
        "document.getElementById('viewer').dispatchEvent("
        "new CustomEvent('n2f:select', {detail: {uri: null}}))"
    )
    pg.page.wait_for_selector("#inspector", state="hidden")
    assert pg.sheet() == "none"
    assert pg.page.text_content("#dock-details").strip() == "Product"
    # a pick of a part opens it again, and focus goes back to the 3D pane when it closes
    pg.page.evaluate(
        "document.getElementById('viewer').dispatchEvent("
        "new CustomEvent('n2f:select', {detail: {uri: 'part://top-board'}}))"
    )
    pg.page.wait_for_selector("#inspector", state="visible")
    assert (
        pg.page.text_content("#inspector-sheet-title").strip()
        == (pg.index["part://top-board"]["title"])
    )
    pg.page.keyboard.press("Escape")
    pg.page.wait_for_selector("#inspector", state="hidden")
    assert pg.page.evaluate("document.activeElement.id") == "model"


def test_escape_and_close_return_focus_to_the_dock_button(phone: Any) -> None:
    pg = phone()
    for name in ("tree", "view"):
        pg.open(name)
        assert pg.page.evaluate("document.activeElement.hasAttribute('data-sheet-close')")
        pg.page.keyboard.press("Escape")
        pg.page.wait_for_selector(SHEETS[name], state="hidden")
        assert pg.sheet() == "none"
        assert pg.page.evaluate("document.activeElement.dataset.sheetOpen") == name
        assert pg.page.get_attribute(f"[data-sheet-open={name}]", "aria-expanded") == "false"
    pg.open("inspector")
    pg.page.tap("#inspector [data-sheet-close]")
    pg.page.wait_for_selector("#inspector", state="hidden")
    assert pg.page.evaluate("document.activeElement.dataset.sheetOpen") == "inspector"
    # the dock button toggles, and only one sheet is open at a time
    pg.open("tree")
    pg.page.tap("#tree [data-sheet-close]")
    pg.open("view")
    pg.page.tap("[data-sheet-open=view]")
    pg.page.wait_for_selector("#view-panel", state="hidden")
    assert pg.sheet() == "none"


def test_closed_sheets_cannot_be_reached_by_keyboard(phone: Any) -> None:
    pg = phone()
    stray = pg.page.evaluate(
        """() => ['#tree', '#inspector', '#view-panel'].flatMap(s =>
          [...document.querySelectorAll(
            [' a[href]', ' button', ' input', ' [tabindex]'].map(t => s + t).join(','))]
            .filter(e => getComputedStyle(e).visibility !== 'hidden')
            .map(e => s + ' ' + e.tagName))"""
    )
    assert stray == []
    pg.page.focus("[data-sheet-open=tree]")
    seen = []
    for _ in range(14):
        pg.page.keyboard.press("Tab")
        seen.append(
            pg.page.evaluate("!!document.activeElement.closest('#tree,#inspector,#view-panel')")
        )
    assert not any(seen)
    # an open sheet is a labelled region, not a trap: Tab leaves it
    pg.open("tree")
    assert pg.page.get_attribute("#tree", "role") == "region"
    assert pg.page.get_attribute("#tree", "aria-label")


def test_a_deep_link_opens_the_inspector_and_a_bare_load_opens_none(phone: Any) -> None:
    pg = phone("#select=part://top-board")
    pg.page.wait_for_selector("#inspector", state="visible")
    assert pg.sheet() == "inspector"
    assert pg.title() == pg.index["part://top-board"]["title"]
    assert phone().sheet() == "none"
    # a "Go to" link in the sheet leaves for another lens and takes the sheet with it
    pg.page.tap("#inspector-entry a[href^='#drawing']")
    pg.page.wait_for_function("document.getElementById('lens-workbench').hidden")
    assert pg.sheet() == "none"


def test_a_lens_change_closes_the_sheet(phone: Any) -> None:
    pg = phone()
    pg.open("tree")
    pg.page.tap("#tab-verification")
    pg.page.wait_for_function("document.getElementById('lens-workbench').hidden")
    assert pg.sheet() == "none"
    pg.page.tap("#tab-workbench")
    pg.page.wait_for_function("!document.getElementById('lens-workbench').hidden")
    assert pg.sheet() == "none" and pg.page.is_hidden("#tree")


def test_touch_targets_are_at_least_44_px(phone: Any) -> None:
    pg = phone()
    boxes = {
        "tab": pg.page.eval_on_selector_all(
            "[role=tab]", "els => els.map(e => [e.offsetWidth, e.offsetHeight])"
        ),
        "dock": pg.page.eval_on_selector_all(
            ".dock button", "els => els.map(e => [e.offsetWidth, e.offsetHeight])"
        ),
        "header": [pg.size(".hdr-toggle")],
    }
    for name in ("tree", "inspector", "view"):
        pg.open(name)
        boxes[f"close {name}"] = [pg.size(f"{SHEETS[name]} [data-sheet-close]")]
        if name == "view":
            boxes["view buttons"] = pg.page.eval_on_selector_all(
                "#view-panel button",
                "els => els.filter(e => e.offsetParent).map(e => [e.offsetWidth, e.offsetHeight])",
            )
        pg.page.keyboard.press("Escape")
        pg.page.wait_for_selector(SHEETS[name], state="hidden")
    for name, items in boxes.items():
        assert items, name
        for w, h in items:
            assert w >= 44 and h >= 44, (name, w, h)


def test_the_top_bar_keeps_its_details_behind_a_button(phone: Any) -> None:
    pg = phone()
    toggle = "header.top .hdr-toggle"
    assert pg.page.get_attribute(toggle, "aria-expanded") == "false"
    assert pg.page.get_attribute(toggle, "aria-controls") == "hdr-vitals hdr-counts"
    assert pg.page.is_hidden("#hdr-vitals") and pg.page.is_hidden("#hdr-counts")
    assert pg.page.is_visible("header.top h1")
    pg.page.tap(toggle)
    assert pg.page.get_attribute(toggle, "aria-expanded") == "true"
    assert pg.page.is_visible("#hdr-vitals") and pg.page.is_visible("#hdr-counts")
    pg.page.tap(toggle)
    assert pg.page.is_hidden("#hdr-vitals")
    # the pane still fills what the bar leaves
    assert pg.size("#model")[1] >= 0.55 * H


def test_nothing_scrolls_sideways_with_a_sheet_open(phone: Any) -> None:
    pg = phone()
    for name in ("tree", "inspector", "view"):
        pg.open(name)
        width = pg.page.evaluate("document.documentElement.scrollWidth")
        assert width <= W, (name, width)
        right = pg.page.eval_on_selector(SHEETS[name], "e => e.getBoundingClientRect().right")
        assert right <= W + 1, (name, right)
        pg.page.keyboard.press("Escape")
        pg.page.wait_for_selector(SHEETS[name], state="hidden")
    for lens in pg.page.eval_on_selector_all(
        "[role=tab]", "els => els.map(e => e.dataset.lensTab)"
    ):
        pg.page.evaluate(f"location.hash = '#lens={lens}'")
        pg.page.wait_for_function(f"!document.getElementById('lens-{lens}').hidden")
        assert pg.page.evaluate("document.documentElement.scrollWidth") <= W, lens
    # a sheet open on the inspector of a part with a long table
    pg2 = phone("#select=part://apron-frame")
    pg2.page.wait_for_selector("#inspector", state="visible")
    assert pg2.page.evaluate("document.documentElement.scrollWidth") <= W


def test_the_sheets_work_without_webgl(browser: Any, report_url: str) -> None:
    from playwright.sync_api import Error

    try:
        bare = browser.browser_type.launch(args=["--disable-3d-apis", "--disable-gpu"])
    except Error as exc:
        pytest.skip(f"Playwright Chromium unavailable: {exc}")
    try:
        pg = Phone(bare, report_url)
        pg.page.wait_for_selector("#model.off", state="attached")
        assert "cannot show the 3D view" in str(pg.page.text_content("#viewer"))
        assert pg.page.is_hidden("[data-sheet-open=view]")
        assert pg.page.is_visible("[data-sheet-open=tree]")
        pg.open("tree")
        pg.page.tap('#tree li[data-uri="part://top-board"] > .row')
        pg.page.wait_for_selector("#inspector", state="visible")
        assert (
            pg.page.text_content("#inspector-sheet-title").strip()
            == (pg.index["part://top-board"]["title"])
        )
        pg.page.keyboard.press("Escape")
        pg.page.wait_for_selector("#inspector", state="hidden")
        pg.close(check=False)
    finally:
        bare.close()
