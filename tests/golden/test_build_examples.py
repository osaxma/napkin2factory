"""M2 exit: build bracket and enclosure geometry in temp copies; every artifact parses."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pygltflib
import pytest

from napkin2factory.core.loader import load_product
from napkin2factory.geometry.build import build_geometry, build_part
from napkin2factory.geometry.render import image_variance
from tests.conftest import EXAMPLES, copy_product
from tests.validate_outputs import validate_outputs


@pytest.fixture(scope="module")
def built_enclosure(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = copy_product(
        EXAMPLES / "enclosure", tmp_path_factory.mktemp("enc") / "enclosure", git=False
    )
    product = load_product(root)
    build_geometry(product)
    return root


def test_bracket_builds_and_validates(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    product = load_product(root)
    parts, asms = build_geometry(product)
    assert set(parts) == {"l-bracket"} and set(asms) == {"bracket"}
    assert parts["l-bracket"].reads == [
        "part://l-bracket#geometry",
        "part://l-bracket#material",
        "part://l-bracket#mass",
        "part://l-bracket#process",
        "part://l-bracket#kind",
        "part://l-bracket#interfaces",
        "part://l-bracket#rev",
        "part://l-bracket#role",  # M3: a role change rebuilds the part (N7)
        "param://bracket-length",
        "param://bracket-height",
        "param://bracket-width",
        "param://bracket-thickness",
        "param://bend-radius",
        "param://hole-diameter",
        "param://hole-spacing",
        "param://hole-inset",
    ]
    assert validate_outputs(root, "geometry") == []


def test_enclosure_artifacts(built_enclosure: Path) -> None:
    assert validate_outputs(built_enclosure, "geometry") == []
    props = json.loads((built_enclosure / "build/assemblies/enclosure/props.json").read_text())
    assert props["instance_counts"] == {"part://base": 1, "part://bracket": 2, "part://lid": 1}
    assert props["declared_counts"] == props["instance_counts"]
    assert "part://m4x10-screw" not in props["instance_counts"]  # BOM-only COTS, absent from 3D
    assert props["mass"] < 2.0 and props["bbox"]["z"] == pytest.approx(81.5, abs=0.01)


def test_enclosure_glb_instancing(built_enclosure: Path) -> None:
    """D13: one mesh per part URI, one node per occurrence, URIs on nodes/meshes/materials."""
    g = pygltflib.GLTF2().load(str(built_enclosure / "build/assemblies/enclosure/model.glb"))
    assert sorted(m.name for m in g.meshes) == ["part://base", "part://bracket", "part://lid"]
    assert sorted(m.name for m in g.materials) == ["part://base", "part://bracket", "part://lid"]
    bracket_nodes = [n for n in g.nodes if (n.extras or {}).get("n2f_uri") == "part://bracket"]
    assert [n.name for n in bracket_nodes] == ["part://bracket#1", "part://bracket#2"]
    assert len({n.mesh for n in bracket_nodes}) == 1, "both brackets share one mesh"
    assert bracket_nodes[0].translation != bracket_nodes[1].translation


def test_interface_pattern_applied_to_both_parties(built_enclosure: Path) -> None:
    base = json.loads((built_enclosure / "build/parts/base/features.json").read_text())
    lid = json.loads((built_enclosure / "build/parts/lid/features.json").read_text())
    pb = [p for p in base["patterns"] if p["interface"] == "iface://lid-base-mount"]
    pl = [p for p in lid["patterns"] if p["interface"] == "iface://lid-base-mount"]
    assert len(pb) == 1 and len(pl) == 1
    xy_b = sorted((round(c[0], 3), round(c[1], 3)) for c in pb[0]["centers"])
    xy_l = sorted((round(c[0], 3), round(c[1], 3)) for c in pl[0]["centers"])
    assert xy_b == xy_l and len(xy_b) == 4
    assert pb[0]["centers"][0][2] == 80.0 and pl[0]["centers"][0][2] == 0.0
    # and the holes really were cut
    lid_props = json.loads((built_enclosure / "build/parts/lid/props.json").read_text())
    assert lid_props["volume"] < 224 * 174 * 1.5 - 4 * 3.1415 * 2.25**2 * 1.5 + 1


def test_renders_are_not_blank(built_enclosure: Path) -> None:
    from PIL import Image

    for view in ("front", "top", "right", "iso", "section"):
        img = np.asarray(
            Image.open(built_enclosure / "build/assemblies/enclosure/renders" / f"{view}.png")
        )
        assert image_variance(img) > 100, view


def test_step_reimport_matches(built_enclosure: Path) -> None:
    from build123d import import_step

    props = json.loads((built_enclosure / "build/parts/base/props.json").read_text())
    shape = import_step(str(built_enclosure / "build/parts/base/model.step"))
    assert abs(shape.volume - props["volume"]) < 0.005 * props["volume"]
    assert len(shape.solids()) == 1


def test_part_only_build(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=False)
    product = load_product(root)
    built = build_part(product, "lid", render=False)
    assert built.props["bbox"]["x"] == pytest.approx(224.0)
    assert not (root / "build/parts/lid/renders").exists()
    assert (root / "build/parts/lid/model.glb").is_file()
