"""A wiring diagram made safe to inline in the report (D13: the page is ``file://`` safe).

The ``elec`` rules draw the diagrams; this module never trusts them to be page-ready.  Inline
SVG shares the page's document, so it keeps only what draws: no script, no event handler, no
foreign object, no reference to anything outside the drawing (an external ``href`` or
``url(...)``, a CSS ``@import``), no XML prolog or doctype.  Every ``id`` is prefixed per
circuit, so two diagrams on one page never answer to each other's markers or clip paths, and
a drawing with a size but no ``viewBox`` gets one, so it scales with the card.  The rules
of a ``<style>`` inside the drawing are scoped to it (an inline ``<style>`` applies to the
whole page: a drawing's ``text{fill:#000}`` would restyle every other drawing's text).

Size: the drawing fills the card's width, but never shrinks below :data:`MIN_SCALE` of its
own size (a wide diagram's text would turn unreadable); past that the card scrolls sideways,
the page never widens (the overseer's note to M4, S-159).
"""

from __future__ import annotations

import re

_PROLOG = re.compile(r"<\?xml[^>]*\?>|<!DOCTYPE[^>]*>|<!--.*?-->", re.S | re.I)
_DROP_ELEMENTS = ("script", "foreignObject", "iframe", "object", "embed", "audio", "video")
_EVENT_ATTR = re.compile(r"""\s+on[a-zA-Z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""")
_HREF_ATTR = re.compile(r"""\s+((?:xlink:)?href)\s*=\s*("([^"]*)"|'([^']*)')""")
_URL = re.compile(r"""url\(\s*(['"]?)([^)'"]*)\1\s*\)""")
_IMPORT = re.compile(r"@import[^;]*;?", re.I)
_ID_ATTR = re.compile(r"""(\s)id\s*=\s*("([^"]*)"|'([^']*)')""")
_SVG_OPEN = re.compile(r"<svg\b[^>]*>", re.I)
_NUMBER = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*(px|mm)?\s*$")
_STYLE = re.compile(r"(<style\b[^>]*>)(.*?)(</style\s*>)", re.S | re.I)
#: The smallest scale a drawing is shown at before the card scrolls instead.
MIN_SCALE = 0.8
#: CSS pixels per millimetre (96 per inch).
PX_PER_MM = 96 / 25.4


def _drop_element(text: str, tag: str) -> str:
    paired = re.compile(rf"<{tag}\b[^>]*>.*?</{tag}\s*>", re.S | re.I)
    single = re.compile(rf"<{tag}\b[^>]*/?>", re.I)
    return single.sub("", paired.sub("", text))


def _local_href(match: re.Match[str], prefix: str) -> str:
    target = match.group(3) if match.group(3) is not None else match.group(4) or ""
    if not target.startswith("#"):
        return ""  # an outside reference: the page must not reach for it (D13)
    return f' {match.group(1)}="#{prefix}-{target[1:]}"'


def _local_url(match: re.Match[str], prefix: str) -> str:
    target = match.group(2).strip()
    if not target.startswith("#"):
        return "none"
    return f"url(#{prefix}-{target[1:]})"


def _px(m: re.Match[str] | None) -> float | None:
    if m is None:
        return None
    return float(m.group(1)) * (PX_PER_MM if m.group(2) == "mm" else 1.0)


def _root(svg_open: str, prefix: str) -> str:
    """The ``<svg>`` tag with a ``viewBox``, the prefix as its id and its sizing style."""
    w = re.search(r"""\bwidth\s*=\s*["']([^"']*)["']""", svg_open)
    h = re.search(r"""\bheight\s*=\s*["']([^"']*)["']""", svg_open)
    wm = _NUMBER.match(w.group(1)) if w else None
    hm = _NUMBER.match(h.group(1)) if h else None
    extra = f' id="{prefix}"'
    if not re.search(r"\bviewBox\s*=", svg_open) and wm is not None and hm is not None:
        extra += f' viewBox="0 0 {wm.group(1)} {hm.group(1)}"'
    width = _px(wm)
    style = "width:100%;height:auto;max-width:none;cursor:default"
    if width is not None:
        style += f";min-width:{width * MIN_SCALE:.0f}px"
    extra += f' style="{style}"'
    tag = re.sub(r"""\s(?:id|style)\s*=\s*("[^"]*"|'[^']*')""", "", svg_open)
    return tag[:-1].rstrip("/").rstrip() + extra + ">"


def _scoped(css: str, prefix: str) -> str:
    """Each rule's selectors prefixed with ``#<prefix>``; at-rules dropped."""
    out = []
    for block in css.split("}"):
        if "{" not in block:
            continue
        selectors, body = block.split("{", 1)
        if selectors.strip().startswith("@"):
            continue
        scoped = ", ".join(
            f"#{prefix} {sel.strip()}" for sel in selectors.split(",") if sel.strip()
        )
        out.append(f"{scoped}{{{body}}}")
    return "".join(out)


def inline_svg(text: str, prefix: str) -> str:
    """``text`` (an SVG file) as markup safe to put in the page; ``""`` if it is no SVG.

    ``prefix`` is put before every ``id`` and every local reference to one (``#x``,
    ``url(#x)``), e.g. ``wiring-power``.
    """
    body = _PROLOG.sub("", text or "").strip()
    start = body.lower().find("<svg")
    end = body.lower().rfind("</svg>")
    if start < 0 or end < start:
        return ""
    body = body[start : end + len("</svg>")]
    for tag in _DROP_ELEMENTS:
        body = _drop_element(body, tag)
    body = _EVENT_ATTR.sub("", body)
    body = _IMPORT.sub("", body)
    body = _HREF_ATTR.sub(lambda m: _local_href(m, prefix), body)
    body = _URL.sub(lambda m: _local_url(m, prefix), body)

    def _id(m: re.Match[str]) -> str:
        value = m.group(3) if m.group(3) is not None else m.group(4) or ""
        return f'{m.group(1)}id="{prefix}-{value}"'

    body = _ID_ATTR.sub(_id, body)
    body = _STYLE.sub(lambda m: m.group(1) + _scoped(m.group(2), prefix) + m.group(3), body)
    first = _SVG_OPEN.search(body)
    if first is not None:
        body = body[: first.start()] + _root(first.group(0), prefix) + body[first.end() :]
    return body
