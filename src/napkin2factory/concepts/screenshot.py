"""Styled concept screenshots: the inline viewer, ``style.yaml`` materials, a studio rig (N6).

One self-contained HTML page per card (the report's inline module machinery, the massing
GLB as base64, zero external references) boots the viewer with per-part materials from the
resolved style (each massing call's role → palette colour and finish), the fixed studio
lighting and a preset camera; headless Chromium snapshots ``iso`` and ``front`` at
1200 × 900 into ``renders/styled-iso.png`` and ``renders/styled-front.png``.

:class:`ScreenshotSession` keeps one browser page for a whole ``n2f concept build --all``.
When Playwright is missing, Chromium will not start, or ``N2F_NO_PLAYWRIGHT=1`` is set, the
z-buffer ``iso.png``/``front.png`` are copied to the styled names instead and the card says
so (``[revisit]``): z-buffer renders are for correctness, viewer screenshots for appearance
(D12 as amended by S-059 and N6).
"""

from __future__ import annotations

import base64
import html
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.model.style import StyleFile, role_for

#: Snapshot size in CSS pixels (device scale 1): at least 1200 px wide (N6).
VIEWPORT: tuple[int, int] = (1200, 900)
#: The views written, in order, as ``styled-<view>.png``.
VIEWS: tuple[str, ...] = ("iso", "front")
#: Software WebGL so the screenshots work on machines without a GPU (as the report test).
CHROMIUM_ARGS: tuple[str, ...] = ("--use-gl=swiftshader", "--enable-unsafe-swiftshader")
#: Set to 1 to force the z-buffer fallback (tests, machines without a browser).
NO_PLAYWRIGHT_ENV = "N2F_NO_PLAYWRIGHT"

Method = Literal["viewer", "zbuffer-fallback"]


@dataclass
class ScreenshotResult:
    """What :func:`styled_screenshots` wrote and how."""

    paths: dict[str, Path] = field(default_factory=dict)
    method: Method = "viewer"
    notes: list[str] = field(default_factory=list)

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        """JSON form (paths relative to ``root`` when given)."""

        def rel(p: Path) -> str:
            if root is not None:
                try:
                    return p.relative_to(root).as_posix()
                except ValueError:
                    pass
            return str(p)

        return {
            "method": self.method,
            "paths": {k: rel(v) for k, v in self.paths.items()},
            "notes": list(self.notes),
        }


def fallback_note(why: str) -> str:
    """The card note for the z-buffer fallback."""
    return f"styled screenshots unavailable ({why}): showing correctness renders [revisit]"


def card_materials(card: ConceptCard, style: StyleFile) -> dict[str, dict[str, Any]]:
    """Viewer materials by GLB node URI: each massing call's role → colour and finish."""
    from napkin2factory.concepts.massing import concept_uri

    return {concept_uri(card.id, c.as_): style.material(role_for(c)) for c in card.massing}


def styled_page(glb: bytes, materials: dict[str, dict[str, Any]], style: StyleFile) -> str:
    """One self-contained page: the inline viewer bundle, the GLB, studio options."""
    from napkin2factory.report.inline import bundle_viewer, inline_module_script

    options = {
        "background": style.background,
        "materials": materials,
        "lighting": "studio",
        "camera": "iso",
        "transparent": False,
    }
    w, h = VIEWPORT
    return (
        '<!doctype html>\n<html><head><meta charset="utf-8"><title>styled concept</title>'
        f"<style>html,body{{margin:0;padding:0;overflow:hidden;background:{style.background}}}"
        f"#viewer{{width:{w}px;height:{h}px}}</style></head><body>\n"
        f'<div id="viewer" data-n2f-glb="glb-data" '
        f'data-n2f-options="{html.escape(json.dumps(options, sort_keys=True))}"></div>\n'
        f'<script type="text/plain" id="glb-data">{base64.b64encode(glb).decode()}</script>\n'
        f"{inline_module_script(bundle_viewer())}\n</body></html>\n"
    )


