"""Typer application root for the ``n2f`` command (GRAND_PLAN §5)."""

from __future__ import annotations

import json
import shlex
import sys

import typer

from napkin2factory import __version__
from napkin2factory.cli import build as build_cmd
from napkin2factory.cli import check as check_cmd
from napkin2factory.cli import concept as concept_cmd
from napkin2factory.cli import context as context_cmd
from napkin2factory.cli import decide as decide_cmd
from napkin2factory.cli import docs as docs_cmd
from napkin2factory.cli import doctor as doctor_cmd
from napkin2factory.cli import ecr as ecr_cmd
from napkin2factory.cli import engine as engine_cmd
from napkin2factory.cli import graph as graph_cmd
from napkin2factory.cli import init as init_cmd
from napkin2factory.cli import mcp as mcp_cmd
from napkin2factory.cli import publish as publish_cmd
from napkin2factory.cli import release as release_cmd
from napkin2factory.cli import serve as serve_cmd
from napkin2factory.cli import skill as skill_cmd
from napkin2factory.cli import snapshot as snapshot_cmd
from napkin2factory.cli import undo as undo_cmd
from napkin2factory.cli import validate as validate_cmd

EPILOG = "\n\n".join(
    [
        "[bold]Start here[/bold]",
        "1. `n2f version` (is it installed?), then `n2f doctor` (is this machine ready?)",
        "2. `n2f init <dir>` makes the product folder; work in it from now on",
        "3. Shape the design: `n2f concept new` and the other `n2f concept` verbs, then the "
        "files under `model/`",
        "4. `n2f build`, then `n2f check`; open `build/report/index.html`, or `n2f serve`",
        "[bold]For an agent[/bold]",
        'Every verb takes `--json` (stdout is then one JSON object; an error is `{"error", '
        '"message", "next"}`) except `graph` (`--format json`), `serve`, `mcp`, `skill`.',
        "Exit codes: 0 ok; 1 the model or the command failed (the message says what to do); "
        "2 a usage error (a bad option or verb: fix the command line); 3 a gate refused "
        "(release, change request, promote); 4 a problem with this machine; 5 a failed check "
        "(fix the design); 70 the warm engine stopped under a command that changes the product "
        "(the message says what to look at and what to run).",
        "Every product verb takes `--dir <folder>` (`-C`), so you never have to change directory.",
        "Commands run in a warm per-product process that `n2f init` starts: "
        "`n2f engine status`; `N2F_NO_ENGINE=1` turns it off.",
        "`n2f docs` lists the rest.",
    ]
)

app = typer.Typer(
    name="n2f",
    help="napkin2factory: from napkin to factory.",
    epilog=EPILOG,
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
app.command("decide")(decide_cmd.decide)
app.command("context")(context_cmd.context)
app.command("serve")(serve_cmd.serve)
app.command("snapshot")(snapshot_cmd.snapshot)
app.command("discard")(snapshot_cmd.discard)
undo_cmd.register(app)
app.command("doctor")(doctor_cmd.doctor)
app.command("docs")(docs_cmd.docs)
app.add_typer(ecr_cmd.ecr_app, name="ecr")
app.add_typer(concept_cmd.concept_app, name="concept")
app.add_typer(engine_cmd.engine_app(), name="engine")
app.command("release")(release_cmd.release)
app.command("diff")(release_cmd.diff)
app.command("publish")(publish_cmd.publish)
app.command("impact")(graph_cmd.impact)
app.command("mcp")(mcp_cmd.mcp)
app.command("skill")(skill_cmd.skill)


def run_app(args: list[str], prog_name: str | None = None) -> None:
    """Run the ``n2f`` command line ``args`` and exit with its code (the one entry, S-313).

    The CLI and the warm engine both call this, so a command reads the same either way. Under
    ``--json`` a usage error (a bad option, an unknown verb) is one JSON object on stdout like
    the other errors: ``{"error": "usage_error", "message", "next"}``, exit 2; in text mode
    click and typer print theirs as they always did.
    """
    if "--json" not in args:
        app(args=args, prog_name=prog_name)
        return
    try:
        rv = app(args=args, prog_name=prog_name, standalone_mode=False)
    except Exception as exc:
        # click's exception classes: typer carries its own copy of click, so they are told apart
        # by what they have rather than imported
        if type(exc).__name__ == "Abort":
            sys.stderr.write("Aborted!\n")
            raise SystemExit(1) from None
        if not (hasattr(exc, "format_message") and hasattr(exc, "exit_code")):
            raise
        ctx = getattr(exc, "ctx", None)
        names: list[str] = []
        while ctx is not None and ctx.parent is not None:
            names.insert(0, str(ctx.info_name))
            ctx = ctx.parent
        helper = shlex.join(["n2f", *names, "--help"])
        message = exc.format_message()
        sys.stderr.write(f"Error: {message}\n")
        sys.stdout.write(
            json.dumps(
                {"error": "usage_error", "message": message, "next": f"run `{helper}`"}, indent=2
            )
            + "\n"
        )
        raise SystemExit(exc.exit_code) from None
    raise SystemExit(rv if isinstance(rv, int) else 0)


def main() -> None:
    """Entry point kept for installs whose ``n2f`` script still points here (see ``entry.py``)."""
    from napkin2factory.cli.entry import main as entry_main

    entry_main()
