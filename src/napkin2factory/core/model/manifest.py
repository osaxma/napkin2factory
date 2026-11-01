"""n2f.yaml (the product manifest) and operator.yaml schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from napkin2factory.core.model.base import AsmUri, DecId, Model, Slug

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


#: Where a domain's work stands in this product (F11): ``in`` (done here), ``external`` (done
#: elsewhere; a stub module stands for it) or ``later`` (left for a later stage).
ScopeState = Literal["in", "external", "later"]
#: The owner's words for each state (docs/vocabulary.md: in / done elsewhere / later).
SCOPE_WORDS: dict[str, str] = {"in": "in", "external": "done elsewhere", "later": "later"}


class ScopeEntry(Model):
    """One domain's line under ``scope:`` (F11): its state, the decision behind it, a note.

    ``stub`` names the sub-assembly (``build: external``) that stands for an ``external``
    domain's work; without it any ``build: external`` sub-assembly does (S-124).
    """

    state: ScopeState
    decision: DecId | None = None
    note: str | None = None
    stub: AsmUri | None = None

    @model_validator(mode="after")
    def _stub_only_external(self) -> ScopeEntry:
        if self.stub is not None and self.state != "external":
            raise ValueError(
                f"`stub:` names the module that stands for work done elsewhere; with state "
                f"{self.state!r} remove it, or set `state: external`"
            )
        return self


def scope_line(domain: str, entry: ScopeEntry, decision_title: str | None = None) -> str:
    """One scope line in owner words (F11): "Electrical: later — <note> (DEC-xxx)".

    The note is the entry's own, else the decision's title; the decision id closes the line
    so the owner can find it in the decisions list.
    """
    text = f"{domain.capitalize()}: {SCOPE_WORDS[entry.state]}"
    note = entry.note or decision_title
    if note:
        text += f" — {note}"
    if entry.decision:
        text += f" ({entry.decision})"
    return text


class Manifest(Model):
    """``n2f.yaml``.

    ``scope`` (F11) records, per domain, whether its work is ``in`` this product, done
    elsewhere (``external``) or ``later``.  A domain not listed is ``in`` when the product
    has content for it and absent otherwise; the field is optional and changes nothing
    when left out (F16).
    """

    schema_version: int = Field(default=1, alias="schema")
    system: str = ">=0.5,<0.6"
    product: ProductInfo
    units: Literal["metric"] = "metric"
    manufacturer_profile: str | None = None
    scope: dict[Slug, ScopeEntry] = Field(default_factory=dict)

    @field_validator("system")
    @classmethod
    def _specifier(cls, v: str) -> str:
        from packaging.specifiers import InvalidSpecifier, SpecifierSet

        try:
            SpecifierSet(v)
        except InvalidSpecifier as exc:
            raise ValueError(f"system pin {v!r} is not a version range like '>=0.5,<0.6'") from exc
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
