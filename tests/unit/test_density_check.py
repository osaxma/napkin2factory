"""Tests for made-part material density checks and density_is_assumed (S-186)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from napkin2factory.core.checks.engine import part_density_checks
from napkin2factory.core.model import Manifest, Operator
from napkin2factory.core.model.parts import Material, Part
from napkin2factory.core.product import Paths, Product
from napkin2factory.geometry.materials import (
    DEFAULT_DENSITY,
    density_is_assumed,
    density_kg_m3,
)
from tests.conftest import EXAMPLES, copy_product, n2f


def _make_part(
    pid: str,
    name: str,
    kind: str = "custom",
    material: Material | None = None,
) -> Part:
    """Helper to construct a Part model."""
    data: dict[str, Any] = {
        "id": pid,
        "name": name,
        "kind": kind,
        "process": "cut-block" if kind == "custom" else "none",
        "tolerance_class": "ISO2768-m" if kind == "custom" else None,
    }
    if material is not None:
        data["material"] = material
    return Part.model_validate(data)


def _product_with(parts: list[Part]) -> Product:
    """Helper to construct a minimal Product holding the given parts."""
    return Product(
        paths=Paths(Path(".")),
        manifest=Manifest.model_validate({"product": {"id": "test", "name": "Test"}}),
        operator=Operator(),
        parts={p.id: p for p in parts},
    )


def test_density_is_assumed_logic() -> None:
    """density_is_assumed returns True when density_kg_m3 falls back to mild steel."""
    # None
    assert density_is_assumed(None) is True
    rho, src = density_kg_m3(None)
    assert rho == DEFAULT_DENSITY
    assert "assumed mild steel" in src

    # Unknown material name
    assert density_is_assumed("unobtainium") is True
    assert density_is_assumed(Material(name="unobtainium")) is True
    rho, src = density_kg_m3("unobtainium")
    assert rho == DEFAULT_DENSITY
    assert "assumed mild steel" in src

    # Known materials in DENSITIES
    assert density_is_assumed("mild steel") is False
    assert density_is_assumed("aluminum") is False
    assert density_is_assumed("aluminium") is False
    assert density_is_assumed("acrylic") is False
    assert density_is_assumed(Material(name="mild steel")) is False
    assert density_is_assumed(Material(name="acrylic")) is False

    # Declared density overrides unknown material
    custom_mat = Material(name="unobtainium", density="2500 kg/m**3")
    assert density_is_assumed(custom_mat) is False
    rho, src = density_kg_m3(custom_mat)
    assert rho == 2500.0
    assert src == "declared on the part"


def test_part_density_checks_status_and_messages() -> None:
    """Unknown material fails; known material, declared density, and bought part pass."""
    part_unknown = _make_part("p-unknown", "Bracket Arm", material=Material(name="mystery_alloy"))
    part_none = _make_part("p-none", "Base Plate", material=None)
    part_known = _make_part("p-known", "Top Rail", material=Material(name="mild steel"))
    part_declared = _make_part(
        "p-declared", "Foam Pad", material=Material(name="special foam", density="150 kg/m**3")
    )
    part_bought = _make_part(
        "p-bought", "Screw M4", kind="cots", material=Material(name="unknown_bought_alloy")
    )
    part_ref = _make_part(
        "p-ref", "Wall Mount", kind="reference", material=Material(name="unknown_ref_alloy")
    )

    product = _product_with(
        [part_unknown, part_none, part_known, part_declared, part_bought, part_ref]
    )

    results = part_density_checks(product)
    by_id = {r.id: r for r in results}

    # Custom part with unknown material fails in plain owner words
    r_unknown = by_id["material://p-unknown"]
    assert r_unknown.status == "fail"
    assert r_unknown.subject == "part://p-unknown"
    assert r_unknown.kind == "material"
    assert (
        r_unknown.message
        == "Part Bracket Arm: material 'mystery_alloy' is not in the materials table "
        "and has no density, so its mass and cost would be guessed as mild steel. "
        "Name a known material or give its density."
    )

    # Custom part with no material declared fails in plain owner words
    r_none = by_id["material://p-none"]
    assert r_none.status == "fail"
    assert r_none.subject == "part://p-none"
    assert "no material declared and has no density" in r_none.message

    # Custom part with known material passes
    r_known = by_id["material://p-known"]
    assert r_known.status == "pass"
    assert r_known.subject == "part://p-known"
    assert "material 'mild steel' is in the materials table" in r_known.message

    # Custom part with declared density passes
    r_declared = by_id["material://p-declared"]
    assert r_declared.status == "pass"
    assert r_declared.subject == "part://p-declared"
    assert "density declared on the part" in r_declared.message

    # Bought (cots) and reference parts are exempt
    assert "material://p-bought" not in by_id
    assert "material://p-ref" not in by_id


def test_part_density_checks_uses_recording_proxy() -> None:
    """Reads are performed through the recording proxy accessor."""
    part = _make_part("p1", "Plate", material=Material(name="mild steel"))
    product = _product_with([part])

    accessed: list[str] = []

    def spy_proxy(obj: Any, uri: str) -> Any:
        accessed.append(uri)
        return obj

    results = part_density_checks(product, proxy=spy_proxy)
    assert len(results) == 1
    assert results[0].status == "pass"
    assert accessed == ["part://p1"]


def test_n2f_check_fails_for_custom_part_with_assumed_density(tmp_path: Path) -> None:
    """n2f check fails with exit code 2 when a made part has assumed density."""
    dst = copy_product(EXAMPLES / "bracket", tmp_path / "bracket")
    part_file = dst / "model/parts/l-bracket.yaml"
    data = yaml.safe_load(part_file.read_text(encoding="utf-8"))
    data["material"] = {"name": "unobtainium", "spec": "unknown spec"}
    part_file.write_text(yaml.safe_dump(data), encoding="utf-8")

    res = n2f("check", "--json", cwd=dst)
    assert res.returncode == 2
    checks = json.loads(res.stdout)
    mat_row = next(r for r in checks["results"] if r["id"] == "material://l-bracket")
    assert mat_row["status"] == "fail"
    assert "material 'unobtainium' is not in the materials table" in mat_row["message"]

    # Now add explicit declared density: check should pass
    data["material"]["density"] = "4500 kg/m**3"
    part_file.write_text(yaml.safe_dump(data), encoding="utf-8")
    res2 = n2f("check", "--json", cwd=dst)
    assert res2.returncode == 0
    checks2 = json.loads(res2.stdout)
    mat_row2 = next(r for r in checks2["results"] if r["id"] == "material://l-bracket")
    assert mat_row2["status"] == "pass"
