"""decisions.yaml schema."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import Field

from napkin2factory.core.model.base import DecId, Model, UriField


class Decision(Model):
    """A logged choice with rationale, linked to what it affects."""

    id: DecId
    date: dt.date
    title: str
    context: str | None = None
    decision: str
    rationale: str | None = None
    links: list[UriField] = Field(default_factory=list)
    made_by: Literal["agent", "human"] = "agent"
    disclosed: bool = True
    verify: bool = False  # engineering numbers awaiting human confirmation
    sources: list[str] = Field(default_factory=list)


class DecisionsFile(Model):
    """Top level of ``model/decisions.yaml``."""

    decisions: list[Decision] = Field(default_factory=list)
