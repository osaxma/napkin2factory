"""interfaces/<id>.yaml schema (decision D16): a named frame plus a feature pattern."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from napkin2factory.core.model.base import ChildUri, Model, PartUri, Quantity, Slug


class Frame(Model):
    """Origin and normal of the interface plane, in the first party's coordinates."""

    origin: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    normal: list[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0])
    x_axis: list[float] | None = None

    @model_validator(mode="after")
    def _three(self) -> Frame:
        if len(self.origin) != 3 or len(self.normal) != 3:
            raise ValueError("frame origin and normal are [x, y, z]")
        return self


class BoltPatternSpec(Model):
    """A rectangular or circular bolt pattern."""

    pattern: Literal["rect", "circle", "line"] = "rect"
    count: int = 4
    diameter: Quantity
    spacing: list[Quantity] | None = None  # rect: [dx, dy]; line: [pitch]
    pitch_circle: Quantity | None = None  # circle
    fastener: PartUri | None = None


class MatingFaceSpec(Model):
    """Two flat faces that are expected to touch (allowed contact, D29)."""

    width: Quantity
    depth: Quantity
    flatness_note: str | None = None


class Interface(Model):
    """A contract both parties' generators consume (D16)."""

    id: Slug
    kind: Literal["bolt-pattern", "mating-face"]
    parties: list[ChildUri]
    frame: Frame = Field(default_factory=Frame)
    spec: BoltPatternSpec | MatingFaceSpec
    description: str | None = None

    @model_validator(mode="after")
    def _kind_spec(self) -> Interface:
        if len(self.parties) != 2:
            raise ValueError("an interface has exactly two parties")
        if self.kind == "bolt-pattern" and not isinstance(self.spec, BoltPatternSpec):
            raise ValueError("bolt-pattern spec needs count, diameter, spacing")
        if self.kind == "mating-face" and not isinstance(self.spec, MatingFaceSpec):
            raise ValueError("mating-face spec needs width and depth")
        return self

    @property
    def uri(self) -> str:
        """``iface://<id>``."""
        return f"iface://{self.id}"
