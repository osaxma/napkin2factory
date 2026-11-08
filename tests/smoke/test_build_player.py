"""M3c: the build player, the cut lists on the Build lens and the print packet (S-320, B-0299).

A prebuilt test-stand report: the markup is read from the file, then a browser drives the player
from ``file://`` and emulates print media.  Browser tests skip when Chromium is unavailable.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import EXAMPLES, copy_product, real_page_errors

GL_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]


@pytest.fixture(scope="module")
def report_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = copy_product(
        EXAMPLES / "test-stand",
        tmp_path_factory.mktemp("bp") / "test-stand",
        git=False,
        prebuilt=True,
    )
    return root / "build/report/index.html"


def test_the_markup_has_the_player_the_cut_lists_and_the_print_sheet(report_file: Path) -> None:
    html = report_file.read_text(encoding="utf-8")
    assert 'id="build-player"' in html and 'data-player="next"' in html
    assert 'aria-live="polite"' in html
    assert len(re.findall(r'class="step" id="step-', html)) > 1
    assert 'data-parts="[' in html
    # a cut list with its unit named in the heading and the columns
    assert "Cut list (sizes in millimetres" in html and "length (mm)" in html
    assert "@media print" in html and "@page drawings" in html
    assert "clearHighlights" in html  # the viewer API the player calls


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


def _open(browser: Any, url: str, errors: list[str]) -> Any:
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.set_default_timeout(15000)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.wait_for_function("window.n2fWorkbench !== undefined")
    return page


def test_next_steps_the_cards_and_calls_the_viewer(browser: Any, report_file: Path) -> None:
    errors: list[str] = []
    page = _open(browser, report_file.as_uri(), errors)
    page.click("[data-lens-tab=build]")
    # a stand-in viewer records the calls (the real one needs WebGL)
    page.evaluate(
        """() => { window.__calls = [];
        window.n2fViewer = { clearHighlights() { window.__calls.push(['clear']); },
                             highlight(u, c) { window.__calls.push(['hl', u]); } }; }"""
    )
    # before any interaction every step is shown as before
    assert page.locator("#build.playing").count() == 0
    page.click("[data-player=next]")
    first = page.get_attribute("#build .step.current", "data-step")
    assert "Step 1 of" in page.inner_text("[data-player=state]")
    page.click("[data-player=next]")
    second = page.get_attribute("#build .step.current", "data-step")
    assert second != first and "Step 2 of" in page.inner_text("[data-player=state]")
    calls = page.evaluate("window.__calls")
    assert calls[-2] == ["clear"] and calls[-1][0] == "hl"
    assert all(u.startswith("part://") for u in calls[-1][1])
    # the keyboard steps back; a deep link opens the player at that step
    page.focus("[data-player=prev]")
    page.keyboard.press("ArrowLeft")
    assert page.get_attribute("#build .step.current", "data-step") == first
    page.evaluate(f"location.hash = '#step-{second}'")
    page.wait_for_function(
        f"document.querySelector('#build .step.current').dataset.step === '{second}'"
    )
    page.click("[data-player=all]")
    assert page.locator("#build.playing").count() == 0
    page.close()
    assert real_page_errors(errors) == [], errors


def test_print_shows_every_lens_and_hides_the_screen_controls(
    browser: Any, report_file: Path
) -> None:
    errors: list[str] = []
    page = _open(browser, report_file.as_uri(), errors)
    page.emulate_media(media="print")
    assert page.is_hidden("header .tabs")
    assert page.is_hidden("#tree")
    shown = page.eval_on_selector_all(".lens", "els => els.map(e => e.offsetHeight > 0)")
    assert shown and all(shown)
    page.close()
    assert real_page_errors(errors) == [], errors
