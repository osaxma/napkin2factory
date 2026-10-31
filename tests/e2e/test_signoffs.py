"""M4: sign-off semantics (D9, D25) on tracked copies of the examples.

Split from test_checks.py so the two halves run on different test workers (S-080).
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from napkin2factory.core.checks.stage import compute_stage
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES, copy_product, n2f
from tests.e2e.test_checks import _checks, _result

os.environ.setdefault("N2F_OFFLINE", "1")


def test_signoff_semantics(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=True)
    # add a non-safety manual requirement
    req = root / "model/requirements.yaml"
    req.write_text(
        req.read_text()
        + """  - id: REQ-008
    title: Label applied
    statement: The rating label is applied to the lid.
    category: usability
    verify: {kind: manual}
    allocation: [part://lid]
"""
    )
    data = _checks(root)
    assert _result(data, "req://REQ-008")["status"] == "needs-human"
    assert _result(data, "req://REQ-004")["status"] == "needs-human"
    r1 = n2f("signoff", "REQ-008", "--by", "Tester", "--statement", "Label seen.", cwd=root)
    assert r1.returncode == 0, r1.stderr
    r2 = n2f(
        "signoff",
        "REQ-004",
        "--by",
        "Tester",
        "--statement",
        "Edges checked.",
        "--example",
        cwd=root,
    )
    assert r2.returncode == 0, r2.stderr
    so = yaml.safe_load((root / "model/signoffs/REQ-004.yaml").read_text())
    assert so["example"] is True and so["evidence_keys"] and "part://base" in so["evidence_keys"]
    data = _checks(root)
    assert _result(data, "req://REQ-008")["status"] == "pass"  # non-safety → pass
    assert _result(data, "req://REQ-004")["status"] == "signed"  # safety → signed
    assert _result(data, "req://REQ-004")["detail"]["signoff"]["example"] is True
    # an example sign-off is counted apart, never as "signed"; the verify gate stays open
    assert data["summary"]["example"] == 1 and data["summary"]["signed"] == 0
    assert data["summary"]["needs-human"] == 0
    st = compute_stage(load_product(root))
    verify = st.gates[2]
    assert st.stage == "verify" and not verify.ok and verify.blockers == []
    assert verify.detail["example_signoffs"] == ["REQ-004"]
    assert verify.detail["why"] == "1 example sign-off — not a review"
    assert verify.caveats == [st.next_step]
    assert st.next_step == (
        "replace the 1 example sign-off (not a review) with a real one — "
        '`n2f signoff REQ-004 --by <name> --statement "…"` — '
        "or release with --allow-example-signoffs for a demonstration"
    )
    r = n2f("check", cwd=root)
    assert "1 example sign-off (not a review)" in r.stdout and "1 signed off" not in r.stdout
    r = n2f("status", cwd=root)
    assert "stage: Verify" in r.stdout and "1 example sign-off (not a review)" in r.stdout
    assert "next: replace the 1 example sign-off" in r.stdout
    # a real sign-off on the same requirement makes it count as signed and closes the gate
    r3 = n2f("signoff", "REQ-004", "--by", "Tester", "--statement", "Edges checked.", cwd=root)
    assert r3.returncode == 0, r3.stderr
    data = _checks(root)
    assert data["summary"]["example"] == 0 and data["summary"]["signed"] == 1
    st = compute_stage(load_product(root))
    assert st.gates[2].ok and st.stage == "verify" and "no Revision" in st.next_step
    assert st.headline == "ready"  # n2f status: "stage: ready to release" (gate B, B5)
    r = n2f("check", cwd=root)
    assert "1 signed off" in r.stdout and "example" not in r.stdout
    # change the evidence (base geometry) → back to needs-human
    params = root / "model/parameters.yaml"
    params.write_text(
        params.read_text().replace(
            "box-height:        {value: 80,", "box-height:        {value: 85,"
        )
    )
    data = _checks(root)
    res = _result(data, "req://REQ-004")
    assert res["status"] == "needs-human" and "evidence changed" in res["message"]
    assert _result(data, "req://REQ-008")["status"] == "pass"  # its evidence (lid) is unchanged
    assert data["summary"]["signed"] == 0 and data["summary"]["example"] == 0


def test_signoff_refuses_failing_requirement(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=False)
    req = root / "model/requirements.yaml"
    req.write_text(req.read_text().replace('op: "<=", value: 150 mm', 'op: "<=", value: 100 mm'))
    r = n2f("signoff", "REQ-001", "--by", "x", "--statement", "s", cwd=root)
    assert r.returncode == 1 and "currently fails" in r.stderr


def test_signoff_binds_parts_without_geometry(tmp_path: Path) -> None:
    """A cited bought part with ``geometry: none`` keys on its record (S-050)."""
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=True)
    req = root / "model/requirements.yaml"
    req.write_text(
        req.read_text()
        + """  - id: REQ-009
    title: Screws are the specified grade
    statement: The lid screws are the stainless A2 screws named in the BOM.
    category: safety
    safety: true
    priority: must
    verify: {kind: manual, note: "Check the screw packaging against the BOM line."}
    allocation: [part://m4x10-screw]
    rationale: Mild-steel screws rust in the owner's workshop.
    source: design
"""
    )
    assert _result(_checks(root), "req://REQ-009")["status"] == "needs-human"
    r = n2f("signoff", "REQ-009", "--by", "Tester", "--statement", "Packaging checked.", cwd=root)
    assert r.returncode == 0, r.stderr
    so = yaml.safe_load((root / "model/signoffs/REQ-009.yaml").read_text())
    assert so["evidence_keys"]["part://m4x10-screw"] != "missing"
    assert _result(_checks(root), "req://REQ-009")["status"] == "signed"
    screw = root / "model/parts/m4x10-screw.yaml"
    # a revision bump alone keeps the sign-off valid …
    screw.write_text(screw.read_text().replace("rev: A", "rev: B"))
    assert _result(_checks(root), "req://REQ-009")["status"] == "signed"
    # … and so does a styling role (N7: a colour is not evidence; M6 found the v0.2 `role`
    # field had voided every v0.1 sign-off on a bought part) …
    screw.write_text(screw.read_text().replace("kind: cots", "kind: cots\nrole: fastener"))
    assert "role: fastener" in screw.read_text()
    assert _result(_checks(root), "req://REQ-009")["status"] == "signed"
    # … a change to the part's record voids it
    screw.write_text(screw.read_text().replace("unit: 0.12 USD", "unit: 0.15 USD"))
    assert _result(_checks(root), "req://REQ-009")["status"] == "needs-human"
