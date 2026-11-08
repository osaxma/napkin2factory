"""End-to-end browser interaction tests for the report workbench (V9, S-196).

Drives the interactive workbench page from ``file://`` on the three example tiers (table,
test-stand, kiln): the tree and inspector, 3D selection, deep links, the build player,
full-screen drawings with pan/zoom, and self-contained bundle limits.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import EXAMPLES, copy_product, real_page_errors

GL_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]

TIERS = [
    pytest.param("table"),
    # tiers 2 and 3 run in make check-full: each prebuild is slow, S-196, V9
    pytest.param("test-stand", marks=pytest.mark.full),
    pytest.param("kiln", marks=pytest.mark.full),
]


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


@pytest.fixture(scope="module", params=TIERS)
def report_data(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> tuple[str, Path, str]:
    tier: str = request.param
    root = copy_product(
        EXAMPLES / tier,
        tmp_path_factory.mktemp(f"wb-{tier}") / tier,
        git=False,
        prebuilt=True,
    )
    report_file = root / "build/report/index.html"
    return (report_file.as_uri(), report_file, tier)


@pytest.fixture
def report_url(report_data: tuple[str, Path, str]) -> str:
    return report_data[0]


@pytest.fixture
def report_file(report_data: tuple[str, Path, str]) -> Path:
    return report_data[1]


@pytest.fixture
def tier_name(report_data: tuple[str, Path, str]) -> str:
    return report_data[2]


class Page:
    """A page on the report workbench that collects its errors."""

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


def test_the_tree_lists_every_part_and_assembly(open_page: Any) -> None:
    pg = open_page()
    parts_and_asms = [
        uri for uri, entry in pg.index.items() if entry.get("kind") in ("part", "assembly")
    ]
    assert len(parts_and_asms) > 0
    tree_uris = set(
        pg.page.eval_on_selector_all(
            "#tree li[data-uri]", "els => els.map(e => e.getAttribute('data-uri'))"
        )
    )
    missing = [uri for uri in parts_and_asms if uri not in tree_uris]
    assert not missing, f"Missing parts or assemblies in tree: {missing}"


def test_picks_in_the_tree_show_the_index_in_the_inspector(open_page: Any) -> None:
    pg = open_page()
    candidates = [
        uri for uri, entry in pg.index.items() if entry.get("kind") in ("part", "assembly")
    ]
    assert len(candidates) > 0

    if len(candidates) <= 12:
        sample_uris = candidates
    else:
        n = len(candidates)
        indices = [int(round(i * (n - 1) / 11)) for i in range(12)]
        sample_uris = [candidates[i] for i in indices]

    # Ensure all tree groups are expanded so every row can be clicked
    pg.page.evaluate(
        'document.querySelectorAll("#tree li[aria-expanded=false]")'
        '.forEach(li => li.setAttribute("aria-expanded", "true"))'
    )

    for uri in sample_uris:
        entry = pg.index[uri]
        pg.page.locator(f'#tree li[data-uri="{uri}"] > .row').first.click()
        assert pg.title() == entry["title"]
        assert pg.page.evaluate("location.hash") == f"#lens=workbench&select={uri}"
        entry_text = str(pg.page.text_content("#inspector-entry"))
        if entry.get("mass"):
            assert entry["mass"] in entry_text
        if entry.get("mass_label"):
            assert entry["mass_label"] in entry_text
        if entry.get("cost"):
            assert entry["cost"] in entry_text
        if entry.get("cost_label"):
            assert entry["cost_label"] in entry_text


def test_a_pick_in_3d_selects_and_the_tree_mirrors_it(open_page: Any) -> None:
    pg = open_page()
    pg.page.evaluate("window.n2fViewerReady")
    if pg.page.evaluate("window.n2fViewer.glState") == "unavailable":
        pytest.skip("WebGL unavailable on this host (S-232)")
    nodes = pg.page.evaluate("window.n2fViewer.nodes()")
    part_uris = [u for u in nodes if u.startswith("part://")]
    if not part_uris:
        pytest.skip("No part nodes available in 3D viewer")
    part_uri = part_uris[0]
    pg.page.evaluate(f"window.n2fViewer.select({json.dumps(part_uri)})")
    assert pg.title() == pg.index[part_uri]["title"]
    assert pg.page.get_attribute(f'#tree li[data-uri="{part_uri}"]', "aria-selected") == "true"

    other_uri = (
        part_uris[1]
        if len(part_uris) > 1
        else next(
            (u for u, e in pg.index.items() if e.get("kind") == "part" and u != part_uri), part_uri
        )
    )
    pg.page.locator(f'#tree li[data-uri="{other_uri}"] > .row').first.click()
    assert pg.title() == pg.index[other_uri]["title"]
    assert pg.page.evaluate(f"window.n2fViewer.nodes().includes({json.dumps(other_uri)})")


def test_a_deep_link_opens_lens_and_entry(open_page: Any) -> None:
    pg0 = open_page()
    part_uri = next(u for u, e in pg0.index.items() if e.get("kind") == "part")
    pg = open_page(f"#lens=build&select={part_uri}")
    assert pg.visible_lens() == ["build"]
    assert pg.page.get_attribute("#tab-build", "aria-selected") == "true"
    assert pg.title() == pg.index[part_uri]["title"]
    assert pg.page.evaluate("window.n2fWorkbench.current()") == part_uri


def test_the_build_player_steps_and_the_deep_link_follows(open_page: Any) -> None:
    pg = open_page()
    pg.page.click("[data-lens-tab=build]")
    pg.page.wait_for_function("!document.getElementById('lens-build').hidden")

    # A stand-in viewer records calls (real one needs WebGL)
    pg.page.evaluate(
        """() => { window.__calls = [];
        window.n2fViewer = { clearHighlights() { window.__calls.push(['clear']); },
                             highlight(u, c) { window.__calls.push(['hl', u]); } }; }"""
    )

    assert pg.page.locator("#build.playing").count() == 0

    total_steps = pg.page.locator("#build .step[data-step]").count()
    assert total_steps >= 1

    pg.page.click("[data-player=next]")
    first = pg.page.get_attribute("#build .step.current", "data-step")
    assert "Step 1 of" in pg.page.inner_text("[data-player=state]")

    calls = pg.page.evaluate("window.__calls")
    assert calls[-2] == ["clear"] and calls[-1][0] == "hl"
    assert all(u.startswith("part://") for u in calls[-1][1])

    if total_steps > 1:
        pg.page.click("[data-player=next]")
        second = pg.page.get_attribute("#build .step.current", "data-step")
        assert second != first
        assert "Step 2 of" in pg.page.inner_text("[data-player=state]")
        target_step = second
    else:
        target_step = first

    pg.page.evaluate(f"location.hash = '#step-{target_step}'")
    pg.page.wait_for_function(
        f"document.querySelector('#build .step.current').dataset.step === '{target_step}'"
    )

    pg.page.click("[data-player=all]")
    assert pg.page.locator("#build.playing").count() == 0


def test_a_drawing_opens_full_screen_and_zooms(open_page: Any, tier_name: str) -> None:
    pg = open_page("#lens=drawings")
    card = pg.page.locator("[data-pzcard]").first
    card.wait_for(state="visible")
    opener = card.locator("button.pz-open")
    opener.click()

    dlg = pg.page.get_by_role("dialog")
    dlg.wait_for(state="visible")
    assert dlg.get_attribute("aria-modal") == "true"
    pg.page.wait_for_function("document.querySelector('.pzv-view svg')")

    before = pg.page.locator(".pzv-view svg").bounding_box()["width"]
    dlg.get_by_role("button", name="Zoom in").click()
    assert pg.page.locator(".pzv-view svg").bounding_box()["width"] > before

    dlg.get_by_role("button", name="Close").click()
    assert pg.page.locator(".pzv").is_hidden()
    assert opener.evaluate("e => e === document.activeElement")

    if tier_name == "test-stand":
        wcard = pg.page.locator("section[id^=wiring] [data-pzcard]").first
        wopener = wcard.locator("button.pz-open")
        wopener.click()
        dlg.wait_for(state="visible")
        pg.page.wait_for_function("document.querySelector('.pzv-view svg')")
        dlg.get_by_role("button", name="Zoom in").click()
        left0 = pg.page.locator(".pzv-view svg").bounding_box()["x"]
        pg.page.locator(".pzv-view").focus()
        pg.page.keyboard.press("ArrowLeft")
        assert pg.page.locator(".pzv-view svg").bounding_box()["x"] > left0
        dlg.get_by_role("button", name="Close").click()
        assert pg.page.locator(".pzv").is_hidden()
        assert wopener.evaluate("e => e === document.activeElement")


def test_the_report_stays_self_contained_and_small(open_page: Any, report_file: Path) -> None:
    assert report_file.stat().st_size <= 20 * 1024 * 1024
    html = report_file.read_text(encoding="utf-8")
    assert 'src="http' not in html
    assert 'href="http' not in html
    assert "url(http" not in html

    pg = open_page()
    tabs = pg.page.eval_on_selector_all("[role=tab]", "els => els.map(e => e.dataset.lensTab)")
    panels = pg.page.eval_on_selector_all("[role=tabpanel]", "els => els.map(e => e.dataset.lens)")
    assert len(tabs) == len(panels)
    assert len(tabs) == 5
