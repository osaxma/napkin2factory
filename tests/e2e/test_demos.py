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


def test_demo_electrical(tmp_path: Path) -> None:
    """v0.6 DoD 4: wiring left for later at v1.0.0 → ECR-003 adds it → the headroom choice
    raised and decided → v1.1.0 with the wiring done here → the diff shows it added."""
    r = _run_demo("demo-electrical.sh", tmp_path / "demo")
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    out = r.stdout + r.stderr
    for w in GIT_WORDS:
        assert w not in out.lower(), f"git vocabulary {w!r} leaked"
    work = tmp_path / "demo"
    import yaml

    first = (work / "build/release/v1.0.0/README.txt").read_text(encoding="utf-8")
    assert "Wiring (left for later" in first
    later = (work / "build/release/v1.1.0/README.txt").read_text(encoding="utf-8")
    assert "Wiring (left for later" not in later
    assert yaml.safe_load((work / "changes/ECR-003.yaml").read_text())["released_in"] == "v1.1.0"
    assert yaml.safe_load((work / "n2f.yaml").read_text())["scope"]["electrical"]["state"] == "in"
    decs = yaml.safe_load((work / "model/decisions.yaml").read_text())["decisions"]
    picked = [d for d in decs if any("supply-headroom" in s for s in d.get("sources", []))]
    assert len(picked) == 1 and "option dedicated" in picked[0]["sources"][0]
    for cid in ("power", "control", "sensing", "earth"):
        assert (work / f"build/electrical/{cid}/diagram.svg").is_file()
    assert "electrical/power/diagram.svg" in _zip_names(work / "build/release/kiln-v1.1.0.zip")
    html = (work / "build/site/diff/v1.0.0..v1.1.0/index.html").read_text(encoding="utf-8")
    assert "Wiring: added" in html  # the diff page's added section (M6, S-169)


def _zip_names(path: Path) -> str:
    import zipfile

    with zipfile.ZipFile(path) as z:
        return "\n".join(z.namelist())


def test_demo_napkin(tmp_path: Path) -> None:
    """DoD 5: four directions built → board → one red with reasons → promote → factory green."""
    r = _run_demo("demo-napkin.sh", tmp_path / "demo")
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    out = r.stdout + r.stderr
    for w in GIT_WORDS:
        assert w not in out.lower(), f"git vocabulary {w!r} leaked"
    assert out.count("this direction has problems:") == 1
    assert "C-001 — this direction has problems:" in out
    assert "240 mm for the open door (the 702 mm door leaf opened to 110°)" in out
    assert "correctness render" not in out  # the styled pictures were taken (N6)
    # promotion reconciled with the model: the 11 envelope numbers and the 2 door numbers
    assert "Seeded 0 parameters (13 already declared)" in out
    assert "+ REQ-024 The open door keeps to its room beside the hinge" in out
    work = tmp_path / "demo"
    board = work / "build/concepts/board.html"
    assert board.is_file() and board.stat().st_size <= 20 * 1024 * 1024
    for cid in ("C-001", "C-003"):
        assert (work / f"build/concepts/{cid}/renders/styled-iso.png").is_file()
    import json

    import yaml

    card = yaml.safe_load((work / "concepts/C-003.yaml").read_text())
    assert card["status"] == "promoted"
    decs = yaml.safe_load((work / "model/decisions.yaml").read_text())["decisions"]
    dec = next(d for d in decs if d["id"] == card["decision"]["dec"])
    assert dec["title"].startswith("Design direction:")
    assert "concepts/C-001.yaml" in dec["sources"]
    env = dict(os.environ, N2F_OFFLINE="1")
    check = subprocess.run(
        ["uv", "run", "--project", str(EXAMPLES.parent), "n2f", "check", "--json"],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    data = json.loads(check.stdout)
    assert data["summary"]["fail"] == 0
    reqs = yaml.safe_load((work / "model/requirements.yaml").read_text())["requirements"]
    form = [r["id"] for r in reqs if r["verify"]["kind"] == "rule"]
    assert len(form) >= 2
    status = {r["id"]: r["status"] for r in data["results"]}
    assert all(status[f"req://{rid}"] == "pass" for rid in form), status
