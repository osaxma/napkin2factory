"""Markdown → Typst emitter and PDF compilation (decision D28).

A deliberately small, in-house emitter over markdown-it-py's token stream (via its
``SyntaxTreeNode`` view of the same tokens).  It covers what manual pages use: headings,
paragraphs, emphasis, strikethrough, lists, tables, images, code, links, block quotes and
rules.  Anything else is rendered as escaped plain text and reported in the warnings list,
so a page never fails to emit.  No Typst ``@preview`` packages are used, because those are
downloaded at compile time.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

DISCLAIMER = (
    "This design was produced with an AI system and has not been reviewed by a licensed engineer."
)

# Characters with markup meaning in Typst text.  ``/`` is handled separately (only ``//``
# and ``/*`` start comments).
_SPECIAL = set("\\#*_@$<>[]`~")
_LINE_MARKER = re.compile(r"^(\s*)([-+=/](?=\s|$)|\d+\.(?=\s|$))")
_LINK_SCHEMES = ("http://", "https://", "mailto:", "tel:")


class TypstError(RuntimeError):
    """Typst failed to compile a document; the message starts with the compiler's own lines."""


def markdown_parser(html: bool = True) -> MarkdownIt:
    """The shared "gfm-like" parser (tables, strikethrough) without linkify.

    Args:
        html: Whether raw HTML is recognised as ``html_block``/``html_inline`` tokens.

    Returns:
        A configured ``MarkdownIt`` instance.
    """
    return MarkdownIt("gfm-like", {"linkify": False, "html": html})


def escape_text(text: str) -> str:
    """Escape Typst markup characters so ``text`` renders literally.

    Args:
        text: Plain text (no markup intended).

    Returns:
        The text with backslash, ``# * _ @ $ < > [ ] ` ~`` backslash-escaped and ``//``/``/*``
        broken so they cannot open a comment.
    """
    out: list[str] = []
    for i, ch in enumerate(text):
        if ch in _SPECIAL:
            out.append("\\" + ch)
        elif ch == "/" and i + 1 < len(text) and text[i + 1] in "/*":
            out.append("\\/")
        else:
            out.append(ch)
    return "".join(out)


def escape_string(text: str) -> str:
    """Escape a value for a Typst string literal (``"..."``).

    Args:
        text: The raw value.

    Returns:
        The value with backslashes, quotes and newlines escaped.
    """
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _guard_line_start(line: str) -> str:
    """Escape a list/heading/enum marker that would otherwise start a Typst construct."""
    m = _LINE_MARKER.match(line)
    if not m:
        return line
    lead, marker = m.group(1), m.group(2)
    rest = line[m.end() :]
    if marker[-1] == ".":
        return f"{lead}{marker[:-1]}\\.{rest}"
    return f"{lead}\\{marker}{rest}"


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + ln if ln.strip() else ln for ln in text.split("\n"))


@dataclass
class _Piece:
    """One rendered inline fragment."""

    text: str
    kind: str = "text"  # text | code (an embedded #expr) | strong | emph
    inner: str = ""


