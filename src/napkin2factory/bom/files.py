"""BOM validation (D15) now; CSV and XLSX writers arrive at M5."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext


def write_bom_files(ctx: RunContext, rollups: dict[str, Any]) -> list[Path]:
    """Write ``validation.json`` (and, from M5, CSV/XLSX); return the files written."""
    from napkin2factory.bom.validation import validate_bom

    out_dir = ctx.build_dir / "bom"
    out_dir.mkdir(parents=True, exist_ok=True)
    validation = validate_bom(ctx.product, ctx.build_dir)
    path = out_dir / "validation.json"
    path.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [path]
