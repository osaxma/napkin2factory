"""M6: closing a change request is gated by checks and sign-offs (B-0015).

Split from test_ecr.py so the two halves run on different test workers (S-080).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from tests.conftest import EXAMPLES, copy_product
from tests.e2e.test_ecr import _no_git_words, _run


def test_close_refused_when_checks_fail(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=True)
    _run("build", "--no-render", cwd=root)
    _run("ecr", "new", "--title", "Too big", "--set", "param://bracket-length=200mm", cwd=root)
    _run("ecr", "impact", "ECR-001", cwd=root)
    _run("ecr", "approve", "ECR-001", "--by", "x", cwd=root)
    _run("ecr", "apply", "ECR-001", cwd=root)
    _run("build", "--no-render", cwd=root)
    r = _run("ecr", "close", "ECR-001", cwd=root, ok=False)
    assert r.returncode == 3 and "cannot close" in r.stderr and "REQ-001" in r.stderr


def test_close_refused_while_signoff_needed(tmp_path: Path) -> None:
    """B-0015: close refuses while a requirement waits for a human sign-off, like release."""
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=True)
    _run("build", "--no-render", cwd=root)
    _run(
        "ecr",
        "new",
        "--title",
        "Wider cable entry",
        "--set",
        "param://cable-cutout-width=45mm",
        cwd=root,
    )
    _run("ecr", "impact", "ECR-001", cwd=root)
    _run("ecr", "approve", "ECR-001", "--by", "x", cwd=root)
    _run("ecr", "apply", "ECR-001", cwd=root)
    _run("build", "--no-render", cwd=root)
    r = _run("ecr", "close", "ECR-001", cwd=root, ok=False)
    err = " ".join(r.stderr.split())  # undo terminal wrapping
    assert r.returncode == 3, r.stdout + r.stderr
    assert "ECR-001 cannot close" in err and "REQ-004" in err and "sign-off" in err
    assert '`n2f signoff REQ-004 --by <name> --statement "…"`' in err
    assert "sign it off, then close again" in err
    data = yaml.safe_load((root / "changes/ECR-001.yaml").read_text())
    assert data["status"] == "applied"
    _run("signoff", "REQ-004", "--by", "x", "--statement", "inspected", cwd=root)
    r = _run("ecr", "close", "ECR-001", "--json", cwd=root)
    assert json.loads(r.stdout)["stage"] in ("verify", "released")
    data = yaml.safe_load((root / "changes/ECR-001.yaml").read_text())
    assert data["status"] == "closed"


def test_close_gate_lists_fails_before_signoffs() -> None:
    from napkin2factory.core.errors import GateBlocked
    from napkin2factory.ecr.lifecycle import _close_gate

    results = [
        {"id": "req://REQ-004", "status": "needs-human", "message": "inspect the edges"},
        {"id": "req://REQ-001", "status": "fail", "message": "too tall"},
        {
            "id": "req://REQ-002",
            "status": "signed",
            "message": "EXAMPLE",
            "detail": {"signoff": {"example": True}},
        },
        {"id": "req://REQ-003", "status": "pass", "message": "ok"},
    ]
    with pytest.raises(GateBlocked) as exc:
        _close_gate("ECR-007", results)
    msg = str(exc.value)
    assert exc.value.exit_code == 3
    assert msg.index("req://REQ-001") < msg.index("REQ-004 needs a human sign-off")
    assert "(inspect the edges)" in msg and "REQ-002" not in msg
    _no_git_words(msg)
    # an example sign-off alone never blocks closing
    _close_gate("ECR-007", results[2:])
