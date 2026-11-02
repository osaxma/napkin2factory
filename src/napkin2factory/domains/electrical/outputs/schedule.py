"""The cable schedule, the terminal labels and the cable to buy (E5, S-145).

Pure functions of the circuits' records (``<circuit>/connections.json``, the wave-2
contract), in circuit then wire order, so the three tables can never disagree with the
diagrams:

* ``schedule.csv`` — one row per wire: what to cut and where it goes;
* ``labels.csv`` — one row per wire end: the label the shop puts on it;
* ``cables.csv`` — per conductor type, the total length to buy; a wire with no length
  makes the total read "not given", never a guess (the parts list does not carry these
  lines in v0.6: S-145).
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

#: The header rows, exactly as the wave-2 contract fixes them.
SCHEDULE_COLUMNS = (
    "wire",
    "circuit",
    "from",
    "to",
    "conductor",
    "cross_section_mm2",
    "length_m",
    "colour",
    "via",
)
LABEL_COLUMNS = ("label", "device", "terminal", "wire", "circuit")
CABLE_COLUMNS = (
    "conductor",
    "label",
    "cross_section_mm2",
    "insulation",
    "total_length_m",
    "wires",
)
NOT_GIVEN = "not given"


def number(value: float | None) -> str:
    """A number for a table: up to three decimals, no trailing zeros; ``None`` is not given."""
    if value is None:
        return NOT_GIVEN
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _wires(records: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [(rec, w) for rec in records for w in rec["wires"]]


def schedule_rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    """One row per wire: id, circuit, both ends in words, conductor, size, length, colour, entry."""
    return [
        {
            "wire": w["id"],
            "circuit": rec["circuit"],
            "from": w["from_words"],
            "to": w["to_words"],
            "conductor": w["conductor"] or NOT_GIVEN,
            "cross_section_mm2": number(w["csa_mm2"]),
            "length_m": number(w["length_m"]),
            "colour": w["colour"],
            "via": w["via_words"] or "",
        }
        for rec, w in _wires(records)
    ]


def end_tag(end: str) -> tuple[str, str]:
    """``device://switch#2`` → ``("switch", "2")``: the short device tag and the terminal."""
    base, _, terminal = end.partition("#")
    return base.split("://", 1)[1], terminal


def label_rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    """One row per wire end: the label (wire id, then where this end lands), device, terminal.

    The label reads ``<wire> <device>:<terminal>``, e.g. ``heater-1 switch:1``: the shop
    prints it on the sleeve at that end.  ``device`` is the end in words without the
    terminal ("Switch", "the supply").
    """
    rows = []
    for rec, w in _wires(records):
        for end, words in ((w["from"], w["from_words"]), (w["to"], w["to_words"])):
            tag, terminal = end_tag(end)
            rows.append(
                {
                    "label": f"{w['id']} {tag}:{terminal}",
                    "device": words.removesuffix(f" terminal {terminal}"),
                    "terminal": terminal,
                    "wire": w["id"],
                    "circuit": rec["circuit"],
                }
            )
    return rows


def cable_rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    """The cable to buy: per conductor id (first-seen order), its total length and its wires."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for _, w in _wires(records):
        groups.setdefault(w["conductor"] or NOT_GIVEN, []).append(w)
    rows = []
    for cid, wires in groups.items():
        lengths = [w["length_m"] for w in wires]
        total = None if any(v is None for v in lengths) else sum(lengths)
        first = wires[0]
        rows.append(
            {
                "conductor": cid,
                "label": first["conductor_label"],
                "cross_section_mm2": number(first["csa_mm2"]),
                "insulation": first.get("insulation") or NOT_GIVEN,
                "total_length_m": number(total),
                "wires": " ".join(w["id"] for w in wires),
            }
        )
    return rows


def csv_text(columns: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    """The rows as CSV (UTF-8 text, a header row, newline line ends: byte-stable)."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def write_tables(
    records: list[dict[str, Any]], folder: Path
) -> tuple[dict[str, list[dict[str, str]]], list[Path]]:
    """Write the three tables into ``folder``; return their rows (for the hash) and paths."""
    folder.mkdir(parents=True, exist_ok=True)
    tables = {
        "schedule.csv": (SCHEDULE_COLUMNS, schedule_rows(records)),
        "labels.csv": (LABEL_COLUMNS, label_rows(records)),
        "cables.csv": (CABLE_COLUMNS, cable_rows(records)),
    }
    paths = []
    for name, (columns, rows) in tables.items():
        path = folder / name
        path.write_text(csv_text(columns, rows), encoding="utf-8")
        paths.append(path)
    return {name: rows for name, (_, rows) in tables.items()}, paths