@dataclass
class _Emitter:
    base_dir: Path | None
    root: Path | None
    warnings: list[str]

    # ---- inline --------------------------------------------------------------------

    def inline(self, node: SyntaxTreeNode) -> str:
        return self._join(self._pieces(node.children))

    def _pieces(self, nodes: list[SyntaxTreeNode]) -> list[_Piece]:
        out: list[_Piece] = []
        for n in nodes:
            out.extend(self._piece(n))
        return out

    def _piece(self, n: SyntaxTreeNode) -> list[_Piece]:
        t = n.type
        if t == "text":
            return [_Piece(escape_text(n.content))]
        if t == "softbreak":
            return [_Piece(" ")]
        if t == "hardbreak":
            return [_Piece(" \\\n")]
        if t == "strong":
            return [_Piece("", "strong", self._join(self._pieces(n.children)))]
        if t == "em":
            return [_Piece("", "emph", self._join(self._pieces(n.children)))]
        if t == "s":
            return [_Piece(f"#strike[{self._join(self._pieces(n.children))}]", "code")]
        if t == "code_inline":
            return [self._code_inline(n.content)]
        if t == "link":
            return self._link(n)
        if t == "image":
            return [self._image(n)]
        if t == "html_inline":
            self.warnings.append(f"raw HTML rendered as text: {n.content.strip()[:60]}")
            return [_Piece(escape_text(n.content))]
        self.warnings.append(f"unsupported inline {t!r} rendered as text")
        return [_Piece(escape_text(n.content or _plain(n)))]

    @staticmethod
    def _code_inline(code: str) -> _Piece:
        if "`" in code or not code.strip():
            return _Piece(f'#raw("{escape_string(code)}")', "code")
        return _Piece(f"`{code}`")

    def _link(self, n: SyntaxTreeNode) -> list[_Piece]:
        href = str(n.attrs.get("href", ""))
        label = self._join(self._pieces(n.children))
        if href.lower().startswith(_LINK_SCHEMES):
            return [_Piece(f'#link("{escape_string(href)}")[{label}]', "code")]
        # doc://, relative and in-page links have no meaning in a standalone PDF: keep the label.
        return [_Piece(label)]

    def _image(self, n: SyntaxTreeNode) -> _Piece:
        src = str(n.attrs.get("src", ""))
        alt = _plain(n) or Path(src).name
        resolved = self._resolve_image(src)
        if resolved is None:
            self.warnings.append(f"image not found, alt text used: {src}")
            return _Piece(escape_text(alt))
        return _Piece(f'#image("{escape_string(resolved)}")', "code")

    def _resolve_image(self, src: str) -> str | None:
        if self.base_dir is None or not src or "://" in src or src.startswith("data:"):
            return None
        path = (self.base_dir / src).resolve()
        if not path.is_file():
            return None
        root = (self.root or self.base_dir).resolve()
        try:
            rel = path.relative_to(root)
        except ValueError:
            return None
        return "/" + rel.as_posix()

    @staticmethod
    def _join(pieces: list[_Piece]) -> str:
        out: list[str] = []
        for i, p in enumerate(pieces):
            prev = out[-1][-1:] if out else ""
            ahead = _lookahead(pieces[i + 1 :])
            nxt = ahead[:1]
            if p.kind in ("strong", "emph"):
                delim = "*" if p.kind == "strong" else "_"
                func = "strong" if p.kind == "strong" else "emph"
                glued = prev.isalnum() or nxt.isalnum() or not p.inner.strip()
                if glued:
                    text, is_code = f"#{func}[{p.inner}]", True
                else:
                    text, is_code = f"{delim}{p.inner}{delim}", False
            else:
                text, is_code = p.text, p.kind == "code"
            # A following "(", "[" or ".name" would continue the embedded expression.
            if is_code and (nxt in ("(", "[") or re.match(r"\.[A-Za-z_]", ahead)):
                text += ";"
            out.append(text)
        return "".join(out)

    # ---- blocks --------------------------------------------------------------------

    def blocks(self, nodes: list[SyntaxTreeNode], sep: str = "\n\n") -> str:
        return sep.join(b for b in (self.block(n) for n in nodes) if b != "")

    def block(self, n: SyntaxTreeNode) -> str:
        t = n.type
        if t == "heading":
            level = int(n.tag[1])
            text = self.inline(n.children[0]).replace(" \\\n", " ")
            return "=" * level + " " + text
        if t == "paragraph":
            text = self.inline(n.children[0])
            return "\n".join(_guard_line_start(ln) for ln in text.split("\n"))
        if t in ("bullet_list", "ordered_list"):
            return self._list(n)
        if t == "table":
            return self._table(n)
        if t in ("fence", "code_block"):
            return self._raw_block(n)
        if t == "hr":
            return "#line(length: 100%)"
        if t == "blockquote":
            return f"#quote(block: true)[\n{self.blocks(n.children)}\n]"
        if t == "html_block":
            self.warnings.append(f"raw HTML block rendered as text: {n.content.strip()[:60]}")
            lines = [_guard_line_start(escape_text(ln)) for ln in n.content.strip().split("\n")]
            return " \\\n".join(lines)
        self.warnings.append(f"unsupported block {t!r} rendered as text")
        text = escape_text(_plain(n).strip())
        return "\n".join(_guard_line_start(ln) for ln in text.split("\n"))

    def _list(self, n: SyntaxTreeNode) -> str:
        ordered = n.type == "ordered_list"
        start = int(n.attrs.get("start", 1)) if ordered else 1
        tight = all(c.hidden for item in n.children for c in item.children if c.type == "paragraph")
        items: list[str] = []
        for i, item in enumerate(n.children):
            marker = "- "
            if ordered:
                marker = f"{start}. " if (i == 0 and start != 1) else "+ "
            body = self.blocks(item.children, "\n" if tight else "\n\n")
            body = _indent(body, " " * len(marker)).lstrip(" ") if body else ""
            items.append(marker + body)
        return ("\n" if tight else "\n\n").join(items)

    def _table(self, n: SyntaxTreeNode) -> str:
        header: list[str] = []
        rows: list[list[str]] = []
        aligns: list[str] = []
        for section in n.children:
            for tr in section.children:
                cells = [self.inline(c.children[0]) if c.children else "" for c in tr.children]
                if section.type == "thead":
                    header = cells
                    for c in tr.children:
                        style = str(c.attrs.get("style", ""))
                        aligns.append(style.split(":", 1)[1] if ":" in style else "auto")
                else:
                    rows.append(cells)
        ncols = max([len(header), *(len(r) for r in rows)]) if (header or rows) else 1
        lines = ["#table(", f"  columns: {ncols},"]
        if any(a != "auto" for a in aligns):
            trailing = "," if len(aligns) == 1 else ""
            lines.append(f"  align: ({', '.join(aligns)}{trailing}),")
        if header:
            cells = ", ".join(f"[*{c}*]" if c.strip() else "[]" for c in header)
            lines.append(f"  table.header({cells}),")
        for row in rows:
            row = row + [""] * (ncols - len(row))
            lines.append("  " + ", ".join(f"[{c}]" for c in row) + ",")
        lines.append(")")
        return "\n".join(lines)

    @staticmethod
    def _raw_block(n: SyntaxTreeNode) -> str:
        code = n.content.rstrip("\n")
        lang = ""
        if n.type == "fence" and n.info:
            lang = re.sub(r"[^A-Za-z0-9_+-]", "", n.info.split()[0])
        longest = max((len(m) for m in re.findall(r"`+", code)), default=0)
        fence = "`" * max(3, longest + 1)
        return f"{fence}{lang}\n{code}\n{fence}"


