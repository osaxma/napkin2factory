"""The fast safe loader reads what the pure-Python one reads (S-295, M7)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from napkin2factory.core.yamlio import read_yaml, safe_load


def test_fast_loader_matches_the_pure_python_loader(tmp_path: Path) -> None:
    text = "a: 1\nb: [1, 2.5, x]\nc: {d: null, e: 'q'}\nf: 2026-01-02\n# note\n"
    assert safe_load(text) == yaml.safe_load(text)
    path = tmp_path / "x.yaml"
    path.write_text(text, encoding="utf-8")
    assert read_yaml(path) == yaml.safe_load(text)


def test_empty_file_is_an_empty_mapping(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert read_yaml(path) == {}


def test_bad_yaml_raises_a_yaml_error() -> None:
    with pytest.raises(yaml.YAMLError):
        safe_load("a: [1, 2\nb: }")


def test_unsafe_tags_are_refused() -> None:
    with pytest.raises(yaml.YAMLError):
        safe_load("a: !!python/object/apply:os.system ['true']")
