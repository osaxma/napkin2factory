"""parts/<id>.yaml schema."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field, model_validator

from napkin2factory.core.model.base import IfaceUri, Model, Quantity, ReqUri, Slug, table_check
from napkin2factory.core.model.style import StyleRole

_KIT_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _kit_name(v: Any) -> str:
    if not isinstance(v, str) or not _KIT_RE.match(v):
        raise ValueError(
            f"{v!r} is not a kit generator name (lowercase with underscores, e.g. bracket_l)"
        )
    return v


KitName = Annotated[str, BeforeValidator(_kit_name)]


def geometry_spec(v: Any) -> Any:
    """Pick the geometry variant up front so errors name one schema, not three."""
    if v is None or v == "none":
        return "none"
    if isinstance(v, (KitGeometry, ModuleGeometry)):
        return v
    if isinstance(v, dict):
        if "kit" in v:
            return KitGeometry.model_validate(v)
        if "module" in v:
            return ModuleGeometry.model_validate(v)
        raise ValueError(
            "geometry is {kit: <generator>, args: {...}} or {module: geometry/<file>.py} or 'none'"
        )
    raise ValueError(f"geometry must be a mapping or 'none', got {type(v).__name__}")


def _processes() -> list[str]:
    from napkin2factory.core.registry import registry

    return list(registry().processes())


#: A manufacturing process: ``core/data/processes.yaml`` plus the domains' (F6).
Process = Annotated[str, table_check("process", _processes)]
ToleranceClass = Literal["ISO2768-f", "ISO2768-m", "ISO2768-c", "ISO2768-v"]
CostBasis = Literal["estimate", "quote", "catalog"]


class Material(Model):
    """Material name and optional specification."""

    name: str
    spec: str | None = None
    density: Quantity | None = None  # overrides the built-in density table


class Cost(Model):
    """Declared unit cost and where the number comes from."""

    unit: Quantity
    basis: CostBasis = "estimate"
    note: str | None = None
    currency_note: str | None = None


class Source(Model):
    """Where a COTS part is bought."""

    vendor: str
    mpn: str
    url: str | None = None
    verified: bool = False
    note: str | None = None


class KitGeometry(Model):
    """Declarative generator call: ``{kit: enclosure, args: {...}}``."""

    kit: KitName
    args: dict[str, Any] = Field(default_factory=dict)


class ModuleGeometry(Model):
    """Custom Python: ``{module: geometry/outer_shell.py}`` exposing ``build(P, I, kit)``."""

    module: str


class Part(Model):
    """A custom or COTS part."""

    id: Slug
    rev: str = "A"
    name: str
    kind: Literal["custom", "cots", "reference"] = "custom"  # reference = owner-supplied/existing
    process: Process = "none"
    material: Material | None = None
    finish: str | None = None
    tolerance_class: ToleranceClass | None = None
    geometry: Annotated[
        KitGeometry | ModuleGeometry | Literal["none"], BeforeValidator(geometry_spec)
    ] = "none"
    interfaces: list[IfaceUri] = Field(default_factory=list)
    satisfies: list[ReqUri] = Field(default_factory=list)
    cost: Cost | None = None
    lead_time: Quantity | None = None
    mass: Quantity | None = None
    source: Source | None = None
    quantity_basis: int | None = None
    notes: str | None = None
    manufacturer_notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    #: Styling role (``style.yaml``): picks the palette colour and finish, and opts the part
    #: into style-sourced geometry defaults when it is body, door, stand, controls or trim.
    role: StyleRole | None = None

    @model_validator(mode="after")
    def _kind_rules(self) -> Part:
        if self.kind in ("cots", "reference") and self.tolerance_class is not None:
            raise ValueError("only custom parts declare tolerance_class")
        if self.kind == "cots" and isinstance(self.geometry, ModuleGeometry):
            raise ValueError("COTS geometry is a kit primitive (block/tube) or 'none'")
        return self

    @property
    def uri(self) -> str:
        """``part://<id>``."""
        return f"part://{self.id}"

    @property
    def has_geometry(self) -> bool:
        """True unless geometry is ``none``."""
        return self.geometry != "none"
