"""``n2f docs``: the using-side documentation, readable from the installed tool (S-231).

The pages an agent needs while it works on a product (the kit, the napkin stage, the wiring,
the product files, the command map…) live in the repository's ``docs/``, which an installed
tool cannot reach. They ship inside the wheel (``napkin2factory/_docs/``, see
``pyproject.toml``) and this verb prints them; ``docs/`` stays the one source.
``materials`` is served from the calc-kit table (B-0318).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import typer

from napkin2factory.cli.common import JsonOption, console, emit_json, handle_errors
from napkin2factory.core.errors import N2FError

# The topic name is the file's name without ``.md``. ``pyproject.toml`` force-includes
# exactly these files into the wheel; tests/unit/test_docs_verb.py keeps the two in step.
PAGE_TOPICS: tuple[str, ...] = (
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

TOPICS: tuple[str, ...] = tuple(sorted((*PAGE_TOPICS, "materials")))

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


def _format_youngs_modulus(val: Any) -> str:
    if val is None:
        return "not on file"
    try:
        gpa = float(val) / 1e9
        return f"{gpa:g} GPa"
    except (ValueError, TypeError):
        return "not on file"


def _format_yield_strength(val: Any) -> str:
    if val is None:
        return "not on file"
    try:
        mpa = float(val) / 1e6
        return f"{mpa:g} MPa"
    except (ValueError, TypeError):
        return "not on file"


def format_material_summary_line(row: dict[str, Any]) -> str:
    """Format one row of materials.yaml as a single summary line without sources (B-0318)."""
    name = row["name"]
    keywords = ", ".join(str(k) for k in row.get("keywords", []))
    density = f"{row['density']} kg/m³"
    youngs_modulus = _format_youngs_modulus(row.get("youngs_modulus"))
    yield_strength = _format_yield_strength(row.get("yield_strength"))
    process_class = row.get("process_class") or "no process class"
    verify = " [verify]" if row.get("verify") else ""
    return (
        f"{name} ({keywords}): {density}, {youngs_modulus}, {yield_strength}, "
        f"{process_class}{verify}"
    )


def material_row_object(row: dict[str, Any]) -> dict[str, Any]:
    """Return a material row as an object without sources."""
    out = {k: v for k, v in row.items() if k != "source"}
    if out.get("youngs_modulus") is not None:
        try:
            out["youngs_modulus"] = float(out["youngs_modulus"])
        except (ValueError, TypeError):
            pass
    if out.get("yield_strength") is not None:
        try:
            out["yield_strength"] = float(out["yield_strength"])
        except (ValueError, TypeError):
            pass
    return out


def materials_topic_text() -> str:
    """All rows of materials.yaml formatted one line per row without sources (B-0318)."""
    from napkin2factory.calckit import load_table

    rows = load_table("materials")
    return "\n".join(format_material_summary_line(r) for r in rows) + "\n"


def known_materials() -> list[str]:
    """Names of all materials known to the shared materials table."""
    from napkin2factory.calckit import load_table

    return [str(r["name"]) for r in load_table("materials") if r.get("name")]


def lookup_material(name: str) -> dict[str, Any] | None:
    """Find a material row in materials.yaml matching a name, keyword or alias."""
    target = name.strip().lower()
    if not target:
        return None
    from napkin2factory.calckit import load_table

    rows = load_table("materials")
    target_norm = target.replace("-", " ").replace("_", " ")

    # 1. Exact match on row name (case-insensitive, normalized)
    for row in rows:
        rname = str(row.get("name", "")).lower()
        if rname == target or rname.replace("-", " ").replace("_", " ") == target_norm:
            return dict(row)

    # 2. Exact match on keywords
    for row in rows:
        keywords = [str(k).lower() for k in row.get("keywords", [])]
        if any(
            kw == target or kw.replace("-", " ").replace("_", " ") == target_norm for kw in keywords
        ):
            return dict(row)

    # 3. Target contained in keyword or row name
    for row in rows:
        keywords = [str(k).lower() for k in row.get("keywords", [])]
        rname = str(row.get("name", "")).lower()
        if target in rname or any(target in kw for kw in keywords):
            return dict(row)

    # 4. 1-based index if given as an integer within range
    if target.isdigit() and 1 <= int(target) <= len(rows):
        return dict(rows[int(target) - 1])

    return None


def format_material_row_whole(row: dict[str, Any]) -> str:
    """Format one material row whole (all fields including source) as YAML."""
    import yaml

    data = dict(row)
    if data.get("youngs_modulus") is not None:
        try:
            data["youngs_modulus"] = float(data["youngs_modulus"])
        except (ValueError, TypeError):
            pass
    if data.get("yield_strength") is not None:
        try:
            data["yield_strength"] = float(data["yield_strength"])
        except (ValueError, TypeError):
            pass
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)


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
    if topic == "materials":
        return "Every material a card may name", materials_topic_text()
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


def _sections(text: str) -> list[tuple[str, str]]:
    """(heading, body including the heading line) for each heading outside code fences."""
    lines = text.splitlines()
    marks: list[tuple[int, str]] = []
    fenced = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and re.match(r"#{1,6} \S", line):
            marks.append((i, line.lstrip("#").strip()))
    out = []
    for n, (start, heading) in enumerate(marks):
        end = marks[n + 1][0] if n + 1 < len(marks) else len(lines)
        out.append((heading, "\n".join(lines[start:end]).strip()))
    return out


@handle_errors
def docs(
    topic: str | None = typer.Argument(
        None, help="Which page to print; leave out to list the topics."
    ),
    section: str | None = typer.Argument(
        None, help="A section heading, or for materials, a material name."
    ),
    section_opt: str | None = typer.Option(None, "--section", help="Alias for section."),
    json_out: bool = JsonOption,
) -> None:
    """Print a documentation page that ships with the tool (no topic: list the topics)."""
    sec = section or section_opt
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

    if topic == "materials":
        if sec:
            row = lookup_material(sec)
            if row is None:
                raise N2FError(
                    f"no material {sec!r}; known materials: {', '.join(known_materials())}",
                    next="n2f docs materials",
                )
            if json_out:
                emit_json({"topic": "materials", "material": row, **row})
                return
            typer.echo(format_material_row_whole(row), nl=False)
            return

        from napkin2factory.calckit import load_table

        raw_rows = load_table("materials")
        text = materials_topic_text()
        if json_out:
            rows_objects = [material_row_object(r) for r in raw_rows]
            emit_json(
                {
                    "topic": "materials",
                    "title": "Every material a card may name",
                    "materials": rows_objects,
                    "rows": rows_objects,
                    "text": text,
                }
            )
            return
        typer.echo(text, nl=not text.endswith("\n"))
        return

    title, text = read_topic(topic)
    if sec:
        parts = _sections(text)
        want = sec.strip()
        hit = None
        if want.isdigit() and 1 <= int(want) <= len(parts):
            hit = int(want) - 1
        else:
            low = want.lower()
            hit = next(
                (i for i, (h, _) in enumerate(parts) if h.lower() == low),
                next((i for i, (h, _) in enumerate(parts) if low and low in h.lower()), None),
            )
        if hit is None:
            raise N2FError(
                f"no section {want!r} in {topic}",
                next=f"n2f docs {topic}",
            )
        section_text = parts[hit][1]
        if json_out:
            emit_json(
                {
                    "topic": topic,
                    "title": title,
                    "section": {"n": hit + 1, "heading": parts[hit][0]},
                    "text": section_text,
                }
            )
            return
        typer.echo(section_text, nl=not section_text.endswith("\n"))
        return

    if json_out:
        emit_json({"topic": topic, "title": title, "text": text})
        return
    typer.echo(text, nl=not text.endswith("\n"))
