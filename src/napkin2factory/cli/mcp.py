"""``n2f mcp``: serve the verbs as tools to an agent client over stdio (S-255, R14).

Experimental. The server needs the optional extra (``pip install "napkin2factory[mcp]"``);
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
    """Serve the n2f verbs as tools over stdio (experimental); needs the mcp extra."""
    if not _sdk_present():
        typer.echo(INSTALL_LINE, err=True)
        raise typer.Exit(code=1)
    folder = (dir_ or Path.cwd()).resolve()
    if not folder.is_dir():
        typer.echo(f"✗ {folder} is not a folder", err=True)
        raise typer.Exit(code=1)
    from napkin2factory.mcp.server import serve

    asyncio.run(serve(folder))
