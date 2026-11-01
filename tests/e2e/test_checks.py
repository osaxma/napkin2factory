"""M4: evaluators, rule packs, interference (+ allowed contact), interface mismatch,
sign-off semantics, stage computation, exit codes."""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from napkin2factory.core.checks.stage import compute_stage
from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES, copy_product, n2f

os.environ.setdefault("N2F_OFFLINE", "1")


def _checks(root: Path) -> dict:  # type: ignore[type-arg]
    run_build(load_product(root), target="checks", quiet=True, render=False)
    return json.loads((root / "build/checks/checks.json").read_text())


def _result(data: dict, cid: str) -> dict:  # type: ignore[type-arg]
    return next(r for r in data["results"] if r["id"] == cid)


def _write_part(root: Path, pid: str, **fields: object) -> None:
    data = {
        "id": pid,
        "rev": "A",
        "name": pid,
        "kind": "custom",
        "process": "cut-block",
        "material": {"name": "mild steel"},
        "finish": "none",
        "tolerance_class": "ISO2768-m",
        "cost": {"unit": "1 USD"},
    }
    data.update(fields)
    (root / "model/parts" / f"{pid}.yaml").write_text(yaml.safe_dump(data, sort_keys=False))


def _blank_product(tmp_path: Path, name: str = "fx") -> Path:
    r = n2f("init", str(tmp_path / name), "--template", "blank", "--no-tracking")
    assert r.returncode == 0, r.stderr
    root = tmp_path / name
    (root / "model/requirements.yaml").write_text(
        yaml.safe_dump(
            {
                "requirements": [
                    {
                        "id": "REQ-001",
                        "title": "No overlap",
                        "statement": "Parts do not overlap.",
                        "category": "geometry",
                        "verify": {"kind": "interference", "target": "asm://top"},
                        "allocation": ["asm://top"],
                    },
                ]
            },
            sort_keys=False,
        )
    )
    return root


def _two_blocks(tmp_path: Path, offset: float, mating: bool) -> Path:
    root = _blank_product(tmp_path)
    for pid in ("a", "b"):
        _write_part(
            root,
            pid,
            geometry={"kit": "block", "args": {"length": 50, "width": 50, "height": 50}},
            interfaces=(["iface://ab"] if mating else []),
        )
    if mating:
        (root / "model/interfaces/ab.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "ab",
                    "kind": "mating-face",
                    "parties": ["part://a", "part://b"],
                    "spec": {"width": "50 mm", "depth": "50 mm"},
                },
                sort_keys=False,
            )
        )
    (root / "model/assemblies/top.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "top",
                "name": "Top",
                "geometry": {"module": "geometry/top.py"},
                "children": [{"part": "part://a"}, {"part": "part://b"}],
            },
            sort_keys=False,
        )
    )
    (root / "model/geometry/top.py").write_text(
        "def build(P, I, parts):\n"
        "    from napkin2factory.geometry.assembly import AssemblyResult, place\n"
        "    r = AssemblyResult()\n"
        "    r.add(place('part://a', parts['a']))\n"
        f"    r.add(place('part://b', parts['b'], translate=({offset}, 0.0, 0.0)))\n"
        "    return r\n"
    )
    return root


def test_interference_overlapping_blocks_fail(tmp_path: Path) -> None:
    data = _checks(_two_blocks(tmp_path, 40.0, mating=False))
    res = _result(data, "interference://top")
    assert res["status"] == "fail" and "part://a#1" in res["message"]
    assert _result(data, "req://REQ-001")["status"] == "fail"
    assert abs(res["detail"]["interferences"][0]["volume"] - 10 * 50 * 50) < 1


def test_interference_touching_blocks_pass(tmp_path: Path) -> None:
    data = _checks(_two_blocks(tmp_path, 50.0, mating=False))
    assert _result(data, "interference://top")["status"] == "pass"


def test_allowed_contact_mating_face(tmp_path: Path) -> None:
    """D29: parts joined by a mating-face interface may overlap; recorded as allowed-contact."""
    root = _two_blocks(tmp_path, 49.0, mating=True)
    data = _checks(root)
    res = _result(data, "interference://top")
    assert res["status"] == "pass"
    assert res["evidence"]["allowed-contact"] == [
        "part://a#1 ~ part://b#1: allowed-contact: iface://ab"
    ]
    assert _result(data, "iface://ab")["status"] == "pass"


