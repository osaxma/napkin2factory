"""B-0020: a design change that only edits a part's YAML still bumps its revision.

The part's geometry does not change (its built outputs hash the same), so the bump rests
on the declared-field diff, which must span the whole change request (from before it was
applied), not only the most recent snapshot: a sign-off in between makes its own.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from napkin2factory.core.vcs import Vcs
from tests.conftest import EXAMPLES, copy_product
from tests.e2e.test_ecr import _run


def test_yaml_only_design_change_bumps_revision_after_signoff(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=True)
    _run("build", "--no-render", cwd=root)
    # author a finish-only change (no geometry), capture it as a patch, revert (D7)
    part = root / "model/parts/lid.yaml"
    original = part.read_text()
    assert "finish: powder coat, grey" in original
    part.write_text(original.replace("finish: powder coat, grey", "finish: powder coat, black"))
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
        "Black lid",
        "--kind",
        "design",
        "--task",
        "Powder coat the lid black",
        "--patch",
        "changes/ECR-001.patch",
        cwd=root,
    )
    Vcs(root).snapshot("file ECR-001")
    _run("ecr", "impact", "ECR-001", cwd=root)
    _run("ecr", "approve", "ECR-001", "--by", "Owner", cwd=root)
    lid_hash_before = _lid_hash(root)
    _run("ecr", "apply", "ECR-001", cwd=root)
    assert "finish: powder coat, black" in part.read_text()
    _run("build", "--no-render", cwd=root)
    assert _lid_hash(root) == lid_hash_before  # geometry unchanged: only the YAML moved
    # the sign-off snapshots on its own, after the change was applied
    _run("signoff", "REQ-004", "--by", "x", "--statement", "inspected", cwd=root)
    r = _run("ecr", "close", "ECR-001", cwd=root)
    out = " ".join(r.stdout.split())  # undo terminal wrapping
    assert "part://lid: rev A → B" in out, out
    assert yaml.safe_load(part.read_text())["rev"] == "B"
    # B-0033: closing names the stage as `n2f status` does, in words
    assert "ECR-001 closed · stage: ready to release · next: `n2f release vX.Y.Z`" in out
    # nothing else changed, so nothing else moves
    assert yaml.safe_load((root / "model/parts/base.yaml").read_text())["rev"] == "A"


def _lid_hash(root: Path) -> str:
    from napkin2factory.core.graph.manifest import Manifest

    return Manifest.load(root / "build").entries["part:lid"].output_hash
