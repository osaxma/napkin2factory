"""M6: the change-request loop on a temporary tracked copy of the enclosure (D23)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
import yaml

from tests.conftest import EXAMPLES, copy_product, n2f

# the module's shared product is built once, on one worker (S-196)
pytestmark = pytest.mark.xdist_group("test_ecr")

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


def _legacy_new(*args: str, cwd: Path) -> None:
    """File a change request the v0.7 way: no baseline, as the kiln's drafts exist (B-0263).

    Takes the arguments ``ecr new`` took; `ecr new` is now `ecr start`, so the old steps
    (impact on the patch, approve, apply, close) are reached through this.
    """
    import argparse

    from napkin2factory.core.loader import load_product
    from napkin2factory.ecr import lifecycle

    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--kind", default="parametric")
    ap.add_argument("--reason")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--task", action="append", default=[])
    ap.add_argument("--patch")
    ap.add_argument("--by", default="human")
    ns = ap.parse_args(args)
    lifecycle.new_ecr(
        load_product(cwd), ns.title, ns.kind, ns.reason, ns.set, ns.task, ns.patch, ns.by
    )


@pytest.fixture(scope="module")
def product(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = copy_product(
        EXAMPLES / "enclosure",
        tmp_path_factory.mktemp("ecr") / "enclosure",
        git=True,
        prebuilt=True,
        render=False,
    )
    _run("build", "--no-render", cwd=root)
    return root


def test_parametric_loop(product: Path) -> None:
    root = product
    _legacy_new(
        "--title",
        "Taller box",
        "--set",
        "param://box-height=100mm",
        "--set",
        "req://REQ-001#verify.value=120 mm",
        cwd=root,
    )
    ecr_id = "ECR-001"
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
    # REQ-004 is checked by hand: close waits for its sign-off (B-0015)
    _run("signoff", "REQ-004", "--by", "x", "--statement", "inspected", cwd=root)
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


def test_reject_and_state_machine(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=True)
    _legacy_new("--title", "Nope", "--set", "param://bracket-width=70mm", cwd=root)
    r = _run("ecr", "approve", "ECR-001", "--by", "x", cwd=root, ok=False)
    assert r.returncode == 3 and "impact" in r.stderr
    _run("ecr", "reject", "ECR-001", "--reason", "not needed", cwd=root)
    r = _run("ecr", "impact", "ECR-001", cwd=root, ok=False)
    assert r.returncode == 3
    r = _run(
        "ecr", "start", "--title", "Bad target", "--set", "param://nope=1mm", cwd=root, ok=False
    )
    assert r.returncode == 3 and "does not exist" in r.stderr


def test_not_tracked_refusal_wording(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=False)
    _legacy_new("--title", "x", "--set", "param://bracket-width=70mm", cwd=root)
    _run("ecr", "impact", "ECR-001", cwd=root)
    _run("ecr", "approve", "ECR-001", "--by", "x", cwd=root)
    r = _run("ecr", "apply", "ECR-001", cwd=root, ok=False)
    assert r.returncode == 4 and "n2f init" in r.stderr
