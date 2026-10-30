import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from napkin2factory.geometry.kit import KitContext, KitError, run


def _frame(**kw):
    args = {
        "length": 600,
        "width": 400,
        "height": 700,
        "member": {"profile": "square-tube", "size": "25 mm", "wall": "2 mm"},
    }
    args.update(kw)
    return run("frame", args, KitContext("f"))


def _section(profile, s, w):
    if profile == "square-tube":
        return s * s - (s - 2 * w) ** 2
    return 2 * s * w - w * w


def _check_common(r, length, width, height, profile, s, w, n_members):
    shape = r.shape
    assert shape.volume > 0
    # one weldment: the fuse must leave a single solid
    assert len(shape.solids()) == 1
    bb = shape.bounding_box().size
    assert abs(bb.X - length) < 1e-3 and abs(bb.Y - width) < 1e-3 and abs(bb.Z - height) < 1e-3
    # fused volume == analytic sum of true-length members: proves no interference between
    # members (rail-end join overlaps are swallowed by leg material)
    expected = sum(_section(profile, s, w) * m.length for m in r.features.members)
    assert abs(shape.volume - expected) / expected < 1e-3
    assert len(r.features.members) == n_members
    assert r.features.extra["member_count"] == n_members
    assert sum(c.qty for c in r.cut_list) == n_members
    assert abs(r.props["total_member_length"] - sum(c.length * c.qty for c in r.cut_list)) < 1e-6
    assert shape.label == "part://f"


def test_frame_basic(check_golden):
    r = _frame()
    fp = check_golden("frame", "basic", r)
    assert fp["features"]["members"] == 12
    _check_common(r, 600, 400, 700, "square-tube", 25, 2, 12)
    cuts = {(c.length, c.qty) for c in r.cut_list}
    assert cuts == {(700.0, 4), (550.0, 4), (350.0, 4)}
    assert all(c.profile == "square-tube 25x25x2" for c in r.cut_list)
    assert r.features.extra["weld_joints"] == 16
    assert r.features.process == "welding"
    labels = {m.label for m in r.features.members}
    assert {"leg-1", "leg-4", "top-rail-x-1", "bottom-rail-y-2"} <= labels
    assert {d.label for d in r.dims} >= {"length", "width", "height", "member"}


def test_frame_angle(check_golden):
    r = _frame(member={"profile": "angle", "size": 30, "wall": 3}, bottom_rails=False)
    fp = check_golden("frame", "angle", r)
    assert fp["features"]["members"] == 8
    _check_common(r, 600, 400, 700, "angle", 30, 3, 8)
    cuts = {(c.length, c.qty) for c in r.cut_list}
    assert cuts == {(700.0, 4), (540.0, 2), (340.0, 2)}
    assert r.cut_list[0].profile == "angle 30x30x3"
    assert r.features.extra["weld_joints"] == 8


def test_frame_square_footprint_groups_rails():
    r = _frame(length=500, width=500)
    assert {(c.length, c.qty) for c in r.cut_list} == {(700.0, 4), (450.0, 8)}


def test_frame_rejects_bad_args():
    with pytest.raises(ValueError, match="width"):
        _frame(width=40)  # smaller than 2 * size
    with pytest.raises(ValueError, match="2\\*wall"):
        _frame(member={"size": 10, "wall": 5})
    with pytest.raises(ValueError, match="collide"):
        _frame(height=100, bottom_rail_height=60)
    with pytest.raises(ValueError, match="height"):
        _frame(height=20)
    with pytest.raises(KitError):
        _frame(member={"profile": "round", "size": 25, "wall": 2})
    with pytest.raises(KitError):
        _frame(bogus=1)
    with pytest.raises(ValueError, match="bare legs"):
        _frame(top_rails=False, bottom_rails=False)


@settings(max_examples=6, deadline=None)
@given(
    length=st.floats(150, 1200),
    width=st.floats(150, 900),
    height=st.floats(200, 1000),
    profile=st.sampled_from(["square-tube", "angle"]),
    size=st.floats(15, 50),
    wall_frac=st.floats(0.05, 0.3),
    rails=st.sampled_from([(True, True), (True, False), (False, True)]),
)
def test_frame_properties(length, width, height, profile, size, wall_frac, rails):
    top, bottom = rails
    wall = size * wall_frac
    r = _frame(
        length=length,
        width=width,
        height=height,
        member={"profile": profile, "size": size, "wall": wall},
        top_rails=top,
        bottom_rails=bottom,
    )
    n = 4 + 4 * top + 4 * bottom
    _check_common(r, length, width, height, profile, size, wall, n)
    for c in r.cut_list:
        assert any(abs(c.length - v) < 1e-6 for v in (height, length - 2 * size, width - 2 * size))
