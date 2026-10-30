import itertools
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from napkin2factory.core.model.interfaces import BoltPatternSpec, Frame, Interface
from napkin2factory.geometry.kit import KitContext, KitError, run
from napkin2factory.geometry.kit.hole_pattern import centers_2d, centers_from_spec


def _bbox(r):
    bb = r.shape.bounding_box()
    return bb.size.X, bb.size.Y, bb.size.Z


def _rel(a, b):
    return abs(a - b) / abs(b)


# ---------------------------------------------------------------- block


def test_block_basic(check_golden):
    r = run("block", {"length": "200 mm", "width": 100, "height": "5 cm"}, KitContext("b"))
    fp = check_golden("block", "basic", r)
    assert r.shape.volume > 0
    assert _rel(r.shape.volume, 200 * 100 * 50) < 0.005
    assert _bbox(r) == pytest.approx((200, 100, 50), abs=1e-3)
    assert r.shape.bounding_box().min.Z == pytest.approx(0, abs=1e-6)
    assert fp["features"] == {k: 0 for k in fp["features"]}
    assert r.features.process == "cut-block"
    assert r.features.extra["cut_size"] == [200, 100, 50]
    assert {d.label for d in r.dims} == {"length", "width", "height"}
    assert r.flat_pattern is None
    (c,) = r.cut_list
    assert c.description == "200×100×50 block"
    assert (c.length, c.width, c.thickness, c.qty) == (200, 100, 50, 1)
    assert r.shape.label == "part://b"


def test_block_rejects_bad_args():
    with pytest.raises(KitError):
        run("block", {"length": 10, "width": 10}, KitContext("b"))
    with pytest.raises(ValueError, match="fillet"):
        run("block", {"length": 10, "width": 10, "height": 10, "fillet": 5}, KitContext("b"))
    with pytest.raises(ValueError, match="not both"):
        run(
            "block",
            {"length": 10, "width": 10, "height": 10, "fillet": 1, "chamfer": 1},
            KitContext("b"),
        )


@settings(max_examples=6, deadline=None)
@given(
    l_=st.floats(5, 500),
    w=st.floats(5, 500),
    h=st.floats(5, 300),
    f=st.floats(0, 0.4),
    edge=st.sampled_from(["none", "fillet", "chamfer"]),
)
def test_block_properties(l_, w, h, f, edge):
    args = {"length": l_, "width": w, "height": h}
    expected = l_ * w * h
    if edge == "fillet" and f > 0.01:
        r_ = f * min(l_, w)
        args["fillet"] = r_
        expected -= (4 - math.pi) * r_ * r_ * h
    elif edge == "chamfer" and f > 0.01:
        args["chamfer"] = f * min(l_, w, h)
    res = run("block", args, KitContext("b"))
    assert res.shape.volume > 0
    assert _bbox(res) == pytest.approx((l_, w, h), abs=1e-3)
    if "chamfer" in args:
        assert res.shape.volume < expected
    else:
        assert _rel(res.shape.volume, expected) < 0.005


# ---------------------------------------------------------------- tube


def test_tube_basic(check_golden):
    r = run("tube", {"size": "25 mm", "wall": 2, "length": 300}, KitContext("t"))
    fp = check_golden("tube", "basic", r)
    expected = math.pi / 4 * (25**2 - 21**2) * 300
    assert r.shape.volume > 0 and _rel(r.shape.volume, expected) < 0.005
    assert _bbox(r) == pytest.approx((25, 25, 300), abs=1e-3)
    assert r.shape.bounding_box().min.Z == pytest.approx(0, abs=1e-6)
    assert fp["cut_items"] == 1 and fp["cut_length_total"] == pytest.approx(300)
    assert r.features.extra == {"profile": "round 25x2", "outer": 25, "wall": 2, "solid": False}
    (c,) = r.cut_list
    assert c.profile == "round 25x2" and c.length == 300 and c.qty == 1
    assert {d.label for d in r.dims} == {"size", "length", "wall"}


def test_tube_square(check_golden):
    r = run(
        "tube",
        {"shape": "square", "size": 30, "wall": 3, "length": 500, "axis": "x"},
        KitContext("t"),
    )
    check_golden("tube", "square", r)
    expected = (30**2 - 24**2) * 500
    assert _rel(r.shape.volume, expected) < 0.005
    assert _bbox(r) == pytest.approx((500, 30, 30), abs=1e-3)
    bb = r.shape.bounding_box()
    assert bb.min.X == pytest.approx(0, abs=1e-6) and bb.min.Y == pytest.approx(-15, abs=1e-6)
    assert r.cut_list[0].profile == "square 30x3"


