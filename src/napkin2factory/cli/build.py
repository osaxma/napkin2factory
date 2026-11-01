"""``n2f build`` (M2: ``--target geometry``; M3 routes every target through the DAG)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import typer

from napkin2factory.cli.common import (
    DirOption,
    JsonOption,
    console,
    emit_json,
    handle_errors,
    product_root,
    warn_if_pin_excludes,
)
from napkin2factory.cli.kernel import KERNEL_NOTE, load_cad_kernel
from napkin2factory.core.loader import Product, load_product

__all__ = ["KERNEL_NOTE", "build", "load_cad_kernel"]

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
    explain: bool = typer.Option(False, "--explain", help="Dry run: what would rebuild, and why."),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Skip the vendor-link check of the BOM (same as N2F_OFFLINE=1).",
    ),
    json_out: bool = JsonOption,
) -> None:
    """Generate 3D, drawings, BOM, manuals, checks and the report from the model."""
    if offline:
        os.environ["N2F_OFFLINE"] = "1"
    root = product_root(dir)
    warn_if_pin_excludes(root, json_out)
    if target not in TARGETS:
        raise typer.BadParameter(f"--target must be one of {', '.join(TARGETS)}")
    product = load_product(root)
    if explain:
        from napkin2factory.core.graph.runner import explain_build

        plan = explain_build(product, target, render=not no_render)
        if json_out:
            emit_json({"plan": [{"rule": r, "run": run, "why": why} for r, run, why in plan]})
        else:
            for rid, run, why in plan:
                mark = "[yellow]rebuild[/yellow]" if run else "[dim]keep   [/dim]"
                console.print(f"  {mark} {rid} [dim]({why})[/dim]")
        return
    load_cad_kernel()
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
                    "render_notes": _render_notes(product),
                }
            )
        else:
            console.print(
                f"[green]✓[/green] geometry: {len(parts)} parts, {len(asms)} assemblies "
                f"→ {product.paths.build}"
            )
            print_render_notes(product)
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
        emit_json({**summary, "render_notes": _render_notes(product)})
    else:
        print_render_notes(product)


def _render_notes(product: Product) -> dict[str, Any]:
    from napkin2factory.geometry.build import render_notes

    return render_notes(product)


def print_render_notes(product: Product) -> None:
    """Print what the pictures had to remark (S-088), in plain words, after the summary."""
    from rich.markup import escape

    from napkin2factory.geometry.build import render_note_lines

    for line in render_note_lines(product, _render_notes(product)):
        console.print(f"  [yellow]note[/yellow] {escape(line)}", highlight=False)
