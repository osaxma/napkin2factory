"""A parent assembly must rebuild when only its own placement changes, reloading the
up-to-date sub-assembly from disk instead of failing (S-049; found by the gate-3 rework)."""

from __future__ import annotations

import json
from pathlib import Path

from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product
from napkin2factory.core.yamlio import read_yaml, write_yaml
from napkin2factory.templates import TEMPLATES_DIR
from tests.conftest import EXAMPLES, copy_product

PART = """id: {id}
rev: A
name: {id}
kind: custom
process: cut-block
material: {{name: aluminium, spec: "6082"}}
tolerance_class: ISO2768-m
geometry: {{kit: block, args: {{length: {l} mm, width: 20 mm, height: 20 mm}}}}
cost: {{unit: 1 USD, basis: estimate}}
lead_time: 1 d
"""

TOP_MODULE = '''"""Top assembly: the pair offset along X by a parameter only this module reads."""


def build(P, I, parts):  # noqa: N803
    """Place the pair and one extra block."""
    from napkin2factory.geometry.assembly import AssemblyResult, place

    res = AssemblyResult()
    res.add(place("asm://pair", parts["pair"], translate=(P.mm("offset"), 0.0, 0.0), label="pair"))
    res.add(place("part://b", parts["b"], translate=(0.0, 100.0, 0.0), label="extra"))
    return res
'''


def _nested_product(tmp_path: Path) -> Path:
    root = copy_product(TEMPLATES_DIR / "blank", tmp_path / "nested", git=True)
    model = root / "model"
    (model / "parts" / "a.yaml").write_text(PART.format(id="a", l=20))
    (model / "parts" / "b.yaml").write_text(PART.format(id="b", l=30))
    (model / "assemblies" / "pair.yaml").write_text(
        "id: pair\nrev: A\nname: Pair\nchildren:\n  - {part: part://a, qty: 1}\n"
        "  - {part: part://b, qty: 1}\n"
    )
    (model / "assemblies" / "top.yaml").write_text(
        "id: top\nrev: A\nname: Top\ngeometry: {module: geometry/top.py}\nchildren:\n"
        "  - {asm: asm://pair, qty: 1}\n  - {part: part://b, qty: 1}\n"
    )
    (model / "geometry" / "top.py").write_text(TOP_MODULE)
    params = read_yaml(model / "parameters.yaml")
    params["parameters"] = {"offset": {"value": 50, "unit": "mm", "description": "pair offset"}}
    write_yaml(model / "parameters.yaml", params)
    return root


def test_parent_rebuilds_with_cached_sub_assembly(tmp_path: Path) -> None:
    root = _nested_product(tmp_path)
    run_build(load_product(root), quiet=True, render=False, target="geometry")
    before = json.loads((root / "build/assemblies/top/instances.json").read_text())
    assert len(before) == 3

    params = read_yaml(root / "model/parameters.yaml")
    params["parameters"]["offset"]["value"] = 80
    write_yaml(root / "model/parameters.yaml", params)
    summary = run_build(load_product(root), quiet=True, render=False, target="geometry")
    ran = {str(k) for k in summary.get("ran", [])}
    skipped = {str(k) for k in summary.get("skipped", [])}
    assert any(k.startswith("asm:top") for k in ran), ran
    assert not any(k.startswith("asm:pair") for k in ran), ran
    assert any(k.startswith("asm:pair") for k in skipped), skipped
    after = json.loads((root / "build/assemblies/top/instances.json").read_text())
    assert len(after) == 3
    moved = [i for i in after if i["parent"] is not None]
    was = [j for j in before if j["parent"] is not None]
    assert moved
    for i, b in zip(moved, was, strict=True):
        assert abs(i["translation"][0] - (b["translation"][0] + 30)) < 1e-6


def test_shared_bolt_is_one_hole(tmp_path: Path) -> None:
    """Two interfaces whose patterns coincide on one part cut each hole once (S-051)."""
    from napkin2factory.geometry.build import build_part

    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=False)
    src = (root / "model/interfaces/lid-base-mount.yaml").read_text()
    (root / "model/interfaces/lid-bracket-mount.yaml").write_text(
        src.replace("id: lid-base-mount", "id: lid-bracket-mount")
    )
    for part in ("lid", "base"):
        path = root / f"model/parts/{part}.yaml"
        path.write_text(
            path.read_text().replace(
                "iface://lid-base-mount]", "iface://lid-base-mount, iface://lid-bracket-mount]"
            )
        )
    built = build_part(load_product(root), "lid", root / "build", render=False)
    holes = built.result.features.holes
    assert len(holes) == 4, [h.label for h in holes]
    assert len(built.result.features.patterns) == 2
