"""HTML and PDF outputs for a manual page (D8, D28) plus the manual index.

For each page the ``doc:<id>`` rule already writes ``page.md`` and ``reads.json``; this
module adds ``page.html``, ``page.typ`` (the emitted Typst source, kept for debugging) and
``page.pdf``.  A PDF compile failure never fails the build: ``page.pdf.error.txt`` records
the gap instead.  Every page run also rewrites ``build/docs/index.html``.
"""

from __future__ import annotations

import html as html_lib
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from napkin2factory.core.loader import heading_anchor
from napkin2factory.docs.html import CSS, render_html
from napkin2factory.docs.typst import (
    DISCLAIMER,
    TypstError,
    compile_pdf,
    markdown_parser,
    markdown_to_typst,
)

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext

SAFETY_BANNER = "SAFETY — read before use"


def _subtitle(doc: Any) -> str:
    audience = ", ".join(str(a) for a in doc.meta.audience)
    bits = [f"Audience: {audience}" if audience else ""]
    if doc.meta.safety:
        bits.append("Safety page")
    return " · ".join(b for b in bits if b)


def _headings(markdown_text: str) -> list[str]:
    """Markdown text of every real heading (not ``#`` lines inside code fences)."""
    tokens = markdown_parser().parse(markdown_text)
    return [
        tokens[i + 1].content
        for i, t in enumerate(tokens)
        if t.type == "heading_open" and i + 1 < len(tokens)
    ]


def _anchor_fn(doc: Any, markdown_text: str) -> Any:
    """Heading ids that match ``doc.anchors`` (slugged from the un-templated source).

    A templated heading (``## Power for {{ P["v"] }}``) renders differently from its
    source, so when the rendered page has as many headings as the source the source
    anchors are used in order; otherwise each heading is slugged as rendered.
    """
    rendered = _headings(markdown_text)
    source = [heading_anchor(h) for h in _headings(doc.body)]
    if len(rendered) != len(source):
        return heading_anchor
    queue = list(source)

    def anchor(text: str) -> str:
        return queue.pop(0) if queue else heading_anchor(text)

    return anchor


def _link_fn(doc: Any, out_dir: Path) -> Any:
    """Rewrite ``doc://id#a`` to the sibling page and relative images to the doc folder."""

    def rewrite(url: str, kind: str) -> str:
        if url.startswith("doc://"):
            target, _, frag = url[len("doc://") :].partition("#")
            return f"../{target}/page.html" + (f"#{frag}" if frag else "")
        if kind == "image" and url and "://" not in url and not url.startswith(("/", "data:")):
            path = (doc.path.parent / url).resolve()
            if path.is_file():
                return Path(os.path.relpath(path, out_dir.resolve())).as_posix()
        return url

    return rewrite


def write_doc_outputs(ctx: RunContext, doc: Any, rendered: Any) -> list[Path]:
    """Write ``page.html``, ``page.typ`` and ``page.pdf`` (or ``page.pdf.error.txt``).

    Args:
        ctx: The build context.
        doc: The ``core.loader.Doc`` being built.
        rendered: The ``docs.engine.Rendered`` page (templated Markdown and reads).

    Returns:
        The files written for this page (plus ``index.html`` when this page owns it).
    """
    out_dir = ctx.build_dir / "docs" / doc.meta.id
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    page_html = out_dir / "page.html"
    page_html.write_text(
        render_html(
            rendered.markdown,
            doc.meta.title,
            _anchor_fn(doc, rendered.markdown),
            subtitle=_subtitle(doc),
            banner=SAFETY_BANNER if doc.meta.safety else "",
            link_fn=_link_fn(doc, out_dir),
        ),
        encoding="utf-8",
    )
    written.append(page_html)

    root = ctx.product.paths.root
    source, warnings = markdown_to_typst(
        rendered.markdown,
        doc.meta.title,
        subtitle=_subtitle(doc),
        banner=SAFETY_BANNER if doc.meta.safety else None,
        base_dir=doc.path.parent,
        root=root,
    )
    page_typ = out_dir / "page.typ"
    page_typ.write_text(source, encoding="utf-8")
    written.append(page_typ)

    page_pdf = out_dir / "page.pdf"
    error_txt = out_dir / "page.pdf.error.txt"
    try:
        pdf = compile_pdf(source, root)
    except TypstError as exc:
        page_pdf.unlink(missing_ok=True)
        error_txt.write_text(str(exc) + "\n", encoding="utf-8")
        written.append(error_txt)
    else:
        page_pdf.write_bytes(pdf)
        error_txt.unlink(missing_ok=True)
        written.append(page_pdf)

    warn_txt = out_dir / "page.typ.warnings.txt"
    if warnings:
        warn_txt.write_text("\n".join(warnings) + "\n", encoding="utf-8")
        written.append(warn_txt)
    else:
        warn_txt.unlink(missing_ok=True)

    index = write_index(ctx)
    if _index_owner(ctx) == doc.meta.id:
        written.append(index)
    return written


def _ordered_docs(ctx: RunContext) -> list[Any]:
    docs = list(ctx.product.docs.values())
    return sorted(docs, key=lambda d: (not d.meta.safety, d.meta.order, d.meta.id))


def _index_owner(ctx: RunContext) -> str | None:
    """The page whose rule records ``index.html`` as an output (the first listed)."""
    docs = _ordered_docs(ctx)
    return docs[0].meta.id if docs else None


def write_index(ctx: RunContext) -> Path:
    """Write ``build/docs/index.html`` listing every page, safety pages first.

    Args:
        ctx: The build context.

    Returns:
        The index path.
    """
    esc = html_lib.escape
    rows: list[str] = []
    for d in _ordered_docs(ctx):
        did = esc(d.meta.id)
        audience = esc(", ".join(str(a) for a in d.meta.audience))
        mark = '<span class="safety">SAFETY</span> ' if d.meta.safety else ""
        cls = ' class="safety-row"' if d.meta.safety else ""
        rows.append(
            f'<li{cls} data-doc="{did}">{mark}<a href="{did}/page.html">{esc(d.meta.title)}</a>'
            f' — <span class="audience">{audience}</span>'
            f' · <a href="{did}/page.pdf">PDF</a></li>'
        )
    name = ctx.product.manifest.product.name
    title = f"{name} — manual"
    css = (
        CSS + "\n.safety { background: #b00020; color: #fff; padding: 0 0.3rem; font-weight: 700; }"
    )
    page = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{esc(title)}</title>",
            f"<style>\n{css}\n</style>",
            "</head>",
            "<body>",
            f"<h1>{esc(title)}</h1>",
            '<ul class="pages">',
            *rows,
            "</ul>",
            f'<footer><p class="disclaimer">{esc(DISCLAIMER)}</p></footer>',
            "</body>",
            "</html>",
        ]
    )
    path = ctx.build_dir / "docs" / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page + "\n", encoding="utf-8")
    return path
