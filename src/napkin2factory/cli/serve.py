"""``n2f serve``: a local HTTP server for the report (convenience only; file:// works too)."""

from __future__ import annotations

import functools
import http.server
import socketserver
from pathlib import Path

import typer

from napkin2factory.cli.common import DirOption, console, handle_errors, product_root
from napkin2factory.core.errors import N2FError


@handle_errors
def serve(
    dir: Path | None = DirOption,
    port: int = typer.Option(8765, "--port", "-p"),
    site: bool = typer.Option(
        False, "--site", help="Serve build/site (versions and diffs) instead of the latest report."
    ),
) -> None:
    """Serve the generated report on localhost (the report also opens straight from disk)."""
    root = product_root(dir)
    folder = root / "build" / ("site" if site else "report")
    if not (folder / "index.html").is_file():
        raise N2FError(f"nothing to serve yet in {folder}; run `n2f build` first")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        console.print(f"serving {folder} at http://127.0.0.1:{port}/  (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            console.print("stopped")
