"""A part's mass reads the calc kit's density table, so its rule's key does (B-0080, S-129).

``geometry/materials.py`` takes the shared rows (mild steel, firebrick, fibre board) from
``calckit/data/materials.yaml``; the part rule's ``material`` input is the row its density
comes from, read from the file, so editing one density reruns exactly the parts of that
material.  The edit is made in a copy of the table, which the lookup is pointed at.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from napkin2factory.core.graph.manifest import Entry, Manifest
from napkin2factory.core.graph.rules import Rule, build_rules
from napkin2factory.core.graph.runner import compute_key, needs_run
from napkin2factory.core.loader import Product, load_product
from napkin2factory.geometry import materials
from tests.conftest import EXAMPLES


def _part_rules(product: Product) -> dict[str, Rule]:
    return {r.id: r for r in build_rules(product, render=False) if r.kind == "part"}


def test_editing_a_density_reruns_the_parts_of_that_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    product = load_product(EXAMPLES / "kiln")
    before = _part_rules(product)
    steel = {rid for rid, r in before.items() if r.inputs["material"].startswith("mild steel:")}
    brick = {rid for rid, r in before.items() if r.inputs["material"].startswith("K-23")}
    assert steel and brick  # the kiln holds both, and parts with a density of their own
    assert any(r.inputs["material"] == "package" for r in before.values())

    # a build of the old keys, as the manifest holds them
    build = tmp_path / "build"
    manifest = Manifest(
        entries={
            rid: Entry(
                key=compute_key(rule, [], product, Manifest(), build, {}),
                reads=[],
                outputs={},
                output_hash="",
                duration=0.0,
                inputs=dict(rule.inputs),
            )
            for rid, rule in before.items()
        }
    )
    assert not any(needs_run(r, product, manifest, build)[0] for r in before.values())

    table = tmp_path / "materials.yaml"
    text = materials.SHARED_TABLE.read_text(encoding="utf-8")
    assert text.count("density: 7850") == 1
    table.write_text(text.replace("density: 7850", "density: 7870"), encoding="utf-8")
    monkeypatch.setattr(materials, "SHARED_TABLE", table)

    after = _part_rules(product)
    rerun = {
        rid: why
        for rid, r in after.items()
        for run, why in [needs_run(r, product, manifest, build)]
        if run
    }
    assert set(rerun) == steel
    assert set(rerun.values()) == {"input material"}
    assert after[next(iter(steel))].inputs["material"] == "mild steel: 7870"
