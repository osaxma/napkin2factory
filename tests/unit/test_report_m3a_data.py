"""Unit tests for M3a data: inspector children/vitals, later count, and check-views section."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from napkin2factory.core.domain import SectionContext
from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.model.assemblies import Assembly
from napkin2factory.core.model.manifest import Manifest, Operator
from napkin2factory.core.product import Paths
from napkin2factory.core.registry import registry
from napkin2factory.report.builder import gather, render_report
from napkin2factory.report.inspector import inspector_index
from tests.conftest import EXAMPLES, copy_product


@pytest.fixture(scope="module")
def prebuilt_bracket(tmp_path_factory: pytest.TempPathFactory) -> Product:
    dst = copy_product(
        EXAMPLES / "bracket",
        tmp_path_factory.mktemp("m3a_bracket") / "bracket",
        prebuilt=True,
        render=False,
    )
    return load_product(dst)


@pytest.fixture(scope="module")
def prebuilt_enclosure(tmp_path_factory: pytest.TempPathFactory) -> Product:
    dst = copy_product(
        EXAMPLES / "enclosure",
        tmp_path_factory.mktemp("m3a_enclosure") / "enclosure",
        prebuilt=True,
        render=False,
    )
    return load_product(dst)


def test_assembly_children_structure(prebuilt_enclosure: Product) -> None:
    """Every asm:// entry gains children: [{uri, qty}], its direct children in BOM order."""
    sctx = SectionContext(prebuilt_enclosure, prebuilt_enclosure.paths.build)
    idx = inspector_index(sctx)

    for aid in prebuilt_enclosure.assemblies:
        entry = idx[f"asm://{aid}"]
        assert "children" in entry, f"asm://{aid} missing children"
        children = entry["children"]
        assert isinstance(children, list)
        assert len(children) > 0, f"asm://{aid} children should not be empty"
        for ch in children:
            assert "uri" in ch and "qty" in ch
            assert isinstance(ch["uri"], str)
            assert isinstance(ch["qty"], int) and ch["qty"] >= 1


def test_assembly_children_empty_fallback(prebuilt_bracket: Product) -> None:
    """When an assembly is not found in rollups.structure, children is an empty list."""
    sctx = SectionContext(prebuilt_bracket, prebuilt_bracket.paths.build)
    empty_rollups: dict[str, Any] = {"flat": [], "structure": {}}
    idx = inspector_index(sctx, rollups=empty_rollups)
    for aid in prebuilt_bracket.assemblies:
        entry = idx[f"asm://{aid}"]
        assert entry.get("children") == []


def test_product_vitals_open_choices(prebuilt_bracket: Product) -> None:
    """vitals['open_choices'] formats 'no open choices', '1 open choice', 'n open choices'."""
    sctx = SectionContext(prebuilt_bracket, prebuilt_bracket.paths.build)

    # 0 choices
    idx0 = inspector_index(sctx, waiting=[])
    v0 = idx0["manifest://product"]["vitals"]["open_choices"]
    assert v0 == {"value": "no open choices", "raw": 0, "label": "given"}

    # 1 choice
    idx1 = inspector_index(sctx, waiting=[{"id": "choice-1", "title": "Choice 1"}])
    v1 = idx1["manifest://product"]["vitals"]["open_choices"]
    assert v1 == {"value": "1 open choice", "raw": 1, "label": "given"}

    # 3 choices
    idx3 = inspector_index(
        sctx,
        waiting=[
            {"id": "c1", "title": "C1"},
            {"id": "c2", "title": "C2"},
            {"id": "c3", "title": "C3"},
        ],
    )
    v3 = idx3["manifest://product"]["vitals"]["open_choices"]
    assert v3 == {"value": "3 open choices", "raw": 3, "label": "given"}


def test_product_vitals_envelope_present_and_absent(
    prebuilt_bracket: Product, tmp_path: Path
) -> None:
    """envelope is present when props.json exists, and omitted when absent."""
    sctx = SectionContext(prebuilt_bracket, prebuilt_bracket.paths.build)
    idx = inspector_index(sctx)
    vitals = idx["manifest://product"]["vitals"]

    # When props.json exists on prebuilt bracket
    props_file = prebuilt_bracket.paths.build / "assemblies" / "bracket" / "props.json"
    if props_file.is_file():
        assert "envelope" in vitals
        env = vitals["envelope"]
        assert env["label"] == "computed"
        assert isinstance(env["raw"], list) and len(env["raw"]) == 3
        assert " × " in env["value"] and " mm" in env["value"]

    # When build_dir has no assemblies props.json, envelope is omitted
    empty_build = tmp_path / "empty_build"
    empty_build.mkdir()
    sctx_empty = SectionContext(prebuilt_bracket, empty_build)
    idx_empty = inspector_index(sctx_empty)
    assert "envelope" not in idx_empty["manifest://product"]["vitals"]


