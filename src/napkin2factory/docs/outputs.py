"""HTML and PDF outputs for a manual page (M5); M3 writes Markdown and reads.json only."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext


def write_doc_outputs(ctx: RunContext, doc: Any, rendered: Any) -> list[Path]:
    """Return the extra files written for a page (none until M5)."""
    return []
