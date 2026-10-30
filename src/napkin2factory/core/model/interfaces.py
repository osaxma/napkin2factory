"""interfaces/<id>.yaml schema (decision D16): a named frame plus a feature pattern."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from napkin2factory.core.model.base import ChildUri, Model, PartUri, QuantityOrParam, Slug


def _coord(v: Any) -> Any:
    """A frame coordinate: millimetres as a number, a quantity string, or a ``param://``."""
    if isinstance(v, bool):
        raise ValueError("a coordinate cannot be a boolean")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        from napkin2factory.core.model.base import _to_quantity_or_param

        return _to_quantity_or_param(v)
    return v


class Frame(Model):
    """Origin and normal of the interface plane, in the party's coordinates (mm).

    Coordinates may be numbers (mm), quantity strings or ``param://`` references; the
    latter are resolved when the interface is read through ``I`` (S-014).
    """

    origin: list[Any] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    normal: list[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0])
    x_axis: list[float] | None = None

    @field_validator("origin", mode="before")
    @classmethod
    def _origin(cls, v: Any) -> Any:
        return [_coord(x) for x in v] if isinstance(v, list) else v

    @field_serializer("origin")
    def _ser_origin(self, v: list[Any]) -> list[Any]:
        from napkin2factory.core.units import format_quantity, is_quantity

        return [
            format_quantity(x)
            if is_quantity(x)
            else (str(x) if not isinstance(x, (int, float)) else x)
            for x in v
        ]

    @model_validator(mode="after")
    def _three(self) -> Frame:
        if len(self.origin) != 3 or len(self.normal) != 3:
            raise ValueError("frame origin and normal are [x, y, z]")
        return self


class BoltPatternSpec(Model):
    """A rectangular or circular bolt pattern.

    The build cuts this pattern into every party automatically (S-013): holes along the
    frame normal, reaching ``depth`` on each side of the frame plane (default 10 mm, enough
    for a sheet or a lip without piercing the far wall of a box).
    """

    pattern: Literal["rect", "circle", "line"] = "rect"
    count: int = 4
    diameter: QuantityOrParam
    spacing: list[QuantityOrParam] | None = None  # rect: [dx, dy]; line: [pitch]
    pitch_circle: QuantityOrParam | None = None  # circle
    fastener: PartUri | None = None
    depth: QuantityOrParam = "10 mm"


class MatingFaceSpec(Model):
    """Two flat faces that are expected to touch (allowed contact, D29)."""

    width: QuantityOrParam
    depth: QuantityOrParam
    flatness_note: str | None = None


class Interface(Model):
    """A contract both parties' generators consume (D16)."""

    id: Slug
    kind: Literal["bolt-pattern", "mating-face"]
    parties: list[ChildUri]
    frame: Frame = Field(default_factory=Frame)
    frames: dict[str, Frame] = Field(default_factory=dict)  # per party, in its own coordinates
    spec: BoltPatternSpec | MatingFaceSpec
    description: str | None = None

    def frame_for(self, party_uri: str) -> Frame:
        """The frame in ``party_uri``'s own coordinates (falls back to ``frame``)."""
        return self.frames.get(party_uri, self.frame)

    @model_validator(mode="before")
    @classmethod
    def _spec_by_kind(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("spec"), dict):
            kind = data.get("kind")
            if kind == "bolt-pattern":
                data = {**data, "spec": BoltPatternSpec.model_validate(data["spec"])}
            elif kind == "mating-face":
                data = {**data, "spec": MatingFaceSpec.model_validate(data["spec"])}
        return data

    @model_validator(mode="after")
    def _kind_spec(self) -> Interface:
        if len(self.parties) != 2:
            raise ValueError("an interface has exactly two parties")
        if self.kind == "bolt-pattern" and not isinstance(self.spec, BoltPatternSpec):
            raise ValueError("bolt-pattern spec needs count, diameter, spacing")
        if self.kind == "mating-face" and not isinstance(self.spec, MatingFaceSpec):
            raise ValueError("mating-face spec needs width and depth")
        party_strs = {str(p) for p in self.parties}
        for key in self.frames:
            if key not in party_strs:
                raise ValueError(
                    f"frames key {key!r} is not one of the parties {sorted(party_strs)}"
                )
        return self

    @property
    def uri(self) -> str:
        """``iface://<id>``."""
        return f"iface://{self.id}"
