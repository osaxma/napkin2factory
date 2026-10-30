"""assemblies/<id>.yaml schema (decision D18)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field, model_validator

from napkin2factory.core.model.base import AsmUri, Model, PartUri, Quantity, ReqUri, Slug
from napkin2factory.core.model.parts import ModuleGeometry


def _asm_geometry(v: Any) -> Any:
    if v is None or v == "none":
        return "none"
    if isinstance(v, ModuleGeometry):
        return v
    if isinstance(v, dict) and "module" in v:
        return ModuleGeometry.model_validate(v)
    raise ValueError("assembly geometry is {module: geometry/<file>.py} or 'none'")


class Child(Model):
    """One membership line: a part or a sub-assembly with a quantity."""

    part: PartUri | None = None
    asm: AsmUri | None = None
    qty: int = 1

    @model_validator(mode="after")
    def _one_of(self) -> Child:
        if (self.part is None) == (self.asm is None):
            raise ValueError("a child is exactly one of {part: part://x} or {asm: asm://y}")
        if self.qty < 1:
            raise ValueError("qty must be at least 1")
        return self

    @property
    def uri(self) -> str:
        """The child's URI string."""
        return str(self.part if self.part is not None else self.asm)


class Exploded(Model):
    """Viewer hint for the exploded mode."""

    axis: Literal["x", "y", "z"] = "z"
    spacing: Quantity = "80 mm"


class Assembly(Model):
    """Membership and quantities (the BOM structure); geometry is Python."""

    id: Slug
    rev: str = "A"
    name: str
    geometry: Annotated[ModuleGeometry | Literal["none"], BeforeValidator(_asm_geometry)] = "none"
    children: list[Child] = Field(default_factory=list)
    exploded: Exploded = Field(default_factory=Exploded)
    satisfies: list[ReqUri] = Field(default_factory=list)
    notes: str | None = None

    @property
    def uri(self) -> str:
        """``asm://<id>``."""
        return f"asm://{self.id}"
