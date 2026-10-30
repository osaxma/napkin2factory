"""BOM CSV and XLSX writers (M5); M3 writes nothing beyond rollups.json."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext


def write_bom_files(ctx: RunContext, rollups: dict[str, Any]) -> list[Path]:
    """Return the extra files written for the BOM (none until M5)."""
    return []
