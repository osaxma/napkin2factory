"""Massing fidelity (N3): every generator returns a silhouette in the full path's frame."""

import pytest

from napkin2factory.core.model.interfaces import BoltPatternSpec, Frame, Interface
from napkin2factory.geometry.features import to_json
from napkin2factory.geometry.kit import GENERATORS, Kit, KitContext, run

# the "basic" golden case of each generator (tests/golden/test_kit_*.py)
BASIC = {
    "plate": {"width": "100 mm", "depth": 80, "thickness": "3 mm", "holes": {"diameter": "6.6 mm"}},
    "block": {"length": "200 mm", "width": 100, "height": "5 cm"},
    "tube": {"size": "25 mm", "wall": 2, "length": 300},
    "panel": {
        "width": "400 mm",
        "height": 300,
        "thickness": 2,
        "holes": [{"center": [x, y], "diameter": 5} for x in (-180, 180) for y in (-130, 130)],
        "cutouts": [
            {"center": [0, 50], "width": 100, "height": 60, "corner_radius": 5, "label": "window"}
        ],
    },
    "hole_pattern": {
        "plate_width": 120,
        "plate_depth": 100,
        "thickness": 5,
        "diameter": 8,
        "spacing": [80, 60],
    },
    "bracket_l": {
        "length": "60 mm",
        "height": 40,
        "width": 50,
        "thickness": "2 mm",
        "bend_radius": 3,
        "holes": {"diameter": "6.6 mm", "spacing": 25, "inset": 12},
    },
    "enclosure": {
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
    },
    "frame": {
        "length": 600,
        "width": 400,
        "height": 700,
        "member": {"profile": "square-tube", "size": "25 mm", "wall": "2 mm"},
    },
}


def _massing(name, args, part_id="m"):
    return run(name, args, KitContext(part_id, fidelity="massing"))


def _bounds(res):
    bb = res.shape.bounding_box()
    return [bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z]


def test_every_generator_has_a_case():
    assert set(BASIC) == set(GENERATORS)


@pytest.mark.parametrize("name", GENERATORS)
def test_massing_silhouette(name, check_golden):
    r = _massing(name, BASIC[name])
    check_golden("massing", name, r)
    assert r.features.summary() == {k: 0 for k in r.features.summary()}
    assert r.features.extra == {"fidelity": "massing"}
    assert to_json(r.features)["extra"]["fidelity"] == "massing"
    assert r.flat_pattern is None
    assert r.flat_map is None
    assert r.cut_list == []
    assert r.props["fidelity"] == "massing"
    assert r.notes[0] == "massing silhouette: features omitted"
    assert r.shape.label == "part://m"
    assert len(r.shape.solids()) == 1
    assert r.shape.volume > 0
    assert len(r.dims) in (2, 3)  # tube: size + length; the rest: three overall sizes

    # frame coincidence: the silhouette sits exactly where the full part does
    args = {k: v for k, v in BASIC[name].items() if k != "flange"}
    full = run(name, args, KitContext("m"))
    assert r.features.process == full.features.process
    assert _bounds(r) == pytest.approx(_bounds(full), abs=0.05)


def test_enclosure_flange_is_not_massing():
    """A lip is a feature: the silhouette stays length × width × height (S-0xx)."""
    with_lip = _massing("enclosure", BASIC["enclosure"])
    no_lip = _massing("enclosure", {**BASIC["enclosure"], "flange": 0})
    full_lip = run("enclosure", BASIC["enclosure"], KitContext("m"))
    assert _bounds(with_lip) == pytest.approx(_bounds(no_lip), abs=1e-6)
    assert _bounds(with_lip) == pytest.approx([-100, -60, 0, 100, 60, 60], abs=1e-6)
    assert _bounds(full_lip)[3] == pytest.approx(112, abs=0.05)  # the full part carries the lip


def test_enclosure_silhouette_keeps_wall_thickness():
    r = _massing("enclosure", {**BASIC["enclosure"], "flange": 0})
    t = 1.5
    expected = 200 * 120 * 60 - (200 - 2 * t) * (120 - 2 * t) * (60 - t)
    assert r.shape.volume == pytest.approx(expected, rel=1e-6)
    assert r.props["inner_length"] == pytest.approx(197)
    assert r.props["inner_height"] == pytest.approx(58.5)


