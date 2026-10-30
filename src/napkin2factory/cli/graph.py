"""``n2f graph`` and ``n2f impact``."""

from __future__ import annotations

from pathlib import Path

import typer

from napkin2factory.cli.common import (
    DirOption,
    JsonOption,
    console,
    emit_json,
    handle_errors,
    product_root,
)
from napkin2factory.core.loader import load_product


@handle_errors
def graph(
    dir: Path | None = DirOption,
    format: str = typer.Option("dot", "--format", "-f", help="dot | json"),
    around: str | None = typer.Option(None, "--around", help="Only the neighbourhood of this URI."),
) -> None:
    """Show what depends on what (for engineers; Graphviz or JSON format)."""
    from napkin2factory.core.graph.export import graph_data, to_dot, to_json

    product = load_product(product_root(dir))
    data = graph_data(product, around=around)
    typer.echo(to_dot(data) if format == "dot" else to_json(data), nl=False)


@handle_errors
def impact(
    dir: Path | None = DirOption,
    ecr: str | None = typer.Option(None, "--ecr", help="Change request id, e.g. ECR-001."),
    set_: list[str] = typer.Option(
        [], "--set", help="Hypothetical edit <uri>=<value>; repeatable."
    ),
    json_out: bool = JsonOption,
) -> None:
    """Report what a change would touch, before anything changes."""
    from napkin2factory.core.errors import N2FError
    from napkin2factory.core.graph.impact import compute_impact, parse_set, summarize

    product = load_product(product_root(dir))
    edits = [parse_set(s) for s in set_]
    kind, tasks = "parametric", []
    if ecr:
        if ecr not in product.ecrs:
            raise N2FError(f"change request {ecr} does not exist; `n2f ecr list` shows them")
        e = product.ecrs[ecr]
        edits = list(e.edits) + edits
        kind, tasks = e.kind, list(e.tasks)
    if not edits and kind == "parametric":
        raise N2FError("nothing to assess: pass --ecr ECR-xxx or --set param://x=50mm")
    report = compute_impact(product, edits, kind=kind, tasks=tasks)
    if json_out:
        emit_json(report.to_dict())
    else:
        console.print(summarize(report, product), markup=False)
