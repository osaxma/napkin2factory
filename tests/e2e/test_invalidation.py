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
    plan = {rid: run for rid, run, _ in explain_build(load_product(enclosure_built), render=False)}
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


def test_part_yaml_edit_rebuilds_only_readers_of_that_field(enclosure_built: Path) -> None:
    p = enclosure_built / "model" / "parts" / "bracket.yaml"
    p.write_text(p.read_text().replace("finish: zinc plated", "finish: zinc plated, bright"))
    s = _build(enclosure_built)
    # finish is read by the BOM (and the drawing title block), not by the geometry
    assert "part:bracket" not in s["ran"] and "bom" in s["ran"]
    assert "part:lid" not in s["ran"] and "part:base" not in s["ran"]
    p.write_text(p.read_text().replace('spec: "2 mm CR4 (DC01)"', 'spec: "2 mm stainless 304"'))
    s = _build(enclosure_built)
    assert s["ran"][:2] == ["validate", "part:bracket"]  # material drives density → geometry props


def test_cost_edit_touches_bom_not_geometry(enclosure_built: Path) -> None:
    product = load_product(enclosure_built)
    impact = compute_impact(product, [parse_set("part://base#cost.unit=40 USD")])
    assert "bom" in impact.rules and not any(r.startswith("part:") for r in impact.rules)
    assert not any(r.startswith("drawing:") for r in impact.rules)
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


# ---- review gate 1 regressions -------------------------------------------------------


def test_adding_a_part_rebuilds_bom_and_checks(enclosure_built: Path) -> None:
    (enclosure_built / "model/parts/spare-washer.yaml").write_text(
        "id: spare-washer\nname: Spare washer\nkind: cots\nprocess: none\ngeometry: none\n"
        "source: {vendor: McMaster-Carr, mpn: 93475A250, url: 'https://www.mcmaster.com/93475A250/'}\n"
        "cost: {unit: 0.05 USD}\n"
    )
    s = _build(enclosure_built)
    assert {"validate", "bom", "checks", "report"} <= set(s["ran"]), s
    assert not any(r.startswith("part:") for r in s["ran"])
    rollups = json.loads((enclosure_built / "build/bom/rollups.json").read_text())
    assert rollups["orphans"] == ["part://spare-washer"]
    (enclosure_built / "model/parts/spare-washer.yaml").unlink()
    s = _build(enclosure_built)
    assert {"validate", "bom", "checks"} <= set(s["ran"])


def test_adding_a_requirement_reruns_checks(enclosure_built: Path) -> None:
    req = enclosure_built / "model/requirements.yaml"
    original = req.read_text()
    req.write_text(
        original
        + """  - id: REQ-009
    title: Lid is thin
    statement: The lid sheet is at most 3 mm thick.
    category: manufacturing
    verify: {kind: param_bound, target: param://lid-thickness, op: "<=", value: 3 mm}
    allocation: [param://lid-thickness]
"""
    )
    s = _build(enclosure_built)
    assert "checks" in s["ran"] and "part:lid" not in s["ran"]
    checks = json.loads((enclosure_built / "build/checks/checks.json").read_text())
    assert any(r["id"] == "req://REQ-009" for r in checks["results"])
    req.write_text(original)
    assert "checks" in _build(enclosure_built)["ran"]


def test_deleting_a_doc_prunes_and_reruns_consumers(enclosure_built: Path) -> None:
    safety = enclosure_built / "model/docs/safety.md"
    text = safety.read_text()
    safety.unlink()
    s = _build(enclosure_built)
    assert {"validate", "checks", "report"} <= set(s["ran"]), s
    assert not (enclosure_built / "build/docs/safety").exists()
    manifest = Manifest.load(enclosure_built / "build")
    assert "doc:safety" not in manifest.entries
    safety.write_text(text)
    s = _build(enclosure_built)
    assert "doc:safety" in s["ran"]


