"""``model/loads/<id>.yaml``: load cases (F11, the reserved slot).

A load case says where a load acts (``acts_on``; not ``on``, which YAML reads as "true"), how
much, and on which faces: "the shelf carries 20 kg on its top face".  A requirement cites one
as ``load://<id>`` in its allocation, so the case is written once and every requirement that
depends on it names the same numbers.  v0.5 defines the family and its validation only; no
solver reads it yet, so a load case changes no check verdict.  The mechanical domain
registers the family (``domains/mechanical``), which makes ``load://`` a URI scheme.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import Field, model_validator

from napkin2factory.core.model.base import Model, Quantity, Slug, UriField
from napkin2factory.core.units import parse_quantity, same_dimension

if TYPE_CHECKING:
    from napkin2factory.core.errors import Problems
    from napkin2factory.core.loader import Product

LoadKind = Literal["force", "moment", "pressure", "mass", "acceleration", "temperature"]
#: A unit of each kind, to check a load's ``value`` carries the right dimension.
KIND_UNITS: dict[str, str] = {
    "force": "N",
    "moment": "N*m",
    "pressure": "Pa",
    "mass": "kg",
    "acceleration": "m/s**2",
    "temperature": "degC",
}
Direction = Literal["+x", "-x", "+y", "-y", "+z", "-z"]


class Load(Model):
    """One load case: ``acts_on`` (a part or assembly), ``faces`` on it, ``kind`` and ``value``."""

    id: Slug
    name: str
    kind: LoadKind
    value: Quantity
    acts_on: UriField
    faces: list[str] = Field(default_factory=list)
    direction: Direction | None = None
    source: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Load:
        if self.acts_on.scheme not in ("part", "asm"):
            raise ValueError(
                f"`acts_on:` names the part or assembly the load acts on, not {self.acts_on}"
            )
        if self.acts_on.selector:
            raise ValueError(
                f"`acts_on:` is a part or assembly ({self.acts_on.base}); faces go in `faces:`"
            )
        if not same_dimension(self.value, parse_quantity(1, KIND_UNITS[self.kind])):
            raise ValueError(
                f"a {self.kind} load is given in {KIND_UNITS[self.kind]} or a unit like it, "
                f"not {self.value}"
            )
        return self

    @property
    def uri(self) -> str:
        """``load://<id>``."""
        return f"load://{self.id}"


def validate_refs(product: Product, problems: Problems) -> None:
    """Each load acts on a part or assembly the product holds (F11, F15).

    A requirement citing ``load://<id>`` is resolved by the loader's own URI check (the
    family registers the scheme), so a missing load case is reported where it is cited.
    """
    for lid, load in sorted(product.families.get("loads", {}).items()):
        if product.exists(load.acts_on.base) or str(load.acts_on.base) in product.broken:
            continue
        table = product.parts if load.acts_on.scheme == "part" else product.assemblies
        problems.add(
            product.files.get(f"load://{lid}", product.root / "model" / "loads" / f"{lid}.yaml"),
            f"load://{lid}",
            f"`acts_on: {load.acts_on}` names nothing in the model; known "
            f"{load.acts_on.scheme} ids: {', '.join(sorted(table)) or 'none'}",
            "name the part or assembly the load acts on",
            rule="load",
        )
