"""Shared CLI plumbing: output, exit codes, product-root discovery, persona vocabulary."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

import typer
from rich.console import Console
from rich.markup import escape

from napkin2factory.core.errors import N2FError, Problems
from napkin2factory.core.loader import MANIFEST, find_product_root

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

P = ParamSpec("P")
R = TypeVar("R")


def product_root(path: Path | None) -> Path:
    """Resolve the product directory from ``--dir`` or the current directory."""
    if path is not None:
        p = Path(path).resolve()
        if not (p / MANIFEST).is_file():
            raise N2FError(
                f"{p} isn't a napkin2factory product folder (no {MANIFEST}); "
                "run `n2f init <dir>` to start one"
            )
        return p
    found = find_product_root()
    if found is None:
        raise N2FError(
            f"this folder isn't a napkin2factory product (no {MANIFEST} here or above); "
            "cd into a product folder or run `n2f init <dir>` to start one"
        )
    return found


def emit_json(payload: dict[str, Any]) -> None:
    """Print a JSON document to stdout."""
    sys.stdout.write(json.dumps(payload, indent=2, default=str) + "\n")


def print_problems(problems: Problems, root: Path) -> None:
    """Print findings grouped by severity, in persona-friendly form."""
    for p in problems.errors:
        err_console.print(f"[red]✗[/red] {escape(p.format(root))}")
    for p in problems.warnings:
        err_console.print(f"[yellow]![/yellow] {escape(p.format(root))}")


def handle_errors(fn: Callable[P, R]) -> Callable[P, R]:
    """Translate :class:`N2FError` into the exit codes of GRAND_PLAN §5."""

    @wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except N2FError as exc:
            err_console.print(f"[red]✗[/red] {escape(str(exc))}")
            detail = getattr(exc, "detail", "")
            if detail and "--json" in sys.argv:
                emit_json({"error": str(exc), "detail": detail, "code": getattr(exc, "code", "")})
            raise typer.Exit(code=exc.exit_code) from exc

    return wrapper


DirOption = typer.Option(None, "--dir", "-C", help="Product folder (default: the current one).")
JsonOption = typer.Option(False, "--json", help="Machine-readable output.")
