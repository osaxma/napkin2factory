"""requirements.yaml schema."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field, model_validator

from napkin2factory.core.model.base import Model, Quantity, ReqId, UriField

Op = Literal["<", "<=", "==", "!=", ">=", ">"]


def __getattr__(name: str) -> Any:
    """``VERIFY_TARGET_SCHEMES`` and ``COMPARING_KINDS`` read the verify-kind registry (F3)."""
    from napkin2factory.core.registry import registry

    kinds = registry().verify_kinds()
    if name == "VERIFY_TARGET_SCHEMES":
        return {k: v.target_schemes for k, v in kinds.items()}
    if name == "COMPARING_KINDS":
        return frozenset(k for k, v in kinds.items() if v.compares)
    raise AttributeError(name)


def _verify_kind(v: Any) -> Any:
    """A verify kind must be installed: the error lists the installed ones (F14, DoD 7)."""
    from napkin2factory.core.registry import registry

    if isinstance(v, str):
        registry().verify_kind(v)
    return v


def _category(v: Any) -> Any:
    """A requirement category from the table (``core/data``) or a domain (F6)."""
    from napkin2factory.core.registry import check_known, registry

    return (
        check_known("requirement category", v, registry().categories()) if isinstance(v, str) else v
    )


#: A verify kind's name, checked against the verify-kind registry (F6: a table, not a Literal).
VerifyKind = Annotated[str, BeforeValidator(_verify_kind)]
#: A requirement category, checked against ``core/data/requirement_categories.yaml`` (F6).
Category = Annotated[str, BeforeValidator(_category)]


class Verify(Model):
    """How a requirement is checked (§4.2 ``verify`` semantics).

    ``rule`` (v0.2, form requirements) passes when no part has a ``fail`` row for the
    rule-pack rule it targets (``rule://form-v0/form-corner-radius``) in the same check run.
    """

    kind: VerifyKind
    target: UriField | None = None
    op: Op | None = None
    value: Quantity | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Verify:
        from napkin2factory.core.registry import registry

        kind = registry().verify_kind(self.kind)
        schemes = kind.target_schemes
        if not schemes:
            return self  # a kind without a target (manual)
        if self.target is None:
            raise ValueError(f"verify.kind {self.kind} needs a target ({'/'.join(schemes)}://…)")
        if self.target.scheme not in schemes:
            raise ValueError(
                f"verify.kind {self.kind} targets {', '.join(s + '://' for s in schemes)}, "
                f"not {self.target}"
            )
        if kind.compares and (self.op is None or self.value is None):
            raise ValueError(f"verify.kind {self.kind} needs 'op' and 'value'")
        if kind.check is not None:
            kind.check(self)
        return self


class Requirement(Model):
    """One atomic, testable requirement."""

    id: ReqId
    title: str
    statement: str
    category: Category
    priority: Literal["must", "should"] = "must"
    safety: bool = False
    verify: Verify | None = None
    allocation: list[UriField] | Literal["unallocated"] | None = None
    rationale: str | None = None
    source: str | None = None
    tags: list[str] = Field(default_factory=list)


class RequirementsFile(Model):
    """Top level of ``model/requirements.yaml``."""

    requirements: list[Requirement] = Field(default_factory=list)
