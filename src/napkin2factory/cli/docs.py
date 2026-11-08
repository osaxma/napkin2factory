"""``n2f docs``: the using-side documentation, readable from the installed tool (S-231).

The pages an agent needs while it works on a product (the kit, the napkin stage, the wiring,
the product files, the command map…) live in the repository's ``docs/``, which an installed
tool cannot reach. They ship inside the wheel (``napkin2factory/_docs/``, see
``pyproject.toml``) and this verb prints them; ``docs/`` stays the one source.
"""

from __future__ import annotations

from pathlib import Path

import typer

from napkin2factory.cli.common import JsonOption, console, emit_json, handle_errors
from napkin2factory.core.errors import N2FError

# The topic name is the file's name without ``.md``. ``pyproject.toml`` force-includes
# exactly these files into the wheel; tests/unit/test_docs_verb.py keeps the two in step.
TOPICS: tuple[str, ...] = (
    "agent-guide",
    "calckit",
    "checks",
    "cli",
    "domains",
    "ecr-loop",
    "electrical",
    "how-it-works",
    "kit",
    "napkin",
    "product-model",
    "render-checklist",
    "schema-policy",
    "vocabulary",
)

_PACKAGE_DIR = Path(__file__).resolve().parents[1]


def docs_dir() -> Path:
    """The folder the pages are read from.

    A source checkout (``pyproject.toml`` and ``docs/`` beside ``src/``) reads its own
    ``docs/``, so a developer sees an edit at once; an installed tool reads the copy
    packaged next to the code.
    """
    repo = _PACKAGE_DIR.parents[1]
    if (repo / "pyproject.toml").is_file() and (repo / "docs" / "agent-guide.md").is_file():
        return repo / "docs"
    return _PACKAGE_DIR / "_docs"


def read_topic(topic: str, root: Path | None = None) -> tuple[str, str]:
    """Return ``(title, text)`` of ``topic``.

    Raises:
        N2FError: ``topic`` is not a known topic (the message lists the known ones), or its
            page is missing from this install.
    """
    if topic not in TOPICS:
        raise N2FError(
            f"no docs topic {topic!r}; the topics are: {', '.join(TOPICS)}",
            next="n2f docs",
        )
    path = (root or docs_dir()) / f"{topic}.md"
    if not path.is_file():
        raise N2FError(
            f"the page for {topic!r} is missing from this install ({path})",
            next="n2f docs",
        )
    text = path.read_text(encoding="utf-8")
    return _title(text, topic), text


def _title(text: str, fallback: str) -> str:
    """The first ``# `` heading of a page, without the marker."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


@handle_errors
def docs(
    topic: str | None = typer.Argument(
        None, help="Which page to print; leave out to list the topics."
    ),
    json_out: bool = JsonOption,
) -> None:
    """Print a documentation page that ships with the tool (no topic: list the topics)."""
    if topic is None:
        rows = [{"topic": t, "title": read_topic(t)[0]} for t in TOPICS]
        if json_out:
            emit_json({"topics": rows})
            return
        width = max(len(r["topic"]) for r in rows)
        for r in rows:
            console.print(f"{r['topic']:<{width}}  {r['title']}", markup=False, soft_wrap=True)
        console.print("\nRead one with `n2f docs <topic>`.", markup=False)
        return
    title, text = read_topic(topic)
    if json_out:
        emit_json({"topic": topic, "title": title, "text": text})
        return
    typer.echo(text, nl=not text.endswith("\n"))
