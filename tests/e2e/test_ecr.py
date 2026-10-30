"""M6: the change-request loop on a temporary tracked copy of the enclosure (D23)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
import yaml

from tests.conftest import EXAMPLES, copy_product, n2f

os.environ.setdefault("N2F_OFFLINE", "1")
GIT_WORDS = ("fatal:", "git ", "branch", "commit", "merge", "repository")


def _no_git_words(text: str) -> None:
    low = text.lower()
    for w in GIT_WORDS:
        assert w not in low, f"git vocabulary {w!r} leaked: {text}"


def _run(*args: str, cwd: Path, ok: bool = True):  # type: ignore[no-untyped-def]
    r = n2f(*args, cwd=cwd)
    if ok:
        assert r.returncode == 0, f"{args}: {r.stdout}\n{r.stderr}"
    _no_git_words(r.stdout + r.stderr)
    return r


@pytest.fixture(scope="module")
def product(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = copy_product(
        EXAMPLES / "enclosure", tmp_path_factory.mktemp("ecr") / "enclosure", git=True
    )
    _run("build", "--no-render", cwd=root)
    return root


def test_parametric_loop(product: Path) -> None:
    root = product
    r = _run(
        "ecr",
        "new",
        "--title",
        "Taller box",
        "--set",
        "param://box-height=100mm",
        "--set",
        "req://REQ-001#verify.value=120 mm",
        "--json",
        cwd=root,
    )
    ecr_id = json.loads(r.stdout)["id"]
    assert ecr_id == "ECR-001" and (root / "changes/ECR-001.yaml").is_file()
    # impact before anything changes
    r = _run("ecr", "impact", ecr_id, "--json", cwd=root)
    impact = json.loads(r.stdout)
    assert "part:base" in impact["rules"] and impact["firm"] is True
    data = yaml.safe_load((root / "changes/ECR-001.yaml").read_text())
    assert data["status"] == "impact" and data["impact"]["rules"]
    assert (root / "build/changes/ECR-001-impact.md").is_file()
    params_before = (root / "model/parameters.yaml").read_text()
    assert re.search(r"box-height:\s+\{value: 80,", params_before)  # untouched
    # apply refuses before approval
    r = _run("ecr", "apply", ecr_id, cwd=root, ok=False)
    assert r.returncode == 3 and "approve" in r.stderr
    _run("ecr", "approve", ecr_id, "--by", "Owner", cwd=root)
    r = _run("ecr", "apply", ecr_id, cwd=root)
    params_after = (root / "model/parameters.yaml").read_text()
    assert re.search(r"box-height:\s+\{value: 100,\s+unit: mm", params_after), params_after
    # comments and the other lines are preserved (one-value diff)
    diff_lines = [
        a
        for a, b in zip(params_before.splitlines(), params_after.splitlines(), strict=True)
        if a != b
    ]
    assert len(diff_lines) == 1
    reqs = yaml.safe_load((root / "model/requirements.yaml").read_text())
    assert reqs["requirements"][0]["verify"]["value"] == "120 mm"
    data = yaml.safe_load((root / "changes/ECR-001.yaml").read_text())
    assert data["status"] == "applied" and data["applied"]["snapshot"]
    # rebuild + check + close → revision bumps and changelog
    _run("build", "--no-render", cwd=root)
    _run("check", cwd=root)
    r = _run("ecr", "close", ecr_id, "--json", cwd=root)
    out = json.loads(r.stdout)
    assert out["bumped"]["part://base"] == ["A", "B"]
    assert out["bumped"]["asm://enclosure"] == ["A", "B"]
    assert "part://lid" not in out["bumped"]
    assert "part://bracket" not in out["bumped"]
    assert "rev: B" in (root / "model/parts/base.yaml").read_text()
    changelog = (root / "CHANGELOG.md").read_text()
    assert "ECR-001" in changelog and "part://base: rev A → B" in changelog
    data = yaml.safe_load((root / "changes/ECR-001.yaml").read_text())
    assert data["status"] == "closed"
    r = _run("ecr", "list", "--json", cwd=root)
    assert json.loads(r.stdout)["ecrs"][0]["status"] == "closed"


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


def test_reject_and_state_machine(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=True)
    _run("ecr", "new", "--title", "Nope", "--set", "param://bracket-width=70mm", cwd=root)
    r = _run("ecr", "approve", "ECR-001", "--by", "x", cwd=root, ok=False)
    assert r.returncode == 3 and "impact" in r.stderr
    _run("ecr", "reject", "ECR-001", "--reason", "not needed", cwd=root)
    r = _run("ecr", "impact", "ECR-001", cwd=root, ok=False)
    assert r.returncode == 3
    r = _run("ecr", "new", "--title", "Bad target", "--set", "param://nope=1mm", cwd=root, ok=False)
    assert r.returncode == 3 and "does not exist" in r.stderr


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
    r = _run("ecr", "close", "ECR-001", "--json", cwd=root)
    assert json.loads(r.stdout)["bumped"]["part://lid"] == ["A", "B"]


def test_not_tracked_refusal_wording(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=False)
    _run("ecr", "new", "--title", "x", "--set", "param://bracket-width=70mm", cwd=root)
    _run("ecr", "impact", "ECR-001", cwd=root)
    _run("ecr", "approve", "ECR-001", "--by", "x", cwd=root)
    r = _run("ecr", "apply", "ECR-001", cwd=root, ok=False)
    assert r.returncode == 4 and "n2f init" in r.stderr
