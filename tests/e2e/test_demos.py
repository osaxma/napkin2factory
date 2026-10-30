"""M8: both kiln demos run unattended (DoD item 4). Slow; part of make check-full."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.conftest import EXAMPLES

pytestmark = pytest.mark.full  # make check-full (D27)

DEMOS = EXAMPLES / "kiln"
GIT_WORDS = ("fatal:", "branch", "commit", "merge", "repository")


def _run_demo(script: str, workdir: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["DEMO_DIR"] = str(workdir)
    env["N2F_OFFLINE"] = "1"
    env["COLUMNS"] = "200"
    workdir.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        ["bash", str(DEMOS / script)], env=env, capture_output=True, text=True, check=False
    )


def test_demo_parametric(tmp_path: Path) -> None:
    r = _run_demo("demo.sh", tmp_path / "demo")
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    out = r.stdout + r.stderr
    for w in GIT_WORDS:
        assert w not in out.lower(), f"git vocabulary {w!r} leaked"
    work = tmp_path / "demo"
    assert (work / "build/changes/ECR-001-impact.md").is_file()
    assert (work / "build/site/diff/v1.0.0..v1.1.0/index.html").is_file()
    assert (work / "build/release/kiln-v1.1.0.zip").is_file()
    assert "EXAMPLE" in out  # the re-sign step is labelled
    import yaml

    assert yaml.safe_load((work / "changes/ECR-001.yaml").read_text())["released_in"] == "v1.1.0"
    html = (work / "build/site/diff/v1.0.0..v1.1.0/index.html").read_text()
    assert "chamber-height" in html and "250 mm" in html


def test_demo_design(tmp_path: Path) -> None:
    r = _run_demo("demo-design.sh", tmp_path / "demo")
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    work = tmp_path / "demo"
    assert (work / "build/site/diff/v1.1.0..v1.2.0/index.html").is_file()
    assert (work / "build/release/kiln-v1.2.0.zip").is_file()
    assert (work / "model/parts/peephole-plug.yaml").is_file()
    import yaml

    assert yaml.safe_load((work / "changes/ECR-002.yaml").read_text())["released_in"] == "v1.2.0"
