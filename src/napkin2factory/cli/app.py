"""Typer application root for the ``n2f`` command (GRAND_PLAN §5)."""

from __future__ import annotations

import typer

from napkin2factory import __version__
from napkin2factory.cli import build as build_cmd
from napkin2factory.cli import check as check_cmd
from napkin2factory.cli import concept as concept_cmd
from napkin2factory.cli import context as context_cmd
from napkin2factory.cli import doctor as doctor_cmd
from napkin2factory.cli import ecr as ecr_cmd
from napkin2factory.cli import graph as graph_cmd
from napkin2factory.cli import init as init_cmd
from napkin2factory.cli import publish as publish_cmd
from napkin2factory.cli import release as release_cmd
from napkin2factory.cli import serve as serve_cmd
from napkin2factory.cli import snapshot as snapshot_cmd
from napkin2factory.cli import validate as validate_cmd

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
def version(json_out: bool = typer.Option(False, "--json")) -> None:
    """Print the installed napkin2factory version."""
    if json_out:
        typer.echo(f'{{"version": "{__version__}"}}')
    else:
        typer.echo(f"napkin2factory {__version__}")


app.command("init")(init_cmd.init)
app.command("validate")(validate_cmd.validate)
app.command("lint")(validate_cmd.lint)
app.command("build")(build_cmd.build)
app.command("graph")(graph_cmd.graph)
app.command("check")(check_cmd.check)
app.command("status")(check_cmd.status)
app.command("signoff")(check_cmd.signoff)
app.command("context")(context_cmd.context)
app.command("serve")(serve_cmd.serve)
app.command("snapshot")(snapshot_cmd.snapshot)
app.command("discard")(snapshot_cmd.discard)
app.command("doctor")(doctor_cmd.doctor)
app.add_typer(ecr_cmd.ecr_app, name="ecr")
app.add_typer(concept_cmd.concept_app, name="concept")
app.command("release")(release_cmd.release)
app.command("diff")(release_cmd.diff)
app.command("publish")(publish_cmd.publish)
app.command("impact")(graph_cmd.impact)


def main() -> None:
    """Entry point used by the ``n2f`` console script."""
    app()
