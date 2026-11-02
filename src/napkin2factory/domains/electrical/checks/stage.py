"""The ``electrical`` check stage (E6). Stub until M3: it reports no row yet."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # an installed domain is imported while the core's schemas load (S-153)
    from napkin2factory.core.checks.results import CheckResult
    from napkin2factory.core.domain import StageContext

#: The ``kind`` of every row this stage writes (the Verify gate row counts them).
ROW_KIND = "electrical"


def electrical_checks(sctx: StageContext) -> list[CheckResult]:
    """The wiring rows of ``n2f check`` (stub: none). Read the model through ``sctx.proxy``."""
    return []


def electrical_check_reads(product: Any) -> list[str]:
    """Keys the rows depend on that are not model fields (the ``elec:`` outputs; stub: none)."""
    return []