def _plain(n: SyntaxTreeNode) -> str:
    """The plain text under a node (for alt text and fallbacks)."""
    if n.type in ("text", "code_inline", "html_inline", "html_block", "fence", "code_block"):
        return n.content
    if n.type in ("softbreak", "hardbreak"):
        return " "
    return "".join(_plain(c) for c in n.children) if n.children else (n.content or "")


def _lookahead(pieces: list[_Piece]) -> str:
    """The first two characters the following pieces will emit (``#`` for markup)."""
    for p in pieces:
        if p.kind in ("strong", "emph"):
            return "#"
        if p.text:
            return p.text[:2]
    return ""


def markdown_to_typst(
    markdown_text: str,
    title: str | None = None,
    *,
    subtitle: str | None = None,
    banner: str | None = None,
    base_dir: Path | None = None,
    root: Path | None = None,
) -> tuple[str, list[str]]:
    """Emit a standalone Typst document for a Markdown page.

    Args:
        markdown_text: The (already templated) Markdown body.
        title: Optional title shown as a centred title block and set as document title.
        subtitle: Optional italic line under the title (audience, safety flag).
        banner: Optional text for a red, full-width warning banner (safety pages).
        base_dir: Folder that relative image paths are resolved against (the doc's folder).
            Without it every image falls back to its alt text.
        root: The Typst project root passed to :func:`compile_pdf`; images are emitted as
            root-relative paths and images outside it fall back to alt text.  Defaults to
            ``base_dir``.

    Returns:
        ``(typst_source, warnings)`` — warnings name every construct rendered as plain text
        and every missing image.
    """
    warnings: list[str] = []
    emitter = _Emitter(base_dir=base_dir, root=root, warnings=warnings)
    tree = SyntaxTreeNode(markdown_parser(html=True).parse(markdown_text))
    parts = [
        '#set page(paper: "a4", margin: 2cm)',
        '#set text(font: "Libertinus Serif", size: 11pt)',
    ]
    if title:
        parts.insert(0, f'#set document(title: "{escape_string(title)}")')
    head = "\n".join(parts)
    sections = [head]
    if title:
        sections.append(f'#align(center)[#text(20pt, weight: "bold")[{escape_text(title)}]]')
    if banner:
        sections.append(
            '#block(fill: rgb("#b00020"), inset: 8pt, radius: 3pt, width: 100%)'
            f'[#text(fill: white, weight: "bold")[{escape_text(banner)}]]'
        )
    if subtitle:
        sections.append(f'#text(style: "italic")[{escape_text(subtitle)}]')
    body = emitter.blocks(tree.children)
    if body:
        sections.append(body)
    sections.append(f'#text(size: 8pt, style: "italic")[{escape_text(DISCLAIMER)}]')
    return "\n\n".join(sections) + "\n", warnings


def compile_pdf(typst_source: str, root: Path) -> bytes:
    """Compile Typst source to PDF bytes using only the fonts bundled with Typst.

    Args:
        typst_source: A complete Typst document.
        root: The project root that absolute (``/``-prefixed) image paths resolve against.

    Returns:
        The PDF bytes.

    Raises:
        TypstError: The compiler rejected the document; the message holds its first lines.
    """
    import typst

    try:
        return bytes(
            typst.compile(
                typst_source.encode("utf-8"), root=os.fspath(root), ignore_system_fonts=True
            )
        )
    except (RuntimeError, ValueError, OSError) as exc:
        lines = str(exc).strip().splitlines() or [type(exc).__name__]
        raise TypstError("Typst compilation failed: " + "\n".join(lines[:8])) from exc


def compile_png(typst_source: str, root: Path, ppi: float = 96.0) -> bytes:
    """Render the first page to PNG (for visual checks).

    Args:
        typst_source: A complete Typst document.
        root: The project root for image paths.
        ppi: Pixels per inch.

    Returns:
        PNG bytes of the first page.

    Raises:
        TypstError: The compiler rejected the document.
    """
    import typst

    try:
        out = typst.compile(
            typst_source.encode("utf-8"),
            root=os.fspath(root),
            format="png",
            ppi=ppi,
            ignore_system_fonts=True,
        )
    except (RuntimeError, ValueError, OSError) as exc:
        lines = str(exc).strip().splitlines() or [type(exc).__name__]
        raise TypstError("Typst compilation failed: " + "\n".join(lines[:8])) from exc
    return bytes(out[0] if isinstance(out, list) else out)
