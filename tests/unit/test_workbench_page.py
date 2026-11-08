"""M3a: the workbench page's structure (decisions V1, V2, V6, V7): one panel per lens with a
shown section, each section in its lens's panel, the counts line in words, and every anchor in
``docs/report-anchors.md`` on a built page inside the lens it names.

The page is the table's report (a prebuilt copy) and the electrical fixture's (the wiring and
its anchors, a domain's section); the behaviour of the tree, the inspector and the links is the
smoke test's (``tests/smoke/test_workbench_smoke.py``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from selectolax.lexbor import LexborHTMLParser

from napkin2factory.core.domain import LENSES
from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product
from napkin2factory.core.registry import Registry, registry
from napkin2factory.report import builder
from tests.conftest import EXAMPLES, FIXTURES, copy_product

ROOT = Path(__file__).resolve().parents[2]
ANCHORS_DOC = ROOT / "docs" / "report-anchors.md"
TEMPLATE = ROOT / "src" / "napkin2factory" / "report" / "templates" / "report.html.j2"
WORKBENCH_JS = ROOT / "src" / "napkin2factory" / "report" / "workbench.js"

#: Ids the page has for its own machinery, not as link targets (the doc says so too).
CONTROLS = re.compile(
    r"^(viewer(-.+)?|glb-data(-.+)?|explode|section|section-axis|section-offset|fit|show-all|"
    r"tree|inspector(-.+)?|lens-.+|tab-.+|req-table|req-open-only)$"
)


@pytest.fixture(scope="module")
def table(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """The table's built report (a prebuilt copy: read only)."""
    root = copy_product(
        EXAMPLES / "table", tmp_path_factory.mktemp("wb") / "table", git=False, prebuilt=True
    )
    return root, (root / "build/report/index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def wired(tmp_path_factory: pytest.TempPathFactory) -> str:
    """A report with a domain's section (the electrical fixture's wiring)."""
    root = copy_product(
        FIXTURES / "electrical" / "minimal", tmp_path_factory.mktemp("wbe") / "hb", git=False
    )
    run_build(load_product(root), quiet=True, render=False)
    return (root / "build/report/index.html").read_text(encoding="utf-8")


def _holder(node: Any) -> str | None:
    """The lens of the panel holding ``node``."""
    while node is not None:
        if node.attributes.get("data-lens"):
            return str(node.attributes["data-lens"])
        node = node.parent
    return None


def _under(node: Any, tag: str) -> bool:
    """True when an ancestor of ``node`` is a ``<tag>`` or, with a leading dot, has that class."""
    node = node.parent
    while node is not None:
        if node.tag == tag or (
            tag.startswith(".") and tag[1:] in (node.attributes.get("class") or "").split()
        ):
            return True
        node = node.parent
    return False


def test_one_panel_and_one_tab_per_lens_with_content(table: tuple[Path, str]) -> None:
    _, html = table
    tree = LexborHTMLParser(html)
    reg = registry()
    on_page = {n.attributes["id"] for n in tree.css(".lens section[id]")}
    panels = [n.attributes["data-lens"] for n in tree.css(".lens[data-lens]")]
    tabs = [n.attributes["data-lens-tab"] for n in tree.css("[role=tablist] [role=tab]")]
    wanted = [lens for lens in LENSES if any(s.id in on_page for s in reg.lens_sections(lens))]
    assert panels == wanted and tabs == wanted  # bar order, no tab for an empty lens (V7)
    assert tree.css_first("[role=tablist]") is not None
    for lens in panels:
        panel = tree.css_first(f"#lens-{lens}")
        assert panel.attributes.get("role") == "tabpanel"
        assert tree.css_first(f"#tab-{lens}").attributes["aria-controls"] == f"lens-{lens}"
        # only the open lens is visible; the first one is open until the script says otherwise
        assert ("hidden" in panel.attributes) == (lens != panels[0])
    for section in reg.report_sections():
        if section.id in on_page:
            node = tree.css_first(f"section#{section.id}")
            assert _holder(node) == section.lens, section.id


def test_a_lens_with_no_shown_section_gets_no_tab(
    table: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = table
    original = Registry.report_sections

    def without_history(self: Registry) -> Any:
        return [s for s in original(self) if s.lens != "history"]

    monkeypatch.setattr(Registry, "report_sections", without_history)
    html = builder.render_report(load_product(root), root / "build", "2026-11-08")
    tree = LexborHTMLParser(html)
    assert tree.css_first("#lens-history") is None and tree.css_first("#tab-history") is None
    assert [n.attributes["data-lens-tab"] for n in tree.css("[role=tab]")] == [
        "workbench",
        "drawings",
        "build",
        "verification",
    ]


def test_the_workbench_holds_the_tree_the_3d_pane_and_the_inspector(
    table: tuple[Path, str],
) -> None:
    _, html = table
    tree = LexborHTMLParser(html)
    bench = tree.css_first("#lens-workbench .wb")
    assert bench is not None
    for sel in (
        "nav#tree",
        "section#model #viewer",
        "aside#inspector #inspector-product #overview",
    ):
        assert bench.css_first(sel) is not None, sel
    # the inspector's product view is the overview's words; the numbers moved to the top bar
    assert "Where this product stands" in bench.css_first("#overview").text()
    assert tree.css_first(".tile") is None and tree.css_first("#part-card") is None
    # the lens's other sections follow below as cards
    assert tree.css_first("#lens-workbench > .cards #interfaces") is not None
    # the renders are not in the 3D pane any more (Check views, B-0295)
    assert "Rendered views" not in html


def test_the_print_stylesheet_include_ends_the_style() -> None:
    """M3c creates print.css.j2; the line must close the style, and its absence is fine."""
    text = TEMPLATE.read_text(encoding="utf-8")
    style = text.split("<style>", 1)[1].split("</style>", 1)[0]
    assert style.rstrip().splitlines()[-1] == '{% include "print.css.j2" ignore missing %}'


def test_the_counts_line_says_every_status_in_words(table: tuple[Path, str]) -> None:
    _, html = table
    tree = LexborHTMLParser(html)
    index = json.loads(tree.css_first("#inspector-index").text())
    gate = index["manifest://product"]["gate_summary"]
    counts = " ".join(tree.css_first("header.top .counts").text().split())
    assert f"{gate['pass'] + gate['signed']} OK" in counts
    assert f"{gate['needs-human']} needs your sign-off" in counts
    assert f"{gate['warn']} worth a look" in counts
    assert f"{gate['skip']} not checked" in counts
    assert re.search(r"\d+ left for later", counts)  # later is counted, even at 0 (B-0134)
    assert all(a.attributes["href"] == "#requirements" for a in tree.css("header.top .counts a"))
    # the vitals carry their labels (N5)
    vitals = " ".join(tree.css_first("header.top .vitals").text().split())
    assert "kg computed" in vitals and "USD estimate" in vitals


def test_the_script_knows_no_domain_kind() -> None:
    """F9, V5: a domain's entries are shown generically, so the package names none of them."""
    js = WORKBENCH_JS.read_text(encoding="utf-8").lower()
    for word in ("circuit", "wiring", "cable", "electrical", "enclosure", "bracket", "kiln"):
        assert word not in js, word
    assert "fetch(" not in js and "xmlhttprequest" not in js  # file:// safe, nothing fetched (D13)


# ---- the anchors list ----------------------------------------------------------------------------


def _anchor_rows() -> list[tuple[re.Pattern[str], str, str, str]]:
    """``(pattern, text, lens, when)`` for each table row of the anchors doc."""
    rows = []
    for line in ANCHORS_DOC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*`?([^|`]+?)`?\s*\|\s*([^|]+?)\s*\|\s*$", line)
        if not m:
            continue
        text, lens, when = m.groups()
        shape = re.escape(text).replace("\\<", "<").replace("\\>", ">")
        pattern = re.compile("^" + re.sub(r"<[^>]+>", r"\\S+", shape) + "$")
        rows.append((pattern, text, lens, when))
    return rows


def _page_ids(html: str) -> dict[str, str | None]:
    """Every id on a page that is not inside an embedded drawing or a manual's own headings."""
    tree = LexborHTMLParser(html)
    out: dict[str, str | None] = {}
    for node in tree.css("main [id]"):
        if node.tag == "svg" or _under(node, "svg") or _under(node, ".doc"):
            continue
        out[node.attributes["id"]] = _holder(node)
    return out


def test_every_listed_anchor_is_on_the_page_in_its_lens(
    table: tuple[Path, str], wired: str
) -> None:
    rows = _anchor_rows()
    assert len(rows) >= 30
    pages = [_page_ids(table[1]), _page_ids(wired)]
    for pattern, text, lens, when in rows:
        found = [(i, h) for ids in pages for i, h in ids.items() if pattern.match(i)]
        if when == "always":
            assert found, f"{text}: listed as always on the page, on neither report"
        for i, holder in found:
            if lens.startswith("the section"):
                continue
            assert holder == lens, f"{i} is in {holder}, the list says {lens}"


def test_every_id_on_the_page_is_listed_or_a_control(table: tuple[Path, str], wired: str) -> None:
    patterns = [p for p, *_ in _anchor_rows()]
    for ids in (_page_ids(table[1]), _page_ids(wired)):
        for i in ids:
            assert CONTROLS.match(i) or any(p.match(i) for p in patterns), f"unlisted id {i}"


def test_the_deep_link_form_is_in_the_agent_guide() -> None:
    guide = (ROOT / "docs" / "agent-guide.md").read_text(encoding="utf-8")
    assert "#lens=" in guide and "select=part://" in guide and "report-anchors.md" in guide
