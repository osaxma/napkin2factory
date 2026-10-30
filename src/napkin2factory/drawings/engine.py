"""``drawing:<id>`` run (M3 placeholder; M5 implements the real views and DXF)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from napkin2factory.core.graph.hashing import sha256_text

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext, RunResult


def make_drawing(ctx: RunContext, part_id: str) -> RunResult:
    """Write a minimal SVG naming the part (placeholder) and record the part read."""
    from napkin2factory.core.graph.rules import RunResult

    part = ctx.product.parts[part_id]
    props_path = ctx.build_dir / "parts" / part_id / "props.json"
    props = json.loads(props_path.read_text(encoding="utf-8")) if props_path.is_file() else {}
    bb = props.get("bbox", {})
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="120" '
        'viewBox="0 0 400 120">'
        f'<g id="titleblock"><text x="10" y="30" font-size="14">{part.uri} rev {part.rev}</text>'
        f'<text x="10" y="60" font-size="12">bbox {bb.get("x")} × {bb.get("y")} × '
        f"{bb.get('z')} mm</text>"
        '<text x="10" y="90" font-size="10">placeholder drawing (M5 replaces)</text></g></svg>\n'
    )
    out = ctx.build_dir / "drawings" / f"{part_id}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    reads = [part.uri, f"{part.uri}#rev"]
    return RunResult(reads=reads, outputs=[out], output_hash=sha256_text(svg))