def test_tube_solid_rod():
    r = run("tube", {"size": 10, "length": 100, "axis": "y"}, KitContext("t"))
    assert _rel(r.shape.volume, math.pi * 25 * 100) < 0.005
    assert _bbox(r) == pytest.approx((10, 100, 10), abs=1e-3)
    assert r.features.extra["solid"] is True and r.features.extra["wall"] == 0
    assert r.cut_list[0].profile == "round 10 solid"
    thick = run("tube", {"size": 10, "wall": 6, "length": 100}, KitContext("t"))
    assert thick.features.extra["solid"] is True


@settings(max_examples=6, deadline=None)
@given(
    shape=st.sampled_from(["round", "square"]),
    size=st.floats(5, 120),
    wall_frac=st.one_of(st.just(0.0), st.floats(0.05, 0.45)),
    length=st.floats(5, 2000),
    axis=st.sampled_from(["x", "y", "z"]),
)
def test_tube_properties(shape, size, wall_frac, length, axis):
    wall = wall_frac * size
    res = run(
        "tube",
        {"shape": shape, "size": size, "wall": wall, "length": length, "axis": axis},
        KitContext("t"),
    )
    inner = size - 2 * wall if wall > 0 else 0.0
    area = math.pi / 4 * (size**2 - inner**2) if shape == "round" else size**2 - inner**2
    assert res.shape.volume > 0
    assert _rel(res.shape.volume, area * length) < 0.005
    want = {"x": (length, size, size), "y": (size, length, size), "z": (size, size, length)}[axis]
    assert _bbox(res) == pytest.approx(want, abs=1e-3)


# ---------------------------------------------------------------- panel

PANEL = {
    "width": "400 mm",
    "height": 300,
    "thickness": 2,
    "holes": [{"center": [x, y], "diameter": 5} for x in (-180, 180) for y in (-130, 130)],
    "cutouts": [
        {"center": [0, 50], "width": 100, "height": 60, "corner_radius": 5, "label": "window"}
    ],
}


def test_panel_basic(check_golden):
    r = run("panel", PANEL, KitContext("door"))
    fp = check_golden("panel", "basic", r)
    area = 400 * 300 - 4 * math.pi * 2.5**2 - (100 * 60 - (4 - math.pi) * 25)
    assert r.shape.volume > 0 and _rel(r.shape.volume, area * 2) < 0.005
    assert _rel(r.flat_pattern.area, area) < 1e-9
    assert _rel(r.flat_pattern.area * 2, r.shape.volume) < 0.005
    assert _bbox(r) == pytest.approx((400, 300, 2), abs=1e-3)
    assert fp["features"]["holes"] == 4 and fp["features"]["cutouts"] == 1
    assert all(h.edge_distance == pytest.approx(17.5) for h in r.features.holes)
    assert r.features.cutouts[0].face == "base" and r.features.cutouts[0].label == "window"
    assert r.features.thickness == 2
    assert len(r.flat_pattern.holes) == 4 and len(r.flat_pattern.cutouts) == 1
    labels = [d.label for d in r.dims]
    assert {"width", "height", "thickness"} <= set(labels)
    assert sum(d.kind == "diameter" for d in r.dims) == 1  # each diameter once


def test_panel_rounded_corners():
    r = run(
        "panel", {"width": 200, "height": 100, "thickness": 3, "corner_radius": 10}, KitContext("p")
    )
    area = 200 * 100 - (4 - math.pi) * 100
    assert _rel(r.shape.volume, area * 3) < 0.005
    assert _rel(r.flat_pattern.area, area) < 1e-9


def test_panel_rejects_outside_features():
    base = {"width": 100, "height": 80, "thickness": 2}
    with pytest.raises(ValueError, match="not inside"):
        run("panel", {**base, "holes": [{"center": [48, 0], "diameter": 6}]}, KitContext("p"))
    with pytest.raises(ValueError, match="not inside"):
        run(
            "panel",
            {**base, "cutouts": [{"center": [30, 0], "width": 50, "height": 10}]},
            KitContext("p"),
        )
    with pytest.raises(ValueError, match="not inside"):  # in the rounded corner
        run(
            "panel",
            {**base, "corner_radius": 20, "holes": [{"center": [47, 37], "diameter": 2}]},
            KitContext("p"),
        )
    with pytest.raises(ValueError, match="overlap"):
        run(
            "panel",
            {
                **base,
                "holes": [{"center": [0, 0], "diameter": 6}, {"center": [4, 0], "diameter": 6}],
            },
            KitContext("p"),
        )


# ---------------------------------------------------------------- hole pattern


def test_hole_pattern_basic(check_golden):
    r = run(
        "hole_pattern",
        {
            "plate_width": 120,
            "plate_depth": 100,
            "thickness": 5,
            "diameter": 8,
            "spacing": [80, 60],
        },
        KitContext("hp"),
    )
    fp = check_golden("hole_pattern", "basic", r)
    expected = 120 * 100 * 5 - 4 * math.pi * 16 * 5
    assert r.shape.volume > 0 and _rel(r.shape.volume, expected) < 0.005
    assert _rel(r.flat_pattern.area * 5, r.shape.volume) < 0.005
    assert _bbox(r) == pytest.approx((120, 100, 5), abs=1e-3)
    assert fp["features"]["holes"] == 4 and fp["features"]["patterns"] == 1
    (p,) = r.features.patterns
    assert sorted((round(x), round(y)) for x, y, _ in p.centers) == [
        (-40, -30),
        (-40, 30),
        (40, -30),
        (40, 30),
    ]
    assert p.interface is None
    assert {"width", "depth", "thickness", "hole", "spacing_x", "spacing_y"} <= {
        d.label for d in r.dims
    }


