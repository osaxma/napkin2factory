"""concepts/C-xxx.yaml schema (NAPKIN_STAGE §3, decision N1).

A concept card is a cheap, disposable direction for the product: a title, rough layout,
envelope numbers, site constraints, a style sketch and a massing made of kit calls.  Cards
live outside the build graph: no build rule reads them and ``n2f validate`` ignores them.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any, Literal

from pydantic import (
    BeforeValidator,
    Field,
    PlainSerializer,
    SerializerFunctionWrapHandler,
    WithJsonSchema,
    model_serializer,
)

from napkin2factory.core.model.base import Model, _id, _to_quantity
from napkin2factory.core.units import UnitError, format_quantity, parse_quantity

ConceptId = Annotated[str, _id(r"C-\d{3}")]
ConceptStatus = Literal["exploring", "rejected", "promoted"]
#: Every status word a card can carry, in display order.
CONCEPT_STATUSES: tuple[str, ...] = ("exploring", "rejected", "promoted")


def _to_layer(v: dict[str, Any]) -> dict[str, Any]:
    """A named layer (``{name: brick, thickness: 64 mm, conductivity: 0.25 W/(m*K)}``).

    Values that parse as quantities become quantities; words (``name``, ``material``)
    stay words.
    """
    out: dict[str, Any] = {}
    for key, value in v.items():
        if isinstance(value, str):
            try:
                out[str(key)] = parse_quantity(value)
            except UnitError:
                out[str(key)] = value
        else:
            out[str(key)] = _to_quantity(value)
    return out


def _to_quantity_or_list(v: Any) -> Any:
    if isinstance(v, list):
        return [_to_layer(x) if isinstance(x, dict) else _to_quantity(x) for x in v]
    return _to_quantity(v)


def _ser_item(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: v if isinstance(v, str) else format_quantity(v) for k, v in x.items()}
    return format_quantity(x)


def _ser_quantity_or_list(v: Any) -> Any:
    if isinstance(v, list):
        return [_ser_item(x) for x in v]
    return format_quantity(v)


#: An envelope entry: one quantity (``170 mm``), a list (``[200 mm, 200 mm, 200 mm]``) or a
#: list of named layers (``[{name: brick, thickness: 64 mm, conductivity: 0.25 W/(m*K)}]``).
EnvelopeValue = Annotated[
    Any,
    BeforeValidator(_to_quantity_or_list),
    PlainSerializer(_ser_quantity_or_list),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "string", "examples": ["170 mm"]},
                {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "object"}]}},
            ]
        }
    ),
]


def _to_site_value(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return _to_quantity(v)
    if isinstance(v, str):
        try:
            return parse_quantity(v)
        except UnitError:
            return v  # a word such as a region code or circuit class ("SA", "240V-13A")
    raise ValueError(f"expected a quantity like '800 mm' or a word like 'SA', got {v!r}")


def _ser_site_value(v: Any) -> Any:
    return v if isinstance(v, (bool, str)) else format_quantity(v)


#: A site entry: a quantity when it parses as one, otherwise kept as a word (or a yes/no).
SiteValue = Annotated[
    Any,
    BeforeValidator(_to_site_value),
    PlainSerializer(_ser_site_value),
    WithJsonSchema({"type": ["string", "boolean"], "examples": ["800 mm", "SA", "240V-13A"]}),
]


class MassingCall(Model):
    """One kit call of a concept's massing: a silhouette solid, named and placed."""

    kit: str
    as_: str = Field(alias="as")
    args: dict[str, Any] = Field(default_factory=dict)
    at: dict[str, Any] | None = None
    #: Material name for the massing mass (``mild steel``, ``K23``…); no material, no mass.
    material: str | None = None
    #: Cost-band process class; defaults to the generator's own ``process``.
    process_class: str | None = None


Label = Literal["computed", "estimate"]


class LabelledValue(Model):
    """One screening number: ``computed`` from massing geometry or ``estimate`` (calc kit)."""

    value: str  # a formatted quantity ("995 mm") or a word ("16 A dedicated circuit")
    label: Label
    source: str


class RuleRow(Model):
    """One concept-rule outcome; ``relies_on`` names the labels of the numbers it used."""

    id: str
    title: str = ""
    severity: Literal["fail", "warn"] = "fail"
    status: Literal["pass", "fail", "warn", "skip"]
    message: str
    relies_on: list[Label] = Field(default_factory=list)


class Screening(Model):
    """What ``n2f concept build`` wrote: labelled numbers, rule rows and a verdict (N5).

    Every field has a default so a hand-written partial block still reads; empty fields
    are left out when written.
    """

    computed: dict[str, LabelledValue] = Field(default_factory=dict)
    estimates: dict[str, LabelledValue] = Field(default_factory=dict)
    rules: list[RuleRow] = Field(default_factory=list)
    verdict: Literal["green", "red"] | None = None
    at: dt.datetime | None = None
    notes: list[str] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _compact(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        return {k: v for k, v in data.items() if v not in (None, [], {})}

    @property
    def failing(self) -> list[RuleRow]:
        """The rule rows that redden the card."""
        return [r for r in self.rules if r.status == "fail"]


class ConceptCard(Model):
    """One concept card (``concepts/C-xxx.yaml``); outside the build graph (N1)."""

    id: ConceptId
    title: str
    status: ConceptStatus = "exploring"
    based_on: ConceptId | None = None
    refs: list[str] = Field(default_factory=list)
    layout: dict[str, str] = Field(default_factory=dict)
    envelope: dict[str, EnvelopeValue] = Field(default_factory=dict)
    site: dict[str, SiteValue] = Field(default_factory=dict)
    style: dict[str, Any] = Field(default_factory=dict)
    massing: list[MassingCall] = Field(default_factory=list)
    notes: str | None = None
    screening: Screening | None = None
    decision: dict[str, Any] | None = None

    @property
    def verdict(self) -> str | None:
        """The screening verdict (``green``/``red``) once ``n2f concept build`` wrote one."""
        return self.screening.verdict if self.screening is not None else None
