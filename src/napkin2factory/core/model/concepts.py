"""concepts/C-xxx.yaml schema (NAPKIN_STAGE §3, decision N1).

A concept card is a cheap, disposable direction for the product: a title, rough layout,
envelope numbers, site constraints, a style sketch and a massing made of kit calls.  Cards
live outside the build graph: no build rule reads them and ``n2f validate`` ignores them.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field, PlainSerializer, WithJsonSchema

from napkin2factory.core.model.base import Model, _id, _to_quantity
from napkin2factory.core.units import UnitError, format_quantity, parse_quantity

ConceptId = Annotated[str, _id(r"C-\d{3}")]
ConceptStatus = Literal["exploring", "rejected", "promoted"]
#: Every status word a card can carry, in display order.
CONCEPT_STATUSES: tuple[str, ...] = ("exploring", "rejected", "promoted")


def _to_quantity_or_list(v: Any) -> Any:
    if isinstance(v, list):
        return [_to_quantity(x) for x in v]
    return _to_quantity(v)


def _ser_quantity_or_list(v: Any) -> Any:
    if isinstance(v, list):
        return [format_quantity(x) for x in v]
    return format_quantity(v)


#: An envelope entry: one quantity (``170 mm``) or a list (``[200 mm, 200 mm, 200 mm]``).
EnvelopeValue = Annotated[
    Any,
    BeforeValidator(_to_quantity_or_list),
    PlainSerializer(_ser_quantity_or_list),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "string", "examples": ["170 mm"]},
                {"type": "array", "items": {"type": "string"}},
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
    screening: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None

    @property
    def verdict(self) -> str | None:
        """The screening verdict (``green``/``red``) once ``n2f concept build`` wrote one."""
        if not self.screening:
            return None
        v = self.screening.get("verdict")
        return str(v) if v is not None else None
