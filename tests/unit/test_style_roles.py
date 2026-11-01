"""v0.5 M3 (F6, F9, S-128): the style roles are a table of neutral words with two aliases."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from napkin2factory.core.model import Part
from napkin2factory.core.model.style import (
    PRESETS,
    ROLE_ALIASES,
    STYLE_ROLES,
    StyleFile,
    canonical_role,
    role_for,
)
from napkin2factory.core.style import load_style
from tests.conftest import EXAMPLES


def test_the_roles_are_neutral_words_from_the_table() -> None:
    assert STYLE_ROLES == (
        "body", "opening", "support", "controls", "trim", "lining", "fastener", "default",
    )  # fmt: skip
    assert ROLE_ALIASES == {"door": "opening", "stand": "support"}
    assert canonical_role("door") == "opening" and canonical_role("trim") == "trim"
    for preset in PRESETS.values():
        assert set(preset["palette"]) == set(STYLE_ROLES) == set(preset["finish"])


def test_an_alias_is_kept_as_written_and_read_as_its_role() -> None:
    part = Part.model_validate({"id": "front", "name": "Front", "role": "door"})
    assert part.role == "door"  # the part file and its hash do not move (F16)
    assert role_for(part) == "opening"
    with pytest.raises(ValidationError, match="opening"):  # the error lists the known roles
        Part.model_validate({"id": "x", "name": "X", "role": "hatch"})


def test_the_kilns_style_reads_its_old_keys_as_the_new_roles() -> None:
    style = load_style(EXAMPLES / "kiln")
    raw = (EXAMPLES / "kiln" / "style.yaml").read_text()
    assert "  door: '#e6e3dc'" in raw and "  stand: '#3a3e42'" in raw
    assert style.colour("opening") == "#e6e3dc" and style.colour("support") == "#3a3e42"


def test_a_style_file_may_use_both_words(tmp_path: Path) -> None:
    s = StyleFile.model_validate({"palette": {"stand": "#010101"}, "finish": {"door": "plastic"}})
    r = s.resolved()
    assert r.palette["support"] == "#010101" and r.finish["opening"] == "plastic"
    assert "stand" not in r.palette and "door" not in r.finish
