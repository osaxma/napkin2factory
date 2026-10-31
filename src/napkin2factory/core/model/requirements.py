"""requirements.yaml schema."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from napkin2factory.core.model.base import Model, Quantity, ReqId, UriField

Category = Literal[
    "performance",
    "geometry",
    "cost",
    "mass",
    "safety",
    "manufacturing",
    "usability",
    "interface",
]
VerifyKind = Literal[
    "param_bound",
    "geometry_prop",
    "bom_rollup",
    "calc",
    "interference",
    "count",
    "interface",
    "manual",
    "rule",
]
Op = Literal["<", "<=", "==", "!=", ">=", ">"]

#: Which URI schemes each verify kind may target.
VERIFY_TARGET_SCHEMES: dict[str, tuple[str, ...]] = {
    "param_bound": ("param",),
    "geometry_prop": ("part", "asm"),
    "bom_rollup": ("bom",),
    "calc": ("calc",),
    "interference": ("asm",),
    "count": ("asm", "part"),
    "interface": ("iface",),
    "manual": (),
    "rule": ("rule",),
}
#: Kinds whose verdict comes from comparing a value with ``op``/``value``.
COMPARING_KINDS: frozenset[str] = frozenset(
    {"param_bound", "geometry_prop", "bom_rollup", "calc", "count"}
)


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
        schemes = VERIFY_TARGET_SCHEMES[self.kind]
        if self.kind == "manual":
            return self
        if self.target is None:
            raise ValueError(f"verify.kind {self.kind} needs a target ({'/'.join(schemes)}://…)")
        if self.target.scheme not in schemes:
            raise ValueError(
                f"verify.kind {self.kind} targets {', '.join(s + '://' for s in schemes)}, "
                f"not {self.target}"
            )
        if self.kind in COMPARING_KINDS and (self.op is None or self.value is None):
            raise ValueError(f"verify.kind {self.kind} needs 'op' and 'value'")
        if self.kind == "geometry_prop" and (
            not self.target.selector or self.target.selector[0] != "props"
        ):
            raise ValueError("geometry_prop targets select a property: part://x#props.mass")
        if self.kind == "rule" and (self.op is not None or self.value is not None):
            raise ValueError("verify.kind rule takes a target only (rule://<pack>/<rule-id>)")
        if self.kind == "bom_rollup" and not self.target.selector:
            raise ValueError("bom_rollup targets select a rollup: bom://rollups#total_cost")
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
