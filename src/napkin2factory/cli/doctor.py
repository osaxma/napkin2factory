"""``n2f doctor``: is this machine ready, and what is installed?

It checks Python, the OCP wheel, git, Typst and Playwright, and lists the installed domains
with what each brings that an agent chooses between: verify kinds (how a requirement can be
checked), check stages (the rows of ``n2f check``) and napkin screens (F14, S-132). Every
name comes from the registries (``core/registry.py``); this module names none by hand.
"""

from __future__ import annotations

import importlib
import importlib.util
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

import typer

from napkin2factory import __version__
from napkin2factory.cli.common import JsonOption, console, emit_json


def _pin_row(start: Path | None = None, version: str = __version__) -> dict[str, str] | None:
    """The product's version pin vs the running version; None outside a product folder."""
    from napkin2factory.core.loader import MANIFEST, find_product_root
    from napkin2factory.core.model import Manifest
    from napkin2factory.core.yamlio import read_yaml

    root = find_product_root(start)
    if root is None:
        return None
    check = f"version pin ({root.name}/{MANIFEST})"
    try:
        manifest = Manifest.model_validate(read_yaml(root / MANIFEST))
    except Exception as exc:
        return {"check": check, "status": "warn", "detail": f"n2f.yaml unreadable: {exc}"}
    if manifest.pin_includes(version):
        return {"check": check, "status": "ok", "detail": f"{manifest.system} includes {version}"}
    return {
        "check": check,
        "status": "warn",
        "detail": f"{manifest.system} does not include {version}; it keeps working; once you "
        f"are happy with the results, set `system:` to a range that includes {version}",
    }


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


def _verify_kind(kind: Any) -> dict[str, Any]:
    """One verify kind as doctor shows it: what it targets and whether it compares a number."""
    return {
        "name": kind.name,
        "title": kind.title,
        "targets": [f"{s}://" for s in kind.target_schemes],
        "compares": kind.compares,
        "binary": kind.binary,
    }


def _screen(screen: Any) -> dict[str, Any]:
    """One napkin screen: its name, title, phase and the card fields it reads."""
    from napkin2factory.concepts.screens import fields_of, phase_of

    return {
        "name": screen.name,
        "title": screen.title,
        "phase": phase_of(screen),
        "fields": [f.name for f in fields_of(screen)],
    }


def installed_domains() -> list[dict[str, Any]]:
    """Every installed domain with what it registers, read from the registries (F14).

    Verify kinds, check stages (in run order) and screens are what doctor prints; the rest
    (rule families, gate rows, report sections, model families) is in ``--json`` only.
    """
    from napkin2factory.core.registry import registry

    reg = registry()
    stage_order = [s.name for s in reg.check_stages()]
    out: list[dict[str, Any]] = []
    for d in reg.domains:
        own_stages = {s.name: s for s in d.check_stages}
        out.append(
            {
                "name": d.name,
                "title": d.title,
                "verify_kinds": [_verify_kind(v) for v in d.verify_kinds],
                "check_stages": [
                    {
                        "name": n,
                        "after": list(own_stages[n].after),
                        "whole_product": own_stages[n].whole_product,
                    }
                    for n in stage_order
                    if n in own_stages
                ],
                "screens": [_screen(s) for s in d.screens],
                "rule_families": [f.name for f in d.rule_families],
                "gate_rows": [{"gate": r.gate, "title": r.title} for r in d.gate_rows],
                "report_sections": [s.id for s in d.report_sections],
                "model_families": [
                    {"name": f.name, "folder": f.folder, "scheme": f.uri_scheme} for f in d.families
                ],
            }
        )
    return out


def other_screens(root: Path | None) -> dict[str, Any]:
    """The napkin screens no domain brings: the system's own, and the product's (F10).

    ``product`` is ``None`` outside a product folder; ``error`` says why a product's
    ``model/screens/`` could not be read.
    """
    from napkin2factory.concepts.screens import GENERIC_SCREENS

    out: dict[str, Any] = {"system": [_screen(s) for s in GENERIC_SCREENS], "product": None}
    if root is not None:
        from napkin2factory.core.packs import product_screens

        try:
            out["product"] = [_screen(s) for s in product_screens(root)]
        except Exception as exc:
            out["product"] = []
            out["error"] = str(exc)
    return out


def _names(items: list[dict[str, Any]], show: Any = None) -> str:
    return ", ".join(show(i) if show else i["name"] for i in items) or "none"


def _kind_text(v: dict[str, Any]) -> str:
    what = [", ".join(v["targets"]) or "no target"]
    if v["compares"]:
        what.append("op and value")
    return f"{v['name']} ({'; '.join(what)})"


def _print_domains(domains: list[dict[str, Any]], screens: dict[str, Any]) -> None:
    console.print("Installed domains (a requirement's verify.kind must be one listed here):")
    for d in domains:
        console.print(f"  {d['name']}: {d['title']}" if d["title"] else f"  {d['name']}")
        console.print(f"    verify kinds: {_names(d['verify_kinds'], _kind_text)}")
        console.print(f"    check stages: {_names(d['check_stages'])}")
        console.print(f"    screens: {_names(d['screens'])}")
    console.print(f"  Napkin screens every product gets: {_names(screens['system'])}")
    if screens["product"] is not None:
        console.print(
            f"  This product's own screens (model/screens/): {_names(screens['product'])}"
        )
    if screens.get("error"):
        console.print(f"  [yellow]![/yellow] {screens['error']}")


def doctor(json_out: bool = JsonOption) -> None:
    """Check that this machine can run napkin2factory, and list the installed domains.

    The domains come with their verify kinds, check stages and napkin screens (F14).
    """
    from napkin2factory.core.loader import find_product_root

    rows = _probe()
    pin = _pin_row()
    if pin is not None:
        rows.append(pin)
    try:
        domains = installed_domains()
    except Exception as exc:  # a broken installed domain must not hide the machine checks
        domains = []
        rows.append(
            {"check": "installed domains", "status": "fail", "detail": f"cannot load: {exc}"}
        )
    screens = other_screens(find_product_root())
    if json_out:
        emit_json({"version": __version__, "checks": rows, "domains": domains, "screens": screens})
    else:
        console.print(f"napkin2factory {__version__}")
        for r in rows:
            mark = {"ok": "[green]✓[/green]", "warn": "[yellow]![/yellow]", "fail": "[red]✗[/red]"}[
                r["status"]
            ]
            console.print(f"  {mark} {r['check']}: {r['detail']}")
        if domains:
            _print_domains(domains, screens)
    if any(r["status"] == "fail" for r in rows):
        raise typer.Exit(code=4)
