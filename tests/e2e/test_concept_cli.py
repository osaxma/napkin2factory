"""M1 (v0.2): `n2f concept new|list|show|reject|lint` on a temp copy of the bracket (N1, N11).

Concepts sit outside the build graph: validate ignores them, build outputs do not change with
or without them, and `n2f status` shows the Napkin stage only while cards exist.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
import yaml

from napkin2factory.core import concepts as cm
from napkin2factory.core.loader import load_product
from napkin2factory.core.model import StyleFile
from napkin2factory.core.model.concepts import Screening
from tests.conftest import EXAMPLES, FIXTURES, copy_product, n2f

os.environ.setdefault("N2F_OFFLINE", "1")
GIT_WORDS = ("fatal:", "git ", "branch", "commit", "merge", "repository", "checkout")


def _run(*args: str, cwd: Path, code: int = 0):  # type: ignore[no-untyped-def]
    r = n2f(*args, cwd=cwd)
    assert r.returncode == code, f"{args}: {r.returncode}\n{r.stdout}\n{r.stderr}"
    low = (r.stdout + r.stderr).lower()
    for w in GIT_WORDS:
        assert w not in low, f"{args}: git vocabulary {w!r} leaked:\n{r.stdout}\n{r.stderr}"
    return r


@pytest.fixture
def product(tmp_path: Path) -> Path:
    return copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)


def test_without_concepts_status_is_byte_identical_to_v01(product: Path) -> None:
    # golden captured from the v0.1 code (commit bcd1451) on a fresh tracked bracket copy
    golden = (FIXTURES / "concepts" / "bracket-status-v01.json").read_text()
    assert _run("status", "--json", cwd=product).stdout == golden


def test_concept_round_trip(product: Path) -> None:
    root = product
    r = _run("concept", "new", "Squared shell", cwd=root)
    assert (root / "concepts" / "C-001.yaml").is_file()
    assert "started concept C-001 — edit concepts/C-001.yaml" in r.stdout
    assert "`n2f concept build C-001`" in r.stdout

    r = _run("concept", "new", "Taller", "--from", "C-001", "--json", cwd=root)
    assert json.loads(r.stdout) == {
        "id": "C-002",
        "status": "exploring",
        "based_on": "C-001",
        "file": "concepts/C-002.yaml",
    }
    card = yaml.safe_load((root / "concepts" / "C-002.yaml").read_text())
    assert card["based_on"] == "C-001" and card["status"] == "exploring"

    listing = json.loads(_run("concept", "list", "--json", cwd=root).stdout)
    assert [c["id"] for c in listing["concepts"]] == ["C-001", "C-002"]
    assert listing["concepts"][1]["based_on"] == "C-001"
    assert all(c["verdict"] is None for c in listing["concepts"])
    table = _run("concept", "list", cwd=root).stdout
    assert "Squared shell" in table and "—" in table

    r = _run("concept", "show", "C-002", cwd=root)
    assert "title: Taller" in r.stdout and "based_on: C-001" in r.stdout
    assert "not built yet — `n2f concept build C-002`" in r.stdout

    r = _run("concept", "reject", "C-002", "--reason", "too tall", cwd=root)
    assert "C-002 rejected: too tall" in r.stdout
    card = yaml.safe_load((root / "concepts" / "C-002.yaml").read_text())
    assert card["status"] == "rejected" and card["decision"]["reason"] == "too tall"
    r = _run("concept", "show", "C-002", cwd=root)
    assert "status: rejected" in r.stdout and "C-002 is rejected: too tall" in r.stdout
    shown = json.loads(_run("concept", "show", "2", "--json", cwd=root).stdout)
    assert shown["status"] == "rejected" and shown["summary"] == "never built"

    # lint: clean, then an unknown site key only warns, then an unknown kit fails
    r = _run("concept", "lint", cwd=root)
    assert "2 concept card(s) look fine" in r.stdout
    c1 = root / "concepts" / "C-001.yaml"
    c1.write_text(c1.read_text().replace("site: {}", "site: {view: garden}"))
    r = _run("concept", "lint", cwd=root)
    assert "C5-site-keys" in r.stderr and "1 warning" in r.stdout
    c1.write_text(
        c1.read_text().replace("massing: []", "massing:\n  - {kit: blob, as: body, args: {}}")
    )
    r = _run("concept", "lint", cwd=root, code=1)
    assert "C3-kit-known" in r.stderr and "concepts/C-001.yaml" in r.stderr
    payload = json.loads(_run("concept", "lint", "--json", cwd=root, code=1).stdout)
    assert payload["ok"] is False and payload["cards"] == 2
    assert {p["rule"] for p in payload["problems"]} == {"C3-kit-known", "C5-site-keys"}

    # N1: validate ignores concepts, even a broken card
    r = _run("validate", cwd=root)
    assert "model is consistent" in r.stdout

    # N11: one card exploring → stage Napkin, pointing at building the cards first
    st = json.loads(_run("status", "--json", cwd=root).stdout)
    assert st["stage"] == "napkin" and st["gates"][0]["name"] == "napkin"
    assert "`n2f concept build --all`" in st["next_step"]
    assert [g["name"] for g in st["gates"]][1:] == ["intake", "design", "verify", "released"]
    r = _run("status", cwd=root)
    assert "stage: Napkin" in r.stdout and "1 concept exploring, none chosen yet" in r.stdout

    # a promoted card (screened, its decision on record) completes Napkin; the stage moves
    # on, and it cannot be rejected
    cm.write_card(
        root,
        cm.load_card(root, "C-001").model_copy(update={"screening": Screening(verdict="green")}),
    )
    cm.update_card_status(root, "C-001", "promoted", {"dec": "DEC-001", "at": "today"})
    st = json.loads(_run("status", "--json", cwd=root).stdout)
    assert st["gates"][0] == {**st["gates"][0], "name": "napkin", "ok": True}
    assert st["stage"] == "intake"
    r = _run("concept", "reject", "C-001", "--reason", "changed my mind", cwd=root, code=3)
    assert "chosen direction" in r.stderr

    # unknown ids are actionable
    r = _run("concept", "show", "C-007", cwd=root, code=1)
    assert "known: C-001, C-002" in r.stderr


def test_concept_verbs_need_a_product_folder(tmp_path: Path) -> None:
    r = _run("concept", "list", cwd=tmp_path, code=1)
    assert "n2f init" in r.stderr


def test_concepts_change_no_build_output(product: Path, tmp_path: Path) -> None:
    """N1: deleting concepts/ changes nothing `n2f build` writes or depends on."""
    from napkin2factory.core.graph.rules import build_rules

    root = product
    shutil.copytree(FIXTURES / "concepts" / "valid" / "concepts", root / "concepts")
    inputs_with = {r.id: r.inputs for r in build_rules(load_product(root))}
    _run("build", "--target", "geometry", "--no-render", cwd=root)
    with_concepts = _geometry_outputs(root)
    shutil.rmtree(root / "concepts")
    shutil.rmtree(root / "build")
    inputs_without = {r.id: r.inputs for r in build_rules(load_product(root))}
    _run("build", "--target", "geometry", "--no-render", cwd=root)
    assert _geometry_outputs(root) == with_concepts
    assert inputs_with == inputs_without


def _geometry_outputs(root: Path) -> dict[str, object]:
    build = root / "build"
    props = {
        str(p.relative_to(build)): json.loads(p.read_text()) for p in build.rglob("props.json")
    }
    assert props and all("tess_hash" in v for k, v in props.items() if k.startswith("parts/"))
    return {"props": props, "geometry": json.loads((build / "geometry.json").read_text())}


def test_init_seeds_style_yaml(tmp_path: Path) -> None:
    dest = tmp_path / "fresh"
    _run("init", str(dest), "--template", "blank", cwd=tmp_path)
    text = (dest / "style.yaml").read_text()
    assert text.startswith("# style.yaml") and "n2f concept promote" in text
    # the industrial preset's values, written out in full (M3, N7)
    assert StyleFile.model_validate(yaml.safe_load(text)) == StyleFile().resolved()
    assert not (dest / "concepts").exists(), "concepts are created, not scaffolded"
    _run("validate", cwd=dest)
    # an existing product folder gets agent files only, never a style.yaml
    existing = copy_product(EXAMPLES / "bracket", tmp_path / "existing", git=False)
    _run("init", str(existing), cwd=tmp_path)
    assert not (existing / "style.yaml").exists()
