"""signoffs/REQ-xxx.yaml schema (decision D25)."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from napkin2factory.core.model.base import Model, ReqUri, UriField

if TYPE_CHECKING:
    from napkin2factory.core.errors import Problems
    from napkin2factory.core.loader import Product


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


def validate_refs(product: Product, problems: Problems) -> None:
    """Every piece of evidence a sign-off cites has its key recorded (F15).

    The requirement it signs is checked by the loader's URI check, like any reference.
    """
    for so in product.signoffs.values():
        missing = [str(e) for e in so.evidence if str(e) not in so.evidence_keys]
        if missing and so.evidence_keys:
            problems.add(
                product.files[f"signoff:{so.requirement.id}"],
                f"signoff {so.requirement.id}",
                f"evidence without a recorded key: {missing}",
                "re-run `n2f signoff` so keys are recorded",
                severity="warn",
                rule="signoff",
            )