def test_interrupt_then_revert_is_not_stale(tmp_path: Path) -> None:
    """Gate-1 B2: after an interrupted rebuild and a revert, the outputs must match the model."""
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "enc", git=False)
    _build(root)
    _set_param(root, "lid-thickness", "3")
    env = dict(os.environ)
    env["N2F_TEST_EXIT_AFTER"] = "part:lid:before"
    proc = subprocess.run(
        [sys.executable, "-m", "napkin2factory.cli", "build", "--no-render", "--json"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 3
    _set_param(root, "lid-thickness", "1.5")
    s = _build(root)
    assert "part:lid" in s["ran"], s
    props = json.loads((root / "build/parts/lid/props.json").read_text())
    assert abs(props["bbox"]["z"] - 1.5) < 1e-6


def test_tampered_output_is_rebuilt(enclosure_built: Path) -> None:
    (enclosure_built / "build/parts/lid/model.step").write_text("junk")
    s = _build(enclosure_built)
    assert s["ran"][0] == "part:lid"


def test_render_flag_is_part_of_the_key(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "enc", git=False)
    run_build(load_product(root), target="geometry", quiet=True, render=False)
    assert not (root / "build/parts/lid/renders").exists()
    s = run_build(load_product(root), target="geometry", quiet=True, render=True)
    assert {"part:lid", "part:base", "part:bracket", "asm:enclosure"} <= set(s["ran"])
    assert (root / "build/parts/lid/renders/iso.png").is_file()
    s = run_build(load_product(root), target="geometry", quiet=True, render=True)
    assert s["ran"] == []


def test_reordering_placements_changes_the_assembly_output(enclosure_built: Path) -> None:
    module = enclosure_built / "model/geometry/enclosure.py"
    text = module.read_text()
    module.write_text(
        text.replace(
            "translate=(x + bw / 2, w / 2, 0.0)", "translate=(x + bw / 2 + 5.0, w / 2, 0.0)"
        )
    )
    s = _build(enclosure_built)
    assert "asm:enclosure" in s["ran"] and "checks" in s["ran"] and "report" in s["ran"], s
    module.write_text(text)
    _build(enclosure_built)


def test_stable_instance_numbering(enclosure_built: Path) -> None:
    """Unlabelled placements are numbered by position, not by placement order (gate-1 B5)."""
    module = enclosure_built / "model/geometry/enclosure.py"
    text = module.read_text()
    unlabelled = text.replace('                label=f"bracket-{i + 1}",\n', "")
    assert unlabelled != text
    module.write_text(unlabelled)
    _build(enclosure_built)
    inst = json.loads((enclosure_built / "build/assemblies/enclosure/instances.json").read_text())
    before = {i["node"]: i["translation"] for i in inst}
    module.write_text(
        unlabelled.replace(
            "for i, x in enumerate((-spacing / 2, spacing / 2)):",
            "for i, x in enumerate((spacing / 2, -spacing / 2)):",
        )
    )
    s = _build(enclosure_built)
    inst = json.loads((enclosure_built / "build/assemblies/enclosure/instances.json").read_text())
    after = {i["node"]: i["translation"] for i in inst}
    assert before == after, "reordering the placement loop must not renumber instances"
    assert "checks" not in s["ran"]
    module.write_text(text)
    _build(enclosure_built)


def test_helper_module_change_rebuilds_dependents(enclosure_built: Path) -> None:
    helper = enclosure_built / "model/geometry/layout.py"
    helper.write_text("LID_Z_EXTRA = 0.0\n")
    module = enclosure_built / "model/geometry/enclosure.py"
    text = module.read_text()
    module.write_text(
        text.replace(
            '    h = P.mm("box-height")',
            '    from layout import LID_Z_EXTRA\n\n    h = P.mm("box-height") + LID_Z_EXTRA',
        )
    )
    import sys as _sys

    _sys.path.insert(0, str(enclosure_built / "model/geometry"))
    try:
        _build(enclosure_built)
        helper.write_text("LID_Z_EXTRA = 25.0\n")
        s = _build(enclosure_built)
        assert "asm:enclosure" in s["ran"], s
        inst = json.loads(
            (enclosure_built / "build/assemblies/enclosure/instances.json").read_text()
        )
        lid = next(i for i in inst if i["uri"] == "part://lid")
        assert abs(lid["translation"][2] - 105.0) < 1e-6
    finally:
        _sys.path.remove(str(enclosure_built / "model/geometry"))
        module.write_text(text)
        helper.unlink()
        _build(enclosure_built)


def test_field_edits_match_impact(enclosure_built: Path) -> None:
    """Gate-1 B3: impact and the build agree on which rules a field edit touches."""
    product = load_product(enclosure_built)
    notes = compute_impact(product, [parse_set("part://lid#notes=hello")])
    assert notes.rules == ["validate"]
    cost = compute_impact(product, [parse_set("part://base#cost.unit=40 USD")])
    assert (
        "bom" in cost.rules and "part:base" not in cost.rules and "drawing:base" not in cost.rules
    )
    part = enclosure_built / "model/parts/base.yaml"
    text = part.read_text()
    part.write_text(text.replace("cost: {unit: 28 USD,", "cost: {unit: 40 USD,"))
    s = _build(enclosure_built)
    # impact is a superset of the build (a rerun with identical output stops the cascade)
    assert set(s["ran"]) <= set(cost.rules), (s["ran"], cost.rules)
    assert {"bom", "checks"} <= set(s["ran"])
    part.write_text(text)
    _build(enclosure_built)
    mat = compute_impact(product, [parse_set("part://base#material.spec=2 mm CR4")])
    assert "part:base" in mat.rules and "asm:enclosure" in mat.rules
    part.write_text(
        text.replace('spec: "1.5 mm CR4 (DC01)"', 'spec: "1.5 mm CR4 (DC01) bright"').replace(
            "finish: powder coat, grey", "finish: powder coat, grey", 1
        )
    )
    s = _build(enclosure_built)
    assert "part:base" in s["ran"]
    part.write_text(text)
    _build(enclosure_built)


def test_key_precision(enclosure_built: Path) -> None:
    _set_param(enclosure_built, "box-length", "200.0004")
    s = _build(enclosure_built)
    assert "part:base" in s["ran"], "a 0.4 µm change is still a change (gate-1 C3)"
    _set_param(enclosure_built, "box-length", "200")
    _build(enclosure_built)
