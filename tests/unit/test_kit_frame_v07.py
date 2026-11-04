"""Tests for v0.7 frame kit additions (S-202):

- rect-tube, round-tube, t-slot profiles
- rail_member and apron_offset_top
- mounting_tabs with through slots for wood movement
- unchanged defaults and volume equality
"""

from __future__ import annotations

import math

import pytest

from napkin2factory.geometry.kit import KitContext, run
from napkin2factory.geometry.kit.frame import (
    MemberSpec,
    profile_name,
    section_area,
    validate_member,
)


def _frame(**kw):
    args = {
        "length": 600,
        "width": 400,
        "height": 700,
        "member": {"profile": "square-tube", "size": "25 mm", "wall": "2 mm"},
    }
    args.update(kw)
    return run("frame", args, KitContext("f"))


def test_rect_tube_profile():
    m = MemberSpec(profile="rect-tube", size=50, size2=25, wall=2)
    expected_area = 50 * 25 - (50 - 4) * (25 - 4)
    assert section_area(m) == expected_area == 284.0
    assert profile_name(m) == "rect-tube 50x25x2"

    # Validation: size2 is required for rect-tube
    with pytest.raises(ValueError, match="requires size2"):
        validate_member(MemberSpec(profile="rect-tube", size=50, wall=2))

    # Frame with rect-tube members
    r = _frame(
        member={"profile": "rect-tube", "size": 50, "size2": 25, "wall": 2},
        bottom_rails=False,
    )
    shape = r.shape
    assert len(shape.solids()) == 1
    # Analytic volume = sum of true length members * 284 mm²
    expected_vol = sum(284.0 * m.length for m in r.features.members)
    assert abs(shape.volume - expected_vol) / expected_vol < 1e-3

    # Cut list exact
    cuts = {c.profile: (c.length, c.qty) for c in r.cut_list}
    assert "rect-tube 50x25x2" in cuts
    assert all(c.profile == "rect-tube 50x25x2" for c in r.cut_list)


def test_round_tube_profile():
    m = MemberSpec(profile="round-tube", size=30, wall=2)
    expected_area = math.pi * 2 * (30 - 2)
    assert abs(section_area(m) - expected_area) < 1e-9
    assert profile_name(m) == "round-tube 30x2"

    r = _frame(
        member={"profile": "round-tube", "size": 30, "wall": 2},
        bottom_rails=False,
    )
    shape = r.shape
    assert len(shape.solids()) == 1
    expected_vol = sum(expected_area * m.length for m in r.features.members)
    assert abs(shape.volume - expected_vol) / expected_vol < 1e-3
    assert r.cut_list[0].profile == "round-tube 30x2"


def test_t_slot_profile():
    m = MemberSpec(profile="t-slot", size=40, slot_width=8, slot_depth=6)
    expected_area = 40 * 40 - 4 * 8 * 6
    assert section_area(m) == expected_area == 1408.0
    assert profile_name(m) == "t-slot 40x40"

    # Validation: missing slot_width/depth
    with pytest.raises(ValueError, match="requires slot_width and slot_depth"):
        validate_member(MemberSpec(profile="t-slot", size=40))

    # Validation: slot_width >= size
    with pytest.raises(ValueError, match="slot_width"):
        validate_member(MemberSpec(profile="t-slot", size=40, slot_width=40, slot_depth=5))

    # Process extrusion-cut
    r = _frame(
        member={"profile": "t-slot", "size": 40, "slot_width": 8, "slot_depth": 6},
        bottom_rails=False,
        process="extrusion-cut",
    )
    assert r.features.process == "extrusion-cut"
    shape = r.shape
    assert len(shape.solids()) == 1
    expected_vol = sum(expected_area * m.length for m in r.features.members)
    assert abs(shape.volume - expected_vol) / expected_vol < 1e-3
    assert all(c.profile == "t-slot 40x40" for c in r.cut_list)


def test_rail_member_and_apron_offset_top():
    # Table benchmark configuration:
    # Legs: 50x50x2 square tube, rails: 50x25x2 rect-tube, recessed apron top offset 10 mm
    r = _frame(
        length=1200,
        width=800,
        height=750,
        member={"profile": "square-tube", "size": 50, "wall": 2},
        rail_member={"profile": "rect-tube", "size": 50, "size2": 25, "wall": 2},
        top_rails=True,
        bottom_rails=False,
        apron_offset_top=10,
    )
    shape = r.shape
    assert len(shape.solids()) == 1
    # Bounding box height still reaches full 750 mm (legs reach full height)
    bb = shape.bounding_box().size
    assert abs(bb.Z - 750) < 1e-3
    assert abs(bb.X - 1200) < 1e-3
    assert abs(bb.Y - 800) < 1e-3

    # Cut list has separate groups for legs and rails
    leg_cut = [c for c in r.cut_list if c.profile == "square-tube 50x50x2"]
    rail_cut = [c for c in r.cut_list if c.profile == "rect-tube 50x25x2"]
    assert len(leg_cut) == 1 and leg_cut[0].qty == 4 and leg_cut[0].length == 750.0
    assert sum(c.qty for c in rail_cut) == 4

    # Analytic volume matches
    leg_area = 50 * 50 - 46 * 46
    rail_area = 50 * 25 - 46 * 21
    expected_vol = 4 * 750.0 * leg_area + sum(c.qty * c.length * rail_area for c in rail_cut)
    assert abs(shape.volume - expected_vol) / expected_vol < 1e-3
    assert r.features.extra["apron_offset_top"] == 10.0


