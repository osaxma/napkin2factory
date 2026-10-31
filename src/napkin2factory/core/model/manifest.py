"""n2f.yaml (the product manifest) and operator.yaml schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from napkin2factory.core.model.base import Model, Slug

Level = Literal["novice", "intermediate", "expert"]
DEFAULT_DOMAINS: dict[str, Level] = {
    "mechanical": "novice",
    "thermal": "novice",
    "electrical": "novice",
    "manufacturing": "novice",
}


class ProductInfo(Model):
    """Product id and display name."""

    id: Slug
    name: str
    description: str | None = None


class Manifest(Model):
    """``n2f.yaml``."""

    schema_version: int = Field(default=1, alias="schema")
    system: str = ">=0.2,<0.3"
    product: ProductInfo
    units: Literal["metric"] = "metric"
    manufacturer_profile: str | None = None

    @field_validator("system")
    @classmethod
    def _specifier(cls, v: str) -> str:
        from packaging.specifiers import InvalidSpecifier, SpecifierSet

        try:
            SpecifierSet(v)
        except InvalidSpecifier as exc:
            raise ValueError(f"system pin {v!r} is not a version range like '>=0.2,<0.3'") from exc
        return v

    def pin_includes(self, version: str) -> bool:
        """True when ``version`` of napkin2factory satisfies this product's ``system`` pin.

        Pre-releases are admitted (``prereleases=True``) but compare below their final
        release under PEP 440, so ``0.2.0.dev0`` is outside ``>=0.2,<0.3`` and inside
        ``>=0.1,<0.3``. The pin only ever warns (D20); it never refuses to run.
        """
        from packaging.specifiers import SpecifierSet

        return SpecifierSet(self.system).contains(version, prereleases=True)


class Operator(Model):
    """``operator.yaml``: who is driving and how to talk to them."""

    persona: Literal["owner", "engineer"] = "owner"
    domains: dict[str, Level] = Field(default_factory=lambda: dict(DEFAULT_DOMAINS))
    verbosity: Literal["terse", "normal", "verbose"] = "normal"
    delegation: Literal["conservative", "balanced", "autonomous"] = "balanced"
    language: str = "en"
    name: str | None = None
