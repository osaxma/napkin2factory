"""M2 (v0.2): the massing composer — card kit calls → placed silhouettes and artifacts (N1, N3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from napkin2factory.concepts.massing import compose, concept_build_dir
from napkin2factory.core.errors import N2FError
from napkin2factory.core.model import ConceptCard
from napkin2factory.geometry.glb import read_glb_summary
from napkin2factory.geometry.kit import KitError
from napkin2factory.geometry.render import image_variance

BODY: dict[str, Any] = {
    "kit": "enclosure",
    "as": "body",
    "material": "mild steel",
    "args": {"length": "400 mm", "width": "300 mm", "height": "200 mm", "thickness": "1.5 mm"},
}
LID: dict[str, Any] = {
    "kit": "plate",
    "as": "lid",
    "args": {"width": "400 mm", "depth": "300 mm", "thickness": "2 mm"},
    "at": {"z": "200 mm"},
}


def _card(massing: list[dict[str, Any]], **extra: Any) -> ConceptCard:
    return ConceptCard.model_validate({"id": "C-004", "title": "t", "massing": massing, **extra})


def test_two_call_card_composes_and_writes_artifacts(tmp_path: Path) -> None:
    result = compose(_card([BODY, LID]), tmp_path)
    out = concept_build_dir(tmp_path, "C-004")
    assert out == tmp_path / "build" / "concepts" / "C-004"

    glb = read_glb_summary((out / "massing.glb").read_bytes())
    assert {"concept://C-004/body", "concept://C-004/lid"} <= set(glb["nodes"])
    assert {"concept://C-004/body", "concept://C-004/lid"} <= set(glb["meshes"])

    # props bbox is the union of the two placed silhouettes
    props = json.loads((out / "props.json").read_text())
    assert props["bbox"]["min"] == pytest.approx([-200, -150, 0], abs=1e-3)
    assert props["bbox"]["max"] == pytest.approx([200, 150, 202], abs=1e-3)
    assert result.size == pytest.approx((400, 300, 202), abs=1e-3)
    assert props["fidelity"] == "massing" and props["concept"] == "C-004"
    # the lid declares no material: no mass anywhere, and the reason is named
    assert "mass" not in props and props["mass_missing"] == ["lid"]
    assert result.mass is None and result.without_material == ["lid"]
    assert props["pieces"]["body"]["process_class"] == "sheet-metal"
    assert props["pieces"]["lid"]["process_class"] == "cut-sheet"

    feats = json.loads((out / "features.json").read_text())
    assert [f["as"] for f in feats] == ["body", "lid"]
    assert all(f["fidelity"] == "massing" for f in feats)
    assert all(f["features"]["extra"]["fidelity"] == "massing" for f in feats)

    for view in ("iso", "front"):
        img = np.asarray(Image.open(out / "renders" / f"{view}.png"))
        assert image_variance(img) > 100, view


def test_mass_when_every_call_declares_a_material() -> None:
    lid = {**LID, "material": "aluminium"}
    result = compose(_card([BODY, lid]), write=False)
    body, plate = result.pieces
    assert plate.mass == pytest.approx(400 * 300 * 2 * 1e-9 * 2700)
    assert result.mass == pytest.approx((body.mass or 0) + (plate.mass or 0))
    assert result.props["mass"] == pytest.approx(result.mass, rel=1e-6)


def test_placement_rotates_and_moves() -> None:
    bar = {
        "kit": "block",
        "as": "bar",
        "args": {"length": "100 mm", "width": "20 mm", "height": "10 mm"},
        "at": {"x": "50 mm", "rz": "90 deg"},
    }
    (piece,) = compose(_card([bar]), write=False).pieces
    assert piece.size == pytest.approx((20, 100, 10), abs=1e-3)
    assert piece.bbox_min[0] == pytest.approx(40, abs=1e-3)
    assert piece.process_class == "cut-block"


def test_model_references_are_refused_with_the_card_id() -> None:
    body = {**BODY, "args": {**BODY["args"], "length": "param://chamber-width"}}
    with pytest.raises(N2FError, match=r"C-004/body: args\.length is 'param://chamber-width'"):
        compose(_card([body]), write=False)
    lid = {**LID, "at": {"z": "param://lid-height"}}
    with pytest.raises(N2FError, match="C-004/lid: at.z"):
        compose(_card([lid]), write=False)


def test_impossible_composition_fails_for_real() -> None:
    body = {**BODY, "args": {**BODY["args"], "thickness": "150 mm"}}
    with pytest.raises(KitError) as info:
        compose(_card([body]), write=False)
    assert str(info.value).startswith("C-004/body:")
    unknown = {**BODY, "kit": "blob"}
    with pytest.raises(KitError, match="C-004/body: unknown kit generator 'blob'"):
        compose(_card([unknown]), write=False)


@pytest.mark.parametrize(
    ("massing", "match"),
    [
        ([], "C-004 has no massing yet"),
        ([BODY, {**LID, "as": "body"}], "two massing calls are named 'body'"),
        ([{**LID, "at": {"q": "1 mm"}}], "C-004/lid: at: has q"),
        ([{**LID, "at": {"x": "5 kg"}}], "C-004/lid: at.x = '5 kg' is not a mm quantity"),
    ],
)
def test_bad_cards_are_actionable(massing: list[dict[str, Any]], match: str) -> None:
    with pytest.raises(N2FError, match=match):
        compose(_card(massing), write=False)


def test_write_needs_a_folder() -> None:
    with pytest.raises(N2FError, match="needs the product folder"):
        compose(_card([BODY]), None)
