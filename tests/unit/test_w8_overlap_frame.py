"""S-343 (B-0323): the overlap screen tests a frame kit's members one by one."""

from __future__ import annotations

import copy
from typing import Any

from napkin2factory.concepts.massing import compose
from napkin2factory.concepts.screening import screen
from napkin2factory.core.model import ConceptCard

BASE_FRAME_CARD: dict[str, Any] = {
    "id": "C-001",
    "title": "Frame stand",
    "site": {"point_load": "1000 N"},
    "massing": [
        {
            "kit": "frame",
            "as": "stand",
            "material": "mild steel",
            "args": {
                "length": "1000 mm",
                "width": "600 mm",
                "height": "700 mm",
                "member": {"profile": "square-tube", "size": "40 mm", "wall": "2 mm"},
                "top_rails": True,
                "bottom_rails": True,
            },
            "at": {"x": "0 mm", "y": "0 mm", "z": "0 mm"},
        },
    ],
}


def _card(**changes: Any) -> ConceptCard:
    """A card modified from ``BASE_FRAME_CARD``."""
    data = copy.deepcopy(BASE_FRAME_CARD)
    for k, v in changes.items():
        data[k] = v
    return ConceptCard.model_validate(data)


def test_plate_through_frame_member_fails() -> None:
    """A plate penetrating a leg fails, naming the frame and the member (B-0323)."""
    shelf = {
        "kit": "plate",
        "as": "shelf",
        "material": "mild steel",
        "args": {"width": "200 mm", "depth": "200 mm", "thickness": "10 mm"},
        "at": {"x": "480 mm", "y": "280 mm", "z": "350 mm"},
    }
    card = _card(massing=[*BASE_FRAME_CARD["massing"], shelf])
    m = compose(card, write=False)
    s = screen(card, m)
    row = s.rule("rough-shapes-overlap")
    assert row is not None
    assert row.status == "fail"
    assert "stand's leg-1" in row.message
    assert "shelf" in row.message
    assert "cm³" in row.message
    assert "meet face to face, or make one shorter" in row.message


def test_plate_in_open_space_passes() -> None:
    """The same plate inside the frame's open volume between members passes (B-0323)."""
    shelf = {
        "kit": "plate",
        "as": "shelf",
        "material": "mild steel",
        "args": {"width": "200 mm", "depth": "200 mm", "thickness": "10 mm"},
        "at": {"x": "0 mm", "y": "0 mm", "z": "350 mm"},
    }
    card = _card(massing=[*BASE_FRAME_CARD["massing"], shelf])
    m = compose(card, write=False)
    s = screen(card, m)
    assert s.rule("rough-shapes-overlap") is None


def test_block_resting_on_top_of_frame_passes() -> None:
    """A block resting on top of the frame touches face to face without overlapping (B-0323)."""
    top = {
        "kit": "block",
        "as": "top",
        "material": "white-oak",
        "args": {"length": "1000 mm", "width": "600 mm", "height": "30 mm"},
        "at": {"x": "0 mm", "y": "0 mm", "z": "700 mm"},
    }
    card = _card(massing=[*BASE_FRAME_CARD["massing"], top])
    m = compose(card, write=False)
    s = screen(card, m)
    assert s.rule("rough-shapes-overlap") is None


def test_two_frames_overlapping_compare_member_boxes() -> None:
    """Two frames compare member boxes with member boxes and report the overlap (B-0323)."""
    stand2 = copy.deepcopy(BASE_FRAME_CARD["massing"][0])
    stand2["as"] = "stand2"
    stand2["at"] = {"x": "20 mm", "y": "0 mm", "z": "0 mm"}
    card = _card(massing=[*BASE_FRAME_CARD["massing"], stand2])
    m = compose(card, write=False)
    s = screen(card, m)
    row = s.rule("rough-shapes-overlap")
    assert row is not None
    assert row.status == "fail"
    assert "stand's" in row.message
    assert "stand2's" in row.message