def test_interface_mismatch_fails(tmp_path: Path) -> None:
    """A party whose recorded pattern disagrees with the other's (wrong spacing) must fail."""
    from napkin2factory.core.checks.interface import check_interface

    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=False)
    _checks(root)
    product = load_product(root)
    iface = product.interfaces["lid-base-mount"]
    assert check_interface(product, iface, root / "build").status == "pass"
    feats_path = root / "build/parts/lid/features.json"
    feats = json.loads(feats_path.read_text())
    pat = next(p for p in feats["patterns"] if p["interface"] == "iface://lid-base-mount")
    pat["centers"][0][0] += 5.0  # one hole 5 mm off
    feats_path.write_text(json.dumps(feats))
    rep = check_interface(product, iface, root / "build")
    assert rep.status == "fail" and "do not match" in rep.message and "://" not in rep.message
    feats["patterns"] = []  # no pattern at all
    feats_path.write_text(json.dumps(feats))
    rep = check_interface(product, iface, root / "build")
    assert rep.status == "fail" and "does not cut the holes" in rep.message


def test_enclosure_matrix_and_rulepacks() -> None:
    root = EXAMPLES / "enclosure"
    data = _checks(root)
    st = {r["id"]: r["status"] for r in data["results"]}
    assert (
        st["req://REQ-004"] == "needs-human"
        and st["req://REQ-005"] == "pass"
        and st["req://REQ-006"] == "pass"
    )
    assert st["rule://sheet-metal-v0/min-bend-radius@base"] == "pass"
    assert st["rule://sheet-metal-v0/relief-present@base"] == "pass"
    assert st["rule://sheet-metal-v0/hole-to-bend@bracket"] == "pass"
    assert st["rule://general-v0/cots-source-verified@m4x10-screw"] == "warn"
    assert st["count://enclosure"] == "pass" and st["doc://assembly"] == "pass"
    assert data["summary"]["fail"] == 0
    assert data["matrix"]["rules"]["cells"]["base"]["rule://sheet-metal-v0/min-flange"] == "pass"


def test_rulepack_tight_bend_radius_fails(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=False)
    params = root / "model/parameters.yaml"
    params.write_text(
        params.read_text().replace(
            "bracket-bend-radius: {value: 2,", "bracket-bend-radius: {value: 0.5,"
        )
    )
    data = _checks(root)
    res = _result(data, "rule://sheet-metal-v0/min-bend-radius@bracket")
    assert res["status"] == "fail" and "0.5" in res["message"]
    assert data["summary"]["fail"] >= 1


def test_summary_keys_and_released_next_step(tmp_path: Path) -> None:
    """checks.json carries every summary key; a released product's next step has no label."""
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=True)
    data = _checks(root)
    assert set(data["summary"]) == {
        "pass",
        "fail",
        "warn",
        "skip",
        "needs-human",
        "signed",
        "example",
    }
    from napkin2factory.core.vcs import Vcs

    v = Vcs(root)
    v.snapshot("ready")
    v.tag("v1.0.0", "Revision v1.0.0")
    st = compute_stage(load_product(root))
    assert st.stage == "released" and st.next_step == "send the Revision to the manufacturer"
    assert st.headline == "released"


def test_broken_product_exits_2(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=False)
    req = root / "model/requirements.yaml"
    req.write_text(req.read_text().replace('op: "<=", value: 150 mm', 'op: "<=", value: 100 mm'))
    r = n2f("check", cwd=root)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "needs attention" in r.stdout  # owner vocabulary for a failing row
    ok = n2f("check", "--json", cwd=EXAMPLES / "bracket")
    assert ok.returncode == 0
    assert json.loads(ok.stdout)["summary"]["fail"] == 0


def test_stage_progression(tmp_path: Path) -> None:
    """Each gate in turn, via n2f status --json; warn never changes the stage."""
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=True)
    s0 = compute_stage(load_product(root))
    assert s0.stage == "intake" and any("not built yet" in b for b in s0.gates[1].blockers)
    assert s0.headline == "design"  # Intake is ticked: the owner is in Design (gate B, B5)
    run_build(load_product(root), target="geometry", quiet=True, render=False)
    s1 = compute_stage(load_product(root))
    assert s1.stage == "design" and "checks have not run" in s1.gates[2].blockers[0]
    _checks(root)
    s2 = compute_stage(load_product(root))
    assert s2.stage == "verify", s2.gates[2].blockers
    assert any("no Revision" in b for b in s2.gates[3].blockers)
    r = n2f("status", "--json", cwd=root)
    assert json.loads(r.stdout)["stage"] == "verify"
    # a warn-only change must not move the stage back
    part = root / "model/parts/l-bracket.yaml"
    part.write_text(
        part.read_text().replace(
            "cost: {unit: 12 USD, basis: estimate, "
            'note: "laser cut + one bend + powder coat, quantity 10"}\n',
            "",
        )
    )
    data = _checks(root)
    assert data["summary"]["fail"] == 0
    assert compute_stage(load_product(root)).stage == "verify"
    # released: snapshot + tag
    from napkin2factory.core.vcs import Vcs

    v = Vcs(root)
    v.snapshot("ready")
    v.tag("v1.0.0", "Revision v1.0.0")
    assert compute_stage(load_product(root)).stage == "released"


