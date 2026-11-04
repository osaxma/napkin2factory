"""Tests for display units in report tables and napkin board (W8, S-219)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from selectolax.lexbor import LexborHTMLParser

from napkin2factory.concepts.board import BOARD_PATH, write_board
from napkin2factory.core import concepts as cm
from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product
from napkin2factory.core.units import parse_quantity
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip
from napkin2factory.report.builder import render_report
from napkin2factory.report.units import display
from tests.conftest import EXAMPLES, copy_product
from tests.unit.test_promote import overlay_cards


def test_display_helper_quantities() -> None:
    """Checklist item 1: display helper formatting and conversion rules."""
    # Lengths: in, or ft above 120 in
    assert display("800 mm", "imperial") == "31.5 in (800 mm)"
    assert display("800 mm", "metric") == "800 mm"
    assert display(parse_quantity("800 mm"), "imperial") == "31.5 in (800 mm)"
    assert display(parse_quantity("800 mm"), "metric") == "800 mm"
    assert display("120 mm", "imperial") == "4.72 in (120 mm)"
    assert display("4 mm", "imperial") == "0.157 in (4 mm)"
    assert display("3500 mm", "imperial") == "11.5 ft (3500 mm)"
    assert display(parse_quantity("120 in"), "imperial") == "120 in (3048 mm)"
    assert display(parse_quantity("150 in"), "imperial") == "12.5 ft (3810 mm)"

    # Masses: lb
    assert display("10 kg", "imperial") == "22 lb (10 kg)"
    assert display("0.5 kg", "imperial") == "1.1 lb (0.5 kg)"
    assert display("0.356422 kg", "imperial") == "0.786 lb (0.356422 kg)"

    # Forces: lbf
    assert display("100 N", "imperial") == "22.5 lbf (100 N)"

    # Stresses: psi / ksi
    assert display("25 MPa", "imperial") == "3.63 ksi (25 MPa)"
    assert display(parse_quantity("500 psi"), "imperial") == "500 psi (3.45 MPa)"

    # Temperatures: °F
    assert display("61 degC", "imperial") == "142 °F (61 degC)"
    assert display("100 degC", "imperial") == "212 °F (100 degC)"

    # Non-converted / universal units stay unchanged
    assert display("30 USD", "imperial") == "30 USD"
    assert display("5 d", "imperial") == "5 d"
    assert display("2.5 kW", "imperial") == "2.5 kW"
    assert display("230V-16A", "imperial") == "230V-16A"
    assert display(12, "imperial") == "12"
    assert display(None, "imperial") == ""


def test_display_in_text() -> None:
    """Complex strings and embedded quantities."""
    s1 = "bbox.x = 120 mm <= 150 mm"
    assert display(s1, "imperial") == "bbox.x = 4.72 in (120 mm) <= 5.91 in (150 mm)"
    assert display(s1, "metric") == s1

    s2 = "mass = 0.356422 kg < 0.5 kg"
    assert display(s2, "imperial") == "mass = 0.786 lb (0.356422 kg) < 1.1 lb (0.5 kg)"
    assert display(s2, "metric") == s2

    s3 = "sheet-metal; 4 mm CR4 (DC01); powder coat, black; ISO2768-m; qty 1; Deburr all edges."
    assert "0.157 in (4 mm)" in display(s3, "imperial")
    assert "ISO2768-m" in display(s3, "imperial")  # ISO standard name not corrupted
    assert display(s3, "metric") == s3

    # Already converted strings are not double-converted
    assert display("31.5 in (800 mm)", "imperial") == "31.5 in (800 mm)"


def test_metric_output_byte_identical_for_prebuilt_bracket(tmp_path: Path) -> None:
    """Checklist item 4: metric output byte-identical to before for the bracket."""
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", prebuilt=True, render=False)
    product = load_product(root)
    assert product.manifest.units == "metric"
    built_html = (root / "build/report/index.html").read_text(encoding="utf-8")
    m = re.search(r"saved (\d{4}-\d{2}-\d{2})", built_html)
    snap = m.group(1) if m else "2026-10-30"
    fresh_html = render_report(product, root / "build", snap)
    # Body before footer timestamp must match byte-for-byte
    assert built_html.split("<footer", 1)[0] == fresh_html.split("<footer", 1)[0]


def test_imperial_copy_shows_in_first_in_three_tables_and_board(tmp_path: Path) -> None:
    """Checklist item 4: imperial copy shows in first with mm in brackets in 3 tables & board."""
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket_imp", prebuilt=True, render=False)

    # Set units: imperial in n2f.yaml
    manifest_data = load_roundtrip(root / "n2f.yaml")
    manifest_data["units"] = "imperial"
    dump_roundtrip(root / "n2f.yaml", manifest_data)

    # Invalidate cached report so run_build rebuilds it
    shutil.rmtree(root / "build/report", ignore_errors=True)

    product = load_product(root)
    assert product.manifest.units == "imperial"
    run_build(product, quiet=True, render=False)

    html = (root / "build/report/index.html").read_text(encoding="utf-8")
    tree = LexborHTMLParser(html)

    # 1. Parameter table: shows "in" first with mm in brackets
    param_table = tree.css_first("#parameters table")
    assert param_table is not None
    param_text = param_table.text()
    assert "4.72 in (120 mm)" in param_text
    assert re.search(r"\b\d+(?:\.\d+)?\s*in\s*\(\d+(?:\.\d+)?\s*mm\)", param_text)

    # 2. Requirement table: shows "in" first with mm in brackets
    req_table = tree.css_first("#requirements table")
    assert req_table is not None
    req_text = req_table.text()
    assert "4.72 in (120 mm)" in req_text
    assert "5.91 in (150 mm)" in req_text
    assert re.search(r"\b\d+(?:\.\d+)?\s*in\s*\(\d+(?:\.\d+)?\s*mm\)", req_text)

    # 3. Parts table: shows "in" first with mm in brackets
    bom_table = tree.css_first("#parts table#bom")
    assert bom_table is not None
    bom_text = bom_table.text()
    assert "0.157 in (4 mm)" in bom_text
    assert re.search(r"\b\d+(?:\.\d+)?\s*in\s*\(\d+(?:\.\d+)?\s*mm\)", bom_text)

    # 4. Napkin board: shows "in" first with mm in brackets
    overlay_cards(root)
    from napkin2factory.concepts.build import build_concepts

    cards = list(cm.load_concepts(root).values())
    done, errors = build_concepts(root, cards, render=False)
    assert not errors and len(done) >= 1
    write_board(root)

    board_html = (root / BOARD_PATH).read_text(encoding="utf-8")
    assert "31.5 in (800 mm)" in board_html or "39.2 in (995 mm)" in board_html
    assert re.search(r"\b\d+(?:\.\d+)?\s*in\s*\(\d+(?:\.\d+)?\s*mm\)", board_html)
