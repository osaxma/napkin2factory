"""interfaces/<id>.yaml schema (decision D16): a named frame plus a feature pattern."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

from napkin2factory.core.expr import check_syntax, referenced_names
from napkin2factory.core.model.base import ChildUri, Model, PartUri, QuantityOrParam, Slug


class FrameExpr(Model):
    """A frame coordinate or an offset written as an expression over parameter slugs (P2).

    ``{expr: "guard-gap + guard-thickness", unit: mm}`` is evaluated exactly like a parameter
    ``expr`` (same grammar, result converted to ``unit``) when the interface is read through
    ``I``; every slug it names is a recorded read (D5).  It replaces helper parameters that
    existed only to write a frame coordinate (S-106).
    """

    expr: str
    unit: str = "mm"

    @field_validator("expr")
    @classmethod
    def _syntax(cls, v: str) -> str:
        check_syntax(v)
        return v

    @property
    def slugs(self) -> list[str]:
        """Parameter slugs the expression names, in order of first appearance."""
        return referenced_names(self.expr)


def _coord(v: Any) -> Any:
    """A frame coordinate or offset: mm as a number, a quantity, ``param://`` or an expression."""
    if isinstance(v, bool):
        raise ValueError("a coordinate cannot be a boolean")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        from napkin2factory.core.model.base import _to_quantity_or_param

        return _to_quantity_or_param(v)
    if isinstance(v, dict):
        return FrameExpr.model_validate(v)
    return v


def _ser_coord(x: Any) -> Any:
    from napkin2factory.core.units import format_quantity, is_quantity

    if isinstance(x, FrameExpr):
        return x.model_dump()
    if is_quantity(x):
        return format_quantity(x)
    return x if isinstance(x, (int, float)) else str(x)


class Frame(Model):
    """Origin, normal and x axis of the interface plane, in the party's coordinates (mm).

    Coordinates may be numbers (mm), quantity strings, ``param://`` references (S-014) or
    ``{expr, unit}`` expressions (P2); all are resolved when the interface is read through
    ``I``.  ``place_by`` needs ``x_axis`` on every frame it uses (P1).
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
        return [_ser_coord(x) for x in v]

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
    # P2: signed distance along the normal from the first party's frame origin to the
    # second's, once both are placed (mm, a quantity, a param:// or an {expr, unit}).
    offset: Any = 0.0
    spec: BoltPatternSpec | MatingFaceSpec
    description: str | None = None

    @field_validator("offset", mode="before")
    @classmethod
    def _offset(cls, v: Any) -> Any:
        return _coord(v)

    @field_serializer("offset")
    def _ser_offset(self, v: Any) -> Any:
        return _ser_coord(v)

    @model_serializer(mode="wrap")
    def _drop_zero_offset(self, handler: SerializerFunctionWrapHandler) -> Any:
        # P14: an interface without an offset dumps (and so hashes) exactly as in v0.3, so
        # sign-off evidence keys on it stay valid across the upgrade (S-106).
        data = handler(self)
        if isinstance(data, dict) and data.get("offset") in (0, 0.0):
            data.pop("offset")
        return data

    def frame_for(self, party_uri: str) -> Frame:
        """The frame in ``party_uri``'s own coordinates (falls back to ``frame``)."""
        return self.frames.get(party_uri, self.frame)

    def expressions(self) -> list[FrameExpr]:
        """Every ``{expr, unit}`` in the frames and the offset (for validation and impact)."""
        out = [c for f in (self.frame, *self.frames.values()) for c in f.origin]
        out.append(self.offset)
        return [c for c in out if isinstance(c, FrameExpr)]

    def expression_slugs(self) -> list[str]:
        """Parameter slugs named inside the interface's expressions (P2), deduplicated."""
        seen: dict[str, None] = {}
        for e in self.expressions():
            for s in e.slugs:
                seen.setdefault(s, None)
        return list(seen)

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
