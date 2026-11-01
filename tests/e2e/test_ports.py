"""P4: a sub-assembly is placed by its port and the joint is checked across levels (S-107).

The fixture ``tests/fixtures/ports``: the top holds a base and two clips; the pod, a
sub-assembly, holds a plate and two rails.  The pod sits on the base (``pod-mount``) and a
clip on each rail (``clip-rail``), both ports of the pod.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from napkin2factory.core.checks.interface import check_interface
from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product
from napkin2factory.core.yamlio import read_yaml, write_yaml
from tests.conftest import FIXTURES, copy_product


def _build(root: Path) -> dict[str, Any]:
    return run_build(load_product(root), quiet=True, render=False, target="geometry")


def _check(root: Path, iface_id: str) -> Any:
    product = load_product(root)
    return check_interface(product, product.interfaces[iface_id], root / "build")


def _z(root: Path, label: str, uri: str) -> list[float]:
    rows = json.loads((root / "build/assemblies/top/instances.json").read_text())
    return [r["translation"][2] for r in rows if r["uri"] == uri and r["label"] == label]


def test_port_places_the_sub_assembly_and_the_joints_meet(tmp_path: Path) -> None:
    root = copy_product(FIXTURES / "ports", tmp_path / "ports")
    _build(root)
    for iface_id in ("pod-mount", "clip-rail"):
        rep = _check(root, iface_id)
        assert rep.status == "pass", (iface_id, rep.message)
        assert rep.alignment["status"] == "pass"
        assert "meet in asm://top" in rep.alignment["message"]
    assert _z(root, "plate", "part://plate") == [10.0]  # on the base's top face
    assert sorted(_z(root, "left", "part://clip") + _z(root, "right", "part://clip")) == [
        25.0,
        25.0,
    ]


def test_a_shifted_sub_assembly_fails_naming_the_occurrences(tmp_path: Path) -> None:
    root = copy_product(FIXTURES / "ports", tmp_path / "ports")
    top = root / "model/geometry/top.py"
    src = top.read_text()
    by_port = 'place_by(I, res, "pod-mount", "asm://pod", parts["pod"], label="pod")'
    assert by_port in src
    top.write_text(
        src.replace(
            by_port, 'place("asm://pod", parts["pod"], translate=(5.0, 0.0, 10.0), label="pod")'
        )
    )
    _build(root)
    rep = _check(root, "pod-mount")
    assert rep.status == "fail"
    assert "part://base#1 and part://plate#1 do not meet in asm://top" in rep.message
    assert "5.0 mm apart" in rep.message
    assert _check(root, "clip-rail").status == "pass"  # the clips followed the rails


def test_a_reloaded_sub_assembly_still_places_by_port_with_onto(tmp_path: Path) -> None:
    """S-049: only the top rebuilds; the pod comes back from disk with its leaves' labels."""
    root = copy_product(FIXTURES / "ports", tmp_path / "ports")
    _build(root)
    params = read_yaml(root / "model/parameters.yaml")
    params["parameters"]["base-z"]["value"] = 30
    write_yaml(root / "model/parameters.yaml", params)
    summary = _build(root)
    ran = {str(k) for k in summary.get("ran", [])}
    skipped = {str(k) for k in summary.get("skipped", [])}
    assert any(k.startswith("asm:top") for k in ran), ran
    assert any(k.startswith("asm:pod") for k in skipped), skipped
    assert _z(root, "plate", "part://plate") == [40.0]
    assert _z(root, "left", "part://clip") == [55.0]
    assert _z(root, "right", "part://clip") == [55.0]
    for iface_id in ("pod-mount", "clip-rail"):
        assert _check(root, iface_id).status == "pass", iface_id