def test_frame_silhouette_volume_is_solid_members():
    r = _massing("frame", BASIC["frame"])
    s, legs, rails_x, rails_y = 25, 4 * 700, 4 * 550, 4 * 350
    assert r.shape.volume == pytest.approx(s * s * (legs + rails_x + rails_y), rel=1e-6)


def test_tube_silhouette_has_no_bore():
    r = _massing("tube", {**BASIC["tube"], "axis": "y"})
    full = run("tube", {**BASIC["tube"], "axis": "y"}, KitContext("m"))
    assert r.shape.volume > full.shape.volume
    assert _bounds(r) == pytest.approx(_bounds(full), abs=0.05)


def test_silhouette_has_far_fewer_faces():
    """Leakage canary: a feature sneaking into the massing path shows up as faces."""
    m = _massing("enclosure", BASIC["enclosure"])
    full = run("enclosure", BASIC["enclosure"], KitContext("m"))
    assert len(m.shape.faces()) <= 11
    assert len(full.shape.faces()) > len(m.shape.faces())


IMPOSSIBLE = [
    ("block", {"length": 10, "width": 10, "height": 10, "fillet": 5}, "fillet 5.0 must be"),
    ("enclosure", {"length": 100, "width": 60, "height": 50, "thickness": 30}, "leaves no wall"),
    ("tube", {"size": 20, "length": -5}, "length must be positive"),
    ("frame", {**BASIC["frame"], "width": 40}, "frame width 40 must exceed"),
]


@pytest.mark.parametrize(("name", "args", "message"), IMPOSSIBLE, ids=[c[0] for c in IMPOSSIBLE])
def test_impossible_composition_fails_in_massing(name, args, message):
    with pytest.raises(ValueError, match=message) as full_exc:
        run(name, args, KitContext("x"))
    with pytest.raises(ValueError, match=message) as massing_exc:
        _massing(name, args)
    assert str(massing_exc.value) == str(full_exc.value)


def test_massing_validates_holes_and_cutouts_too():
    bad_plate = {"width": 20, "depth": 20, "thickness": 3, "holes": {"diameter": 12, "inset": 2}}
    with pytest.raises(ValueError, match="breaks the plate edge"):
        _massing("plate", bad_plate)
    bad = {"face": "front", "center": [0, 0], "width": 400, "height": 20}
    with pytest.raises(ValueError, match="outside"):
        _massing("enclosure", {**BASIC["enclosure"], "cutouts": [bad]})


def test_kit_namespace_follows_fidelity():
    kit = Kit(KitContext("x", fidelity="massing"))
    r = kit.plate(width=100, depth=80, thickness=3, holes={"diameter": 6.6})
    assert r.features.holes == []
    assert r.features.extra["fidelity"] == "massing"
    assert r.shape.volume == pytest.approx(100 * 80 * 3)
    full = Kit(KitContext("x")).plate(width=100, depth=80, thickness=3, holes={"diameter": 6.6})
    assert len(full.features.holes) == 4


def test_hole_pattern_massing_accepts_an_interface():
    iface = Interface(
        id="motor-mount",
        kind="bolt-pattern",
        parties=["part://plate", "part://motor"],
        frame=Frame(origin=[10, -5, 5], normal=[0, 0, -1]),
        spec=BoltPatternSpec(pattern="circle", count=6, diameter="5.5 mm", pitch_circle="6 cm"),
    )
    args = {"plate_width": 150, "plate_depth": 120, "thickness": 5, "interface": "motor-mount"}
    ctx = KitContext("hp", interfaces={"motor-mount": iface}, fidelity="massing")
    r = run("hole_pattern", args, ctx)
    full = run("hole_pattern", args, KitContext("hp", interfaces={"motor-mount": iface}))
    assert r.features.patterns == [] and r.features.holes == []
    assert r.shape.volume == pytest.approx(150 * 120 * 5)
    assert _bounds(r) == pytest.approx(_bounds(full), abs=0.05)
    # the interface still has to fit: a pattern off the plate fails in massing too
    with pytest.raises(ValueError, match="breaks the plate edge"):
        run("hole_pattern", {**args, "plate_width": 60, "plate_depth": 60}, ctx)