def _iface(normal, origin, x_axis=None):
    return Interface(
        id="motor-mount",
        kind="bolt-pattern",
        parties=["part://plate", "part://motor"],
        frame=Frame(origin=origin, normal=normal, x_axis=x_axis),
        spec=BoltPatternSpec(pattern="circle", count=6, diameter="5.5 mm", pitch_circle="6 cm"),
    )


def test_hole_pattern_from_interface():
    iface = _iface([0, 0, -1], [10, -5, 5])
    ctx = KitContext("hp", interfaces={"motor-mount": iface})
    r = run(
        "hole_pattern",
        {"plate_width": 150, "plate_depth": 120, "thickness": 5, "interface": "motor-mount"},
        ctx,
    )
    expected = 150 * 120 * 5 - 6 * math.pi * 2.75**2 * 5
    assert _rel(r.shape.volume, expected) < 0.005
    (p,) = r.features.patterns
    assert p.interface == "iface://motor-mount" and len(p.centers) == 6
    assert all(h.interface == "iface://motor-mount" for h in r.features.holes)
    for x, y, z in p.centers:
        assert math.hypot(x - 10, y + 5) == pytest.approx(30)
        assert z == pytest.approx(5)


def test_hole_pattern_rejects():
    with pytest.raises(ValueError, match="breaks the plate edge"):
        run(
            "hole_pattern",
            {
                "plate_width": 50,
                "plate_depth": 50,
                "thickness": 3,
                "diameter": 6,
                "spacing": [50, 40],
            },
            KitContext("hp"),
        )
    with pytest.raises(ValueError, match="needs a diameter"):
        run(
            "hole_pattern", {"plate_width": 50, "plate_depth": 50, "thickness": 3}, KitContext("hp")
        )


def test_centers_2d_rect4():
    pts = centers_2d("rect", 4, [80, 60], None)
    assert sorted(pts) == sorted([(-40, -30), (40, -30), (-40, 30), (40, 30)])


def test_centers_2d_rect_grid():
    assert centers_2d("rect", 2, [50], None) == [(-25, 0), (25, 0)]
    pts = centers_2d("rect", 6, [40, 30], None)
    assert sorted(pts) == sorted([(x, y) for x in (-40, 0, 40) for y in (-15, 15)])


def test_centers_2d_circle6():
    pts = centers_2d("circle", 6, None, 100)
    assert len(pts) == 6
    assert all(math.hypot(x, y) == pytest.approx(50) for x, y in pts)
    assert pts[0] == pytest.approx((50, 0))


def test_centers_2d_line3():
    pts = centers_2d("line", 3, [25], None)
    assert pts == [(-25, 0), (0, 0), (25, 0)]
    assert sum(x for x, _ in pts) == pytest.approx(0)


def test_centers_2d_errors():
    with pytest.raises(ValueError):
        centers_2d("rect", 5, [10, 10], None)
    with pytest.raises(ValueError):
        centers_2d("circle", 4, None, None)


@pytest.mark.parametrize("normal", [(0, 0, -1), (1, 0, 0)])
@pytest.mark.parametrize(
    "spec",
    [
        BoltPatternSpec(pattern="rect", count=4, diameter="6 mm", spacing=["80 mm", "6 cm"]),
        BoltPatternSpec(pattern="circle", count=6, diameter="5 mm", pitch_circle="50 mm"),
    ],
)
def test_centers_from_spec_in_plane(normal, spec):
    origin = (12.0, -7.0, 33.0)
    frame = Frame(origin=list(origin), normal=list(normal))
    pts3 = centers_from_spec(spec, frame)
    spacing = [s.to("mm").magnitude for s in spec.spacing] if spec.spacing else None
    pc = spec.pitch_circle.to("mm").magnitude if spec.pitch_circle is not None else None
    pts2 = centers_2d(spec.pattern, spec.count, spacing, pc)
    assert len(pts3) == len(pts2) == spec.count
    for p in pts3:
        assert sum((p[i] - origin[i]) * normal[i] for i in range(3)) == pytest.approx(0, abs=1e-9)
    for i, j in itertools.combinations(range(len(pts2)), 2):
        assert math.dist(pts3[i], pts3[j]) == pytest.approx(math.dist(pts2[i], pts2[j]))
    # deterministic: same frame → same points
    assert centers_from_spec(spec, frame) == pts3
