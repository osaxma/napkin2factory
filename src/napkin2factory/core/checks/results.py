"""``CheckResult`` and status semantics (GRAND_PLAN M4).

Statuses: ``pass`` | ``fail`` | ``warn`` | ``skip`` | ``needs-human`` | ``signed``.
Only ``fail`` blocks (``warn`` never does, D10); ``needs-human`` blocks release until a
valid sign-off turns it into ``signed`` (D9/D25).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["pass", "fail", "warn", "skip", "needs-human", "signed"]
BLOCKING: frozenset[str] = frozenset({"fail"})
HUMAN: frozenset[str] = frozenset({"needs-human"})


@dataclass
class CheckResult:
    """One row of the check matrix."""

    id: str
    subject: str
    status: str
    message: str
    persona_message: str = ""
    kind: str = (
        "requirement"  # requirement | rule | interface | interference | count | bom | doc | signoff
    )
    evidence: dict[str, Any] = field(default_factory=dict)
    evidence_keys: dict[str, str] = field(default_factory=dict)
    safety: bool = False
    title: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON form."""
        return {
            "id": self.id,
            "subject": self.subject,
            "status": self.status,
            "kind": self.kind,
            "title": self.title,
            "message": self.message,
            "persona_message": self.persona_message or self.message,
            "evidence": self.evidence,
            "evidence_keys": self.evidence_keys,
            "safety": self.safety,
            "detail": self.detail,
        }


OWNER_WORDS: dict[str, str] = {
    "pass": "OK",
    "fail": "needs attention",
    "warn": "worth a look",
    "skip": "not checked",
    "needs-human": "needs your sign-off",
    "signed": "signed off",
}


def summarize(results: list[CheckResult]) -> dict[str, int]:
    """Counts per status."""
    out: dict[str, int] = {s: 0 for s in ("pass", "fail", "warn", "skip", "needs-human", "signed")}
    for r in results:
        out[r.status] = out.get(r.status, 0) + 1
    return out
