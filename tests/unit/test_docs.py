"""Manual outputs: Markdown → Typst goldens, PDF compile, HTML anchors, end-to-end docs build."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from selectolax.lexbor import LexborHTMLParser

from napkin2factory.core.loader import heading_anchor
from napkin2factory.docs.html import render_fragment, render_html
from napkin2factory.docs.typst import (
    DISCLAIMER,
    TypstError,
    compile_pdf,
    escape_text,
    markdown_to_typst,
)
from tests.conftest import EXAMPLES, copy_product

GOLDENS = Path(__file__).resolve().parent / "goldens" / "typst"
GOLDEN_MD = sorted(GOLDENS.glob("*.md"))
UPDATE = os.environ.get("N2F_UPDATE_GOLDENS") == "1"


def _pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", pdf))


def test_goldens_present() -> None:
    names = {p.stem for p in GOLDEN_MD}
    assert {
        "headings_emphasis",
        "nested_lists",
        "table",
        "code",
        "links_images",
        "blockquote_hr",
        "escaping",
    } <= names


@pytest.mark.parametrize("md_path", GOLDEN_MD, ids=lambda p: p.stem)
def test_typst_golden(md_path: Path) -> None:
    source, _ = markdown_to_typst(md_path.read_text(encoding="utf-8"), title=md_path.stem)
    expected = md_path.with_suffix(".typ")
    if UPDATE or not expected.is_file():
        expected.write_text(source, encoding="utf-8")
        pytest.skip(f"recorded golden {expected.name}")
    assert source == expected.read_text(encoding="utf-8")


@pytest.mark.parametrize("md_path", GOLDEN_MD, ids=lambda p: p.stem)
def test_golden_compiles(md_path: Path, tmp_path: Path) -> None:
    source, _ = markdown_to_typst(md_path.read_text(encoding="utf-8"), title=md_path.stem)
    pdf = compile_pdf(source, tmp_path)
    assert pdf.startswith(b"%PDF-")
    assert _pages(pdf) >= 1


def test_escape_text() -> None:
    assert escape_text("a#b") == "a\\#b"
    assert escape_text("#$*_[]@<>") == "\\#\\$\\*\\_\\[\\]\\@\\<\\>"
    assert escape_text("back\\slash") == "back\\\\slash"
    assert escape_text("`~") == "\\`\\~"
    assert escape_text("a // b /* c") == "a \\// b \\/\\* c"
    assert escape_text("1/2 mm, 100 mm") == "1/2 mm, 100 mm"
    assert escape_text("") == ""


def test_escaped_text_renders_literally(tmp_path: Path) -> None:
    source, _ = markdown_to_typst("Costs $5 #1 *x* @y <z> [w] ~v // u")
    assert compile_pdf(source, tmp_path).startswith(b"%PDF-")


def test_emitter_constructs() -> None:
    source, warnings = markdown_to_typst(
        "# H\n\n- a\n  - b\n\n| x | y |\n|---|---|\n| 1 | 2 |\n\n"
        "[l](https://e.com) `c` ~~s~~\n\n---\n"
    )
    assert "\n= H\n" in source
    assert "- a\n  - b" in source
    assert "#table(\n  columns: 2," in source
    assert "table.header([*x*], [*y*])" in source
    assert '#link("https://e.com")[l]' in source
    assert "`c`" in source and "#strike[s]" in source
    assert "#line(length: 100%)" in source
    assert source.rstrip().endswith(f'#text(size: 8pt, style: "italic")[{DISCLAIMER}]')
    assert '#set page(paper: "a4", margin: 2cm)' in source
    assert warnings == []


def test_image_fallback_and_existing(tmp_path: Path) -> None:
    import typst

    docs = tmp_path / "model" / "docs"
    (docs / "img").mkdir(parents=True)
    (docs / "img" / "dot.png").write_bytes(
        typst.compile(b"#set page(width: 1cm, height: 1cm)\n#rect()", format="png")
    )
    md = "![dot](img/dot.png)\n\n![gone](img/none.png)\n"
    source, warnings = markdown_to_typst(md, base_dir=docs, root=tmp_path)
    assert '#image("/model/docs/img/dot.png")' in source
    assert "\ngone\n" in source
    assert warnings == ["image not found, alt text used: img/none.png"]
    assert compile_pdf(source, tmp_path).startswith(b"%PDF-")
    # Without a base folder nothing can be checked, so images fall back to alt text.
    source, _ = markdown_to_typst(md)
    assert "#image" not in source


def test_unsupported_html_is_plain_text_with_warning(tmp_path: Path) -> None:
    source, warnings = markdown_to_typst('<div class="x">\nhello\n</div>\n\nA <b>bold</b> word.\n')
    assert '\\<div class="x"\\>' in source
    assert "A \\<b\\>bold\\</b\\> word." in source
    assert any("raw HTML block" in w for w in warnings)
    assert sum("raw HTML rendered as text" in w for w in warnings) == 2
    assert compile_pdf(source, tmp_path).startswith(b"%PDF-")


def test_compile_error_raises_typst_error(tmp_path: Path) -> None:
    with pytest.raises(TypstError, match="Typst compilation failed"):
        compile_pdf('#image("/does-not-exist.png")', tmp_path)


def test_render_html_anchors_tables_disclaimer() -> None:
    md = (
        "# Power & wiring\n\nText.\n\n## Fit the *lid*\n\n"
        "| a | b |\n|---|---|\n| 1 | 2 |\n\n<script>alert(1)</script>\n"
    )
    page = render_html(md, "Install", subtitle="Audience: owner", banner="SAFETY — read before use")
    tree = LexborHTMLParser(page)
    h1 = tree.css_first("h1")
    h2 = tree.css_first("h2")
    assert h1 is not None and h1.attributes["id"] == heading_anchor("Power & wiring")
    assert h1.attributes["id"] == "power-wiring"
    assert h2 is not None and h2.attributes["id"] == heading_anchor("Fit the *lid*")
    assert len(tree.css("table th")) == 2 and len(tree.css("table td")) == 2
    footer = tree.css_first("footer")
    assert footer is not None and DISCLAIMER in footer.text()
    assert tree.css_first("title").text() == "Install"  # type: ignore[union-attr]
    assert tree.css_first(".banner").text() == "SAFETY — read before use"  # type: ignore[union-attr]
    assert tree.css("script") == []  # raw HTML is escaped, not passed through
    frag = render_fragment(md)
    assert not frag.lstrip().startswith("<!doctype")
    assert 'id="power-wiring"' in frag


def test_docs_build_end_to_end(tmp_path: Path) -> None:
    from napkin2factory.core.graph.runner import run_build
    from napkin2factory.core.loader import load_product

    root = copy_product(EXAMPLES / "enclosure", tmp_path / "enclosure", git=False)
    run_build(load_product(root), target="docs", quiet=True, render=False)
    docs = root / "build" / "docs"

    page = docs / "assembly" / "page.html"
    assert page.is_file()
    tree = LexborHTMLParser(page.read_text(encoding="utf-8"))
    assert [h.attributes["id"] for h in tree.css("h1, h2")] == ["assembly", "manufacturer-note"]
    assert "100 mm" in tree.body.text()  # type: ignore[union-attr]
    assert tree.css(".banner") == []

    pdf = (docs / "assembly" / "page.pdf").read_bytes()
    assert pdf.startswith(b"%PDF-")
    assert _pages(pdf) >= 1
    assert (docs / "assembly" / "page.typ").is_file()
    assert not (docs / "assembly" / "page.pdf.error.txt").exists()
    assert (docs / "safety" / "page.pdf").read_bytes().startswith(b"%PDF-")
    assert "SAFETY — read before use" in (docs / "safety" / "page.typ").read_text(encoding="utf-8")

    safety = LexborHTMLParser((docs / "safety" / "page.html").read_text(encoding="utf-8"))
    banner = safety.css_first(".banner")
    assert banner is not None and banner.text() == "SAFETY — read before use"

    index = LexborHTMLParser((docs / "index.html").read_text(encoding="utf-8"))
    items = index.css("ul.pages li")
    assert [li.attributes["data-doc"] for li in items] == ["safety", "assembly"]
    assert "SAFETY" in items[0].text()
    hrefs = [a.attributes["href"] for a in index.css("ul.pages a")]
    assert hrefs == [
        "safety/page.html",
        "safety/page.pdf",
        "assembly/page.html",
        "assembly/page.pdf",
    ]
