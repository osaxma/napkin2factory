"""The recording accessor a domain's build code reads the model through (gate E B2, S-138)."""

from __future__ import annotations

import pytest

from napkin2factory.core.graph.recording import Recorded, unwrap
from napkin2factory.core.model.base import Model, PartUri
from napkin2factory.core.uris import Uri
from napkin2factory.geometry.accessors import ReadLog


class Spec(Model):
    """A nested object."""

    snap: str = "firm"
    depth: int = 3


class Thing(Model):
    """An object with a leaf, a URI, a nested object and a dict."""

    name: str
    part: PartUri
    spec: Spec = Spec()
    extra: dict[str, int] = {}

    @property
    def shout(self) -> str:
        """A computed property: reads ``name``."""
        return self.name.upper()


def _thing() -> Thing:
    return Thing(name="Widget", part=Uri.parse("part://plate"), extra={"a": 1})


def test_a_leaf_is_the_plain_value_and_one_read() -> None:
    log = ReadLog()
    t = Recorded(_thing(), "toy://widget", log)
    assert t.name == "Widget" and isinstance(t.name, str)
    assert str(t.part) == "part://plate"
    assert log.keys == ["toy://widget#name", "toy://widget#part"]


def test_a_nested_object_records_only_the_fields_read() -> None:
    log = ReadLog()
    t = Recorded(_thing(), "toy://widget", log)
    spec = t.spec
    assert log.keys == []  # not used yet
    assert spec.snap == "firm"
    assert t.extra["a"] == 1
    assert log.keys == ["toy://widget#spec.snap", "toy://widget#extra.a"]


def test_an_object_used_whole_records_its_path() -> None:
    log = ReadLog()
    t = Recorded(_thing(), "toy://widget", log)
    assert unwrap(t.spec) == Spec()
    assert t.spec == Spec() and bool(t.spec)
    assert log.keys == ["toy://widget#spec"]


def test_a_property_or_method_records_every_field() -> None:
    log = ReadLog()
    t = Recorded(_thing(), "toy://widget", log)
    assert t.shout == "WIDGET"
    assert log.keys == [f"toy://widget#{f}" for f in Thing.model_fields]
    log2 = ReadLog()
    assert Recorded(_thing(), "toy://widget", log2).spec.model_dump() == {
        "snap": "firm",
        "depth": 3,
    }
    assert log2.keys == ["toy://widget#spec"]


def test_a_missing_field_and_a_write_are_errors() -> None:
    t = Recorded(_thing(), "toy://widget", ReadLog())
    with pytest.raises(AttributeError):
        _ = t.nothing
    with pytest.raises(AttributeError, match="does not exist"):
        _ = t.extra.b
    with pytest.raises(AttributeError, match="read-only"):
        t.name = "x"
    assert repr(t.spec) == "<recorded toy://widget#spec>"
    assert unwrap(3) == 3
