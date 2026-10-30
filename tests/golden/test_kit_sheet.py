"""Goldens and properties for the sheet-metal generators ``bracket_l`` and ``enclosure``.

Flat-pattern check (D14/M2): ``flat_pattern.area × thickness`` must match the solid volume
within 2 %.  Straight regions match exactly; the only difference is in the bends: the flat
carries the bend allowance ``(π/2)(r + k·t)`` per unit width while the bent solid holds
``(π/2)(r + t/2)·t`` — i.e. the solid's volume is set by the mid-plane (k = 0.5) and the
flat by the neutral axis (k ≤ 0.5), so the flat is slightly smaller, by
``(π/2)(0.5 − k)·t²`` per unit bend length, well under 2 % for any sane part.  The gap
grows for stubby, thick parts with r/t < 1 (k = 0.33): a 20 mm × 20 mm bracket of 4 mm
sheet with r = 0.5 is ~3 % off — so the property ranges keep legs ≥ 30 mm and t ≤ 3 mm.
"""

import math

import pytest
from build123d import export_step, import_step
from hypothesis import given, settings
from hypothesis import strategies as st

from napkin2factory.geometry.kit import KitContext, run
from napkin2factory.geometry.kit._sheet import bend_allowance, bend_solid, k_factor

BRACKET = {
    "length": "60 mm",
    "height": 40,
    "width": 50,
    "thickness": "2 mm",
    "bend_radius": 3,
    "holes": {"diameter": "6.6 mm", "spacing": 25, "inset": 12},
}

ENCLOSURE = {
    "length": 200,
    "width": "120 mm",
    "height": 60,
    "thickness": 1.5,
    "bend_radius": 2,
    "flange": 12,
    "cutouts": [
        {"face": "base", "center": [0, 0], "width": 50, "height": 30},
        {"face": "front", "center": [30, 0], "width": 40, "height": 20, "corner_radius": 3},
    ],
}


def _bbox(res):
    bb = res.shape.bounding_box().size
    return bb.X, bb.Y, bb.Z


def _flat_ratio(res):
    return res.flat_pattern.area * res.features.thickness / res.shape.volume


# ---------------------------------------------------------------- shared math


def test_k_factor_table_and_bend_allowance():
    assert k_factor(0.5, 1) == 0.33
    assert k_factor(1.5, 1) == 0.40
    assert k_factor(3, 1) == 0.44
    assert k_factor(5, 1) == 0.50
    assert bend_allowance(3, 2, 90, k=0.5) == pytest.approx(math.pi / 2 * 4)
    s = bend_solid(3, 2, 90, 10)
    assert s.volume == pytest.approx(math.pi / 4 * (5**2 - 3**2) * 10, rel=1e-6)


# ---------------------------------------------------------------- bracket_l


def test_bracket_basic(check_golden):
    r = run("bracket_l", BRACKET, KitContext("b"))
    fp = check_golden("bracket_l", "basic", r)
    assert fp["features"]["bends"] == 1
    assert fp["features"]["flanges"] == 2
    assert fp["features"]["holes"] == 4
    assert r.shape.volume > 0 and len(r.shape.solids()) == 1
    x, y, z = _bbox(r)
    assert abs(x - 60) < 1e-3 and abs(y - 50) < 1e-3 and abs(z - 40) < 1e-3
    assert abs(_flat_ratio(r) - 1) < 0.02
    assert r.shape.label == "part://b"
    assert {d.label for d in r.dims} >= {
        "length",
        "height",
        "width",
        "thickness",
        "bend radius",
        "hole",
        "hole inset",
    }
    ba = bend_allowance(3, 2, 90)
    assert r.props["bend_allowance"] == pytest.approx(ba)
    assert r.props["developed_length"] == pytest.approx(55 + 35 + ba)
    assert r.flat_pattern.size() == pytest.approx((55 + 35 + ba, 50))
    assert len(r.flat_pattern.bend_lines) == 1
    hole = r.features.holes[0]
    assert hole.bend_distance == pytest.approx(55 - 12)
    assert hole.edge_distance == pytest.approx(12 - 3.3)


def test_bracket_rejects_bad_geometry():
    with pytest.raises(ValueError, match="bend zone"):
        run("bracket_l", {**BRACKET, "holes": {"diameter": 6.6, "inset": 52}}, KitContext("b"))
    with pytest.raises(ValueError, match="free end"):
        run("bracket_l", {**BRACKET, "holes": {"diameter": 6.6, "inset": 2}}, KitContext("b"))
    with pytest.raises(ValueError, match="side edges"):
        run("bracket_l", {**BRACKET, "holes": {"diameter": 10, "spacing": 42}}, KitContext("b"))
    with pytest.raises(ValueError, match="too short"):
        run("bracket_l", {**BRACKET, "height": 6}, KitContext("b"))


