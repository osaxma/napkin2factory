"""``n2f build`` (M2: ``--target geometry``; M3 routes every target through the DAG)."""

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

TARGETS = ("geometry", "drawings", "bom", "docs", "checks", "report", "site", "all")


@handle_errors
def build(
    dir: Path | None = DirOption,
    target: str = typer.Option("all", "--target", "-t", help="|".join(TARGETS)),
    part: str | None = typer.Option(None, "--part", "-p", help="Build only this part id."),
    clean: bool = typer.Option(
        False, "--clean", help="Forget what was built before and rebuild everything."
    ),
    jobs: int = typer.Option(1, "--jobs", "-j", help="Parallel workers for independent parts."),
    no_render: bool = typer.Option(False, "--no-render", help="Skip PNG renders (faster)."),
    json_out: bool = JsonOption,
) -> None:
    """Generate 3D, drawings, BOM, manuals, checks and the report from the model."""
    root = product_root(dir)
    if target not in TARGETS:
        raise typer.BadParameter(f"--target must be one of {', '.join(TARGETS)}")
    product = load_product(root)
    if target == "geometry":
        from napkin2factory.geometry.build import build_geometry

        parts, asms = build_geometry(
            product,
            only_part=part,
            render=not no_render,
            log=None if json_out else lambda m: console.print(f"  built {m}"),
        )
        if json_out:
            emit_json(
                {
                    "parts": {k: v.props for k, v in parts.items()},
                    "assemblies": {k: v.props for k, v in asms.items()},
                }
            )
        else:
            console.print(
                f"[green]✓[/green] geometry: {len(parts)} parts, {len(asms)} assemblies "
                f"→ {product.paths.build}"
            )
        return
    from napkin2factory.core.graph.runner import run_build

    summary = run_build(
        product,
        target=target,
        only_part=part,
        clean=clean,
        jobs=jobs,
        render=not no_render,
        quiet=json_out,
    )
    if json_out:
        emit_json(summary)
