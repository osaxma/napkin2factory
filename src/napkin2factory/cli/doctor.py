"""``n2f doctor``: is this machine ready? Checks Python, the OCP wheel, git, Typst, Playwright."""

from __future__ import annotations

import importlib
import importlib.util
import platform
import shutil
import sys

import typer

from napkin2factory import __version__
from napkin2factory.cli.common import JsonOption, console, emit_json


def _probe() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    py = sys.version.split()[0]
    rows.append(
        {
            "check": "python",
            "status": "ok" if sys.version_info >= (3, 13) else "warn",
            "detail": f"{py} ({platform.platform()})",
        }
    )
    try:
        import build123d  # noqa: F401

        rows.append(
            {"check": "build123d", "status": "ok", "detail": getattr(build123d, "__version__", "?")}
        )
    except Exception as exc:  # pragma: no cover - environment dependent
        rows.append(
            {
                "check": "build123d",
                "status": "fail",
                "detail": f"not importable: {exc}; run `uv sync`",
            }
        )
    try:
        import OCP  # noqa: F401

        vtk = importlib.util.find_spec("vtk") is not None
        rows.append(
            {
                "check": "OCP kernel",
                "status": "ok",
                "detail": "with VTK"
                if vtk
                else "novtk wheel (renders use the built-in rasterizer)",
            }
        )
    except Exception as exc:  # pragma: no cover
        rows.append({"check": "OCP kernel", "status": "fail", "detail": f"not importable: {exc}"})
    git = shutil.which("git")
    rows.append(
        {
            "check": "git (change tracking)",
            "status": "ok" if git else "fail",
            "detail": git or "not found; install git so snapshots and releases work",
        }
    )
    try:
        import typst  # noqa: F401

        rows.append(
            {"check": "typst (PDF manuals)", "status": "ok", "detail": "typst-py importable"}
        )
    except Exception as exc:  # pragma: no cover
        rows.append(
            {
                "check": "typst (PDF manuals)",
                "status": "warn",
                "detail": f"not importable: {exc}; PDFs will be skipped",
            }
        )
    if importlib.util.find_spec("playwright") is not None:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                b = p.chromium.launch()
                b.close()
            rows.append(
                {
                    "check": "playwright chromium (optional)",
                    "status": "ok",
                    "detail": "browser smoke tests available",
                }
            )
        except Exception:
            rows.append(
                {
                    "check": "playwright chromium (optional)",
                    "status": "warn",
                    "detail": "installed but no browser; run `uv run playwright install chromium`",
                }
            )
    else:
        rows.append(
            {
                "check": "playwright (optional)",
                "status": "warn",
                "detail": "not installed; only needed for browser tests",
            }
        )
    return rows


def doctor(json_out: bool = JsonOption) -> None:
    """Check that this machine can run napkin2factory, and say what to fix if not."""
    rows = _probe()
    if json_out:
        emit_json({"version": __version__, "checks": rows})
    else:
        console.print(f"napkin2factory {__version__}")
        for r in rows:
            mark = {"ok": "[green]✓[/green]", "warn": "[yellow]![/yellow]", "fail": "[red]✗[/red]"}[
                r["status"]
            ]
            console.print(f"  {mark} {r['check']}: {r['detail']}")
    if any(r["status"] == "fail" for r in rows):
        raise typer.Exit(code=4)
