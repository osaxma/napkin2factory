"""M2 (v0.2): `n2f concept build` on a fixture product with one red and one green card (N1, N5).

The fixture is the bracket plus ``tests/fixtures/concepts/product-green-red/concepts``:
C-001 (the v0.1 kiln on an 800 mm alcove, door swing counted) screens red, C-002 green.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

import pytest
import yaml

from tests.conftest import EXAMPLES, FIXTURES, copy_product, n2f

os.environ.setdefault("N2F_OFFLINE", "1")
GIT_WORDS = ("fatal:", "git ", "branch", "commit", "merge", "repository", "checkout")
CONCEPTS = FIXTURES / "concepts" / "product-green-red" / "concepts"
TIMING = os.environ.get("N2F_TIMING") == "1"


def _run(*args: str, cwd: Path, code: int = 0):  # type: ignore[no-untyped-def]
    r = n2f(*args, cwd=cwd)
    assert r.returncode == code, f"{args}: {r.returncode}\n{r.stdout}\n{r.stderr}"
    low = (r.stdout + r.stderr).lower()
    for w in GIT_WORDS:
        assert w not in low, f"{args}: git vocabulary {w!r} leaked:\n{r.stdout}\n{r.stderr}"
    return r


@pytest.fixture
def product(tmp_path: Path) -> Path:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)
    shutil.copytree(CONCEPTS, root / "concepts")
    # the kiln-like cards are screened with the kiln's own heated-box screens (F8, F10)
    shutil.copytree(EXAMPLES / "kiln" / "model" / "screens", root / "model" / "screens")
    return root


def test_concept_build_all_screens_one_red_one_green(product: Path) -> None:
    root = product
    r = _run("concept", "build", "--all", cwd=root)  # red is information: exit 0
    out = r.stdout
    assert out.count("this direction has problems:") == 1
    assert "C-001 — this direction has problems:" in out
    assert "995 mm for the body plus 250 mm for the open door" in out
    assert "C-002 holds up: 400 × 403 × 400 mm (computed)" in out
    # the card's own power and circuit are given; only the fit is an estimate (gate A, C1)
    assert (
        "2.5 kW (on the card) on the 240V-13A circuit — fits with a fifth to spare (estimate)"
        in out
    )
    assert "(estimate)" in out and "worth a look:" in out
    assert "screening failed" not in out.lower()
    for cid in ("C-001", "C-002"):
        # the styled screenshot leads (N6); the z-buffer renders stay beside it
        assert f"see build/concepts/{cid}/renders/styled-iso.png" in out
        folder = root / "build" / "concepts" / cid
        for rel in (
            "massing.glb",
            "props.json",
            "features.json",
            "screening.json",
            "renders/iso.png",
            "renders/front.png",
            "renders/styled-iso.png",
            "renders/styled-front.png",
        ):
            assert (folder / rel).is_file(), f"{cid}: {rel}"

    cards = {
        cid: yaml.safe_load((root / "concepts" / f"{cid}.yaml").read_text())
        for cid in ("C-001", "C-002")
    }
    assert cards["C-001"]["screening"]["verdict"] == "red"
    assert cards["C-002"]["screening"]["verdict"] == "green"
    assert "# notes: anything worth remembering" in (root / "concepts" / "C-001.yaml").read_text()
    for card in cards.values():
        assert {v["label"] for v in card["screening"]["computed"].values()} == {"computed"}
        assert {v["label"] for v in card["screening"]["estimates"].values()} == {"estimate"}

    listing = json.loads(_run("concept", "list", "--json", cwd=root).stdout)
    assert {c["id"]: c["verdict"] for c in listing["concepts"]} == {
        "C-001": "red",
        "C-002": "green",
    }
    table = _run("concept", "list", cwd=root).stdout
    # gate B, C7: the owner reads "screening: holds up / has problems", JSON keeps the verdict
    assert "screening" in table and "verdict" not in table
    assert "has problems" in table and "holds up" in table
    assert "red" not in table and "green" not in table

    shown = _run("concept", "show", "C-002", cwd=root).stdout
    # gate B, C8: where the file is, first; no null fields
    assert shown.startswith("file: concepts/C-002.yaml\n"), shown
    assert ": null" not in shown and "null" not in shown
    # gate B, B2/C17: owner sentences, value names and rule titles; no identifiers
    assert "estimate — a rough engineering formula, before any design:" in shown
    assert "computed — measured from the rough shapes:" in shown
    assert "estimate · from the walls' stored heat and the element power" in shown
    assert "heat-up" in shown and "width with the door open" in shown
    assert "fits the alcove with the door open" in shown
    for word in (
        "thermal_enclosure",
        "mass_cost",
        "massing bounding box",
        "[verify]",
        "fits-site-width",
        "footprint_with_door_swing",
        "calc kit",
    ):
        assert word not in shown, word
    assert "screening: this direction holds up" in shown
    red = json.loads(_run("concept", "show", "C-001", "--json", cwd=root).stdout)
    assert red["summary"].startswith("screening: this direction has problems:")
    # the engineer's references stay in --json
    assert red["screening"]["estimates"]["heat_up_time"]["ref"] == "thermal_enclosure.heat_up_time"
    assert red["screening"]["rules"][0]["id"] == "fits-site-width"

    # gate B, B1: --all builds set-aside cards too, and says which they are
    _run("concept", "reject", "C-002", "--reason", "too small", cwd=root)
    shutil.rmtree(root / "build" / "concepts")
    again = _run("concept", "build", "--all", "--no-render", cwd=root).stdout
    assert "C-002 holds up: 400 × 403 × 400 mm (computed)" in again
    (line,) = [ln for ln in again.splitlines() if "C-002 holds up" in ln]
    assert line.endswith(" (set aside)"), line
    assert (root / "build" / "concepts" / "C-002" / "screening.json").is_file()

    one = json.loads(_run("concept", "build", "C-002", "--json", cwd=root).stdout)
    (entry,) = one["concepts"]
    assert (
        entry["verdict"] == "green"
        and entry["renders"]["iso"] == "build/concepts/C-002/renders/iso.png"
    )
    assert entry["screening"]["estimates"]["heat_up_time"]["label"] == "estimate"
    assert entry["screenshots"]["method"] in ("viewer", "zbuffer-fallback")
    assert entry["screenshots"]["paths"]["iso"] == "build/concepts/C-002/renders/styled-iso.png"
    assert one["errors"] == []


def test_concept_build_errors_exit_one_and_keep_going(product: Path) -> None:
    root = product
    bad = (root / "concepts" / "C-002.yaml").read_text()
    bad = bad.replace("id: C-002", "id: C-003").replace("thickness: 1.5 mm", "thickness: 250 mm")
    (root / "concepts" / "C-003.yaml").write_text(bad)
    r = _run("concept", "build", "--all", cwd=root, code=1)
    assert "C-003/body:" in r.stderr
    assert "C-001 — this direction has problems:" in r.stdout and "C-002 holds up" in r.stdout
    r = _run("concept", "build", cwd=root, code=1)
    assert "or pass --all" in r.stderr
    r = _run("concept", "build", "C-009", cwd=root, code=1)
    assert "there is no concept C-009" in r.stderr


def test_concept_build_leaves_the_build_untouched(product: Path) -> None:
    """N1: build/concepts/ is outside the manifest; the factory build does not notice it."""
    root = product
    _run("build", "--target", "geometry", "--no-render", cwd=root)
    geometry = (root / "build" / "geometry.json").read_text()
    _run("build", "--no-render", cwd=root)
    manifest = root / "build" / ".n2f" / "manifest.json"
    before = json.loads(manifest.read_text())["entries"]
    _run("concept", "build", "--all", cwd=root)
    _run("concept", "board", cwd=root)  # M4: the board is not a build output either
    assert json.loads(manifest.read_text())["entries"] == before
    r = _run("build", "--no-render", cwd=root)
    assert "0 rebuilt" in r.stdout
    after = json.loads(manifest.read_text())["entries"]
    assert after == before, "nothing rebuilt and nothing recorded because of concepts"
    outputs = [rel for e in after.values() for rel in e["outputs"]]
    assert outputs and not any(rel.startswith("concepts") for rel in outputs)
    _run("build", "--target", "geometry", "--no-render", cwd=root)
    assert (root / "build" / "geometry.json").read_text() == geometry
    assert (root / "build" / "concepts" / "C-001" / "massing.glb").is_file()
    assert (root / "build" / "concepts" / "board.html").is_file()


@pytest.mark.skipif(not TIMING, reason="timing assertions run only under N2F_TIMING=1 (D30)")
def test_warm_concept_build_takes_seconds(product: Path) -> None:
    from typer.testing import CliRunner

    from napkin2factory.cli.app import app

    runner = CliRunner()
    first = runner.invoke(app, ["concept", "build", "--all", "-C", str(product)])
    assert first.exit_code == 0, first.output
    t0 = time.perf_counter()
    second = runner.invoke(app, ["concept", "build", "--all", "-C", str(product)])
    elapsed = time.perf_counter() - t0
    assert second.exit_code == 0, second.output
    print(f"warm `n2f concept build --all` (2 cards): {elapsed:.2f} s")
    assert elapsed < 20, f"warm concept build took {elapsed:.1f} s"
