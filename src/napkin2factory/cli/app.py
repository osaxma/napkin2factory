"""Typer application root for the ``n2f`` command."""

from __future__ import annotations

import typer

from napkin2factory import __version__

app = typer.Typer(
    name="n2f",
    help="napkin2factory: from napkin to factory.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


@app.callback()
def _root() -> None:
    """napkin2factory turns a text-only product model into a manufacturable package."""


@app.command()
def version() -> None:
    """Print the installed napkin2factory version."""
    typer.echo(f"napkin2factory {__version__}")


def main() -> None:
    """Entry point used by the ``n2f`` console script."""
    app()
