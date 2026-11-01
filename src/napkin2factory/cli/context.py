"""``n2f context asm://<id> [--json]``: one module's working context (P6, M4).

The text form is Markdown for an agent to read; ``--json`` is the same content for tools.
Nothing is built or written: the parameters a module reads come from the last build.
"""

from __future__ import annotations

from pathlib import Path

import typer

from napkin2factory.cli.build_asm import assembly_id
from napkin2factory.cli.common import (
    DirOption,
    JsonOption,
    emit_json,
    handle_errors,
    product_root,
    warn_if_pin_excludes,
)
from napkin2factory.core.loader import load_product


@handle_errors
def context(
    module: str = typer.Argument(..., help="The assembly, e.g. asm://door"),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Print one module's working context: its files, sizes, joints and requirements."""
    from napkin2factory.core.context import module_context, render_text

    root = product_root(dir)
    warn_if_pin_excludes(root, json_out)
    product = load_product(root)
    data = module_context(product, assembly_id(product, module))
    if json_out:
        emit_json(data)
    else:
        typer.echo(render_text(data), nl=False)
