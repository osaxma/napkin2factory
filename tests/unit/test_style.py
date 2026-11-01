"""M3 (v0.2): ``style.yaml`` schema, presets and resolution (N7)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from napkin2factory.core.errors import N2FError
from napkin2factory.core.model import ConceptCard, MassingCall, Part, StyleFile
from napkin2factory.core.model.style import (
    FINISHES,
    PRESETS,
    STYLE_ROLES,
    STYLED_ROLES,
    role_for,
)
from napkin2factory.core.style import (
    geometry_fingerprint,
    load_style,
    merge_card_style,
)
from napkin2factory.core.units import parse_quantity
from tests.conftest import n2f

VALID = {
    "preset": "appliance",
    "palette": {"body": "#F0EEE9", "controls": "#333333"},
    "finish": {"body": "painted", "trim": "brushed-steel"},
    "accent": "#e07a2e",
    "background": "#eeeeee",
    "radius_scale": 1.5,
    "reveal": "3 mm",
    "fastener_visibility": "hidden-front",
    "corner_radius": "6 mm",
    "overhang": "10 mm",
    "vent_pattern": "holes",
}


def test_a_valid_file_parses() -> None:
    s = StyleFile.model_validate(VALID)
    assert s.palette == {"body": "#f0eee9", "controls": "#333333"}  # normalised to lower case
    assert s.reveal == parse_quantity("3 mm") and s.vent_pattern == "holes"
    assert s.model_dump(mode="json")["corner_radius"] == "6 mm"


@pytest.mark.parametrize(
    "data, msg",
    [
        ({"palette": {"chassis": "#ffffff"}}, "chassis"),  # unknown role key
        ({"finish": {"body": "chrome"}}, "chrome"),  # unknown finish
        ({"finish": {"hinge": "painted"}}, "hinge"),
        ({"palette": {"body": "white"}}, "not a colour"),
        ({"background": "#ffff"}, "not a colour"),
        ({"corner_radius": "4 mm", "chamfer": "2 mm"}, "not both"),
        ({"reveal": "2 kg"}, "length"),
        ({"overhang": "-1 mm"}, "negative"),
        ({"vent_pattern": "louvres"}, "vent_pattern"),
        ({"preset": "baroque"}, "preset"),
        ({"radius_scale": 0}, "radius_scale"),
    ],
)
def test_bad_files_fail(data: dict[str, object], msg: str) -> None:
    with pytest.raises(ValidationError, match=msg):
        StyleFile.model_validate(data)


def test_resolved_fills_preset_values_where_the_file_is_silent() -> None:
    s = StyleFile.model_validate({"preset": "appliance", "palette": {"body": "#ffffff"}})
    r = s.resolved()
    assert r.radius_scale == 1.5 and r.fastener_visibility == "hidden-front"
    assert r.palette["body"] == "#ffffff"  # the file wins per role
    assert r.palette["controls"] == PRESETS["appliance"]["palette"]["controls"]
    assert r.finish["trim"] == "brushed-steel"
    # a value the file sets explicitly wins even when it equals the schema default
    assert StyleFile.model_validate({"preset": "appliance", "radius_scale": 1.0}).resolved() == (
        StyleFile.model_validate(
            {**PRESETS["appliance"], "radius_scale": 1.0, "preset": "appliance"}
        )
    )
    assert r.resolved() == r  # idempotent


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_each_preset_resolves_completely(preset: str) -> None:
    r = StyleFile.model_validate({"preset": preset}).resolved()
    assert set(r.palette) == set(STYLE_ROLES) and set(r.finish) == set(STYLE_ROLES)
    assert all(f in FINISHES for f in r.finish.values())
    for role in STYLE_ROLES:
        m = r.material(role)
        assert m["color"].startswith("#") and 0 <= m["metallic"] <= 1 and 0 <= m["roughness"] <= 1


def test_industrial_shape_cues_are_no_ops() -> None:
    """A product without style.yaml gets industrial: its geometry cues change nothing."""
    r = StyleFile().resolved()
    assert r.preset == "industrial" and r.radius_scale == 1.0
    for name in ("corner_radius", "chamfer", "overhang"):
        assert getattr(r, name).magnitude == 0


def test_role_for_and_opt_in_roles() -> None:
    # neutral role words; door and stand are read as opening and support (F9, F16)
    styled = {"body", "opening", "support", "controls", "trim"}
    assert STYLED_ROLES == styled | {"door", "stand"}
    assert role_for(MassingCall.model_validate({"kit": "block", "as": "door"})) == "opening"
    assert role_for(MassingCall.model_validate({"kit": "block", "as": "lid"})) == "default"
    call = MassingCall.model_validate({"kit": "block", "as": "lid", "role": "trim"})
    assert role_for(call) == "trim"
    part = Part.model_validate({"id": "outer-shell", "name": "Shell", "role": "body"})
    assert role_for(part) == "body"
    assert role_for(Part.model_validate({"id": "stand", "name": "Stand"})) == "support"
    assert role_for(Part.model_validate({"id": "brick", "name": "Brick"})) == "default"
    with pytest.raises(ValidationError):
        Part.model_validate({"id": "x", "name": "X", "role": "chassis"})


def test_load_style(tmp_path: Path) -> None:
    assert load_style(tmp_path) == StyleFile().resolved()  # no file: industrial defaults
    (tmp_path / "style.yaml").write_text("preset: lab\nreveal: 4 mm\n")
    s = load_style(tmp_path)
    assert s.preset == "lab" and s.reveal == parse_quantity("4 mm")
    assert geometry_fingerprint(s)["reveal"] == "4 mm"
    (tmp_path / "style.yaml").write_text("palette: {chassis: '#ffffff'}\n")
    with pytest.raises(N2FError, match=r"style.yaml: palette.chassis"):
        load_style(tmp_path)
    (tmp_path / "style.yaml").write_text("- a list\n")
    with pytest.raises(N2FError, match="mapping"):
        load_style(tmp_path)


def test_card_style_lays_over_the_product_style() -> None:
    product = StyleFile.model_validate({"preset": "industrial", "palette": {"body": "#111111"}})
    product = product.resolved()
    same, notes = merge_card_style(product, {"palette": {"door": "#222222"}, "flair": 1})
    assert same.palette["body"] == "#111111" and same.palette["opening"] == "#222222"
    assert notes == ["card style keys not used: flair"]
    other, _ = merge_card_style(product, {"preset": "appliance", "corner_radius": "8 mm"})
    assert other.palette["body"] == PRESETS["appliance"]["palette"]["body"]
    assert other.corner_radius == parse_quantity("8 mm")
    kept, notes = merge_card_style(product, {"palette": {"body": "beige"}})
    assert kept == product and "card style not used" in notes[0]
    card = ConceptCard.model_validate({"id": "C-001", "title": "t"})
    assert merge_card_style(product, card.style) == (product, [])


def test_init_style_appliance_writes_a_parsing_file(tmp_path: Path) -> None:
    dest = tmp_path / "fresh"
    r = n2f("init", str(dest), "--template", "blank", "--style", "appliance", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    text = (dest / "style.yaml").read_text()
    assert text.startswith("# style.yaml") and "preset: appliance" in text
    s = StyleFile.model_validate(yaml.safe_load(text))
    assert s == StyleFile.model_validate({"preset": "appliance"}).resolved()
    bad = n2f("init", str(tmp_path / "other"), "--style", "baroque", cwd=tmp_path)
    assert bad.returncode != 0 and "industrial | appliance | lab" in bad.stderr
    assert not (tmp_path / "other").exists()
