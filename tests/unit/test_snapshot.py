"""Tests for ``n2f snapshot`` and ``n2f discard`` (B-0198)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tests.conftest import EXAMPLES, copy_product, n2f


def test_discard_preserves_a_started_change_request(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", prebuilt=True)
    changes_dir = root / "changes"

    r_start = n2f("ecr", "start", "--title", "Thicker bracket", cwd=root)
    assert r_start.returncode == 0, r_start.stderr

    r_impact = n2f("ecr", "impact", "ECR-001", cwd=root)
    assert r_impact.returncode == 0, r_impact.stderr

    r_app = n2f("ecr", "approve", "ECR-001", "--by", "Owner", cwd=root)
    assert r_app.returncode == 0, r_app.stderr

    param_file = root / "model" / "parameters.yaml"
    orig_params = param_file.read_text(encoding="utf-8")
    param_file.write_text(orig_params + "\n# dirty edit\n", encoding="utf-8")

    ecr_file = changes_dir / "ECR-001.yaml"
    assert ecr_file.exists()

    r_disc = n2f("discard", "--yes", cwd=root)
    assert r_disc.returncode == 0, r_disc.stderr
    assert "discarded changes in model/parameters.yaml" in r_disc.stdout
    assert re.search(r"matches checkpoint #\d+ again", r_disc.stdout)
    assert "n2f redo" in r_disc.stdout

    assert ecr_file.exists(), "ECR-001.yaml was deleted by discard!"
    assert param_file.read_text(encoding="utf-8") == orig_params, "model edit was not undone!"


def test_discard_json_and_clean(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", prebuilt=True)
    param_file = root / "model" / "parameters.yaml"
    orig_params = param_file.read_text(encoding="utf-8")
    param_file.write_text(orig_params + "\n# dirty edit\n", encoding="utf-8")

    r_disc = n2f("discard", "--json", cwd=root)
    assert r_disc.returncode == 0, r_disc.stderr
    data = json.loads(r_disc.stdout)
    assert data["discarded"] is True
    assert "model/parameters.yaml" in data["files"]
    assert param_file.read_text(encoding="utf-8") == orig_params

    # When clean
    r_clean = n2f("discard", cwd=root)
    assert "nothing to discard" in r_clean.stdout
