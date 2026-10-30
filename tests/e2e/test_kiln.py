"""M8: the kiln builds clean, every artifact parses, golden assembly props hold, and (under
N2F_TIMING=1) a clean build finishes within the 10-minute budget (D30)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES, copy_product
from tests.validate_outputs import validate_outputs

os.environ.setdefault("N2F_OFFLINE", "1")
TIMING = os.environ.get("N2F_TIMING") == "1"
GOLDEN = Path(__file__).parent.parent / "golden" / "goldens" / "kiln.json"


@pytest.fixture(scope="module")
def kiln(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, float]:
    root = copy_product(EXAMPLES / "kiln", tmp_path_factory.mktemp("kiln") / "kiln", git=True)
    t0 = time.perf_counter()
    run_build(load_product(root), quiet=True, render=True)
    return root, time.perf_counter() - t0


def test_kiln_artifacts_complete(kiln: tuple[Path, float]) -> None:
    root, _ = kiln
    assert validate_outputs(root) == []


def test_kiln_checks_green_with_example_signoffs(kiln: tuple[Path, float]) -> None:
    root, _ = kiln
    data = json.loads((root / "build/checks/checks.json").read_text())
    assert data["summary"]["fail"] == 0, [r["id"] for r in data["results"] if r["status"] == "fail"]
    assert data["summary"]["needs-human"] == 0
    signed = [r for r in data["results"] if r["status"] == "signed"]
    assert len(signed) == 4 and all("EXAMPLE" in r["message"] for r in signed)
    inter = next(r for r in data["results"] if r["id"] == "interference://kiln")
    assert inter["detail"]["interferences"] == []
    counts = next(r for r in data["results"] if r["id"] == "count://kiln")
    assert counts["status"] == "pass"


def test_kiln_golden_props(kiln: tuple[Path, float]) -> None:
    """Assembly fingerprint (D14): mass, bbox, instance count; regenerate via `make goldens`."""
    root, _ = kiln
    props = json.loads((root / "build/assemblies/kiln/props.json").read_text())
    fp = {
        "mass": round(props["mass"], 2),
        "bbox": [round(props["bbox"][k], 1) for k in ("x", "y", "z")],
        "instances": props["instances"],
        "parts": sorted(props["instance_counts"]),
    }
    if os.environ.get("N2F_UPDATE_GOLDENS") == "1" or not GOLDEN.is_file():
        GOLDEN.write_text(json.dumps(fp, indent=2) + "\n")
        if os.environ.get("N2F_UPDATE_GOLDENS") != "1":
            pytest.skip("kiln golden recorded for the first time; re-run to compare")
    want = json.loads(GOLDEN.read_text())
    assert abs(fp["mass"] - want["mass"]) <= 0.01 * want["mass"]
    assert all(abs(a - b) <= 0.5 for a, b in zip(fp["bbox"], want["bbox"], strict=True))
    assert fp["instances"] == want["instances"] and fp["parts"] == want["parts"]


def test_kiln_report_budget(kiln: tuple[Path, float]) -> None:
    root, _ = kiln
    size = (root / "build/report/index.html").stat().st_size
    assert size <= 20 * 1024 * 1024, f"report is {size / 1e6:.1f} MB (D13 budget 20 MB)"


@pytest.mark.timing
@pytest.mark.skipif(not TIMING, reason="timing assertions run only under N2F_TIMING=1 (D30)")
def test_kiln_clean_build_under_ten_minutes(kiln: tuple[Path, float]) -> None:
    _, seconds = kiln
    assert seconds < 600, f"clean kiln build took {seconds:.0f} s (budget 600 s, DoD item 3)"