def test_stage_intake_blocked_by_lint(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=False)
    req = root / "model/requirements.yaml"
    req.write_text(
        req.read_text().replace("    allocation: [part://l-bracket, param://bracket-length]\n", "")
    )
    s = compute_stage(load_product(root))
    assert s.stage == "intake" and not s.gates[0].ok and "L3-allocation" in s.gates[0].blockers[0]


def test_doc_staleness_detected(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=False)
    _checks(root)
    # Render the docs, then change a value they read without rebuilding docs: run checks only.
    from napkin2factory.core.checks.engine import doc_staleness

    params = root / "model/parameters.yaml"
    params.write_text(
        params.read_text().replace(
            "bracket-spacing:   {value: 100,", "bracket-spacing:   {value: 120,"
        )
    )
    stale = doc_staleness(load_product(root), root / "build")
    by = {r.id: r for r in stale}
    assert (
        by["doc://assembly"].status == "fail"
        and "param://bracket-spacing" in by["doc://assembly"].message
    )
    assert by["doc://safety"].status == "pass"
    # a full build re-renders and clears it
    data = _checks(root)
    assert _result(data, "doc://assembly")["status"] == "pass"


def test_calc_requirement(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=False)
    (root / "model/calcs/load.py").write_text(
        '"""Bracket load calcs."""\n'
        "from napkin2factory.core.units import Quantity\n\n\n"
        "def stress(P):\n"
        '    """Nominal bending stress, F*L / (w t^2 / 6); F = m g. Source: Roark, cantilever."""\n'
        "    g = Quantity(9.81, 'm/s**2')\n"
        "    f = (P['shelf-load'] * g).to('N')\n"
        "    moment = f * P['bracket-length']\n"
        "    z = P['bracket-width'] * P['bracket-thickness'] ** 2 / 6\n"
        "    return (moment / z).to('MPa')\n"
    )
    req = root / "model/requirements.yaml"
    req.write_text(
        req.read_text()
        + """  - id: REQ-004
    title: Stress margin
    statement: Nominal bending stress stays below 100 MPa.
    category: performance
    verify: {kind: calc, target: calc://load.stress, op: "<", value: 100 MPa}
    allocation: [part://l-bracket, param://bracket-thickness]
"""
    )
    data = _checks(root)
    res = _result(data, "req://REQ-004")
    assert res["status"] == "pass", res
    assert "calc://load.stress" in res["evidence_keys"]
    assert set(res["detail"]["calc"]["reads"]) == {
        "param://shelf-load",
        "param://bracket-length",
        "param://bracket-width",
        "param://bracket-thickness",
    }
    params = root / "model/parameters.yaml"
    params.write_text(
        params.read_text().replace("bracket-thickness: {value: 4,", "bracket-thickness: {value: 1,")
    )
    data = _checks(root)
    assert _result(data, "req://REQ-004")["status"] == "fail"


def test_check_table_uri_display_follows_persona(tmp_path: Path) -> None:
    """B-0008: the owner's tables read ``REQ-001`` and ``base``; the engineer's keep prefixes."""
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=False)
    r = n2f("check", "--all", cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    rows = [ln for ln in r.stdout.splitlines() if ln.startswith("│")]
    req_rows = [ln for ln in rows if "REQ-001" in ln]
    assert req_rows and all("req://" not in ln for ln in req_rows)
    subject_cells = [ln.split("│")[2].strip() for ln in rows if "general-v0/" in ln]
    assert "base" in subject_cells and not any("://" in c for c in subject_cells)
    assert not any(ln.split("│")[1].strip().startswith("rule://") for ln in rows)
    op = root / "operator.yaml"
    op.write_text(op.read_text().replace("persona: owner", "persona: engineer"))
    r = n2f("check", "--all", cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    rows = [ln for ln in r.stdout.splitlines() if ln.startswith("│")]
    subject_cells = [ln.split("│")[2].strip() for ln in rows if "general-v0/" in ln]
    assert "part://base" in subject_cells
    assert any(ln.split("│")[1].strip().startswith("rule://") for ln in rows)
    # machine output is never shortened
    r = n2f("check", "--json", cwd=root)
    assert any(x["subject"] == "part://base" for x in json.loads(r.stdout)["results"])
