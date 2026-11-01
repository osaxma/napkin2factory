"""P5 (S-114): parameter reach, read from recorded reads and expressions, with no build.

The product is the ports fixture (the top holds a base, two clips and the pod; the pod a
plate and two rails) plus a sibling unit, the bay (a shelf), so siblings exist.  Recorded
reads are written into a manifest by hand: the reach check only reads the manifest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from napkin2factory.core.errors import ModelError
from napkin2factory.core.graph.manifest import Entry, Manifest
from napkin2factory.core.loader import load_product, validate
from napkin2factory.core.reach import REACH_KEY, Reach, reach_checks, reach_fingerprint
from napkin2factory.core.yamlio import read_yaml, write_yaml
from napkin2factory.geometry.accessors import make_accessors
from tests.conftest import FIXTURES, copy_product

PARAMS = """parameters:
  base-z: {value: 0, unit: mm}
  top-size: {value: 50, unit: mm, scope: asm://top}
  free-size: {value: 7, unit: mm}
  pod-gap: {value: 3, unit: mm, scope: asm://pod}
  pod-width: {value: 30, unit: mm, scope: asm://pod, export: true}
  bay-depth: {value: 40, unit: mm, scope: asm://bay}
"""


def _product(tmp_path: Path, params: str = PARAMS) -> Path:
    root = copy_product(FIXTURES / "ports", tmp_path / "scope", git=False)
    (root / "model/parameters.yaml").write_text(params)
    write_yaml(
        root / "model/assemblies/bay.yaml",
        {
            "id": "bay",
            "name": "Bay",
            "driver": ["built-as-unit"],
            "children": [{"part": "part://shelf", "qty": 1}],
        },
    )
    shelf = read_yaml(root / "model/parts/base.yaml")
    shelf.update({"id": "shelf", "name": "shelf", "interfaces": []})
    write_yaml(root / "model/parts/shelf.yaml", shelf)
    top = read_yaml(root / "model/assemblies/top.yaml")
    top["children"].append({"asm": "asm://bay", "qty": 1})
    write_yaml(root / "model/assemblies/top.yaml", top)
    return root


def _entry(reads: list[str], iface_reads: list[str] | None = None) -> Entry:
    return Entry(
        key="k", reads=reads, outputs={}, output_hash="h", duration=0.0,
        iface_reads=iface_reads or [],
    )  # fmt: skip


def _rows(root: Path, entries: dict[str, Entry]) -> dict[str, dict[str, object]]:
    rows = reach_checks(load_product(root), Manifest(entries=entries))
    return {r.id: {"status": r.status, **r.detail, "message": r.message} for r in rows}


def test_positions_follow_homes_and_units(tmp_path: Path) -> None:
    reach = Reach(load_product(_product(tmp_path)))
    assert reach.part_position("part://rail") == "pod"
    assert reach.part_position("part://clip") == "top"
    assert reach.asm_position("bay") == "bay"
    assert reach.param_position("pod-gap") == "pod" and reach.param_position("free-size") is None


def test_a_sibling_read_warns(tmp_path: Path) -> None:
    rows = _rows(_product(tmp_path), {"part:rail": _entry(["param://bay-depth"])})
    row = rows["reach://part/rail@bay-depth"]
    assert row["status"] == "warn" and row["why"] == "sibling" and row["how"] == "build"
    assert row["reader_module"] == "asm://pod" and row["scope"] == "asm://bay"
    assert "side by side" in str(row["message"]) and "move it up to the Top" in str(row["message"])
    assert "reach://pod" not in rows  # a flagged module gets no pass row
    assert rows["reach://bay"]["status"] == "skip"  # nothing of the bay recorded yet


def test_an_ancestor_and_an_unscoped_read_are_clean(tmp_path: Path) -> None:
    rows = _rows(
        _product(tmp_path),
        {
            "part:rail": _entry(["param://top-size", "param://free-size", "param://pod-gap"]),
            "asm:pod": _entry(["param://top-size", "param://pod-width"]),
        },
    )
    assert {k: v["status"] for k, v in rows.items()} == {
        "reach://pod": "pass",
        "reach://bay": "skip",
        "reach://top": "skip",
    }
    assert "2 parts and placements checked" in str(rows["reach://pod"]["message"])


def test_an_unexported_child_read_warns_and_an_exported_one_is_clean(tmp_path: Path) -> None:
    rows = _rows(
        _product(tmp_path),
        {"asm:top": _entry(["param://pod-gap", "param://pod-width"])},
    )
    row = rows["reach://asm/top@pod-gap"]
    assert row["status"] == "warn" and row["why"] == "unexported" and row["export"] is False
    assert "keeps to itself" in str(row["message"])
    assert "reach://asm/top@pod-width" not in rows


def test_a_read_through_an_interface_is_exempt(tmp_path: Path) -> None:
    root = _product(tmp_path)
    rows = _rows(
        root, {"part:rail": _entry(["param://bay-depth"], iface_reads=["param://bay-depth"])}
    )
    assert rows["reach://pod"]["status"] == "pass"


def test_resolving_an_interface_tags_its_reads(tmp_path: Path) -> None:
    root = _product(tmp_path)
    iface = read_yaml(root / "model/interfaces/clip-rail.yaml")
    iface["frames"]["part://clip"]["origin"] = [0, 0, {"expr": "bay-depth - pod-gap", "unit": "mm"}]
    write_yaml(root / "model/interfaces/clip-rail.yaml", iface)
    P, I, log = make_accessors(load_product(root))
    P["pod-gap"]  # a direct read stays the rule's own
    I["clip-rail"]
    assert log.keys == ["param://pod-gap", "iface://clip-rail", "param://bay-depth"]
    assert log.iface_reads == ["param://bay-depth"]


def test_a_scoped_expression_reaching_out_warns(tmp_path: Path) -> None:
    params = PARAMS + (
        '  pod-sum: {expr: "bay-depth + pod-gap", unit: mm, scope: asm://pod}\n'
        '  top-sum: {expr: "pod-gap + pod-width + top-size", unit: mm}\n'
    )
    rows = _rows(_product(tmp_path, params), {})
    assert rows["reach://param/pod-sum@bay-depth"]["why"] == "sibling"
    assert rows["reach://param/pod-sum@bay-depth"]["how"] == "expr"
    # an unscoped expression sits at the whole product: a scope's own sizes need exporting
    assert rows["reach://param/top-sum@pod-gap"]["why"] == "unexported"
    assert rows["reach://param/top-sum@top-size"]["why"] == "unexported"
    assert "reach://param/top-sum@pod-width" not in rows
    assert "reach://param/pod-sum@pod-gap" not in rows


def test_an_interface_expression_may_name_either_partys_sizes(tmp_path: Path) -> None:
    root = _product(tmp_path)
    iface = read_yaml(root / "model/interfaces/clip-rail.yaml")
    iface["offset"] = {"expr": "pod-gap - pod-gap", "unit": "mm"}  # the rail's side (pod)
    write_yaml(root / "model/interfaces/clip-rail.yaml", iface)
    assert _rows(root, {}) == _rows(root, {})  # deterministic
    assert not [k for k in _rows(root, {}) if k.startswith("reach://iface/")]
    iface["offset"] = {"expr": "bay-depth - bay-depth", "unit": "mm"}  # neither party's
    write_yaml(root / "model/interfaces/clip-rail.yaml", iface)
    assert _rows(root, {})["reach://iface/clip-rail@bay-depth"]["why"] == "sibling"


def test_no_scoped_parameter_means_no_reach_rows(tmp_path: Path) -> None:
    """P14: a product that never says `scope:` gets the v0.3 matrix."""
    root = copy_product(FIXTURES / "ports", tmp_path / "ports", git=False)
    assert reach_checks(load_product(root), Manifest(entries={"part:rail": _entry([])})) == []


def test_scope_and_export_are_left_out_of_dumps_at_their_defaults(tmp_path: Path) -> None:
    product = load_product(_product(tmp_path))
    assert "scope" not in product.parameters["free-size"].model_dump()
    assert "export" not in product.parameters["pod-gap"].model_dump()
    assert product.parameters["pod-width"].model_dump()["export"] is True


def test_the_fingerprint_follows_scopes_and_recorded_reads(tmp_path: Path) -> None:
    root = _product(tmp_path)
    product = load_product(root)
    one = Manifest(entries={"part:rail": _entry(["param://pod-gap"])})
    two = Manifest(entries={"part:rail": _entry(["param://pod-gap"], ["param://pod-gap"])})
    assert reach_fingerprint(product, one) != reach_fingerprint(product, two)
    before = reach_fingerprint(product, one)
    product.parameters["pod-gap"] = product.parameters["pod-gap"].model_copy(
        update={"export": True}
    )
    assert reach_fingerprint(product, one) != before
    from napkin2factory.core.checks.engine import checks_reads

    assert REACH_KEY in checks_reads(product)


@pytest.mark.parametrize(
    ("line", "words"),
    [
        ("  x: {value: 1, unit: mm, scope: asm://nowhere}", "names no assembly"),
        ("  x: {value: 1, unit: mm, scope: asm://lining}", "names a phantom"),
    ],
)
def test_a_scope_must_name_an_assembly_built_as_a_unit(
    tmp_path: Path, line: str, words: str
) -> None:
    root = _product(tmp_path, PARAMS + line + "\n")
    write_yaml(
        root / "model/assemblies/lining.yaml",
        {"id": "lining", "name": "Lining", "build": "phantom", "children": []},
    )
    bay = read_yaml(root / "model/assemblies/bay.yaml")
    bay["children"].append({"asm": "asm://lining", "qty": 1})
    write_yaml(root / "model/assemblies/bay.yaml", bay)
    _, problems = validate(root)
    found = [p for p in problems.errors if p.rule == "scope"]
    assert found and words in found[0].message, problems.items
    if "phantom" in words:
        assert "asm://bay" in found[0].hint
    with pytest.raises(ModelError):
        load_product(root)


def test_export_without_scope_is_a_warning(tmp_path: Path) -> None:
    root = _product(tmp_path, PARAMS + "  x: {value: 1, unit: mm, export: true}\n")
    _, problems = validate(root)
    assert [p.rule for p in problems.warnings] == ["scope"]
    assert not problems.errors
