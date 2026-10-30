"""changes/ECR-xxx.yaml schema (decision D7)."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import Field, model_validator

from napkin2factory.core.model.base import EcrId, Model, UriField

EcrStatus = Literal["draft", "impact", "approved", "applied", "closed", "rejected"]
EcrKind = Literal["parametric", "design"]
#: Allowed transitions of the ECR state machine.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("impact", "rejected"),
    "impact": ("approved", "rejected", "impact"),
    "approved": ("applied", "rejected"),
    "applied": ("closed",),
    "closed": (),
    "rejected": (),
}


class Edit(Model):
    """One mechanical edit: set a selector to a value."""

    set: UriField
    to: Any

    @model_validator(mode="after")
    def _has_selector(self) -> Edit:
        if not self.set.selector and self.set.scheme != "param":
            raise ValueError(
                f"edit target {self.set} needs a selector, e.g. req://REQ-001#verify.value"
            )
        return self


class Approval(Model):
    """Who approved and when."""

    by: str
    at: dt.datetime
    note: str | None = None


class Applied(Model):
    """Which snapshot the ECR was applied in, and the output hashes before it (for rev bumps)."""

    snapshot: str
    build_id: str | None = None
    at: dt.datetime | None = None
    before: dict[str, str] = Field(default_factory=dict)


class Ecr(Model):
    """An engineering change request."""

    id: EcrId
    title: str
    status: EcrStatus = "draft"
    kind: EcrKind = "parametric"
    requested_by: str = "human"
    reason: str | None = None
    edits: list[Edit] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    patch: str | None = None
    impact: dict[str, Any] | None = None
    approval: Approval | None = None
    applied: Applied | None = None
    released_in: str | None = None
    rejected_reason: str | None = None
    created: dt.date | None = None

    @model_validator(mode="after")
    def _kind_rules(self) -> Ecr:
        if self.kind == "parametric" and not self.edits and self.status == "draft":
            # allowed while drafting; lint warns
            pass
        if self.kind == "parametric" and self.patch:
            raise ValueError("parametric change requests carry edits, not a patch")
        return self

    @property
    def uri(self) -> str:
        """``ecr://<id>``."""
        return f"ecr://{self.id}"

    def can_transition(self, to: str) -> bool:
        """True if the state machine allows ``status -> to``."""
        return to in TRANSITIONS[self.status]