class ScreenshotSession:
    """One headless Chromium page reused across cards; started on first use.

    Use as a context manager.  When the browser cannot be had, :attr:`unavailable` says why
    and every card falls back to the z-buffer renders; the reason is printed once.
    """

    def __init__(self) -> None:
        self._pw: Any = None
        self._browser: Any = None
        self._page: Any = None
        self._errors: list[str] = []
        self.unavailable: str | None = None
        self._started = False
        self._warned = False

    def __enter__(self) -> ScreenshotSession:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def page(self) -> Any:
        """The shared page, or ``None`` (with :attr:`unavailable` set) when there is none."""
        if not self._started:
            self._started = True
            self._start()
        return self._page

    def _start(self) -> None:
        if os.environ.get(NO_PLAYWRIGHT_ENV) == "1":
            self.unavailable = f"{NO_PLAYWRIGHT_ENV}=1 is set"
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.unavailable = "Playwright is not installed"
            return
        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(args=list(CHROMIUM_ARGS))
            w, h = VIEWPORT
            self._page = self._browser.new_page(
                viewport={"width": w, "height": h}, device_scale_factor=1
            )
        except Exception as exc:  # playwright Error, missing browser binary, sandbox refusals
            first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
            self.unavailable = f"Chromium did not start: {first}"
            self.close()
            return
        self._page.on("pageerror", lambda e: self._errors.append(str(e)))
        self._page.on(
            "console", lambda m: self._errors.append(m.text) if m.type == "error" else None
        )

    def take_errors(self) -> list[str]:
        """Page errors since the last call."""
        errors, self._errors = self._errors, []
        return errors

    def warn(self, note: str) -> None:
        """Print ``note`` dim on stderr, once per session."""
        if self._warned:
            return
        self._warned = True
        from rich.console import Console
        from rich.markup import escape

        Console(stderr=True, highlight=False).print(f"[dim]{escape(note)}[/dim]", soft_wrap=True)

    def close(self) -> None:
        """Close the browser (safe to call twice)."""
        for obj, method in ((self._browser, "close"), (self._pw, "stop")):
            if obj is not None:
                try:
                    getattr(obj, method)()
                except Exception:  # noqa: S110 - closing a dead browser is not an error
                    pass
        self._browser = self._pw = self._page = None


def _fallback(out_dir: Path, why: str, session: ScreenshotSession | None) -> ScreenshotResult:
    note = fallback_note(why)
    paths: dict[str, Path] = {}
    for view in VIEWS:
        src = out_dir / f"{view}.png"
        if src.is_file():
            dest = out_dir / f"styled-{view}.png"
            shutil.copyfile(src, dest)
            paths[view] = dest
    if session is not None:
        session.warn(note)
    else:
        from rich.console import Console
        from rich.markup import escape

        Console(stderr=True, highlight=False).print(f"[dim]{escape(note)}[/dim]", soft_wrap=True)
    return ScreenshotResult(paths, "zbuffer-fallback", [note])


def styled_screenshots(
    card: ConceptCard,
    glb_path: Path,
    style: StyleFile,
    out_dir: Path,
    page: ScreenshotSession | None = None,
) -> ScreenshotResult:
    """Write ``styled-iso.png`` and ``styled-front.png`` for one card into ``out_dir``.

    Args:
        card: the concept card (its massing calls give the node URIs and roles).
        glb_path: the card's ``massing.glb``.
        style: the resolved style (the product's, with the card's sketch laid over it).
        out_dir: the card's ``renders/`` folder (the z-buffer renders live there too).
        page: a :class:`ScreenshotSession` to reuse; without one a session is opened and
            closed for this card.

    Returns:
        The written paths, ``method`` (``viewer`` or ``zbuffer-fallback``) and notes.
    """
    if page is None:
        with ScreenshotSession() as session:
            return styled_screenshots(card, glb_path, style, out_dir, session)
    session = page
    out_dir.mkdir(parents=True, exist_ok=True)
    browser_page = session.page()
    if browser_page is None:
        return _fallback(out_dir, session.unavailable or "no browser", session)
    page_file = out_dir / "styled.html"
    page_file.write_text(
        styled_page(glb_path.read_bytes(), card_materials(card, style), style), encoding="utf-8"
    )
    session.take_errors()
    try:
        browser_page.goto(page_file.resolve().as_uri())
        ok = browser_page.evaluate("window.n2fViewerReady.then(() => !!window.n2fViewer)")
        errors = session.take_errors()
        if not ok or errors:
            why = errors[0] if errors else "the viewer did not load"
            return _fallback(out_dir, f"the viewer failed: {why}", session)
        paths: dict[str, Path] = {}
        for view in VIEWS:
            data_url = browser_page.evaluate(
                "(v) => { window.n2fViewer.view(v); return window.n2fViewer.snapshot(); }", view
            )
            png = base64.b64decode(str(data_url).split(",", 1)[1])
            dest = out_dir / f"styled-{view}.png"
            dest.write_bytes(png)
            paths[view] = dest
    except Exception as exc:  # a crashed page or a timeout: show the correctness renders
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        return _fallback(out_dir, f"the viewer failed: {first}", session)
    return ScreenshotResult(paths, "viewer", [])


__all__ = [
    "NO_PLAYWRIGHT_ENV",
    "VIEWPORT",
    "VIEWS",
    "ScreenshotResult",
    "ScreenshotSession",
    "card_materials",
    "fallback_note",
    "styled_page",
    "styled_screenshots",
]
