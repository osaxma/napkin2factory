"""P3: interface frames meet in the assembly; P1: joints closed by coordinates warn (S-106).

The kiln's own placement module runs here without the CAD kernel's solids (parts are
stand-ins; ``place_by`` needs only frames), so its ``instances.json`` is the real placement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from napkin2factory.core.checks.interface import (
    check_alignment,
    coordinate_placement_warnings,
    lowest_common_assemblies,
)
from napkin2factory.core.loader import Product, load_product
from napkin2factory.geometry.accessors import make_accessors, resolve_interface
from napkin2factory.geometry.assembly import AssemblyResult, flatten
from napkin2factory.geometry.build import _load_module, instance_records
from napkin2factory.geometry.exporters import write_json
from tests.conftest import EXAMPLES


class _StandIn:
    """A built part or sub-assembly with no geometry (the door is an empty sub-assembly)."""

    result = AssemblyResult()


class _Parts(dict[str, Any]):
    def __missing__(self, key: str) -> _StandIn:
        return _StandIn()


def _place(product: Product, asm_id: str, build_dir: Path) -> list[dict[str, Any]]:
    """Run the product's assembly module and write its ``instances.json`` like the build."""
    asm = product.assemblies[asm_id]
    module = _load_module(product.paths.model / asm.geometry.module, f"n2f_test_{asm_id}")
    P, I, _log = make_accessors(product)
    leaves, _groups = flatten(module.build(P, I, _Parts()), asm.uri)
    rows = instance_records(leaves)
    write_json(build_dir / "assemblies" / asm_id / "instances.json", rows)
    return json.loads((build_dir / "assemblies" / asm_id / "instances.json").read_text())


@pytest.fixture(scope="module")
def kiln(tmp_path_factory: pytest.TempPathFactory) -> tuple[Product, Path]:
    product = load_product(EXAMPLES / "kiln")
    build_dir = tmp_path_factory.mktemp("kiln-build")
    _place(product, "kiln", build_dir)
    _place(product, "door", build_dir)
    return product, build_dir


def _check(product: Product, iface_id: str, build_dir: Path) -> dict[str, Any]:
    iface = resolve_interface(product, product.interfaces[iface_id])
    return check_alignment(product, iface, build_dir)


def test_every_kiln_interface_meets_in_its_assembly(kiln: tuple[Product, Path]) -> None:
    """DoD 2: the alignment stage passes for every kiln interface, at M0's measured offsets."""
    product, build_dir = kiln
    offsets = {}
    for iface_id in sorted(product.interfaces):
        out = _check(product, iface_id, build_dir)
        assert out["status"] == "pass", (iface_id, out.get("message"))
        offsets[iface_id] = out["offset_mm"]
    # M0's survey (docs/v04-baseline.md §1), now offsets written as expressions (P2)
    assert offsets["controller-mount"] == pytest.approx(40.0)
    assert offsets["guard-standoff-left"] == pytest.approx(26.0)
    assert offsets["guard-hinge-post"] == pytest.approx(3.0)
    assert offsets["shell-frame-mount"] == 0.0
    assert offsets["door-guard-standoff"] == pytest.approx(-26.5)
    assert lowest_common_assemblies(product, "part://door-tray", "part://door-guard") == ["door"]


def _shifted(rows: list[dict[str, Any]], uri: str, dx: float) -> list[dict[str, Any]]:
    out = json.loads(json.dumps(rows))
    for r in out:
        if r["uri"] == uri:
            r["translation"][0] += dx
    return out


def test_controller_box_moved_10_mm_fails(kiln: tuple[Product, Path], tmp_path: Path) -> None:
    """DoD 2, the release's key regression: a box moved 10 mm in the code no longer passes."""
    product, build_dir = kiln
    rows = json.loads((build_dir / "assemblies/kiln/instances.json").read_text())
    write_json(
        tmp_path / "assemblies/kiln/instances.json",
        _shifted(rows, "part://controller-box", 10.0),
    )
    out = _check(product, "controller-mount", tmp_path)
    assert out["status"] == "fail"
    msg = out["message"]
    assert "part://guard-shell#1 and part://controller-box#1 do not meet in asm://kiln" in msg
    assert "10.0 mm apart" in msg
    pair = out["assemblies"]["kiln"]["pairs"][0]
    assert pair["distance_mm"] == pytest.approx(10.0, abs=1e-3)
    assert set(pair["world"]) == {"part://guard-shell#1", "part://controller-box#1"}
    assert {"origin", "normal", "x_axis"} <= set(pair["world"]["part://controller-box#1"])
    # the same box 0.3 mm off is within the 0.5 mm design tolerance (P3)
    write_json(
        tmp_path / "assemblies/kiln/instances.json",
        _shifted(rows, "part://controller-box", 0.3),
    )
    assert _check(product, "controller-mount", tmp_path)["status"] == "pass"


def test_facing_normals_fail(kiln: tuple[Product, Path]) -> None:
    """The v0.3 controller-box frame (normal facing the guard's) fails the one convention."""
    product, build_dir = kiln
    iface = resolve_interface(product, product.interfaces["controller-mount"])
    box = iface.frames["part://controller-box"]
    old = box.model_copy(update={"normal": [-1.0, 0.0, 0.0], "x_axis": [0.0, 1.0, 0.0]})
    iface = iface.model_copy(update={"frames": {**iface.frames, "part://controller-box": old}})
    out = check_alignment(product, iface, build_dir)
    assert out["status"] == "fail"
    assert "turned 180.0°" in out["message"] and "rotated 180.0°" in out["message"]


def test_shared_fallback_frame_is_not_aligned(kiln: tuple[Product, Path]) -> None:
    product, build_dir = kiln
    iface = resolve_interface(product, product.interfaces["controller-mount"])
    out = check_alignment(product, iface.model_copy(update={"frames": {}}), build_dir)
    assert out["status"] == "skip" and "frames:" in out["message"]


def test_no_coordinate_warning_on_the_kiln(kiln: tuple[Product, Path]) -> None:
    product, build_dir = kiln
    assert coordinate_placement_warnings(product, build_dir) == []


def test_joint_closed_by_coordinates_warns(kiln: tuple[Product, Path], tmp_path: Path) -> None:
    """P1: the hinge post placed by typed-in numbers next to a guard placed onto the stand."""
    product, build_dir = kiln
    rows = json.loads((build_dir / "assemblies/kiln/instances.json").read_text())
    for r in rows:
        if r["uri"] == "part://hinge-post":
            r["via"] = "coordinates"
    write_json(tmp_path / "assemblies/kiln/instances.json", rows)
    (warn,) = coordinate_placement_warnings(product, tmp_path)
    assert warn.status == "warn" and warn.id == "placement://kiln@guard-shell+hinge-post"
    assert "typed-in coordinates" in warn.message and "iface" not in warn.message
    assert warn.detail["interfaces"] == ["iface://guard-hinge-post"]
    assert warn.detail["fix"].startswith('place_by(I, res, "guard-hinge-post", "part://hinge-post"')
    # a product built before v0.4 has no `via`: no warning
    for r in rows:
        r.pop("via")
    write_json(tmp_path / "assemblies/kiln/instances.json", rows)
    assert coordinate_placement_warnings(product, tmp_path) == []
