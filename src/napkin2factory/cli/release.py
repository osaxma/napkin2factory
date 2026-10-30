"""``n2f release`` and ``n2f diff``."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.markup import escape

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
def release(
    version: str = typer.Argument(..., help="Revision name, e.g. v1.0.0"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Build the package and site preview without tagging or editing the model.",
    ),
    no_render: bool = typer.Option(False, "--no-render"),
    allow_example_signoffs: bool = typer.Option(
        False,
        "--allow-example-signoffs",
        help="Demonstrations only: release although safety sign-offs are EXAMPLES, not reviews.",
    ),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Freeze a Revision: checks must be green and every safety requirement signed."""
    from napkin2factory.ecr.release import release as do_release

    product = load_product(product_root(dir))
    result = do_release(
        product,
        version,
        dry_run=dry_run,
        render=not no_render,
        allow_example_signoffs=allow_example_signoffs,
    )
    if allow_example_signoffs and not json_out:
        console.print(
            "[yellow]EXAMPLE SIGN-OFFS: this Revision is a demonstration, "
            "not a reviewed design[/yellow]"
        )
    if json_out:
        emit_json(result)
        return
    tag = (
        "[yellow]dry run[/yellow] — nothing tagged"
        if dry_run
        else f"Revision [bold]{result['version']}[/bold] released"
    )
    console.print(f"[green]✓[/green] {tag}")
    console.print(f"  package: {escape(result['zip'])}")
    console.print(f"  site:    {escape(result['site'])}/index.html")
    if result["closed_ecrs"]:
        console.print(f"  includes: {', '.join(result['closed_ecrs'])}")


@handle_errors
def diff(
    ref_a: str = typer.Argument(..., help="Older Revision, e.g. v1.0.0"),
    ref_b: str = typer.Argument(..., help="Newer Revision, or 'working' for the current model"),
    out: Path | None = typer.Option(
        None, "--out", help="Folder for the page (default build/site/diff/A..B)."
    ),
    render: bool = typer.Option(
        False, "--render", help="Also render PNGs while building the refs (slower)."
    ),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Compare two Revisions: drawing overlays, BOM delta with cost impact, 3D side by side."""
    from napkin2factory.ecr.diff import diff as do_diff

    product = load_product(product_root(dir))
    result = do_diff(product, ref_a, ref_b, out=out, render=render)
    if json_out:
        emit_json({"page": result["page"], **result["delta"]})
        return
    d = result["delta"]
    console.print(
        f"[green]✓[/green] {ref_a} → {ref_b}: {len(d['parts'])} part(s) differ, "
        f"cost {d['totals']['cost_delta']:+.2f} USD, mass {d['totals']['mass_delta']:+.3f} kg"
    )
    for p in d["parts"]:
        console.print(f"  {p['state']:8} {p['uri']} (rev {p['rev']})")
    console.print(f"  page: {escape(result['page'])}")
