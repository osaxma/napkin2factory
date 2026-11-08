"""``n2f mcp``: serve seven combined tools to an agent client over stdio (S-255, R14, S-327).

Experimental. Each step goes to the folder's warm engine (started if none
answers). The server needs the optional extra (``pip install "napkin2factory[mcp]"``);
without it this verb says so and stops. Every tool acts only inside the folder given here.
"""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path

import typer

from napkin2factory.cli.common import DirOption

INSTALL_LINE = (
    'The MCP server needs an extra package. Install it with: pip install "napkin2factory[mcp]" '
    '(or: uv tool install "napkin2factory[mcp]"), then run n2f mcp again.'
)


def _sdk_present() -> bool:
    """Is the protocol library installed?"""
    try:
        importlib.import_module("mcp")
        importlib.import_module("mcp.server.lowlevel")
    except ImportError:
        return False
    return True


def mcp(dir_: Path | None = DirOption) -> None:
    """Serve seven tools (init, napkin, promote, context, sync, decide, ecr) over stdio.

    Experimental; needs the mcp extra. Steps run in the folder's warm engine.

    Not this: `n2f serve` (the report on localhost) and `n2f engine` (a warm process that makes
    commands faster).
    """
    if not _sdk_present():
        typer.echo(INSTALL_LINE, err=True)
        raise typer.Exit(code=1)
    folder = (dir_ or Path.cwd()).resolve()
    if not folder.is_dir():
        typer.echo(f"✗ {folder} is not a folder", err=True)
        raise typer.Exit(code=1)
    from napkin2factory.mcp.server import serve

    asyncio.run(serve(folder))
