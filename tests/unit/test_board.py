"""M4 (v0.2): ``n2f concept board`` — self-contained, labelled, red in place (N10).

The product is the bracket example with the four fixture cards (C-001 and C-004 red, C-002
and C-003 green; C-003 carries a reference image) built once with their pictures, plus an
unbuilt C-005.
"""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

import pytest
from markupsafe import escape

from napkin2factory.concepts import board as board_mod
from napkin2factory.concepts.board import BOARD_PATH, write_board
from napkin2factory.core import concepts as cm
from tests.conftest import EXAMPLES, copy_product, real_page_errors
from tests.unit.test_promote import overlay_cards

CHROMIUM_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from napkin2factory.concepts.build import build_concepts

    root = copy_product(EXAMPLES / "bracket", tmp_path_factory.mktemp("board") / "bracket")
    overlay_cards(root)
    cards = list(cm.load_concepts(root).values())
    done, errors = build_concepts(root, cards, render=True)
    assert errors == [] and len(done) == 4
    cm.new_card(root, "Not built yet either")  # C-005
    return root


@pytest.fixture(scope="module")
def page(built: Path) -> str:
    write_board(built)
    return (built / BOARD_PATH).read_text(encoding="utf-8")


def _article(page: str, cid: str) -> str:
    m = re.search(rf'<article class="[^"]*" id="card-{cid}".*?</article>', page, re.DOTALL)
    assert m, cid
    return m.group(0)


def test_board_is_self_contained_and_within_budget(built: Path, page: str) -> None:
    assert not re.search(r'(?:src|href)="(?:https?:)?//', page)
    assert "<link" not in page
    assert page.count('<script type="module">') == 1
    assert (built / BOARD_PATH).stat().st_size <= board_mod.MAX_REPORT_BYTES
    from napkin2factory.report.builder import MAX_REPORT_BYTES

    assert board_mod.MAX_REPORT_BYTES == MAX_REPORT_BYTES  # the report's budget (D13)
    assert "Compare directions, then choose in conversation or with" in page
    assert "<code>n2f concept promote C-00x</code>" in page
    # read-only: nothing on the page writes
    assert "<form" not in page and "<button" not in page


def test_cards_in_id_order_red_in_place_with_reasons(page: str) -> None:
    order = re.findall(r'<article class="[^"]*" id="card-(C-\d{3})"', page)
    assert order == ["C-001", "C-002", "C-003", "C-004", "C-005"]
    red = _article(page, "C-001")
    assert 'class="concept red exploring"' in red
    assert "this direction has problems:" in red
    assert html.escape("it needs 1245 mm of width — 995 mm for the body") in red
    assert "worth a look:" in red  # the lift-class warning
    assert "this direction has problems:" in _article(page, "C-004")
    green = _article(page, "C-003")
    assert "holds up in screening" in green and "this direction has problems" not in green
    assert "based on C-002" in green


def test_every_label_is_a_badge_next_to_its_value(page: str, built: Path) -> None:
    shown = 0
    for card in cm.load_concepts(built).values():
        if card.screening is None:
            continue
        art = _article(page, card.id)
        values = card.screening.values  # given, computed and estimates
        shown += len(values)
        for lv in values.values():
            assert f'{html.escape(lv.value)}<span class="lbl {lv.label}"' in art, (card.id, lv)
        assert art.count('class="lbl ') == len(values)
    assert page.count('class="lbl ') == shown


def test_inputs_sources_and_rule_labels_are_on_the_page(page: str, built: Path) -> None:
    """Review gate A, C1/C2: given inputs apart, sources visible, problems labelled."""
    assert '<span class="key given">given</span> from the card' in page
    red = _article(page, "C-001")
    card = cm.load_card(built, "C-001")
    assert card.screening is not None
    # the card's power and circuit are given, under their own heading
    assert "<h3>From the card</h3>" in red
    assert '2.5 kW<span class="lbl given"' in red
    # the door-swing basis and every estimate's source are printed, not tooltip-only
    foot = card.screening.computed["footprint_with_door_swing"]
    assert f'<span class="src">{escape(foot.source)}</span>' in red
    for lv in card.screening.estimates.values():
        assert f'<span class="src">{escape(lv.source)}</span>' in red, lv
    # the two cost rows share one source line, printed once; a wide band says why (C10)
    cost = card.screening.estimates["cost_high"]
    assert red.count(f'<span class="src">{escape(cost.source)}</span>') == 1
    assert '<span class="src band">a wide band: only the parts screening can price' in red
    # gate B, B2: the owner's sentences only; the engineer's refs never reach the page
    for lv in card.screening.values.values():
        if lv.ref:
            assert escape(lv.ref) not in red, lv.ref
    assert "calc kit" not in page and "[verify]" not in red
    assert "a rough engineering formula, before any design" in page
    # each problem starts with the labels of the numbers it relied on
    bad = red[red.index('class="limits bad"') :]
    bad = bad[: bad.index("</div>")]
    assert '<li><span class="rely computed"' in bad


def test_unbuilt_card_says_so(page: str) -> None:
    art = _article(page, "C-005")
    assert ">not built yet<" in art and "<code>n2f concept build C-005</code>" in art
    assert 'class="lbl ' not in art and "data-n2f-glb" not in art


