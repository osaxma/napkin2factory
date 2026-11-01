"""Evidence keys compare within a tolerance, so a build on another machine matches (S-121)."""

from __future__ import annotations

import json
from pathlib import Path

from napkin2factory.core.checks.evidence import INV_PREFIX, _asm_key, _part_key, keys_match


def _inv(**fields: object) -> str:
    return INV_PREFIX + json.dumps(fields, sort_keys=True, separators=(",", ":"))


def test_inv_keys_match_within_tolerance() -> None:
    a = _inv(volume=2045550.132, area=4102223.638, bbox=[672.4, 672.4, 637.2], counts=[136, 386, 1])
    noise = _inv(
        volume=2045550.132 * (1 + 1e-10),
        area=4102223.638 * (1 - 1e-10),
        bbox=[672.4, 672.4, 637.2],
        counts=[136, 386, 1],
    )
    assert keys_match(a, a)
    assert keys_match(a, noise)
    real = _inv(
        volume=2045550.132 * 1.01,
        area=4102223.638,
        bbox=[672.4, 672.4, 637.2],
        counts=[136, 386, 1],
    )
    assert not keys_match(a, real)
    assert not keys_match(
        a,
        _inv(
            volume=2045550.132, area=4102223.638, bbox=[672.4, 672.4, 637.2], counts=[137, 386, 1]
        ),
    )


def test_inv_keys_need_the_same_shape_and_text_fields() -> None:
    a = _inv(volume=1.0, features="sha256:aaa")
    assert not keys_match(a, _inv(volume=1.0, features="sha256:bbb"))
    assert not keys_match(a, _inv(volume=1.0))
    assert not keys_match(a, INV_PREFIX + "not json")


def test_text_keys_compare_exactly() -> None:
    assert keys_match("sha256:abc", "sha256:abc")
    assert not keys_match("sha256:abc", "sha256:abd")
    assert not keys_match("sha256:abc", _inv(volume=1.0))


def test_part_key_ignores_the_mesh_and_rounds_features(tmp_path: Path) -> None:
    part = tmp_path / "parts" / "p"
    part.mkdir(parents=True)
    props = {
        "volume": 10.0,
        "area": 20.0,
        "bbox": {"x": 1.0, "y": 2.0, "z": 3.0},
        "centroid": {"x": 0.5, "y": 1.0, "z": 1.5},
        "face_count": 6,
        "edge_count": 12,
        "solid_count": 1,
        "tess_hash": "sha256:one",
    }
    (part / "props.json").write_text(json.dumps(props))
    (part / "features.json").write_text(json.dumps({"holes": [{"at": [1.00000004, 2.0]}]}))
    k1 = _part_key(part)
    assert k1.startswith(INV_PREFIX)
    props["tess_hash"] = "sha256:another-machine"
    (part / "props.json").write_text(json.dumps(props))
    (part / "features.json").write_text(json.dumps({"holes": [{"at": [0.99999996, 2.0]}]}))
    assert _part_key(part) == k1  # the mesh is not evidence; 1e-7 mm of feature noise rounds away
    (part / "features.json").write_text(json.dumps({"holes": [{"at": [1.5, 2.0]}]}))
    assert not keys_match(k1, _part_key(part))  # a moved hole is
    assert _part_key(tmp_path / "parts" / "missing") == "missing"


def test_asm_key_rounds_placements(tmp_path: Path) -> None:
    asm = tmp_path / "assemblies" / "a"
    asm.mkdir(parents=True)
    inst = [
        {
            "node": "part://x#1",
            "parent": None,
            "rotation": [0.0, 0.0, 0.0, 1.0],
            "translation": [1.0, 2.0, 3.0],
            "uri": "part://x",
            "via": "iface://j",
            "label": "x",
        }
    ]
    (asm / "instances.json").write_text(json.dumps(inst))
    (asm / "props.json").write_text(json.dumps({"instance_counts": {"part://x": 1}}))
    k1 = _asm_key(asm)
    inst[0]["translation"] = [1.00000001, 2.0, 3.0]
    inst[0]["label"] = "renamed"  # how it was placed is not evidence (S-106)
    (asm / "instances.json").write_text(json.dumps(inst))
    assert _asm_key(asm) == k1
    inst[0]["translation"] = [1.5, 2.0, 3.0]
    (asm / "instances.json").write_text(json.dumps(inst))
    assert not keys_match(k1, _asm_key(asm))
