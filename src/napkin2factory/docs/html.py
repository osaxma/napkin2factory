"""Markdown → HTML for manual pages (decision D28) with stable heading anchors.

Heading ids use :func:`napkin2factory.core.loader.heading_anchor` so ``doc://<id>#<anchor>``
references resolve in the rendered page.  Raw HTML in a page is escaped and shown as text,
matching the PDF emitter.
"""

from __future__ import annotations

import html as html_lib
from collections.abc import Callable, Sequence
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

from napkin2factory.core.loader import heading_anchor
from napkin2factory.docs.typst import DISCLAIMER

AnchorFn = Callable[[str], str]
LinkFn = Callable[[str, str], str]

CSS = """
:root { color-scheme: light; }
body { font-family: Georgia, "Times New Roman", serif; line-height: 1.55; color: #1b1b1b;
  background: #fff; max-width: 48rem; margin: 2rem auto; padding: 0 1rem; }
h1, h2, h3, h4, h5, h6 { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  line-height: 1.25; }
.subtitle { color: #555; font-family: system-ui, sans-serif; font-size: 0.9rem; }
.banner { background: #b00020; color: #fff; font-family: system-ui, sans-serif;
  font-weight: 700; padding: 0.6rem 1rem; border-radius: 4px; margin: 1rem 0; }
table { border-collapse: collapse; margin: 1rem 0; }
th, td { border: 1px solid #999; padding: 0.3rem 0.6rem; vertical-align: top; }
th { background: #f2f2f2; }
code, pre { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.9em; }
pre { background: #f6f6f6; padding: 0.75rem; overflow-x: auto; }
blockquote { border-left: 3px solid #ccc; margin-left: 0; padding-left: 1rem; color: #444; }
img { max-width: 100%; }
footer { margin-top: 3rem; border-top: 1px solid #ddd; padding-top: 0.75rem; color: #555;
  font-size: 0.85rem; font-style: italic; }
""".strip()


def _parser(anchor_fn: AnchorFn, link_fn: LinkFn | None) -> MarkdownIt:
    md = MarkdownIt("gfm-like", {"linkify": False, "html": False})

    def heading_open(self: Any, tokens: Sequence[Token], idx: int, options: Any, env: Any) -> str:
        inline = tokens[idx + 1] if idx + 1 < len(tokens) else None
        text = inline.content if inline is not None and inline.type == "inline" else ""
        tokens[idx].attrSet("id", anchor_fn(text))
        return str(self.renderToken(tokens, idx, options, env))

    md.add_render_rule("heading_open", heading_open)
    if link_fn is not None:
        default_image = md.renderer.rules["image"]

        def link_open(self: Any, tokens: Sequence[Token], idx: int, options: Any, env: Any) -> str:
            href = tokens[idx].attrGet("href")
            if href is not None:
                tokens[idx].attrSet("href", link_fn(str(href), "link"))
            return str(self.renderToken(tokens, idx, options, env))

        def image(self: Any, tokens: Sequence[Token], idx: int, options: Any, env: Any) -> str:
            src = tokens[idx].attrGet("src")
            if src is not None:
                tokens[idx].attrSet("src", link_fn(str(src), "image"))
            return str(default_image(tokens, idx, options, env))

        md.add_render_rule("link_open", link_open)
        md.add_render_rule("image", image)
    return md


def render_fragment(
    markdown_text: str,
    anchor_fn: AnchorFn = heading_anchor,
    link_fn: LinkFn | None = None,
) -> str:
    """Render Markdown to body HTML only (for embedding in the report).

    Args:
        markdown_text: The (already templated) Markdown body.
        anchor_fn: Maps a heading's Markdown text to its ``id``.
        link_fn: Optional ``(url, kind) -> url`` rewrite for links (``kind="link"``) and
            images (``kind="image"``).

    Returns:
        The HTML fragment.
    """
    return _parser(anchor_fn, link_fn).render(markdown_text)


def render_html(
    markdown_text: str,
    title: str,
    anchor_fn: AnchorFn = heading_anchor,
    *,
    subtitle: str = "",
    banner: str = "",
    link_fn: LinkFn | None = None,
) -> str:
    """Render Markdown to a standalone HTML document with inline CSS and the disclaimer.

    Args:
        markdown_text: The (already templated) Markdown body.
        title: The document title (``<title>``).
        anchor_fn: Maps a heading's Markdown text to its ``id``.
        subtitle: Optional line shown under the banner (audience, safety flag).
        banner: Optional red banner text (safety pages).
        link_fn: Optional ``(url, kind) -> url`` rewrite for links and images.

    Returns:
        The complete HTML document.
    """
    esc = html_lib.escape
    head = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{esc(title)}</title>",
        f"<style>\n{CSS}\n</style>",
        "</head>",
        "<body>",
    ]
    top: list[str] = []
    if banner:
        top.append(f'<div class="banner" role="alert">{esc(banner)}</div>')
    if subtitle:
        top.append(f'<p class="subtitle">{esc(subtitle)}</p>')
    body = render_fragment(markdown_text, anchor_fn, link_fn)
    foot = [
        f'<footer><p class="disclaimer">{esc(DISCLAIMER)}</p></footer>',
        "</body>",
        "</html>",
    ]
    return "\n".join([*head, *top, "<main>", body.rstrip("\n"), "</main>", *foot]) + "\n"
