"""The ``circuit`` verify kind (``circuit://<id>#load_current`` …). Stub until M3."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # an installed domain is imported while the core's schemas load (S-153)
    from napkin2factory.core.checks.results import CheckResult


def evaluate_circuit(ctx: Any, req: Any, res: CheckResult, evidence: dict[str, str]) -> str | None:
    """A circuit's figure against the requirement's ``op``/``value`` (stub: skipped)."""
    res.message = f"{req.verify.target}: the wiring checks are not in this version yet"
    return "skip"
