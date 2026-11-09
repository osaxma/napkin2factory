"""Wave 8: concept switch refuses a missing or broken parameters file (B-0326)."""

from __future__ import annotations

import json
from pathlib import Path

from napkin2factory.core.vcs import Vcs
from tests.conftest import EXAMPLES, copy_product, n2f


def test_concept_switch_refuses_missing_parameters(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)
    params_file = root / "model" / "parameters.yaml"
    params_file.unlink()

    vcs = Vcs(root)
    before_snapshots = vcs.snapshot_count()
    before_unsaved = vcs.unsaved_files()

    r = n2f("concept", "switch", "C-001", "--override", "--reason", "try", "--json", cwd=root)
    assert r.returncode == 1, r.stdout + r.stderr
    data = json.loads(r.stdout)

    assert "model/parameters.yaml" in data["message"]
    assert data["message"] == "model/parameters.yaml is missing, so the switch cannot start"
    assert data["next"] == f"n2f undo --dir {root}, then run the switch again"
    assert not params_file.exists()
    assert vcs.snapshot_count() == before_snapshots
    assert vcs.unsaved_files() == before_unsaved


def test_concept_switch_refuses_invalid_yaml_parameters(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)
    params_file = root / "model" / "parameters.yaml"
    bad_yaml = "parameters:\n  width:\n    type: length\n   value: 100\n"
    params_file.write_text(bad_yaml, encoding="utf-8")

    vcs = Vcs(root)
    before_hash = vcs.working_hash()
    before_snapshots = vcs.snapshot_count()

    r = n2f("concept", "switch", "C-001", "--override", "--reason", "try", "--json", cwd=root)
    assert r.returncode == 1, r.stdout + r.stderr
    data = json.loads(r.stdout)

    assert "model/parameters.yaml" in data["message"]
    assert "line 4" in data["message"]
    assert data["next"] == "fix model/parameters.yaml line 4, then run the switch again"
    assert params_file.read_text(encoding="utf-8") == bad_yaml
    assert vcs.working_hash() == before_hash
    assert vcs.snapshot_count() == before_snapshots


def test_concept_switch_refuses_unvalidated_model(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)
    params_file = root / "model" / "parameters.yaml"
    content = params_file.read_text(encoding="utf-8")
    broken = content.replace("unit: mm,", "unit: mm, extra_key_refused: true,", 1)
    params_file.write_text(broken, encoding="utf-8")

    vcs = Vcs(root)
    before_hash = vcs.working_hash()
    before_snapshots = vcs.snapshot_count()

    r = n2f("concept", "switch", "C-001", "--override", "--reason", "try", "--json", cwd=root)
    assert r.returncode == 1, r.stdout + r.stderr
    data = json.loads(r.stdout)

    assert "model/parameters.yaml" in data["message"]
    assert "extra_key_refused" in data["message"]
    assert data["next"] == f"n2f validate --json --dir {root}"
    assert params_file.read_text(encoding="utf-8") == broken
    assert vcs.working_hash() == before_hash
    assert vcs.snapshot_count() == before_snapshots
