"""Print every engineering number a person still has to confirm, as Markdown.

The list is assembled from three places so nobody has to collect it by hand:

* rows marked ``verify: true`` in the calc kit's data tables
  (``src/napkin2factory/calckit/data/*.yaml``);
* decisions marked ``verify: true`` in each example product
  (``examples/*/model/decisions.yaml``);
* lines of ``DECISIONS.md`` tagged ``[verify]`` or ``[revisit]``, grouped by the
  ``## `` heading they fall under.

Run it with ``uv run python scripts/verify_list.py`` or ``make verify-list``.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from napkin2factory.core.yamlio import read_yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path("src/napkin2factory/calckit/data")
EXAMPLES_DIR = Path("examples")
DECISIONS_MD = Path("DECISIONS.md")
LINE_WIDTH = 120
TAGS = ("[verify]", "[revisit]")
# Fields that name a data-table row, in order of preference.
NAME_FIELDS = ("name", "label", "process_class", "material_class", "region")
# Fields that qualify a row name when several rows share it (e.g. one label per region).
QUALIFIER_FIELDS = ("region", "material_class")
HEADING = re.compile(r"^##\s+(.*)$")
HEADING_ID = re.compile(r"^[A-Z]+-\d+$")


@dataclass(frozen=True)
class TableRow:
    """One data-table row still to be confirmed."""

    table_file: str
    row: str
    source: str | None


@dataclass(frozen=True)
class ProductDecision:
    """One product decision still to be confirmed."""

    product: str
    decision_id: str
    title: str


@dataclass(frozen=True)
class TaggedLine:
    """One ``DECISIONS.md`` line tagged ``[verify]`` or ``[revisit]``."""

    heading_id: str
    line_no: int
    text: str


def _is_verify(entry: Any) -> bool:
    return isinstance(entry, dict) and entry.get("verify") is True


def row_name(row: dict[str, Any], fallback: str) -> str:
    """Return a readable name for a data-table row.

    Args:
        row: The row mapping.
        fallback: Used when the row has no naming field (e.g. its mapping key or index).

    Returns:
        The first naming field found, qualified by region or material class when present.
    """
    name = next((str(row[f]) for f in NAME_FIELDS if row.get(f) is not None), fallback)
    qualifiers = [
        str(row[f]) for f in QUALIFIER_FIELDS if row.get(f) is not None and str(row[f]) != name
    ]
    return f"{' / '.join(qualifiers)}: {name}" if qualifiers else name


def table_rows(data: Any, table_file: str) -> list[TableRow]:
    """Return the ``verify: true`` rows of one loaded data table.

    Args:
        data: The parsed YAML document (``{table:, rows: [...]}`` or a mapping of rows).
        table_file: The file name to report.

    Returns:
        One ``TableRow`` per row marked ``verify: true``, in file order.
    """
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        items: Iterable[tuple[str, Any]] = ((f"row {i + 1}", r) for i, r in enumerate(data["rows"]))
    elif isinstance(data, dict):
        items = ((str(k), v) for k, v in data.items())
    elif isinstance(data, list):
        items = ((f"row {i + 1}", r) for i, r in enumerate(data))
    else:
        items = ()
    out = []
    for key, row in items:
        if _is_verify(row):
            source = row.get("source")
            out.append(
                TableRow(table_file, row_name(row, key), None if source is None else str(source))
            )
    return out


def collect_table_rows(root: Path) -> list[TableRow]:
    """Collect ``verify: true`` rows from every calc-kit data table under ``root``."""
    out: list[TableRow] = []
    for path in sorted((root / DATA_DIR).glob("*.yaml")):
        out.extend(table_rows(read_yaml(path), path.name))
    return out


def product_decisions(data: Any, product: str) -> list[ProductDecision]:
    """Return the ``verify: true`` decisions of one loaded ``decisions.yaml``.

    Args:
        data: The parsed YAML document (``{decisions: [...]}``).
        product: The product directory name to report.

    Returns:
        One ``ProductDecision`` per decision marked ``verify: true``, in file order.
    """
    entries = data.get("decisions") if isinstance(data, dict) else None
    return [
        ProductDecision(product, str(e.get("id", "?")), str(e.get("title", "")))
        for e in entries or []
        if _is_verify(e)
    ]


def collect_product_decisions(root: Path) -> list[ProductDecision]:
    """Collect ``verify: true`` decisions from every example product under ``root``."""
    out: list[ProductDecision] = []
    for path in sorted((root / EXAMPLES_DIR).glob("*/model/decisions.yaml")):
        out.extend(product_decisions(read_yaml(path), path.parent.parent.name))
    return out


def trim(text: str, width: int = LINE_WIDTH) -> str:
    """Collapse whitespace and cut ``text`` to ``width`` characters, marking a cut with ``…``."""
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def heading_label(heading: str) -> str:
    """Return a short label for a ``## `` heading's text.

    Args:
        heading: The heading text after ``## ``.

    Returns:
        Its id (``S-064``) when the heading starts with one, else the text before the
        first `` — `` (``Review gate 3 (engineering)``), trimmed.
    """
    first = heading.split(maxsplit=1)[0] if heading.strip() else ""
    if HEADING_ID.match(first):
        return first
    return trim(heading.split(" — ", 1)[0], 60)


def tagged_lines(markdown: str) -> list[TaggedLine]:
    """Return the lines tagged ``[verify]`` or ``[revisit]``, each with its ``## `` heading id.

    Lines before the first ``## `` heading (the preamble that explains the tags) and lines
    of an ``## Index`` section (a summary table repeating the entries below) are skipped.

    Args:
        markdown: The text of ``DECISIONS.md``.

    Returns:
        One ``TaggedLine`` per tagged line, in file order.
    """
    out: list[TaggedLine] = []
    heading: str | None = None
    for no, line in enumerate(markdown.splitlines(), start=1):
        m = HEADING.match(line)
        if m:
            heading = None if m.group(1).startswith("Index") else heading_label(m.group(1))
        if heading is not None and any(tag in line for tag in TAGS):
            out.append(TaggedLine(heading, no, trim(line)))
    return out


def collect_tagged_lines(root: Path) -> list[TaggedLine]:
    """Collect the tagged lines of ``DECISIONS.md`` under ``root`` (none if it is missing)."""
    path = root / DECISIONS_MD
    return tagged_lines(path.read_text(encoding="utf-8")) if path.is_file() else []


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def render(rows: list[TableRow], decisions: list[ProductDecision], lines: list[TaggedLine]) -> str:
    """Render the three lists as one Markdown document.

    Args:
        rows: Data-table rows to confirm.
        decisions: Product decisions to confirm.
        lines: Tagged ``DECISIONS.md`` lines.

    Returns:
        The Markdown text, ending in a newline.
    """
    out = [
        "# Numbers still to be confirmed",
        "",
        f"{len(rows)} data-table rows, {len(decisions)} product decisions, "
        f"{len(lines)} tagged lines in DECISIONS.md.",
        "",
        "## Calc kit data tables (`verify: true`)",
        "",
    ]
    if rows:
        out += ["| Table | Row | Source |", "|---|---|---|"]
        out += [f"| {r.table_file} | {_cell(r.row)} | {_cell(r.source or '—')} |" for r in rows]
    else:
        out.append("None.")
    out += ["", "## Product decisions (`verify: true`)", ""]
    if decisions:
        out += ["| Product | Decision | Title |", "|---|---|---|"]
        out += [f"| {d.product} | {d.decision_id} | {_cell(d.title)} |" for d in decisions]
    else:
        out.append("None.")
    out += ["", "## DECISIONS.md (`[verify]` / `[revisit]`)", ""]
    if not lines:
        out.append("None.")
    current: str | None = None
    for t in lines:
        if t.heading_id != current:
            if current is not None:
                out.append("")
            out.append(f"### {t.heading_id}")
            out.append("")
            current = t.heading_id
        out.append(f"- L{t.line_no}: {t.text}")
    return "\n".join(out) + "\n"


def build_report(root: Path) -> str:
    """Collect every source under ``root`` and render the Markdown list."""
    return render(
        collect_table_rows(root), collect_product_decisions(root), collect_tagged_lines(root)
    )


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point: print the list for ``--root`` (default: this repository)."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT, help="repository root (default: %(default)s)"
    )
    args = parser.parse_args(argv)
    sys.stdout.write(build_report(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
