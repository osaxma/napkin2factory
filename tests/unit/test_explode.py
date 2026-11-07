"""Unit tests for the single explode resolver, GLB extras and ``Exploded.directions`` (v0.9 M1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pygltflib
import pytest
from pydantic import ValidationError

from napkin2factory.core.graph.values import sha256_json
from napkin2factory.core.model import Assembly, Exploded, Interface
from napkin2factory.geometry.assembly import (
    AssemblyResult,
    exploded_scene,
    export_assembly_glb,
    flatten,
    place,
    place_by,
)
from napkin2factory.geometry.explode import (
    RULES,
    SOURCES,
    ExplodeMove,
    ExplodeUnit,
    assembly_centre,
    resolve,
    units_of,
)


def test_sources_and_priority_order() -> None:
    """Priority order is declared > interface > fallback; missing sources fall through."""
    assert SOURCES == ("declared", "interface", "fallback")
    assert tuple(name for name, _ in RULES) == SOURCES

    u_all = ExplodeUnit(
        node="part://a#1",
        uri="part://a",
        label="top-cap",
        away=(0.0, 1.0, 0.0),
        centre=(50.0, 0.0, 0.0),
        has_geometry=True,
    )
    # 1. Declared label beats declared URI, interface, and fallback
    moves = resolve(
        [u_all],
        assembly_centre=(0.0, 0.0, 0.0),
        spacing_mm=80.0,
        declared={"top-cap": [0.0, 0.0, -2.0], "part://a": [-1.0, 0.0, 0.0]},
    )
    assert moves["part://a#1"] == ExplodeMove(
        direction=(0.0, 0.0, -1.0), distance=80.0, source="declared"
    )

    # 2. Declared URI beats interface and fallback when label is not in declared
    moves_uri = resolve(
        [u_all],
        assembly_centre=(0.0, 0.0, 0.0),
        spacing_mm=80.0,
        declared={"part://a": [-3.0, 0.0, 0.0]},
    )
    assert moves_uri["part://a#1"] == ExplodeMove(
        direction=(-1.0, 0.0, 0.0), distance=80.0, source="declared"
    )

    # 3. Missing declared falls through to interface (normalised)
    u_iface = ExplodeUnit(
        node="part://a#1",
        uri="part://a",
        label="top-cap",
        away=(0.0, 5.0, 0.0),
        centre=(50.0, 0.0, 0.0),
        has_geometry=True,
    )
    moves_iface = resolve([u_iface], (0.0, 0.0, 0.0), 80.0, {})
    assert moves_iface["part://a#1"] == ExplodeMove(
        direction=(0.0, 1.0, 0.0), distance=80.0, source="interface"
    )

    # 4. Missing declared and interface falls through to fallback
    u_fb = ExplodeUnit(
        node="part://a#1",
        uri="part://a",
        label="top-cap",
        away=None,
        centre=(50.0, -10.0, 5.0),
        has_geometry=True,
    )
    moves_fb = resolve([u_fb], (0.0, 0.0, 0.0), 80.0, {})
    assert moves_fb["part://a#1"] == ExplodeMove(
        direction=(1.0, 0.0, 0.0), distance=80.0, source="fallback"
    )


def test_fallback_dominant_axis_and_plus_z_default() -> None:
    """Fallback picks the dominant axis away from assembly centre, or +Z when centred/None."""
    units = [
        ExplodeUnit("part://nx#1", "part://nx", None, None, (-40.0, 10.0, 25.0), True),
        ExplodeUnit("part://py#1", "part://py", None, None, (5.0, 80.0, 25.0), True),
        ExplodeUnit("part://nz#1", "part://nz", None, None, (5.0, 15.0, -25.0), True),
        ExplodeUnit("part://centred#1", "part://centred", None, None, (10.0, 20.0, 30.0), True),
        ExplodeUnit("part://tiny#1", "part://tiny", None, None, (10.0, 20.0, 30.0 + 5e-7), True),
        ExplodeUnit("part://nocentre#1", "part://nocentre", None, None, None, True),
    ]
    moves = resolve(units, assembly_centre=(10.0, 20.0, 30.0), spacing_mm=50.0, declared={})
    assert moves["part://nx#1"].direction == (-1.0, 0.0, 0.0)
    assert moves["part://py#1"].direction == (0.0, 1.0, 0.0)
    assert moves["part://nz#1"].direction == (0.0, 0.0, -1.0)
    assert moves["part://centred#1"].direction == (0.0, 0.0, 1.0)
    assert moves["part://tiny#1"].direction == (0.0, 0.0, 1.0)
    assert moves["part://nocentre#1"].direction == (0.0, 0.0, 1.0)
    assert all(m.source == "fallback" for m in moves.values())


def test_steps_nearest_first_per_direction() -> None:
    """Two units on one side get steps 1 and 2 nearest-first; the opposite side starts at 1."""
    # Place the further +X unit before the nearer +X unit to prove ordering is by centre position
    u_far_px = ExplodeUnit(
        "part://flange#2", "part://flange", "outer", (1.0, 0.0, 0.0), (90.0, 0.0, 0.0), True
    )
    u_near_px = ExplodeUnit(
        "part://flange#1", "part://flange", "inner", (1.0, 0.0, 0.0), (30.0, 0.0, 0.0), True
    )
    # And two on the -X side (further at -80, nearer at -20)
    u_far_nx = ExplodeUnit(
        "part://side#2", "part://side", None, (-1.0, 0.0, 0.0), (-80.0, 0.0, 0.0), True
    )
    u_near_nx = ExplodeUnit(
        "part://side#1", "part://side", None, (-1.0, 0.0, 0.0), (-20.0, 0.0, 0.0), True
    )

    moves = resolve(
        [u_far_px, u_near_px, u_far_nx, u_near_nx],
        assembly_centre=(0.0, 0.0, 0.0),
        spacing_mm=80.0,
        declared={},
    )
    assert moves["part://flange#1"].distance == pytest.approx(80.0)
    assert moves["part://flange#2"].distance == pytest.approx(160.0)
    assert moves["part://side#1"].distance == pytest.approx(80.0)
    assert moves["part://side#2"].distance == pytest.approx(160.0)


def test_zero_declared_stays_and_takes_no_step() -> None:
    """A zero declared vector stays at distance 0 and does not advance steps on any axis."""
    u_base = ExplodeUnit("part://base#1", "part://base", "base", None, (0.0, 0.0, 0.0), True)
    u_lid = ExplodeUnit(
        "part://lid#1", "part://lid", "lid", (0.0, 0.0, 1.0), (0.0, 0.0, 40.0), True
    )
    moves = resolve(
        [u_base, u_lid],
        assembly_centre=(0.0, 0.0, 20.0),
        spacing_mm=60.0,
        declared={"base": [0.0, 0.0, 0.0]},
    )
    assert moves["part://base#1"] == ExplodeMove(
        direction=(0.0, 0.0, 0.0), distance=0.0, source="declared"
    )
    assert moves["part://lid#1"] == ExplodeMove(
        direction=(0.0, 0.0, 1.0), distance=60.0, source="interface"
    )


def test_geometry_less_unit_gets_move_but_takes_no_step() -> None:
    """A geometry-less unit gets a move after the last modelled unit without taking a step."""
    u_bolt = ExplodeUnit("part://bolt#1", "part://bolt", None, None, None, False)
    u_mid = ExplodeUnit("part://mid#1", "part://mid", None, (0.0, 0.0, 1.0), (0.0, 0.0, 10.0), True)
    u_top = ExplodeUnit("part://top#1", "part://top", None, (0.0, 0.0, 1.0), (0.0, 0.0, 30.0), True)

    moves = resolve([u_bolt, u_mid, u_top], (0.0, 0.0, 0.0), 50.0, {})
    assert moves["part://mid#1"].distance == pytest.approx(50.0)
    assert moves["part://top#1"].distance == pytest.approx(100.0)
    assert moves["part://bolt#1"] == ExplodeMove(
        direction=(0.0, 0.0, 1.0), distance=150.0, source="fallback"
    )


def test_unknown_declared_key_is_ignored() -> None:
    """An unknown key in ``declared`` is ignored without affecting known units."""
    u = ExplodeUnit("part://a#1", "part://a", "left", (0.0, -1.0, 0.0), (0.0, -10.0, 0.0), True)
    moves = resolve(
        [u],
        assembly_centre=(0.0, 0.0, 0.0),
        spacing_mm=40.0,
        declared={"part://nonexistent": [1.0, 0.0, 0.0], "other-label": [0.0, 0.0, 1.0]},
    )
    assert moves["part://a#1"] == ExplodeMove(
        direction=(0.0, -1.0, 0.0), distance=40.0, source="interface"
    )


def test_exploded_directions_schema_and_dump_defaults() -> None:
    """``Exploded.directions`` validates keys/vectors and leaves default dumps/hashes unchanged."""
    default_asm = Assembly.model_validate(
        {"id": "box", "name": "Box", "children": [{"part": "part://a", "qty": 1}]}
    )
    assert default_asm.exploded.directions == {}
    dumped = default_asm.model_dump(mode="json")
    assert dumped["exploded"] == {"axis": "z", "spacing": "80 mm"}
    assert "directions" not in dumped["exploded"]
    assert sha256_json(default_asm.exploded.model_dump(mode="json")) == sha256_json(
        {"axis": "z", "spacing": "80 mm"}
    )

    with_dirs = Exploded.model_validate(
        {
            "axis": "z",
            "spacing": "50 mm",
            "directions": {
                "part://a": [0, 0, 0],
                "asm://sub": [1, 0, 0],
                "left-flange": [0, -1.5, 0],
            },
        }
    )
    assert with_dirs.directions["part://a"] == [0.0, 0.0, 0.0]
    assert with_dirs.model_dump(mode="json")["directions"]["left-flange"] == [0.0, -1.5, 0.0]

    for bad in (
        {"part://a": [1.0, 0.0]},  # only 2 numbers
        {"part://a": [1.0, 0.0, float("nan")]},  # non-finite
        {"part://a": [True, 0.0, 0.0]},  # boolean
        {"req://REQ-001": [1.0, 0.0, 0.0]},  # wrong URI scheme
        {"part://a#1": [1.0, 0.0, 0.0]},  # instance fragment not allowed
        {"": [1.0, 0.0, 0.0]},  # empty key
    ):
        with pytest.raises(ValidationError):
            Exploded.model_validate({"directions": bad})


@dataclass
class _ToyPart:
    """Built-part stand-in with a small unit-cube tessellation for GLB and scene tests."""

    tess: tuple[np.ndarray, np.ndarray]


def _cube(offset: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> _ToyPart:
    ox, oy, oz = offset
    verts = np.array(
        [
            [ox - 5.0, oy - 5.0, oz - 5.0],
            [ox + 5.0, oy - 5.0, oz - 5.0],
            [ox + 5.0, oy + 5.0, oz - 5.0],
            [ox - 5.0, oy + 5.0, oz + 5.0],
        ],
        dtype=np.float32,
    )
    tris = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint32)
    return _ToyPart((verts, tris))


def test_place_by_away_and_glb_extras_match_resolver(tmp_path: Path) -> None:
    """``place_by`` records ``away`` from the interface normal and writes ``n2f_explode``."""
    iface = Interface.model_validate(
        {
            "id": "ab",
            "kind": "mating-face",
            "parties": ["part://a", "part://b"],
            "frames": {
                "part://a": {"origin": [10.0, 0.0, 0.0], "normal": [1, 0, 0], "x_axis": [0, 1, 0]},
                "part://b": {"origin": [0.0, 0.0, 0.0], "normal": [0, 0, -1], "x_axis": [1, 0, 0]},
            },
            "offset": 4.0,
            "spec": {"width": "10 mm", "depth": "10 mm"},
        }
    )
    part_a = _cube()
    part_b = _cube()
    res = AssemblyResult()
    # Rotate part://a by +90° about Z so its +X interface normal points along +Y in the assembly
    a_placed = res.add(
        place("part://a", part_a, translate=(0.0, 0.0, 0.0), rotate=(0.0, 0.0, 90.0), label="base")
    )
    b_placed = res.add(place_by({"ab": iface}, res, "ab", "part://b", part_b, label="cap"))
    assert a_placed.away is None
    assert b_placed.away == pytest.approx((0.0, 1.0, 0.0))

    # Reverse order: placing the first party onto the second flips the sign (-normal)
    res_rev = AssemblyResult()
    res_rev.add(place("part://b", part_b, translate=(0.0, 0.0, 0.0)))
    a_rev = place_by({"ab": iface}, res_rev, "ab", "part://a", part_a)
    assert a_rev.away == pytest.approx((0.0, 0.0, 1.0))

    leaves, groups = flatten(res, "asm://toy")
    units = units_of(leaves, groups)
    moves = resolve(
        units, assembly_centre(leaves), spacing_mm=50.0, declared={"base": [0.0, 0.0, 0.0]}
    )
    assert moves["part://a#1"] == ExplodeMove((0.0, 0.0, 0.0), 0.0, "declared")
    assert moves["part://b#1"] == ExplodeMove((0.0, 1.0, 0.0), 50.0, "interface")

    glb_path = export_assembly_glb("asm://toy", leaves, groups, tmp_path / "toy.glb", moves)
    gltf = pygltflib.GLTF2().load(str(glb_path))
    by_name: dict[str, Any] = {n.name: n.extras for n in gltf.nodes}
    assert by_name["part://a#1"]["n2f_explode"] == {
        "dir": [0.0, 0.0, 0.0],
        "distance": 0.0,
        "source": "declared",
    }
    assert by_name["part://b#1"]["n2f_explode"] == {
        "dir": [0.0, 1.0, 0.0],
        "distance": 50.0,
        "source": "interface",
    }

    # And exploded_scene shifts only part://b#1 by +50 mm along +Y
    scene = exploded_scene(leaves, groups, moves)
    assert len(scene.meshes) == 2
