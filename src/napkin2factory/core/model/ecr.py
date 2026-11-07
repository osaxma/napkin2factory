"""changes/ECR-xxx.yaml schema (decision D7)."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from napkin2factory.core.model.base import EcrId, Model, UriField

EcrStatus = Literal["draft", "approved", "closed", "rejected", "aborted"]
_RETIRED_STATUS_MESSAGES: dict[str, str] = {
    "applied": (
        "status `applied` is gone in file format 2: its edit is in the model, so set "
        "`closed` (`n2f init .` does this for a folder still in format 1)"
    ),
    "impact": (
        "status `impact` is gone in file format 2: use `draft`, and look at the impact "
        "with `n2f ecr impact`"
    ),
}
EcrKind = Literal["parametric", "design"]
#: The states in which a request is still being worked on: it has a baseline (R6), and an
#: approved one the hash of the model it approved (R7).
OPEN_STATUSES: tuple[str, ...] = ("draft", "approved")
#: Allowed transitions of the ECR state machine (schema 2, R8, S-261).
#:
#: ``draft → approved → closed`` or ``draft | approved → aborted``; a new impact report on an
#: approved request puts it back to ``draft`` (an approval belongs to one impact report, R7).
#: ``rejected`` is a state of schema 1 files, kept readable as history: nothing goes there.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("approved", "aborted"),
    "approved": ("aborted", "draft", "closed"),
    "closed": (),
    "rejected": (),
    "aborted": (),
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
    # The folder's saved-state hash when approved (v0.8 R7): `ecr close` refuses when the
    # model has changed since. Absent on approvals recorded before v0.8.
    model_hash: str | None = None


class Baseline(Model):
    """The state a live change request started from (v0.8 R6): its checkpoint and vitals.

    The checkpoint is also kept as the marker ``ecr/<ECR id>/baseline``; mass and cost are
    the plain strings a checkpoint carries (None: not measured, the build was stale).
    """

    checkpoint: str
    mass: str | None = None
    cost: str | None = None


class Applied(Model):
    """Schema 1 history, readable on closed requests only: the snapshot it was applied in."""

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
    baseline: Baseline | None = None
    impact: dict[str, Any] | None = None
    approval: Approval | None = None
    applied: Applied | None = None
    released_in: str | None = None
    rejected_reason: str | None = None
    aborted_reason: str | None = None
    created: dt.date | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _retired_status(cls, v: Any) -> Any:
        """Give a plain message when a schema-1 status is written in a schema-2 file (B-0283)."""
        if isinstance(v, str) and v in _RETIRED_STATUS_MESSAGES:
            raise PydanticCustomError("retired_status", _RETIRED_STATUS_MESSAGES[v])
        return v

    @model_validator(mode="after")
    def _kind_rules(self) -> Ecr:
        if self.kind == "parametric" and self.patch:
            raise ValueError("parametric change requests carry edits, not a patch")
        return self

    @model_validator(mode="after")
    def _open_rules(self) -> Ecr:
        """An open request says where it started; an approved one, which model it approved."""
        if self.status in OPEN_STATUSES and self.baseline is None:
            raise ValueError(
                f"{self.id} is {self.status} but does not say where it started (`baseline:`). "
                "A change request is opened with `n2f ecr start`; if this file was written by "
                "hand, abort it with `n2f ecr abort` or set its status to aborted"
            )
        if self.status == "approved" and (self.approval is None or not self.approval.model_hash):
            raise ValueError(
                f"{self.id} is approved but does not say which model it approved "
                "(`approval.model_hash:`). Approve it with `n2f ecr approve`, or set its "
                "status back to draft and run `n2f ecr impact` again"
            )
        return self

    @model_validator(mode="after")
    def _history_rules(self) -> Ecr:
        """A patch file and the old ``applied`` record are history, kept on finished requests."""
        if self.patch and self.status not in ("closed", "rejected"):
            raise ValueError(
                "a change request no longer carries a patch: edit the model files directly "
                "after `n2f ecr start` (a patch stays readable only on closed and rejected "
                "requests)"
            )
        if self.applied is not None and self.status != "closed":
            raise ValueError(
                "`applied:` is history from the old file format; only a closed request has it"
            )
        return self

    @property
    def uri(self) -> str:
        """``ecr://<id>``."""
        return f"ecr://{self.id}"

    def can_transition(self, to: str) -> bool:
        """True if the state machine allows ``status -> to``."""
        return to in TRANSITIONS[self.status]
