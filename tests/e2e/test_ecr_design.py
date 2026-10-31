"""M6: a design change request with a patch, on a tracked copy of the enclosure (D7).

Split from test_ecr.py so it runs on its own test worker (S-080).
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import EXAMPLES, copy_product
from tests.e2e.test_ecr import _run


def test_design_ecr_with_patch(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=True)
    _run("build", "--no-render", cwd=root)
    # author the change, capture the diff, revert (the D7 workflow)
    part = root / "model/parts/lid.yaml"
    original = part.read_text()
    part.write_text(original.replace("corner_radius: 5 mm", "corner_radius: 10 mm"))
    import subprocess

    diff = subprocess.run(
        ["git", "diff"], cwd=root, capture_output=True, text=True, check=True
    ).stdout
    part.write_text(original)
    (root / "changes").mkdir(exist_ok=True)
    (root / "changes/ECR-001.patch").write_text(diff)
    _run(
        "ecr",
        "new",
        "--title",
        "Rounder lid",
        "--kind",
        "design",
        "--task",
        "Round the lid corners to 10 mm",
        "--patch",
        "changes/ECR-001.patch",
        cwd=root,
    )
    from napkin2factory.core.vcs import Vcs

    Vcs(root).snapshot("file ECR-001")
    r = _run("ecr", "impact", "ECR-001", cwd=root)
    assert "Designer tasks" in r.stdout and "estimates" in r.stdout
    _run("ecr", "approve", "ECR-001", "--by", "Owner", cwd=root)
    r = _run("ecr", "apply", "ECR-001", cwd=root)
    assert "corner_radius: 10 mm" in part.read_text()
    assert "task for the designer" in r.stdout
    _run("build", "--no-render", cwd=root)
    _run("signoff", "REQ-004", "--by", "x", "--statement", "inspected", cwd=root)
    r = _run("ecr", "close", "ECR-001", "--json", cwd=root)
    assert json.loads(r.stdout)["bumped"]["part://lid"] == ["A", "B"]