def test_mounting_tabs():
    # 8 flat mounting tabs inside the top apron rails
    # Frame length 1200 (hx=600), width 800 (hy=400), height 750
    # Rails: 50x25x2 (rail width into table = 25 mm).
    # Back rail inside face: y = 400 - 25 = 375. Front rail inside face: y = -375.
    # Right rail inside face: x = 600 - 25 = 575. Left rail inside face: x = -575.
    # Tabs: width across rail = 40 mm, length along rail = 50 mm, thickness = 4 mm.
    # For back rail: tab center y = 375 - 20 = 355.
    # For front rail: tab center y = -355.
    # For right rail: tab center x = 575 - 20 = 555.
    # For left rail: tab center x = -555.
    def _tab(x: float, y: float, rail: str) -> dict[str, object]:
        return {
            "x": x,
            "y": y,
            "width": 40,
            "length": 50,
            "thickness": 4,
            "slot_length": 20,
            "slot_width": 8,
            "rail": rail,
        }

    tabs = [
        # 4 tabs on X rails (2 front, 2 back)
        _tab(-250, 355, "x"),
        _tab(250, 355, "x"),
        _tab(-250, -355, "x"),
        _tab(250, -355, "x"),
        # 4 tabs on Y rails (2 left, 2 right)
        _tab(555, -100, "y"),
        _tab(555, 100, "y"),
        _tab(-555, -100, "y"),
        _tab(-555, 100, "y"),
    ]

    r = _frame(
        length=1200,
        width=800,
        height=750,
        member={"profile": "square-tube", "size": 50, "wall": 2},
        rail_member={"profile": "rect-tube", "size": 50, "size2": 25, "wall": 2},
        top_rails=True,
        bottom_rails=False,
        mounting_tabs=tabs,
    )
    shape = r.shape
    assert len(shape.solids()) == 1

    # Props and notes list each tab
    assert r.props["tab_count"] == 8
    assert len(r.props["mounting_tabs"]) == 8
    first_tab = r.props["mounting_tabs"][0]
    assert first_tab["center"] == (-250, 355, 750)
    assert first_tab["slot_length"] == 20.0
    assert first_tab["slot_width"] == 8.0
    assert len(r.notes) == 8

    # Analytic volume includes members plus tabs minus slots
    leg_area = 50 * 50 - 46 * 46
    rail_area = 50 * 25 - 46 * 21
    slot_area = (20.0 - 8.0) * 8.0 + math.pi * 4.0**2
    tab_vol = (40.0 * 50.0 - slot_area) * 4.0
    members_vol = 4 * 750.0 * leg_area + 2 * (1200 - 100) * rail_area + 2 * (800 - 100) * rail_area
    expected_total = members_vol + 8 * tab_vol
    assert abs(shape.volume - expected_total) / expected_total < 1e-3
    assert abs(r.props["material_volume"] - expected_total) / expected_total < 1e-3


def test_unchanged_defaults_volume_equality():
    # Build with default parameters before and after
    r1 = _frame()
    r2 = _frame(rail_member=None, apron_offset_top=0, mounting_tabs=[])
    assert abs(r1.shape.volume - r2.shape.volume) < 1e-9
    assert r1.props["material_volume"] == r2.props["material_volume"]
    assert len(r1.features.members) == len(r2.features.members) == 12


def test_validation_errors():
    # slot_length < slot_width
    with pytest.raises(ValueError, match="slot_length.*must be >= slot_width"):
        _frame(
            mounting_tabs=[
                {
                    "x": 0,
                    "y": 100,
                    "width": 40,
                    "length": 40,
                    "thickness": 3,
                    "slot_length": 5,
                    "slot_width": 10,
                }
            ]
        )

    # slot_length > width
    with pytest.raises(ValueError, match="must not exceed tab width"):
        _frame(
            mounting_tabs=[
                {
                    "x": 0,
                    "y": 100,
                    "width": 20,
                    "length": 40,
                    "thickness": 3,
                    "slot_length": 25,
                    "slot_width": 10,
                }
            ]
        )

    # slot_width > length
    with pytest.raises(ValueError, match="must not exceed tab length"):
        _frame(
            mounting_tabs=[
                {
                    "x": 0,
                    "y": 100,
                    "width": 40,
                    "length": 15,
                    "thickness": 3,
                    "slot_length": 20,
                    "slot_width": 18,
                }
            ]
        )

    # negative apron_offset_top
    with pytest.raises(ValueError, match="apron_offset_top must not be negative"):
        _frame(apron_offset_top=-5)

    # overhang combined with apron_offset_top
    with pytest.raises(ValueError, match="overhang cannot be combined with apron_offset_top"):
        _frame(overhang=10, apron_offset_top=10)
