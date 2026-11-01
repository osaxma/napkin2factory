"""assemblies/<id>.yaml schema (decision D18)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import (
    BeforeValidator,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from napkin2factory.core.model.base import (
    AsmUri,
    IfaceUri,
    Model,
    PartUri,
    Quantity,
    ReqUri,
    Slug,
    table_check,
)
from napkin2factory.core.model.parts import ModuleGeometry


def _asm_geometry(v: Any) -> Any:
    if v is None or v == "none":
        return "none"
    if isinstance(v, ModuleGeometry):
        return v
    if isinstance(v, dict) and "module" in v:
        return ModuleGeometry.model_validate(v)
    raise ValueError("assembly geometry is {module: geometry/<file>.py} or 'none'")


def _drivers() -> list[str]:
    from napkin2factory.core.registry import registry

    return list(registry().drivers())


#: Why a sub-assembly is built on its own (P7): ``core/data/drivers.yaml`` plus the domains'
#: (F6), each with its owner words (``core.build_units.driver_words``).
Driver = Annotated[str, table_check("build-unit driver", _drivers)]


def __getattr__(name: str) -> Any:
    """``DRIVERS`` (every driver, table order) is read from the registry on each access."""
    if name == "DRIVERS":
        return tuple(_drivers())
    raise AttributeError(name)


def _drop_defaults(data: Any, defaults: dict[str, Any]) -> Any:
    """Leave out fields still at their v0.4 defaults, so a v0.3 file dumps as before (P14)."""
    if isinstance(data, dict):
        for key, default in defaults.items():
            if key in data and data[key] == default:
                data.pop(key)
    return data


class Child(Model):
    """One membership line: a part or a sub-assembly with a quantity.

    ``spare`` says why the line holds more interface hardware than its joints need (P9; the
    hardware check then passes the surplus); ``loose`` marks a line shipped loose for the
    installer instead of fitted in the build step (S-105).
    """

    part: PartUri | None = None
    asm: AsmUri | None = None
    qty: int = 1
    spare: str | None = None
    loose: bool = False

    @field_validator("spare")
    @classmethod
    def _spare_has_reason(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError('spare needs a reason, e.g. spare: "two extra for the installer"')
        return v

    @model_serializer(mode="wrap")
    def _dump(self, handler: SerializerFunctionWrapHandler) -> Any:
        return _drop_defaults(handler(self), {"spare": None, "loose": False})

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
    """Membership and quantities (the BOM structure); geometry is Python.

    ``build`` and ``driver`` (P7) say how a sub-assembly is built and why: a ``unit`` is a
    step of the build plan of its own, a ``phantom`` only groups lines and folds into its
    parent's step.  The top assembly is always built and needs neither.
    """

    id: Slug
    rev: str = "A"
    name: str
    build: Literal["unit", "phantom"] = "unit"
    driver: list[Driver] = Field(default_factory=list)
    geometry: Annotated[ModuleGeometry | Literal["none"], BeforeValidator(_asm_geometry)] = "none"
    children: list[Child] = Field(default_factory=list)
    exploded: Exploded = Field(default_factory=Exploded)
    # P4: the joints that cross this assembly's boundary (one part inside, one outside),
    # each an interface between two parts; the loader requires exactly those (S-107).
    ports: list[IfaceUri] = Field(default_factory=list)
    satisfies: list[ReqUri] = Field(default_factory=list)
    notes: str | None = None

    @model_serializer(mode="wrap")
    def _dump(self, handler: SerializerFunctionWrapHandler) -> Any:
        return _drop_defaults(handler(self), {"build": "unit", "driver": []})

    @property
    def uri(self) -> str:
        """``asm://<id>``."""
        return f"asm://{self.id}"
