"""``n2f graph``: the DAG as DOT or JSON, optionally around one URI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.graph.rules import build_rules
from napkin2factory.core.loader import Product


def graph_data(
    product: Product, build_dir: Path | None = None, around: str | None = None
) -> dict[str, Any]:
    """Nodes (rules) and edges (reads → producer) from the manifest, else static deps."""
    build_dir = build_dir or product.paths.build
    manifest = Manifest.load(build_dir)
    rules = build_rules(product)
    producer = {r.produces: r.id for r in rules if r.produces}
    nodes = []
    edges: list[dict[str, str]] = []
    for r in rules:
        entry = manifest.entries.get(r.id)
        nodes.append(
            {
                "id": r.id,
                "kind": r.kind,
                "produces": r.produces,
                "built": entry is not None,
                "reads": entry.reads if entry else [],
            }
        )
        deps: set[str] = set(r.depends_on)
        if entry is not None:
            for k in entry.reads:
                base = k.split("#", 1)[0]
                if base in producer and producer[base] != r.id:
                    deps.add(producer[base])
                if k in producer:
                    deps.add(producer[k])
        for d in sorted(deps):
            edges.append({"from": d, "to": r.id})
    if around:
        keep = _neighbourhood(around, nodes, edges, producer)
        nodes = [n for n in nodes if n["id"] in keep]
        edges = [e for e in edges if e["from"] in keep and e["to"] in keep]
    return {"nodes": nodes, "edges": edges}


def _neighbourhood(
    around: str, nodes: list[dict[str, Any]], edges: list[dict[str, str]], producer: dict[str, str]
) -> set[str]:
    start = producer.get(around, around)
    keep = {start}
    for n in nodes:
        if around in n["reads"] or any(k.split("#")[0] == around for k in n["reads"]):
            keep.add(n["id"])
    changed = True
    while changed:
        changed = False
        for e in edges:
            if e["from"] in keep and e["to"] not in keep:
                keep.add(e["to"])
                changed = True
    for e in edges:
        if e["to"] == start:
            keep.add(e["from"])
    return keep


def to_dot(data: dict[str, Any]) -> str:
    """Graphviz DOT text."""
    colors = {
        "validate": "gray",
        "part": "lightblue",
        "asm": "lightgreen",
        "drawing": "khaki",
        "bom": "orange",
        "asmsheet": "wheat",
        "doc": "plum",
        "checks": "salmon",
        "report": "gold",
        "site": "white",
    }
    lines = ["digraph n2f {", "  rankdir=LR;", "  node [shape=box, style=filled];"]
    for n in data["nodes"]:
        style = "" if n["built"] else ', style="filled,dashed"'
        lines.append(f'  "{n["id"]}" [fillcolor={colors.get(n["kind"], "white")}{style}];')
    for e in data["edges"]:
        lines.append(f'  "{e["from"]}" -> "{e["to"]}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


def to_json(data: dict[str, Any]) -> str:
    """Pretty JSON."""
    return json.dumps(data, indent=2) + "\n"