def test_pictures_viewers_and_refs_are_embedded(page: str) -> None:
    art = _article(page, "C-003")
    assert art.count('src="data:image/png;base64,') == 3  # iso, front, the sketch
    assert 'data-n2f-glb="glb-C-003"' in art
    assert "&#34;lighting&#34;: &#34;studio&#34;" in art and "&#34;materials&#34;" in art
    assert "concept://C-003/body" in html.unescape(art)
    assert "refs/sketch-01.png" in art


def test_board_json_carries_the_data_not_the_bytes(built: Path) -> None:
    result = write_board(built)
    data = result.to_dict(built)
    assert data["board"] == "build/concepts/board.html" and data["dropped"] == []
    assert [c["id"] for c in data["cards"]] == ["C-001", "C-002", "C-003", "C-004", "C-005"]
    c3 = data["cards"][2]
    assert c3["files"]["hero"] == "build/concepts/C-003/renders/styled-iso.png"
    assert c3["refs"][0]["path"] == "concepts/refs/sketch-01.png"
    assert {v["label"] for v in c3["dims"]} == {"computed", "estimate"}
    assert "base64" not in str(data)
    assert result.line() == (
        "board: build/concepts/board.html — 5 directions side by side "
        "(2 with problems, 1 not built yet)"
    )


def test_budget_drops_refs_first_then_front_and_says_so(
    built: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "bracket"
    shutil.copytree(built, root)
    big = root / "concepts" / "refs" / "huge.png"
    big.write_bytes(b"\x89PNG" + bytes(range(256)) * (8 * 1024))  # ~2 MB, base64 ~2.7 MB
    card = root / "concepts" / "C-002.yaml"
    card.write_text(card.read_text().replace("refs: []", "refs: [refs/huge.png]"))
    full = write_board(root)
    assert full.dropped == []
    without_refs = len(board_mod.render_board(board_mod.gather(root), {"refs"}).encode("utf-8"))
    monkeypatch.setattr(board_mod, "MAX_REPORT_BYTES", without_refs + 1024)
    capped = write_board(root)
    page = (root / BOARD_PATH).read_text(encoding="utf-8")
    assert capped.dropped == ["refs"] and capped.bytes <= without_refs + 1024
    assert "these were left out: reference images" in page
    assert "huge.png (not shown)" in page
    monkeypatch.setattr(board_mod, "MAX_REPORT_BYTES", without_refs - 1)
    tighter = write_board(root)
    page = (root / BOARD_PATH).read_text(encoding="utf-8")
    assert tighter.dropped == ["refs", "front"] and tighter.bytes < without_refs
    assert "reference images, front screenshots" in page
    assert tighter.dropped_notes[0].endswith(" MB: reference images, front screenshots")


def test_board_opens_from_file_url_with_every_viewer(built: Path, page: str) -> None:
    pytest.importorskip("playwright")
    from playwright.sync_api import Error, sync_playwright

    path = built / BOARD_PATH
    try:
        with sync_playwright() as p:
            p.chromium.launch(args=CHROMIUM_ARGS).close()
    except Error as exc:
        pytest.skip(f"Playwright Chromium unavailable: {exc}")
    with sync_playwright() as p:
        browser = p.chromium.launch(args=CHROMIUM_ARGS)
        tab = browser.new_page(viewport={"width": 1600, "height": 1000})
        errors: list[str] = []
        tab.on("pageerror", lambda e: errors.append(str(e)))
        tab.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        tab.goto(path.as_uri())
        ids = tab.evaluate("window.n2fViewerReady.then(v => Object.keys(v).sort())")
        nodes = tab.evaluate("window.n2fViewers['viewer-C-003'].nodes()")
        browser.close()
    assert real_page_errors(errors) == [], errors
    assert ids == [f"viewer-C-00{i}" for i in range(1, 5)]
    assert sorted(nodes) == [
        "concept://C-003/body",
        "concept://C-003/controls",
        "concept://C-003/door",
    ]


def test_decision_lines_say_set_aside_with_the_date_only(built: Path) -> None:
    """Review gate B, C12: one plain phrase, the date and never the time."""
    import datetime as dt

    from napkin2factory.core.model.concepts import ConceptDecision

    card = cm.load_card(built, "C-002")
    at = dt.datetime(2026, 10, 31, 19, 26, 39)

    def line(status: str, **kw: object) -> str | None:
        decision = ConceptDecision(at=at, **kw)  # type: ignore[arg-type]
        return board_mod._decision_line(
            card.model_copy(update={"status": status, "decision": decision})
        )

    assert line("rejected", reason="set aside when C-003 was chosen (DEC-018)") == (
        "set aside when C-003 was chosen (DEC-018) — 2026-10-31"
    )
    # the wording cards carried before gate B reads the same
    assert line("rejected", reason="not chosen: C-003 promoted (DEC-018)") == (
        "set aside when C-003 was chosen (DEC-018) — 2026-10-31"
    )
    assert line("rejected", reason="too tall") == "set aside: too tall — 2026-10-31"
    assert line("promoted", dec="DEC-018") == "the chosen direction (DEC-018) — 2026-10-31"
