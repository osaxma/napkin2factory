"""M5 report (D13, D17): self-contained, every URI and REQ id present, file:// smoke."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from selectolax.lexbor import LexborHTMLParser

from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES, copy_product

EXTERNAL = re.compile(r"\b(?:src|href)\s*=\s*['\"]?(?:https?:)?//", re.IGNORECASE)


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    root = copy_product(
        EXAMPLES / "enclosure", tmp_path_factory.mktemp("rep") / "enclosure", git=False
    )
    run_build(load_product(root), quiet=True, render=True)
    path = root / "build/report/index.html"
    return root, path.read_text(encoding="utf-8")


def test_self_contained(report: tuple[Path, str]) -> None:
    root, html = report
    tree = LexborHTMLParser(html)
    assert not tree.css("script[src]")
    assert not tree.css("link[rel=stylesheet]")
    assert not tree.css("link")
    assert not EXTERNAL.search(html), "external reference found"
    assert all(
        s.attributes.get("type") in ("module", "text/plain")
        for s in tree.css("script")
        if s.attributes.get("type")
    )
    modules = [s for s in tree.css("script") if s.attributes.get("type") == "module"]
    assert len(modules) == 1
    body = modules[0].text()
    assert not re.search(r"^\s*import\s.*from\s", body, re.MULTILINE)
    assert "n2fCreateViewer" in body and "GLTFLoader" in body
    size = (root / "build/report/index.html").stat().st_size
    assert size <= 20 * 1024 * 1024
    meta = json.loads((root / "build/report/report.json").read_text())
    assert meta["within_budget"] is True


def test_every_uri_and_requirement_present(report: tuple[Path, str]) -> None:
    root, html = report
    product = load_product(root)
    for p in product.parts.values():
        assert p.uri in html, p.uri
    for r in product.requirements:
        assert f'id="req-{r}"' in html, r
    for d in product.decisions:
        assert d in html
    assert (
        'id="glb-data"' in html
        and len(html.split('id="glb-data">', 1)[1].split("</script>", 1)[0]) > 1000
    )
    assert "data-n2f-glb" in html
    assert 'id="drawing-base"' in html and "<svg" in html
    assert "Disclaimer" in html and "not been reviewed by a licensed engineer" in html


def test_persona_toggle_and_safety_visibility(report: tuple[Path, str]) -> None:
    _, html = report
    tree = LexborHTMLParser(html)
    assert tree.css_first("#btn-owner") is not None and tree.css_first("#btn-engineer") is not None
    assert "html[data-persona=owner] #sec-3d{order:2}" in html
    assert "html[data-persona=engineer] #sec-checks{order:2}" in html
    safety = tree.css_first("#sec-safety")
    assert safety is not None
    assert "owner-only" not in (safety.attributes.get("class") or "") and "engineer-only" not in (
        safety.attributes.get("class") or ""
    )
    assert "html[data-persona=owner] #sec-safety{order:0}" in html
    assert "Sheet edges are sharp" in safety.text()
    # vocabulary swaps: owner words for statuses are present in the owner default view
    assert "needs your sign-off" in html


def test_example_signoff_label(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=True)
    run_build(load_product(root), target="checks", quiet=True, render=False)
    from tests.conftest import n2f

    r = n2f(
        "signoff",
        "REQ-004",
        "--by",
        "Example Reviewer",
        "--statement",
        "Edges checked.",
        "--example",
        cwd=root,
    )
    assert r.returncode == 0, r.stderr
    run_build(load_product(root), quiet=True, render=False)
    html = (root / "build/report/index.html").read_text()
    assert html.count("EXAMPLE SIGN-OFF, NOT A REVIEW") >= 2
    tree = LexborHTMLParser(html)
    header = tree.css_first("header.top").text()
    # the header never presents an example sign-off as verification
    assert "1 example sign-off — not a review" in header
    assert "0 needs your sign-off" not in header and "signed off" not in header
    assert tree.css_first("header.top span.example") is not None
    # the ladder shows verify as not done, with that reason, and the next step to fix it
    nxt = tree.css_first("#sec-next").text()
    assert "1 example sign-off — not a review" in nxt
    assert "replace the 1 example sign-off (not a review) with a real one" in nxt
    assert "allow-example-signoffs" in nxt
    gates = tree.css("#sec-next .kv .badge")
    verify_badge = next(b for b in gates if b.text() == "verify")
    assert "ok" not in (verify_badge.attributes.get("class") or "").split()
    # both personas carry words for it
    assert "example sign-off — not a review" in html.split("<header", 1)[1].split("</header>", 1)[0]


def test_report_opens_from_file_url_without_console_errors(report: tuple[Path, str]) -> None:
    pytest.importorskip("playwright")
    from playwright.sync_api import Error, sync_playwright

    root, _ = report
    path = root / "build/report/index.html"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]
            )
    except Error as exc:
        pytest.skip(f"Playwright Chromium unavailable: {exc}")
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(path.as_uri())
        nodes = page.evaluate("window.n2fViewerReady.then(() => window.n2fViewer.nodes())")
        counts = page.evaluate(
            "Object.fromEntries(window.n2fViewer.nodes()"
            ".map(u => [u, window.n2fViewer.instanceCount(u)]))"
        )
        page.click("#btn-engineer")
        persona = page.evaluate("document.documentElement.getAttribute('data-persona')")
        page.evaluate("window.n2fViewer.select('part://lid')")
        card = page.inner_text("#part-card")
        page.evaluate(
            "window.n2fViewer.explode(1); window.n2fViewer.section(true); "
            "window.n2fViewer.section(false)"
        )
        browser.close()
    assert errors == [], errors
    assert nodes == ["part://base", "part://bracket", "part://lid"]
    assert counts == {"part://base": 1, "part://bracket": 2, "part://lid": 1}
    assert persona == "engineer"
    assert "part://lid" in card and "Lid" in card


def test_revision_label_is_honest(tmp_path: Path) -> None:
    """An edited model is never labelled with the Revision it no longer matches (gate-2 B4)."""
    from napkin2factory.core.vcs import Vcs
    from napkin2factory.report.builder import gather

    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=True)
    run_build(load_product(root), quiet=True, render=False)
    v = Vcs(root)
    v.snapshot("built")
    v.tag("v1.0.0", "r")
    assert (
        gather(load_product(root), root / "build", "2026-10-30")["revision_label"]
        == "Revision v1.0.0"
    )
    params = root / "model/parameters.yaml"
    params.write_text(
        params.read_text().replace(
            "bracket-width:     {value: 60,", "bracket-width:     {value: 70,"
        )
    )
    label = gather(load_product(root), root / "build", "2026-10-30")["revision_label"]
    assert label == "draft — changed since Revision v1.0.0"
