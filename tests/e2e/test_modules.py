"""P6, P12 (S-114): one module built, checked and described alone, on the ports fixture.

The top holds a base and two clips; the pod (a unit) a plate and two rails, joined to the top
by two ports.  ``pod-gap`` is the pod's own size, read by nothing yet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from napkin2factory.core.graph.runner import explain_build, run_build
from napkin2factory.core.loader import load_product
from napkin2factory.core.yamlio import read_yaml, write_yaml
from tests.conftest import FIXTURES, copy_product, n2f

POD_ONLY = ["validate", "part:plate", "part:rail", "asm:pod", "drawing:plate", "drawing:rail"]


def _scoped(root: Path) -> Path:
    params = read_yaml(root / "model/parameters.yaml")
    params["parameters"]["pod-gap"] = {"value": 3, "unit": "mm", "scope": "asm://pod"}
    write_yaml(root / "model/parameters.yaml", params)
    return root


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = _scoped(copy_product(FIXTURES / "ports", tmp_path_factory.mktemp("m") / "ports"))
    run_build(load_product(root), quiet=True, render=False)
    return root


def _json(*args: str, cwd: Path) -> Any:
    res = n2f(*args, "--json", cwd=cwd)
    assert res.returncode in (0, 1, 2), res.stderr  # 2: a check failed (the fixture has no finish)
    return json.loads(res.stdout)


def test_build_asm_runs_exactly_what_the_assembly_needs(tmp_path: Path) -> None:
    root = _scoped(copy_product(FIXTURES / "ports", tmp_path / "ports", git=False))
    summary = _json("build", "--asm", "asm://pod", "--no-render", cwd=root)
    assert summary["ran"] == POD_ONLY and summary["asm"] == "asm://pod"
    assert not (root / "build/checks").exists() and not (root / "build/bom").exists()
    again = _json("build", "--asm", "pod", "--target", "geometry", "--no-render", cwd=root)
    assert again["ran"] == [] and again["skipped"] == POD_ONLY[:4]
    res = n2f("build", "--asm", "pod", "--target", "bom", cwd=root)
    assert res.returncode != 0 and "whole product" in res.stderr
    res = n2f("build", "--asm", "nowhere", cwd=root)
    assert res.returncode != 0 and "known: pod, top" in res.stderr


def test_check_scope_writes_its_own_file_and_leaves_the_matrix_alone(built: Path) -> None:
    before = {p.name: p.read_bytes() for p in (built / "build/checks").glob("*.json")}
    assert set(before) == {"checks.json", "calcs.json"}
    data = _json("check", "--scope", "asm://pod", cwd=built)
    after = {p.name: p.read_bytes() for p in (built / "build/checks").glob("*.json")}
    assert after == before
    on_disk = json.loads((built / "build/checks/scope/pod/checks.json").read_text())
    assert on_disk["scope"] == "asm://pod" and on_disk["results"] == data["results"]
    ids = {r["id"] for r in data["results"]}
    assert {"interference://pod", "count://pod", "reach://pod"} <= ids
    assert not [i for i in ids if i.startswith(("iface://", "doc://", "bom://"))]  # ports: top
    assert {r["module"] for r in data["results"]} == {"pod"}
    assert {r["subject"] for r in data["results"] if r["kind"] == "rule"} <= {
        "part://plate",
        "part://rail",
        "asm://pod",
    }


def test_the_check_matrix_is_grouped_by_module(built: Path) -> None:
    data = json.loads((built / "build/checks/checks.json").read_text())
    groups = data["matrix"]["modules"]
    assert [g["id"] for g in groups] == ["pod", "top"]
    assert groups[0]["title"] == "Pod, built as one unit"
    assert groups[1]["title"] == "Top, the final assembly"
    by_id = {r["id"]: r["module"] for r in data["results"]}
    assert by_id["iface://pod-mount"] == "top"  # a port is checked where both sides meet
    assert by_id["interference://pod"] == "pod"
    assert by_id["rule://general-v0/part-in-assembly@plate"] == "pod"
    assert sum(len(g["ids"]) for g in groups) == len(data["results"])
    html = (built / "build/report/index.html").read_text()
    assert "Pod, built as one unit" in html and "By module" in html


def test_context_of_a_built_module(built: Path) -> None:
    data = _json("context", "asm://pod", cwd=built)
    assert data["module"] == "asm://pod" and data["parameters"]["built"] is True
    assert [p["id"] for p in data["parts"]] == ["plate", "rail"]
    assert [p["param"] for p in data["parameters"]["own"]] == ["pod-gap"]
    assert [p["iface"] for p in data["ports"]] == ["iface://pod-mount", "iface://clip-rail"]
    other = next(p for p in data["ports"][0]["parties"] if not p["inside"])
    assert other["part"] == "part://base" and other["frame"]["origin"] == [0.0, 0.0, 10.0]
    assert data["commands"] == {
        "build": "n2f build --asm pod",
        "check": "n2f check --scope asm://pod",
    }
    top = _json("context", "asm://top", cwd=built)
    assert top["sub_assemblies"][0]["id"] == "pod" and top["ports"] == []
    assert [r["param"] for r in top["parameters"]["outside"]] == ["base-z"]


def test_context_says_when_nothing_is_built(tmp_path: Path) -> None:
    root = _scoped(copy_product(FIXTURES / "ports", tmp_path / "ports", git=False))
    res = n2f("context", "asm://pod", cwd=root)
    assert res.returncode == 0, res.stderr
    text = res.stdout
    assert "nothing built yet" in text
    assert "## Ports" in text and "iface://pod-mount" in text and "iface://clip-rail" in text
    assert "`n2f build --asm pod`" in text and "`n2f check --scope asm://pod`" in text
    assert not (root / "build").exists()  # context builds nothing


def test_editing_an_interface_invalidates_both_parties(tmp_path: Path) -> None:
    """P12: both parties' rules recorded the interface, so both rebuild (D5)."""
    root = copy_product(FIXTURES / "ports", tmp_path / "ports", git=False)
    run_build(load_product(root), quiet=True, render=False, target="geometry")
    iface = read_yaml(root / "model/interfaces/pod-mount.yaml")
    iface["spec"]["width"] = "110 mm"
    write_yaml(root / "model/interfaces/pod-mount.yaml", iface)
    plan = {rid: run for rid, run, _ in explain_build(load_product(root), "geometry", render=False)}
    assert plan["part:base"] and plan["part:plate"]  # one party in the top, one in the pod
    assert not plan["part:rail"] and not plan["part:clip"]
    summary = run_build(load_product(root), quiet=True, render=False, target="geometry")
    assert {"part:base", "part:plate"} <= set(summary["ran"])
