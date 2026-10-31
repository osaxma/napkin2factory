"""``n2f validate`` and ``n2f lint``."""

from __future__ import annotations

from pathlib import Path

import typer

from napkin2factory.cli.common import (
    DirOption,
    JsonOption,
    console,
    emit_json,
    handle_errors,
    print_problems,
    product_root,
    warn_if_pin_excludes,
)
from napkin2factory.core import lint as lint_mod
from napkin2factory.core.loader import validate as validate_mod


@handle_errors
def validate(dir: Path | None = DirOption, json_out: bool = JsonOption) -> None:
    """Check that the product model loads and every reference resolves."""
    root = product_root(dir)
    warn_if_pin_excludes(root, json_out)
    product, problems = validate_mod(root)
    if json_out:
        emit_json(
            {
                "ok": not problems.errors,
                "product": product.id if product else None,
                "problems": [p.to_dict() for p in problems.items],
                "counts": _counts(product),
            }
        )
    else:
        print_problems(problems, root)
        if problems.errors:
            console.print(f"[red]{len(problems.errors)} problem(s)[/red] in the product model")
        else:
            c = _counts(product)
            console.print(
                f"[green]✓[/green] model is consistent: {c['requirements']} requirements, "
                f"{c['parameters']} parameters, {c['parts']} parts, {c['assemblies']} assemblies, "
                f"{c['interfaces']} interfaces"
                + (f" ({len(problems.warnings)} warning(s))" if problems.warnings else "")
            )
    if problems.errors:
        raise typer.Exit(code=1)


@handle_errors
def lint(dir: Path | None = DirOption, json_out: bool = JsonOption) -> None:
    """Check requirement quality and model hygiene (stricter than validate)."""
    root = product_root(dir)
    product, problems = validate_mod(root)
    if product is not None and not problems.errors:
        problems.items.extend(lint_mod.lint(product).items)
    if json_out:
        emit_json({"ok": not problems.errors, "problems": [p.to_dict() for p in problems.items]})
    else:
        print_problems(problems, root)
        if problems.errors:
            console.print(f"[red]{len(problems.errors)} lint problem(s)[/red]")
        else:
            console.print(
                "[green]✓[/green] lint passed"
                + (f" with {len(problems.warnings)} warning(s)" if problems.warnings else "")
            )
    if problems.errors:
        raise typer.Exit(code=1)


def _counts(product: object) -> dict[str, int]:
    if product is None:
        return {}
    return {
        k: len(getattr(product, k))
        for k in (
            "requirements",
            "parameters",
            "parts",
            "assemblies",
            "interfaces",
            "decisions",
            "docs",
        )
    }
