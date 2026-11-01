"""P1: ``place_by`` puts a part where its interface frame meets the placed party's (S-106)."""

from __future__ import annotations

from typing import Any

import pytest

from napkin2factory.core.frames import WorldFrame, world_frame
from napkin2factory.core.model import Frame, Interface
from napkin2factory.geometry.assembly import (
    AssemblyResult,
    flatten,
    location_to_trs,
    place,
    place_by,
)
from napkin2factory.geometry.build import GeometryError


def _iface(
    frames: dict[str, dict[str, Any]],
    offset: float = 0.0,
    parties: tuple[str, str] = ("part://a", "part://b"),
) -> Interface:
    return Interface.model_validate(
        {
            "id": "ab",
            "kind": "mating-face",
            "parties": list(parties),
            "frames": frames,
            "offset": offset,
            "spec": {"width": "10 mm", "depth": "10 mm"},
        }
    )


def _world(p: Any, frame: Frame) -> WorldFrame:
    t, q = location_to_trs(p.location)
    return world_frame(frame, t, q)


def _close(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return all(abs(x - y) < 1e-9 for x, y in zip(a, b, strict=True))


# a's frame: on its +X face, normal +X; b's frame: on its bottom, normal −Z (b is "turned")
FRAMES = {
    "part://a": {"origin": [10.0, 2.0, 3.0], "normal": [1, 0, 0], "x_axis": [0, 1, 0]},
    "part://b": {"origin": [0.0, 0.0, -5.0], "normal": [0, 0, -1], "x_axis": [1, 0, 0]},
}


def test_rotation_and_positive_offset_from_the_first_party() -> None:
    iface = _iface(FRAMES, offset=4.0)
    res = AssemblyResult()
    res.add(place("part://a", None, translate=(100.0, 0.0, 0.0), rotate=(0.0, 0.0, 90.0)))
    b = place_by({"ab": iface}, res, "ab", "part://b", None, label="b")
    assert b.via == "iface://ab" and b.label == "b"
    wa = _world(res.instances[0], iface.frame_for("part://a"))
    wb = _world(b, iface.frame_for("part://b"))
    # same normal and x axis in the world, b's origin 4 mm along a's normal
    assert _close(wb.normal, wa.normal) and _close(wb.x_axis, wa.x_axis)
    expect = tuple(o + 4.0 * n for o, n in zip(wa.origin, wa.normal, strict=True))
    assert _close(wb.origin, expect)
    assert _close(wa.normal, (0.0, 1.0, 0.0))  # a turned 90° about Z: its +X face looks +Y


def test_negative_offset_and_placing_the_first_party() -> None:
    """The child is the first party: it lands ``offset`` *before* the placed second party."""
    iface = _iface(FRAMES, offset=-7.5)
    res = AssemblyResult()
    res.add(place("part://b", None, translate=(0.0, 0.0, 50.0)))
    a = place_by({"ab": iface}, res, "ab", "part://a", None)
    wa = _world(a, iface.frame_for("part://a"))
    wb = _world(res.instances[0], iface.frame_for("part://b"))
    assert _close(wa.normal, wb.normal) and _close(wa.x_axis, wb.x_axis)
    # offset runs first → second: b = a + offset·n, so a = b − offset·n
    expect = tuple(o - (-7.5) * n for o, n in zip(wb.origin, wb.normal, strict=True))
    assert _close(wa.origin, expect)


def test_qty_above_one_needs_onto() -> None:
    iface = _iface(FRAMES)
    res = AssemblyResult()
    res.add(place("part://a", None, translate=(0.0, 0.0, 0.0), label="left"))
    res.add(place("part://a", None, translate=(0.0, 300.0, 0.0), label="right"))
    with pytest.raises(GeometryError, match=r"placed 2 times; pick one with onto=.*'left'"):
        place_by({"ab": iface}, res, "ab", "part://b", None)
    with pytest.raises(GeometryError, match="no occurrence of part://a is labelled 'middle'"):
        place_by({"ab": iface}, res, "ab", "part://b", None, onto="middle")
    b = place_by({"ab": iface}, res, "ab", "part://b", None, onto="right")
    wa = _world(res.instances[1], iface.frame_for("part://a"))
    wb = _world(b, iface.frame_for("part://b"))
    assert _close(wb.origin, wa.origin) and wb.origin[1] == pytest.approx(302.0)


def test_missing_x_axis_is_an_error_with_the_fix() -> None:
    frames = {**FRAMES, "part://b": {"origin": [0.0, 0.0, 0.0], "normal": [0, 0, -1]}}
    res = AssemblyResult()
    res.add(place("part://a", None))
    with pytest.raises(GeometryError) as exc:
        place_by({"ab": _iface(frames)}, res, "ab", "part://b", None)
    msg = str(exc.value)
    assert "part://b" in msg and "no x_axis" in msg
    assert "x_axis: [1.0, 0.0, 0.0]" in msg and "model/interfaces/ab.yaml" in msg


def test_absent_party_and_wrong_party_are_errors() -> None:
    iface = _iface(FRAMES)
    res = AssemblyResult()
    with pytest.raises(GeometryError, match="part://a is not placed yet; place part://a first"):
        place_by({"ab": iface}, res, "ab", "part://b", None)
    res.add(place("part://a", None))
    with pytest.raises(GeometryError, match="part://c is not a party of iface://ab"):
        place_by({"ab": iface}, res, "ab", "part://c", None)


def test_an_assembly_party_points_to_ports() -> None:
    iface = _iface({"part://b": FRAMES["part://b"]}, parties=("asm://a", "part://b"))
    res = AssemblyResult()
    with pytest.raises(GeometryError, match="ports"):
        place_by({"ab": iface}, res, "ab", "part://b", None)


# ---- sub-assemblies placed by a port (P4, S-107) ----------------------------------------


class _Sub:
    """A built sub-assembly stand-in: its leaves, in its own frame (``BuiltAssembly.leaves``)."""

    def __init__(self, *leaves: tuple[str, tuple[float, float, float], str | None]) -> None:
        self.result = AssemblyResult()
        for uri, t, lab in leaves:
            self.result.add(place(uri, None, translate=t, rotate=(0.0, 0.0, 90.0), label=lab))
        self.leaves = flatten(self.result, "asm://sub")[0]


def _leaf_world(sub: Any, placement: Any, label: str) -> Any:
    """The world location of the sub-assembly's leaf labelled ``label``."""
    leaf = next(lf for lf in sub.leaves if lf.label == label)
    return placement.location * leaf.location


def test_a_sub_assembly_is_placed_by_its_port() -> None:
    """The leaf inside moves to where the part would go; the sub-assembly carries it there."""
    iface = _iface(FRAMES, offset=4.0)
    sub = _Sub(("part://b", (5.0, 6.0, 7.0), "b"), ("part://c", (0.0, 0.0, 0.0), None))
    res = AssemblyResult()
    res.add(place("part://a", None, translate=(100.0, 0.0, 0.0), rotate=(0.0, 0.0, 90.0)))
    placed = place_by({"ab": iface}, res, "ab", "asm://sub", sub, label="sub")
    assert placed.via == "iface://ab" and placed.is_assembly
    alone = place_by({"ab": iface}, res, "ab", "part://b", None)
    t_sub, q_sub = location_to_trs(_leaf_world(sub, placed, "b"))
    t_alone, q_alone = location_to_trs(alone.location)
    assert _close(t_sub, t_alone)
    # the same rotation: unit quaternions q and -q, so |q_sub · q_alone| = 1
    assert abs(sum(x * y for x, y in zip(q_sub, q_alone, strict=True))) == pytest.approx(1.0)


def test_inner_picks_the_leaf_and_ambiguity_is_an_error() -> None:
    iface = _iface(FRAMES)
    sub = _Sub(("part://b", (0.0, 0.0, 0.0), "left"), ("part://b", (0.0, 50.0, 0.0), "right"))
    res = AssemblyResult()
    res.add(place("part://a", None))
    with pytest.raises(
        GeometryError, match=r"placed 2 times inside asm://sub; pick one with inner="
    ):
        place_by({"ab": iface}, res, "ab", "asm://sub", sub)
    placed = place_by({"ab": iface}, res, "ab", "asm://sub", sub, inner="right")
    alone = place_by({"ab": iface}, res, "ab", "part://b", None)
    assert _close(
        location_to_trs(_leaf_world(sub, placed, "right"))[0], location_to_trs(alone.location)[0]
    )


def test_a_sub_assembly_holding_both_or_neither_party_is_refused() -> None:
    iface = _iface(FRAMES)
    res = AssemblyResult()
    res.add(place("part://a", None))
    both = _Sub(("part://a", (0.0, 0.0, 0.0), None), ("part://b", (0.0, 0.0, 0.0), None))
    with pytest.raises(GeometryError, match="both of its parties are inside it"):
        place_by({"ab": iface}, res, "ab", "asm://sub", both)
    with pytest.raises(GeometryError, match="neither of its parties is inside it"):
        place_by({"ab": iface}, res, "ab", "asm://sub", _Sub(("part://c", (0, 0, 0), None)))


def test_onto_a_leaf_of_a_placed_sub_assembly() -> None:
    """Two modules joined by a port each side: the anchor is a leaf of a placed sub-assembly."""
    iface = _iface(FRAMES, offset=2.0)
    sub = _Sub(("part://a", (0.0, 0.0, 0.0), "left"), ("part://a", (0.0, 40.0, 0.0), "right"))
    res = AssemblyResult()
    outer = res.add(place("asm://sub", sub, translate=(0.0, 0.0, 30.0), label="pod"))
    with pytest.raises(GeometryError, match=r"'pod/left', 'pod/right'"):
        place_by({"ab": iface}, res, "ab", "part://b", None)
    b = place_by({"ab": iface}, res, "ab", "part://b", None, onto="right")
    alone = AssemblyResult()
    alone.add(place("part://a", None, _leaf_world(sub, outer, "right")))
    expect = place_by({"ab": iface}, alone, "ab", "part://b", None)
    assert _close(location_to_trs(b.location)[0], location_to_trs(expect.location)[0])


def test_place_records_coordinates() -> None:
    assert place("part://a", None).via == "coordinates"
