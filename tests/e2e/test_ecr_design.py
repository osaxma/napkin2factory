"""M6: a design change request, edited in place, on a tracked copy of the enclosure (D7)."""

from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import EXAMPLES, copy_product
from tests.e2e.test_ecr import _run


def test_design_ecr_edited_in_place(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", prebuilt=True, render=False)
    _run("build", "--no-render", cwd=root)
    _run(
        "ecr",
        "start",
        "--title",
        "Rounder lid",
        "--kind",
        "design",
        "--task",
        "Round the lid corners to 10 mm",
        cwd=root,
    )
    part = root / "model/parts/lid.yaml"
    part.write_text(part.read_text().replace("corner_radius: 5 mm", "corner_radius: 10 mm"))
    r = _run("ecr", "impact", "ECR-001", cwd=root)
    assert "Designer tasks" in r.stdout and "Round the lid corners to 10 mm" in r.stdout
    _run("ecr", "approve", "ECR-001", "--by", "Owner", cwd=root)
    _run("build", "--no-render", cwd=root)
    _run("signoff", "REQ-004", "--by", "x", "--statement", "inspected", cwd=root)
    r = _run("ecr", "close", "ECR-001", "--json", cwd=root)
    assert json.loads(r.stdout)["bumped"]["part://lid"] == ["A", "B"]
