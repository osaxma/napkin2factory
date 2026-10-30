"""parameters.yaml schema."""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from napkin2factory.core.model.base import Model, Slug


class Parameter(Model):
    """A named value with a unit, or an expression over other parameters."""

    value: float | int | None = None
    expr: str | None = None
    unit: str = ""
    description: str | None = None
    owner: str | None = None
    min: float | int | None = None
    max: float | int | None = None

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
