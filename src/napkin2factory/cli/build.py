"""``n2f build`` (M2: ``--target geometry``; M3 routes every target through the DAG)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from napkin2factory.cli.common import (
    DirOption,
    JsonOption,
    console,
    emit_json,
    err_console,
    handle_errors,
    product_root,
)
from napkin2factory.core.loader import load_product

TARGETS = ("geometry", "drawings", "bom", "docs", "checks", "report", "site", "all")

KERNEL_NOTE = (
    "loading the CAD kernel (the first run on a machine can take a couple of minutes; "
    "later runs take seconds)…"
)


def load_cad_kernel() -> None:
    """Import build123d/OCP eagerly, announcing the first-import stall on stderr.

    The first ``import build123d`` in a fresh environment loads a ~140 MB native library
    and can take one to two minutes with no output; later imports take seconds. Printing
    the note *before* the import (to stderr, so ``--json`` output stays clean) tells the
    operator the command has not hung.
    """
    if "build123d" in sys.modules:
        return
    err_console.print(f"[dim]{KERNEL_NOTE}[/dim]")
    import build123d  # noqa: F401


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
