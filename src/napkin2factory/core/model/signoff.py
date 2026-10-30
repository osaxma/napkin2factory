"""signoffs/REQ-xxx.yaml schema (decision D25)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import Field

from napkin2factory.core.model.base import Model, ReqUri, UriField


class Signoff(Model):
    """A human sign-off bound to the evidence hashes current at signing."""

    requirement: ReqUri
    by: str
    role: Literal["human", "agent"] = "human"
    date: dt.date
    statement: str
    evidence: list[UriField] = Field(default_factory=list)
    evidence_keys: dict[str, str] = Field(default_factory=dict)
    example: bool = False
