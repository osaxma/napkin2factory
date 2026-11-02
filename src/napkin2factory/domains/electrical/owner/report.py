"""The report's "Wiring" section (F5; filled in M4): diagrams, schedule, circuit rows."""

from __future__ import annotations

from typing import Any

from napkin2factory.core.domain import ReportSection, SectionContext
from napkin2factory.domains.electrical.model import has_content


def wiring_report_data(sctx: SectionContext) -> dict[str, Any]:
    """What the section shows (stub: nothing yet). Read the model through ``sctx.proxy``."""
    return {}


def wiring_report_reads(product: Any) -> list[str]:
    """Keys the section shows that are not model fields (the ``elec:`` outputs; stub: none)."""
    return []


def show_wiring(product: Any) -> bool:
    """The section is on the page only when the product has wiring content."""
    return has_content(product)


REPORT_SECTIONS = (
    ReportSection(
        "wiring",
        "Wiring",
        group="Product",
        fragment="owner/wiring.html.j2",
        data=wiring_report_data,
        reads=wiring_report_reads,
        show=show_wiring,
    ),
)
