"""``report`` run (M3 placeholder; M5 builds the real self-contained page)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from napkin2factory.core.graph.hashing import sha256_text

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext, RunResult


def report_reads(ctx: RunContext) -> list[str]:
    """The report depends on every artifact: checks, parts, assemblies, drawings, docs, BOM."""
    product = ctx.product
    reads = ["rule:checks", "bom://rollups"]
    reads += [p.uri for p in product.parts_with_geometry()]
    reads += [f"drawing://{p.id}" for p in product.parts_with_geometry()]
    reads += [a.uri for a in product.assemblies.values()]
    reads += [f"doc://{d}" for d in product.docs]
    reads += [f"req://{r}#title" for r in product.requirements]
    reads += [f"dec://{d}#title" for d in product.decisions]
    reads += [f"ecr://{e}#status" for e in product.ecrs]
    reads += [
        "set://parts",
        "set://asms",
        "set://docs",
        "set://reqs",
        "set://decs",
        "set://ecrs",
        "set://signoffs",
        "set://params",
        "set://ifaces",
    ]
    return reads


def build_report(ctx: RunContext) -> RunResult:
    """Write a placeholder page listing the product (M5 replaces)."""
    import json

    from napkin2factory.core.graph.rules import RunResult

    name = ctx.product.manifest.product.name
    hashes = []
    for sub in ("parts", "assemblies"):
        for props in sorted((ctx.build_dir / sub).glob("*/props.json")):
            data = json.loads(props.read_text(encoding="utf-8"))
            hashes.append(f"<li>{data.get('uri')}: {data.get('tess_hash', data.get('mass'))}</li>")
    html = (
        f"<!doctype html><html><head><meta charset='utf-8'><title>{name}</title></head>"
        f"<body><h1>{name}</h1><p>placeholder report (M5)</p><ul>{''.join(hashes)}</ul>"
        "</body></html>\n"
    )
    out = ctx.build_dir / "report" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return RunResult(reads=report_reads(ctx), outputs=[out], output_hash=sha256_text(html))
