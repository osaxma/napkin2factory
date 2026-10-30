"""Shared pydantic building blocks: quantities, URIs, ids, strict base model."""

from __future__ import annotations

import re
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    PlainSerializer,
    WithJsonSchema,
)

from napkin2factory.core.units import Quantity as PintQuantity
from napkin2factory.core.units import UnitError, format_quantity, parse_quantity
from napkin2factory.core.uris import SLUG, Uri, UriError


class Model(BaseModel):
    """Strict base: unknown keys are errors, so typos surface as validation problems."""

    model_config = ConfigDict(
        extra="forbid", arbitrary_types_allowed=True, populate_by_name=True, validate_default=True
    )


def _to_quantity(v: Any) -> Any:
    if isinstance(v, PintQuantity):
        return v
    if isinstance(v, bool):
        raise ValueError("a quantity cannot be a boolean")
    if isinstance(v, (int, float, str)):
        try:
            return parse_quantity(v)
        except UnitError as exc:
            raise ValueError(str(exc)) from exc
    if isinstance(v, dict) and "value" in v:
        try:
            return parse_quantity(v["value"], v.get("unit"))
        except UnitError as exc:
            raise ValueError(str(exc)) from exc
    raise ValueError(f"expected a quantity like '50 mm', got {v!r}")


Quantity = Annotated[
    Any,
    BeforeValidator(_to_quantity),
    PlainSerializer(format_quantity, return_type=str),
    WithJsonSchema({"type": "string", "examples": ["50 mm", "60 degC", "85 USD"]}),
]


def _to_uri(v: Any) -> Any:
    if isinstance(v, Uri):
        return v
    try:
        return Uri.parse(v)
    except UriError as exc:
        raise ValueError(str(exc)) from exc


UriField = Annotated[
    Uri,
    BeforeValidator(_to_uri),
    PlainSerializer(str, return_type=str),
    WithJsonSchema({"type": "string", "examples": ["part://outer-shell", "req://REQ-001"]}),
]


def _scheme_validator(*schemes: str) -> Any:
    def check(v: Any) -> Any:
        u = _to_uri(v)
        if u.scheme not in schemes:
            raise ValueError(f"{u} must be one of {', '.join(s + '://' for s in schemes)}")
        return u

    return BeforeValidator(check)


def uri_of(*schemes: str) -> Any:
    """Annotated URI type restricted to the given schemes."""
    return Annotated[
        Uri,
        _scheme_validator(*schemes),
        PlainSerializer(str, return_type=str),
        WithJsonSchema({"type": "string"}),
    ]


PartUri = uri_of("part")
AsmUri = uri_of("asm")
ReqUri = uri_of("req")
ParamUri = uri_of("param")
IfaceUri = uri_of("iface")
DocUri = uri_of("doc")
CalcUri = uri_of("calc")
ChildUri = uri_of("part", "asm")

_SLUG_RE = re.compile(rf"^{SLUG}$")


def _slug(v: Any) -> str:
    if not isinstance(v, str) or not _SLUG_RE.match(v):
        raise ValueError(f"{v!r} is not a slug (lowercase letters, digits, single hyphens)")
    return v


Slug = Annotated[str, BeforeValidator(_slug)]


def _id(pattern: str) -> Any:
    rx = re.compile(pattern)

    def check(v: Any) -> str:
        if not isinstance(v, str) or not rx.fullmatch(v):
            raise ValueError(f"{v!r} does not match {pattern}")
        return v

    return BeforeValidator(check)


ReqId = Annotated[str, _id(r"REQ-\d{3}")]
DecId = Annotated[str, _id(r"DEC-\d{3}")]
EcrId = Annotated[str, _id(r"ECR-\d{3}")]
