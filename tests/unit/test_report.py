"""M5 report (D13, D17 as amended by S-052): self-contained, every URI and REQ id present,
one layout with a section index and in-page links (no persona toggle), file:// smoke.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from selectolax.lexbor import LexborHTMLParser

from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product
from napkin2factory.core.model import StyleFile
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


def test_navigation_and_links_without_toggle(report: tuple[Path, str]) -> None:
    from napkin2factory.report.builder import SECTIONS

    _, html = report
    tree = LexborHTMLParser(html)
    assert tree.css_first("#btn-owner") is None and tree.css_first("#btn-engineer") is None
    nav = {a.attributes.get("data-sec") for a in tree.css("nav.side a[data-sec]")}
    assert {sid for sid, _, _ in SECTIONS} <= nav
    cards = [s.attributes.get("id") for s in tree.css("main > section.card")]
    assert cards and all(c in nav for c in cards), cards
    # safety is always on the page, never inside a collapsed or hidden container
    safety = tree.css_first("#safety")
    assert safety is not None
    assert "Sheet edges are sharp" in safety.text()
    node = safety
    while node is not None and node.tag != "html":
        attrs = node.attributes
        assert "hidden" not in attrs, node.tag
        assert "display:none" not in (attrs.get("style") or "").replace(" ", ""), node.tag
        assert node.tag != "details" or "open" in attrs, "safety inside a collapsed <details>"
        node = node.parent
    # every model URI that has a row on the page links to it
    ids = {n.attributes.get("id") for n in tree.css("[id]")}
    refs = tree.css("a.ref")
    assert tree.css('a.ref[href^="#req-"]') and tree.css('a.ref[href^="#part-"]')
    for a in refs:
        href = a.attributes.get("href") or ""
        assert href.startswith("#") and href[1:] in ids, href
    # owner words are the default persona
    assert "needs your sign-off" in html


def test_anchor_for() -> None:
    from napkin2factory.report.builder import anchor_for

    anchors = {"req://REQ-001": "req-REQ-001", "part://lid": "part-lid"}
    assert anchor_for("req://REQ-001#statement", anchors) == "req-REQ-001"
    assert anchor_for("part://lid", anchors) == "part-lid"
    assert anchor_for("req://REQ-999", anchors) == "requirements"
    assert anchor_for("rule://sheet.min-flange#part://lid", anchors) == "rules"
    assert anchor_for("nope://x", anchors) is None
    assert anchor_for("plain text", anchors) is None


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
    nxt = tree.css_first("#overview").text()
    assert "1 example sign-off — not a review" in nxt
    assert "replace the 1 example sign-off (not a review) with a real one" in nxt
    assert "allow-example-signoffs" in nxt
    gates = tree.css("#stage .badge")
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
        # a product without style.yaml keeps the hash colours: no viewer options at all (M3)
        assert page.get_attribute("#viewer", "data-n2f-options") is None
        page.click('a[data-show3d="part://lid"]')
        card = page.inner_text("#part-card")
        card_links = page.eval_on_selector_all(
            "#part-card a", "els => els.map(e => e.getAttribute('href'))"
        )
        page.evaluate(
            "window.n2fViewer.explode(1); window.n2fViewer.section(true); "
            "window.n2fViewer.section(false)"
        )
        browser.close()
    assert errors == [], errors
    assert nodes == ["part://base", "part://bracket", "part://lid"]
    assert counts == {"part://base": 1, "part://bracket": 2, "part://lid": 1}
    assert "part://lid" in card and "Lid" in card
    assert "#drawing-lid" in card_links, card_links


def test_report_viewer_paints_the_style_palette_by_role(tmp_path: Path) -> None:
    """⤵ M3: with style.yaml the viewer colours parts by role instead of hash colours."""
    pytest.importorskip("playwright")
    from playwright.sync_api import Error, sync_playwright

    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=False)
    base = root / "model" / "parts" / "base.yaml"
    base.write_text(base.read_text() + "role: body\n")
    (root / "style.yaml").write_text("preset: lab\npalette: {body: '#c0392b'}\n")
    run_build(load_product(root), quiet=True, render=False)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]
            )
            page = browser.new_page()
            page.goto((root / "build/report/index.html").as_uri())
            colours = page.evaluate(
                "window.n2fViewerReady.then(() => { const out = {};"
                " window.n2fViewer.scene.traverse(o => { if (o.isMesh && o.userData.n2f_uri)"
                " out[o.userData.n2f_uri] = '#' + o.material.color.getHexString(); });"
                " return out; })"
            )
            browser.close()
    except Error as exc:
        pytest.skip(f"Playwright Chromium unavailable: {exc}")
    assert colours["part://base"] == "#c0392b"  # role body → the file's body colour
    lab = StyleFile.model_validate({"preset": "lab"}).resolved()
    assert colours["part://lid"] == lab.palette["default"]  # no role → the default role


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


def _visible_uri_texts(tree: LexborHTMLParser) -> dict[str, list[str]]:
    """The human-readable places a model URI shows up on the page."""
    return {
        "bom": [td.text(strip=True) for td in tree.css("#bom tbody tr > td:first-child")],
        "refs": [a.text(strip=True) for a in tree.css("main a.ref")],
        "params": [td.text(strip=True) for td in tree.css("#parameters tbody tr > td:first-child")],
        "captions": [f.text(strip=True) for f in tree.css("#drawings figcaption")],
    }


def test_owner_tables_drop_uri_prefixes(report: tuple[Path, str]) -> None:
    """B-0008: the owner reads ``base``, not ``part://base``; attributes keep the full URI."""
    _, html = report
    tree = LexborHTMLParser(html)
    assert tree.css_first("html").attributes.get("data-persona") == "owner"
    texts = _visible_uri_texts(tree)
    assert all(texts.values()), texts
    for where, cells in texts.items():
        for cell in cells:
            assert "://" not in cell, f"{where}: {cell!r}"
    assert "base" in texts["bom"] and "box-height" in texts["params"]
    data_uris = [tr.attributes.get("data-uri") for tr in tree.css("#bom tbody tr")]
    assert data_uris and all(u and u.startswith(("part://", "asm://")) for u in data_uris)
    assert all(a.attributes.get("href", "").startswith("#") for a in tree.css("main a.ref"))
    assert 'data-show3d="part://lid"' in html


def test_engineer_tables_keep_uri_prefixes(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=False)
    op = root / "operator.yaml"
    op.write_text(op.read_text().replace("persona: owner", "persona: engineer"))
    run_build(load_product(root), quiet=True, render=False)
    tree = LexborHTMLParser((root / "build/report/index.html").read_text(encoding="utf-8"))
    assert tree.css_first("html").attributes.get("data-persona") == "engineer"
    texts = _visible_uri_texts(tree)
    assert "part://base" in texts["bom"]
    assert "param://box-height" in texts["params"]
    assert any("://" in t for t in texts["refs"]), texts["refs"]
    assert all(c.startswith("part://") for c in texts["captions"]), texts["captions"]
