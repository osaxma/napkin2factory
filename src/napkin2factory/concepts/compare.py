"""``n2f concept compare``: one table, a row per value, a column per design (v0.8 R11).

Rows are the board's names, units and labels (the key dimensions, the estimate strip —
``cost`` joins it — and the verdict); columns are the cards. A forked card's column is
marked "from the built design"; a parked card's mass and cost show its built figures
"when parked". The text and ``--json`` forms carry the same rows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from napkin2factory.concepts.board import KEY_DIMS, NAMES, STRIP
from napkin2factory.core import concepts as cm
from napkin2factory.core.model.concepts import ConceptCard, LabelledValue
from napkin2factory.report.units import display

#: The owner's words for a screening verdict (JSON keeps ``verdict: green|red``; gate B, C7).
VERDICT_WORDS = {"green": "holds up", "red": "has problems"}


def _manifest(root: Path) -> dict[str, Any]:
    """The product name and display units from ``n2f.yaml`` (defaults: folder name, metric)."""
    name, units = root.name, "metric"
    manifest = root / "n2f.yaml"
    if manifest.is_file():
        try:
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            name = str((data.get("product") or {}).get("name") or name)
            units = str(data.get("units") or "metric")
        except yaml.YAMLError:
            pass
    return {"name": name, "units": units}


def _selected(root: Path, ids: list[str] | None) -> list[ConceptCard]:
    """The cards to compare: the named ones, else every card with a screening or ``built``."""
    if ids:
        return [cm.load_card(root, i) for i in ids]
    return [
        c for c in cm.load_concepts(root).values() if c.screening is not None or c.built is not None
    ]


def _column(card: ConceptCard) -> dict[str, Any]:
    """One card's column: its id, title and where its figures come from."""
    built_event = card.built.event if card.built is not None else None
    return {
        "id": card.id,
        "title": card.title,
        "status": card.status,
        "origin": "built" if built_event == "forked" else "napkin",
        "built_event": built_event,
    }


def _cell(card: ConceptCard, key: str, units: str) -> dict[str, Any] | None:
    """One card's value for a row, or ``None`` when it has none.

    A parked card's built mass and cost stand in for its napkin figures, marked "when
    parked" (R11).
    """
    if card.built is not None and card.built.event == "parked":
        if key == "mass" and card.built.mass:
            return {
                "value": display(card.built.mass, units),
                "label": "computed",
                "source": "when parked",
                "parked": True,
            }
        if key == "cost" and card.built.cost:
            return {
                "value": display(card.built.cost, units),
                "label": "computed",
                "source": "when parked",
                "parked": True,
            }
    sc = card.screening
    if sc is None:
        return None
    lv: LabelledValue | None = {**sc.computed, **sc.estimates}.get(key)
    if lv is None:
        return None
    return {
        "value": display(lv.value, units),
        "label": lv.label,
        "source": lv.source,
        "parked": False,
    }


def _value_row(key: str, cards: list[ConceptCard], units: str) -> dict[str, Any] | None:
    """One row of labelled values, or ``None`` when no card has one."""
    cells = {c.id: cell for c in cards if (cell := _cell(c, key, units)) is not None}
    if not cells:
        return None
    label = next(iter(cells.values()))["label"]
    return {
        "key": key,
        "name": NAMES.get(key, key.replace("_", " ")),
        "label": label,
        "cells": cells,
    }


def _verdict_row(cards: list[ConceptCard]) -> dict[str, Any]:
    """The verdict row: a screening verdict per card."""
    cells: dict[str, dict[str, Any]] = {}
    for c in cards:
        if c.verdict is not None:
            cells[c.id] = {
                "value": VERDICT_WORDS.get(c.verdict, c.verdict),
                "label": None,
                "source": "",
            }
        elif c.built is not None:
            cells[c.id] = {"value": "from the built design", "label": None, "source": ""}
    return {"key": "verdict", "name": "screening", "label": None, "cells": cells}


def compare(root: Path | str, ids: list[str] | None = None) -> dict[str, Any]:
    """The comparison table: columns (cards) and rows (board names, units, labels, verdict)."""
    root = Path(root)
    cards = _selected(root, ids)
    units = _manifest(root)["units"]
    rows: list[dict[str, Any]] = []
    for key in (*KEY_DIMS, *STRIP):
        row = _value_row(key, cards, units)
        if row is not None:
            rows.append(row)
    rows.append(_verdict_row(cards))
    return {
        "product": _manifest(root)["name"],
        "cards": [_column(c) for c in cards],
        "rows": rows,
    }


def _cell_text(cell: dict[str, Any] | None) -> str:
    """One cell as plain words: the value, its label, and "when parked" where it applies."""
    if cell is None:
        return "—"
    text = cell["value"] or "—"
    if cell.get("label"):
        text += f" ({cell['label']})"
    if cell.get("parked"):
        text += " when parked"
    return text


def render_text(data: dict[str, Any]) -> str:
    """The table as aligned plain text: card ids on top, value names down the left."""
    cards = data["cards"]
    rows = data["rows"]
    headers = [c["id"] for c in cards]
    origin = ["from the built design" if c["origin"] == "built" else "" for c in cards]
    name_width = max((len(r["name"]) for r in rows), default=0) + 2
    widths = [
        max(len(h), max((len(_cell_text(r["cells"].get(c["id"]))) for r in rows), default=0))
        for h, c in zip(headers, cards, strict=True)
    ]
    lines: list[str] = [
        (
            " " * name_width + "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))
        ).rstrip()
    ]
    if any(origin):
        lines.append(
            (
                " " * name_width
                + "  ".join(o.ljust(w) for o, w in zip(origin, widths, strict=True))
            ).rstrip()
        )
    for row in rows:
        cells = [_cell_text(row["cells"].get(c["id"])) for c in cards]
        line = row["name"].ljust(name_width) + "  ".join(
            v.ljust(w) for v, w in zip(cells, widths, strict=True)
        )
        lines.append(line.rstrip())
    return "\n".join(lines)


__all__ = ["compare", "render_text"]
