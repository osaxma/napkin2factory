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
from napkin2factory.core.model.base import (
    AsmUri,
    ChildUri,
    Model,
    PartUri,
    QuantityOrParam,
    Slug,
)


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


class HardwareItem(Model):
    """One kind of loose hardware a joint takes (P9): ``per_hole`` or ``per_joint``, not both.

    ``{part: part://m6x16-bolt, per_hole: 2}`` is two bolts in every hole of the pattern;
    ``{part: part://gasket, per_joint: 1}`` is one per occurrence of the joint, holes or not
    (the only form a mating face takes, having no holes).
    """

    part: PartUri
    per_hole: int | None = None
    per_joint: int | None = None

    @model_validator(mode="after")
    def _one_count(self) -> HardwareItem:
        if (self.per_hole is None) == (self.per_joint is None):
            raise ValueError(
                f"hardware {self.part}: give exactly one of per_hole (items in every hole) "
                "or per_joint (items per joint)"
            )
        n = self.per_hole if self.per_hole is not None else self.per_joint
        if n is not None and n < 1:
            raise ValueError(f"hardware {self.part}: the count must be at least 1")
        return self

    @model_serializer(mode="wrap")
    def _dump(self, handler: SerializerFunctionWrapHandler) -> Any:
        data = handler(self)
        if isinstance(data, dict):
            for key in ("per_hole", "per_joint"):
                if data.get(key) is None:
                    data.pop(key, None)
        return data


def _drop_unset_hardware(data: Any) -> Any:
    # P14: a spec without `hardware:` dumps (and so hashes, for sign-off evidence keys)
    # exactly as in v0.3; an explicit `hardware: []` is kept, it says "nothing here".
    if isinstance(data, dict) and data.get("hardware") is None:
        data.pop("hardware", None)
    return data


class BoltPatternSpec(Model):
    """A rectangular or circular bolt pattern.

    The build cuts this pattern into every party automatically (S-013): holes along the
    frame normal, reaching ``depth`` on each side of the frame plane (default 10 mm, enough
    for a sheet or a lip without piercing the far wall of a box).

    ``hardware`` lists everything one hole takes (P9); without it, ``fastener: X`` reads as
    ``[{part: X, per_hole: 1}]``.  Where two interfaces share holes (S-051), each item is
    listed once, on the interface whose joint it is fitted to close (S-105).
    """

    pattern: Literal["rect", "circle", "line"] = "rect"
    count: int = 4
    diameter: QuantityOrParam
    spacing: list[QuantityOrParam] | None = None  # rect: [dx, dy]; line: [pitch]
    pitch_circle: QuantityOrParam | None = None  # circle
    fastener: PartUri | None = None
    depth: QuantityOrParam = "10 mm"
    hardware: list[HardwareItem] | None = None

    @model_serializer(mode="wrap")
    def _dump(self, handler: SerializerFunctionWrapHandler) -> Any:
        return _drop_unset_hardware(handler(self))

    def hardware_items(self) -> list[HardwareItem]:
        """The hardware one joint takes: ``hardware``, else the ``fastener`` alias (P9)."""
        if self.hardware is not None:
            return list(self.hardware)
        if self.fastener is not None:
            return [HardwareItem(part=self.fastener, per_hole=1)]
        return []


class MatingFaceSpec(Model):
    """Two flat faces that are expected to touch (allowed contact, D29).

    A mating face has no holes, so its ``hardware`` (rivets, adhesive, a gasket) is counted
    ``per_joint`` only; a welded joint lists none.
    """

    width: QuantityOrParam
    depth: QuantityOrParam
    flatness_note: str | None = None
    hardware: list[HardwareItem] | None = None

    @field_validator("hardware")
    @classmethod
    def _no_holes(cls, v: list[HardwareItem] | None) -> list[HardwareItem] | None:
        for item in v or []:
            if item.per_hole is not None:
                raise ValueError(
                    f"hardware {item.part}: a mating face has no holes; count it per_joint"
                )
        return v

    @model_serializer(mode="wrap")
    def _dump(self, handler: SerializerFunctionWrapHandler) -> Any:
        return _drop_unset_hardware(handler(self))

    def hardware_items(self) -> list[HardwareItem]:
        """The hardware one joint takes (P9)."""
        return list(self.hardware or [])


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
    # S-118 (gate D): the joint's short name in owner words ("Shell to guard, top wall"),
    # where the two parts' names alone cannot tell two joints apart; optional, the build
    # plan, the sheets and the check messages fall back to "<part> to <part>".
    name: str | None = None
    # S-118: the build step that closes the joint when it is later than the step where its
    # parts first meet (a lid screwed on after the wiring of the final assembly). The joint
    # and its hardware stay listed where the parts meet, marked "closed later, in step N".
    closed_in: AsmUri | None = None

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
        if isinstance(data, dict):
            # S-118: the optional fields of v0.4's gate D dump only when set, so an interface
            # without them hashes as before and no sign-off evidence on it goes stale
            for key in ("name", "closed_in"):
                if data.get(key) is None:
                    data.pop(key, None)
        return data

    @property
    def holes(self) -> int:
        """Holes in one occurrence of the joint: the pattern's count, none for a mating face."""
        return self.spec.count if isinstance(self.spec, BoltPatternSpec) else 0

    def hardware_items(self) -> list[HardwareItem]:
        """The hardware one occurrence of the joint takes, ``fastener`` alias applied (P9)."""
        return self.spec.hardware_items()

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