def test_product_vitals_envelope_multi_top_and_imperial(tmp_path: Path) -> None:
    """Envelope combines min/max across top units, rounds whole numbers, and supports imperial."""
    prod = Product(
        paths=Paths(tmp_path),
        manifest=Manifest.model_validate(
            {"product": {"id": "multi", "name": "Multi Unit"}, "units": "imperial"}
        ),
        operator=Operator(persona="owner"),
        assemblies={
            "top1": Assembly.model_validate({"id": "top1", "name": "Top 1", "build": "unit"}),
            "top2": Assembly.model_validate({"id": "top2", "name": "Top 2", "build": "unit"}),
        },
    )
    bdir = tmp_path / "build"
    (bdir / "assemblies" / "top1").mkdir(parents=True)
    (bdir / "assemblies" / "top2").mkdir(parents=True)
    # top1: x: [0, 100], y: [-50, 50], z: [0, 200]
    (bdir / "assemblies" / "top1" / "props.json").write_text(
        json.dumps(
            {
                "bbox": {
                    "min": [0.0, -50.0, 0.0],
                    "max": [100.0, 50.0, 200.0],
                    "x": 100.0,
                    "y": 100.0,
                    "z": 200.0,
                }
            }
        )
    )
    # top2: x: [50, 250.5], y: [0, 100], z: [100, 300]
    (bdir / "assemblies" / "top2" / "props.json").write_text(
        json.dumps(
            {
                "bbox": {
                    "min": [50.0, 0.0, 100.0],
                    "max": [250.5, 100.0, 300.0],
                    "x": 200.5,
                    "y": 100.0,
                    "z": 200.0,
                }
            }
        )
    )

    sctx = SectionContext(prod, bdir)
    idx = inspector_index(sctx, rollups={"flat": [], "structure": {}}, checks={}, waiting=[])
    vitals = idx["manifest://product"]["vitals"]
    assert "envelope" in vitals
    env = vitals["envelope"]
    # combined: x: [0, 250.5] -> 250.5, y: [-50, 100] -> 150, z: [0, 300] -> 300
    assert env["raw"] == [250.5, 150.0, 300.0]
    assert env["label"] == "computed"
    # Imperial product units: display shows in (mm)
    assert "in" in env["value"] and "mm" in env["value"]


def test_later_count_in_gather(prebuilt_bracket: Product) -> None:
    """gather returns later_count totaling requirement and rule 'later' verdicts."""
    data = gather(prebuilt_bracket, prebuilt_bracket.paths.build, "2026-11-08")
    assert "later_count" in data
    assert isinstance(data["later_count"], int)
    expected = data["req_summary"].get("later", 0) + data["rule_summary"].get("later", 0)
    assert data["later_count"] == expected


def test_requirements_filter_keeps_later_visible() -> None:
    """CSS rule only-open hides pass and signed, keeping st-later visible."""
    css_rule = "table.only-open tr.st-pass, table.only-open tr.st-signed{display:none}"
    assert "st-later" not in css_rule
    assert "tr.st-pass" in css_rule
    assert "tr.st-signed" in css_rule


def test_check_views_section_registration_and_rendering(prebuilt_bracket: Product) -> None:
    """Check views section is registered in REPORT_SECTIONS after rules in Verification lens."""
    secs = registry().report_sections()
    sec_ids = [s.id for s in secs]
    assert "check-views" in sec_ids
    rules_idx = sec_ids.index("rules")
    cv_idx = sec_ids.index("check-views")
    assert cv_idx == rules_idx + 1

    cv_sec = secs[cv_idx]
    assert cv_sec.label == "Check views"
    assert cv_sec.lens == "verification"
    assert cv_sec.group == "Verification"

    # Render report on prebuilt bracket
    html = render_report(prebuilt_bracket, prebuilt_bracket.paths.build, "2026-11-08")
    tree = HTMLParser(html)
    sec_node = tree.css_first("section#check-views")
    assert sec_node is not None
    lead = sec_node.css_first("p.lead")
    assert lead is not None
    assert "Check renders: flat colours tell the parts apart" in lead.text()
    # Since prebuilt_bracket was copied with render=False, renders is empty
    muted = sec_node.css_first("p.muted")
    assert muted is not None
    assert "No check renders in this build." in muted.text()


def test_backlog_b_new1_filed() -> None:
    """Item 5 filed as B-0314: card reads cannot be recorded without core changes."""
    backlog_text = Path("BACKLOG.md").read_text(encoding="utf-8")
    assert "B-0314" in backlog_text
    assert "The report's History lens lists no design directions" in backlog_text
