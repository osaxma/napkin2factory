"""``CheckResult`` and status semantics (GRAND_PLAN M4).

Statuses: ``pass`` | ``fail`` | ``warn`` | ``skip`` | ``needs-human`` | ``signed``.
Only ``fail`` blocks (``warn`` never does, D10); ``needs-human`` blocks release until a
valid sign-off turns it into ``signed`` (D9/D25).

A sign-off flagged ``example: true`` (shipped with the example products) keeps the row
``signed`` and labelled, but the summary counts it under ``example`` rather than
``signed``: it is not a review and never verifies anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["pass", "fail", "warn", "skip", "needs-human", "signed"]
BLOCKING: frozenset[str] = frozenset({"fail"})
HUMAN: frozenset[str] = frozenset({"needs-human"})
#: Keys of the summary, in display order.  ``example`` is not a row status: it counts the
#: ``signed`` rows whose sign-off is an example (not a review).
SUMMARY_KEYS: tuple[str, ...] = ("pass", "fail", "warn", "skip", "needs-human", "signed", "example")


@dataclass
class CheckResult:
    """One row of the check matrix."""

    id: str
    subject: str
    status: str
    message: str
    persona_message: str = ""
    # requirement | rule | interface | interference | count | hardware | bom | doc | signoff
    # | reach (P5)
    kind: str = "requirement"
    evidence: dict[str, Any] = field(default_factory=dict)
    evidence_keys: dict[str, str] = field(default_factory=dict)
    safety: bool = False
    title: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    # P12: the build unit (module) the row belongs to; ``None`` is the whole product
    module: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON form."""
        return {
            "module": self.module,
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


def is_example_signoff(status: str, detail: dict[str, Any]) -> bool:
    """True for a ``signed`` row whose sign-off is flagged ``example`` (not a review)."""
    signoff = detail.get("signoff") or {}
    return status == "signed" and bool(signoff.get("example"))


def _example_noun(n: int) -> tuple[str, str]:
    noun = "example sign-off" if n == 1 else "example sign-offs"
    tail = "not a review" if n == 1 else "not reviews"
    return f"{n} {noun}", tail


def example_signoff_words(n: int) -> str:
    """``"4 example sign-offs (not reviews)"``: the CLI counter, the same in both personas."""
    head, tail = _example_noun(n)
    return f"{head} ({tail})"


def example_signoff_why(n: int) -> str:
    """``"4 example sign-offs — not reviews"``: the report header and the Verify gate's reason."""
    head, tail = _example_noun(n)
    return f"{head} — {tail}"


def summarize(results: list[CheckResult]) -> dict[str, int]:
    """Counts per status; ``signed`` holds real sign-offs only, ``example`` the example ones."""
    out: dict[str, int] = dict.fromkeys(SUMMARY_KEYS, 0)
    for r in results:
        key = "example" if is_example_signoff(r.status, r.detail) else r.status
        out[key] = out.get(key, 0) + 1
    return out
