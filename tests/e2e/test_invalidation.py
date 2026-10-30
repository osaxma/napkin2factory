"""§6.4 invalidation suite on the enclosure: exact rebuild sets, no-op builds, interruption,
impact == invalidation, hypothetical verdicts, --jobs equality."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from napkin2factory.core.graph.impact import compute_impact, parse_set
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.graph.runner import explain_build, run_build
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES, copy_product

FULL = [
    "validate",
    "part:base",
    "part:bracket",
    "part:lid",
    "asm:enclosure",
    "drawing:base",
    "drawing:bracket",
    "drawing:lid",
    "bom",
    "doc:assembly",
    "doc:safety",
    "checks",
    "report",
    "site",
]
LID_SET = [
    "validate",
    "part:lid",
    "asm:enclosure",
    "drawing:lid",
    "bom",
    "doc:assembly",
    "checks",
    "report",
    "site",
]


def _build(root: Path, **kw):  # type: ignore[no-untyped-def]
    return run_build(load_product(root), quiet=True, render=False, **kw)


def _set_param(root: Path, slug: str, value: str) -> None:
    p = root / "model" / "parameters.yaml"
    lines = p.read_text().splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().startswith(f"{slug}:"):
            head, rest = ln.split("{", 1)
            inner = rest.rsplit("}", 1)[0]
            fields = [f.strip() for f in inner.split(",")]
            fields = [f"value: {value}" if f.startswith("value:") else f for f in fields]
            lines[i] = f"{head}{{{', '.join(fields)}}}"
            break
    else:
        raise AssertionError(f"{slug} not found")
    p.write_text("\n".join(lines) + "\n")


@pytest.fixture(scope="module")
def enclosure_built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = copy_product(
        EXAMPLES / "enclosure", tmp_path_factory.mktemp("inv") / "enclosure", git=False
    )
    s = _build(root)
    assert s["ran"] == FULL and s["skipped"] == []
    return root


def test_second_build_is_a_noop(enclosure_built: Path) -> None:
    s = _build(enclosure_built)
    assert s["ran"] == [] and s["skipped"] == FULL


def test_unused_parameter_rebuilds_only_validate(enclosure_built: Path) -> None:
    _set_param(enclosure_built, "unused-note-count", "4")
    impact = compute_impact(
        load_product(enclosure_built), [parse_set("param://unused-note-count=4")]
    )
    assert impact.rules == ["validate"]
    s = _build(enclosure_built)
    assert s["ran"] == ["validate"], s


def test_lid_thickness_exact_set(enclosure_built: Path) -> None:
    product = load_product(enclosure_built)
    impact = compute_impact(product, [parse_set("param://lid-thickness=3mm")])
    assert impact.rules == LID_SET
    assert (
        impact.parts == ["lid"]
        and impact.docs == ["assembly"]
        and impact.interfaces == ["lid-base-mount"]
    )
    _set_param(enclosure_built, "lid-thickness", "3")
    plan = {rid: run for rid, run, _ in explain_build(load_product(enclosure_built))}
    assert [r for r in FULL if plan[r]] == LID_SET
    s = _build(enclosure_built)
    assert s["ran"] == LID_SET
    assert "part:base" not in s["ran"] and "drawing:base" not in s["ran"]
    assert _build(enclosure_built)["ran"] == []


def test_generator_source_change_rebuilds_its_parts(enclosure_built: Path) -> None:
    module = enclosure_built / "model" / "geometry" / "enclosure.py"
    module.write_text(module.read_text() + "\n# touched\n")
    s = _build(enclosure_built)
    # the assembly reruns; its output is identical, so nothing downstream reruns
    assert s["ran"] == ["validate", "asm:enclosure"], s
    assert not any(r.startswith("part:") for r in s["ran"])


def test_interface_spec_change_rebuilds_both_parties(enclosure_built: Path) -> None:
    _set_param(enclosure_built, "screw-clearance", "5")
    product = load_product(enclosure_built)
    impact = compute_impact(product, [parse_set("param://screw-clearance=5mm")])
    assert {"part:base", "part:lid"} <= set(impact.rules) and "part:bracket" not in impact.rules
    s = _build(enclosure_built)
    assert {"part:base", "part:lid", "drawing:base", "drawing:lid", "asm:enclosure"} <= set(
        s["ran"]
    )
    assert "part:bracket" not in s["ran"]


def test_part_yaml_edit_rebuilds_that_part(enclosure_built: Path) -> None:
    p = enclosure_built / "model" / "parts" / "bracket.yaml"
    p.write_text(p.read_text().replace("finish: zinc plated", "finish: zinc plated, bright"))
    s = _build(enclosure_built)
    assert s["ran"][:2] == ["validate", "part:bracket"]
    assert "part:lid" not in s["ran"] and "part:base" not in s["ran"]


def test_cost_edit_touches_bom_not_geometry(enclosure_built: Path) -> None:
    product = load_product(enclosure_built)
    impact = compute_impact(product, [parse_set("part://base#cost.unit=40 USD")])
    assert "bom" in impact.rules and not any(r.startswith("part:") for r in impact.rules)
    assert impact.cost_delta == pytest.approx(12.0)
    req = {r.id: r for r in impact.requirements}
    assert req["REQ-003"].verdict == "would-pass"
    impact2 = compute_impact(product, [parse_set("part://base#cost.unit=100 USD")])
    assert {r.id: r for r in impact2.requirements}["REQ-003"].verdict == "would-fail"


def test_hypothetical_param_bound_verdict(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=False)
    req = root / "model" / "requirements.yaml"
    req.write_text(
        req.read_text()
        + """  - id: REQ-004
    title: Thin sheet
    statement: The sheet is at most 5 mm thick.
    category: manufacturing
    verify: {kind: param_bound, target: param://bracket-thickness, op: "<=", value: 5 mm}
    allocation: [param://bracket-thickness]
"""
    )
    product = load_product(root)
    ok = compute_impact(product, [parse_set("param://bracket-thickness=4.5mm")])
    bad = compute_impact(product, [parse_set("param://bracket-thickness=6mm")])
    assert {r.id: r.verdict for r in ok.requirements}["REQ-004"] == "would-pass"
    assert {r.id: r.verdict for r in bad.requirements}["REQ-004"] == "would-fail"
    assert "6 mm <= 5 mm" in {r.id: r.detail for r in bad.requirements}["REQ-004"]
    assert not ok.firm  # never built: notes say so


@pytest.mark.parametrize("mode", ["after", "before"])
def test_interrupted_build_converges(tmp_path: Path, mode: str) -> None:
    """Kill right after (or before) the manifest write for part:bracket; a rerun converges."""
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "enc", git=False)
    env = dict(os.environ)
    env["N2F_TEST_EXIT_AFTER"] = "part:bracket" if mode == "after" else "part:bracket:before"
    env["COLUMNS"] = "200"
    proc = subprocess.run(
        [sys.executable, "-m", "napkin2factory.cli", "build", "--no-render", "--json"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 3
    manifest = Manifest.load(root / "build")
    assert "part:base" in manifest.entries
    assert ("part:bracket" in manifest.entries) == (mode == "after")
    assert "part:lid" not in manifest.entries
    s = _build(root)
    expected_first = ["part:lid"] if mode == "after" else ["part:bracket", "part:lid"]
    assert s["ran"][: len(expected_first)] == expected_first, s
    assert "validate" in s["skipped"] and "part:base" in s["skipped"]
    assert _build(root)["ran"] == []


def test_jobs_two_matches_jobs_one(tmp_path: Path) -> None:
    a = copy_product(EXAMPLES / "enclosure", tmp_path / "a", git=False)
    b = copy_product(EXAMPLES / "enclosure", tmp_path / "b", git=False)
    _build(a, target="geometry")
    _build(b, target="geometry", jobs=2)
    for pid in ("base", "bracket", "lid"):
        pa = json.loads((a / "build/parts" / pid / "props.json").read_text())
        pb = json.loads((b / "build/parts" / pid / "props.json").read_text())
        for key in ("volume", "area", "mass", "tess_hash", "reads", "bbox"):
            assert pa[key] == pb[key], (pid, key)
    assert _build(b, target="geometry")["ran"] == []


def test_clean_rebuilds_everything(enclosure_built: Path) -> None:
    s = _build(enclosure_built, clean=True)
    assert s["ran"] == FULL


def test_missing_output_triggers_rerun(enclosure_built: Path) -> None:
    (enclosure_built / "build/parts/lid/model.glb").unlink()
    s = _build(enclosure_built)
    assert s["ran"][0] == "part:lid" and "validate" in s["skipped"]
