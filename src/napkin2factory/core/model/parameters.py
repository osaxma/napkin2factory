"""parameters.yaml schema."""

from __future__ import annotations

from typing import Any

from pydantic import Field, SerializerFunctionWrapHandler, model_serializer, model_validator

from napkin2factory.core.model.assemblies import _drop_defaults
from napkin2factory.core.model.base import AsmUri, Model, Slug


class Parameter(Model):
    """A named value with a unit, or an expression over other parameters.

    ``scope`` and ``export`` (P5) say which module a parameter belongs to: a parameter scoped to
    ``asm://door`` is the door's; the door, the assemblies inside it, and its ancestors' rules
    may read it only as the reach check allows (``core/reach.py``), and its parent reads it
    only when it is exported.  Unscoped parameters are the whole product's, as before (P14).
    """

    value: float | int | None = None
    expr: str | None = None
    unit: str = ""
    description: str | None = None
    owner: str | None = None
    min: float | int | None = None
    max: float | int | None = None
    scope: AsmUri | None = None
    export: bool = False

    @model_serializer(mode="wrap")
    def _dump(self, handler: SerializerFunctionWrapHandler) -> Any:
        # P14: the v0.4 fields are left out at their defaults, so a v0.3 record dumps as before
        return _drop_defaults(handler(self), {"scope": None, "export": False})

    @model_validator(mode="after")
    def _value_xor_expr(self) -> Parameter:
        if (self.value is None) == (self.expr is None):
            raise ValueError("a parameter has exactly one of 'value' or 'expr'")
        return self


class ParametersFile(Model):
    """Top level of ``model/parameters.yaml``."""

    parameters: dict[Slug, Parameter] = Field(default_factory=dict)

    def raw(self) -> dict[str, Any]:
        """Slug → declared value/expr, for impact tooling."""
        return {k: v.model_dump() for k, v in self.parameters.items()}