@settings(max_examples=6, deadline=None)
@given(
    length=st.floats(30, 150),
    height=st.floats(30, 150),
    width=st.floats(10, 100),
    t=st.floats(0.5, 3),
    r=st.floats(0.5, 6),
    holes=st.booleans(),
)
def test_bracket_properties(length, height, width, t, r, holes):
    args = {"length": length, "height": height, "width": width, "thickness": t, "bend_radius": r}
    if holes:
        args["holes"] = {"diameter": min(width / 4, (length - r - t) / 3, (height - r - t) / 3)}
    res = run("bracket_l", args, KitContext("b"))
    assert res.shape.volume > 0
    x, y, z = _bbox(res)
    assert abs(x - length) < 1e-3 and abs(y - width) < 1e-3 and abs(z - height) < 1e-3
    assert abs(_flat_ratio(res) - 1) < 0.02


# ---------------------------------------------------------------- enclosure


def test_enclosure_basic(check_golden, tmp_path):
    r = run("enclosure", ENCLOSURE, KitContext("e"))
    fp = check_golden("enclosure", "basic", r)
    assert fp["features"]["bends"] == 8
    assert fp["features"]["flanges"] == 8
    assert fp["features"]["reliefs"] == 4
    assert fp["features"]["cutouts"] == 2
    assert r.shape.volume > 0 and len(r.shape.solids()) == 1
    x, y, z = _bbox(r)  # the lip adds `flange` beyond each wall
    assert abs(x - 224) < 1e-3 and abs(y - 144) < 1e-3 and abs(z - 60) < 1e-3
    assert abs(_flat_ratio(r) - 1) < 0.02
    assert r.shape.label == "part://e"
    assert {d.label for d in r.dims} >= {
        "length",
        "width",
        "height",
        "thickness",
        "bend radius",
        "flange",
    }
    assert r.props["inner_length"] == pytest.approx(197)
    assert r.props["inner_width"] == pytest.approx(117)
    assert r.props["inner_height"] == pytest.approx(58.5)
    assert len(r.flat_pattern.bend_lines) == 8
    assert len(r.flat_pattern.cutouts) == 2

    path = tmp_path / "enclosure.step"
    export_step(r.shape, str(path))
    back = import_step(str(path))
    assert len(back.solids()) == 1
    assert back.volume == pytest.approx(r.shape.volume, rel=1e-4)


def test_enclosure_without_lip():
    r = run(
        "enclosure",
        {"length": 120, "width": 80, "height": 40, "thickness": 2, "bend_radius": 2},
        KitContext("e"),
    )
    s = r.features.summary()
    assert (s["bends"], s["flanges"], s["reliefs"]) == (4, 4, 4)
    x, y, z = _bbox(r)
    assert abs(x - 120) < 1e-3 and abs(y - 80) < 1e-3 and abs(z - 40) < 1e-3
    assert abs(_flat_ratio(r) - 1) < 0.02
    assert r.features.flanges[0].height == pytest.approx(40 - 2 - 2)  # height − t − r


def test_enclosure_rejects_bad_geometry():
    with pytest.raises(ValueError, match="outside"):
        bad = {"face": "base", "center": [80, 0], "width": 50, "height": 30}
        run("enclosure", {**ENCLOSURE, "cutouts": [bad]}, KitContext("e"))
    with pytest.raises(ValueError, match="outside"):
        bad = {"face": "right", "center": [0, 20], "width": 20, "height": 20}
        run("enclosure", {**ENCLOSURE, "cutouts": [bad]}, KitContext("e"))
    with pytest.raises(ValueError, match="relief"):
        run("enclosure", {**ENCLOSURE, "relief": 1}, KitContext("e"))
    with pytest.raises(ValueError, match="too low"):
        run("enclosure", {**ENCLOSURE, "flange": 0, "height": 4}, KitContext("e"))


@settings(max_examples=6, deadline=None)
@given(
    length=st.floats(60, 300),
    width=st.floats(60, 200),
    height=st.floats(25, 100),
    t=st.floats(0.8, 3),
    r=st.floats(0.5, 4),
    flange=st.one_of(st.just(0.0), st.floats(8, 20)),
)
def test_enclosure_properties(length, width, height, t, r, flange):
    res = run(
        "enclosure",
        {
            "length": length,
            "width": width,
            "height": height,
            "thickness": t,
            "bend_radius": r,
            "flange": flange,
            "cutouts": [{"face": "base", "width": length / 4, "height": width / 4}],
        },
        KitContext("e"),
    )
    assert res.shape.volume > 0
    x, y, z = _bbox(res)
    ex, ey = length + 2 * flange, width + 2 * flange
    assert abs(x - ex) < 1e-3 and abs(y - ey) < 1e-3 and abs(z - height) < 1e-3
    assert abs(_flat_ratio(res) - 1) < 0.02
