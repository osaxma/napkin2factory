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

__all__ = ["KERNEL_NOTE", "build", "load_cad_kernel", "targets"]

#: The names ``--help`` shows; every registered rule family is a target too (S-129).
TARGET_HELP = (
    "all (default), geometry, drawings, bom, docs, checks, report, site, or any build "
    "step's name (an unknown name lists them)"
)


def targets() -> tuple[str, ...]:
    """Every ``--target`` name, from the rule-family registry (F3, S-129).

    The names kept from v0.4 (``geometry``, ``drawings`` …) are the families' aliases; each
    family is a target by its own name too, so an installed domain's step is reachable here.
    """
    from napkin2factory.core.graph.rules import target_kinds

    return tuple(target_kinds())


@handle_errors
def build(
    dir: Path | None = DirOption,
    target: str = typer.Option("all", "--target", "-t", help=TARGET_HELP),
    part: str | None = typer.Option(None, "--part", "-p", help="Build only this part id."),
    asm: str | None = typer.Option(
        None, "--asm", help="Build one assembly and what it needs (its parts, sub-assemblies)."
    ),
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
    known = targets()
    if target not in known:
        raise typer.BadParameter(f"--target must be one of {', '.join(known)}")
    product = load_product(root)
    aid = None
    if asm is not None:
        from napkin2factory.cli.build_asm import assembly_id, check_target

        aid = assembly_id(product, asm)
        check_target(target)
    if explain:
        from napkin2factory.core.graph.runner import explain_build

        plan = explain_build(
            product,
            "drawings" if aid and target == "all" else target,
            render=not no_render,
            only_asm=aid,
        )
        if json_out:
            emit_json({"plan": [{"rule": r, "run": run, "why": why} for r, run, why in plan]})
        else:
            for rid, run, why in plan:
                mark = "[yellow]rebuild[/yellow]" if run else "[dim]keep   [/dim]"
                console.print(f"  {mark} {rid} [dim]({why})[/dim]")
        return
    load_cad_kernel()
    if aid is not None:
        from napkin2factory.cli.build_asm import build_assembly_alone

        summary = build_assembly_alone(
            product, aid, target, clean=clean, render=not no_render, quiet=json_out
        )
        if json_out:
            emit_json({**summary, "render_notes": _render_notes(product)})
        else:
            print_render_notes(product)
        return
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
