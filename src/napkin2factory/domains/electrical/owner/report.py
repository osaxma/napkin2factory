"""The report's "Wiring" section (F5, ELECTRICAL_STAGE M4, DoD 2).

Per circuit: its diagram inline (``build/electrical/<c>/diagram.svg``, made page-safe by
:mod:`.svg`) and its wires as a table; then the cable schedule, the "cable to buy" totals
and the wiring check rows (kind ``electrical``) in owner words.  When the wiring is left for
later or done elsewhere, the section opens with the scope line the rest of the system says
(the core's words, S-148, S-150).  A product with no wiring and no scope entry for it has no
section at all (E12).

Reads (D5): every model field shown goes through ``sctx.proxy``; the build files are the
``elec`` rules' outputs, ``circuit://<id>`` and the schedule rule's key, which
:func:`wiring_report_reads` adds to the report rule's reads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from napkin2factory.core.domain import ReportSection, SectionContext
from napkin2factory.core.units import format_quantity, is_quantity
from napkin2factory.domains.electrical.model import circuits, has_content, parse_end
from napkin2factory.domains.electrical.owner.common import (
    CABLES_CSV,
    LABELS_CSV,
    SCHEDULE_CSV,
    built_keys,
    circuit_title,
    device_name,
    end_words,
    entry_words,
    part_name,
    read_connections,
    read_diagram,
    read_table,
)
from napkin2factory.domains.electrical.owner.svg import inline_svg
from napkin2factory.domains.electrical.owner.vocabulary import PURPOSE_WORDS

#: The domain's name: its scope key and the kind of its check rows.
DOMAIN = "electrical"


def _scope_line(product: Any) -> str | None:
    """The scope line for a wiring left for later or done elsewhere, in the core's words."""
    entry = product.manifest.scope.get(DOMAIN)
    if entry is None or entry.state == "in":
        return None
    # imported here: the core's check engine imports the loader, which imports this domain
    from napkin2factory.core.checks.stage import scope_entry

    # the public way to say a domain's scope line (S-163)
    item = scope_entry(product, DOMAIN)
    return None if item is None else str(item["line"])


def _number(value: Any, unit: str) -> str:
    """``2.5`` and ``"mm²"`` → ``"2.5 mm²"``; ``None`` or blank → "not given"."""
    if value is None or value == "":
        return "not given"
    try:
        return f"{float(value):g} {unit}"
    except (TypeError, ValueError):
        return str(value)


def _words(product: Any, text: Any) -> str:
    """A table cell in owner words: a connection end or a cable entry said, else as written."""
    s = "" if text is None else str(text)
    if s.startswith("iface://"):
        return entry_words(product, s[len("iface://") :])
    if s.startswith("circuit://"):
        c = circuits(product).get(s[len("circuit://") :])
        return circuit_title(c) if c is not None else s
    try:
        return end_words(product, parse_end(s))
    except ValueError:
        return s


def _count(wires: Any) -> str:
    """The ``wires`` column of ``cables.csv`` (the wire ids, space-separated) as a count."""
    text = str(wires or "").strip()
    return text if text.isdigit() else str(len(text.split()))


def _wires_from_build(record: dict[str, Any]) -> list[dict[str, str]]:
    """The wires of ``connections.json`` (the ``elec`` rule's words), one row each."""
    rows = []
    for w in record.get("wires", []):
        rows.append(
            {
                "id": str(w.get("id") or ""),
                "from": str(w.get("from_words") or w.get("from") or ""),
                "to": str(w.get("to_words") or w.get("to") or ""),
                "conductor": str(w.get("conductor_label") or w.get("conductor") or "not given"),
                "csa": _number(w.get("csa_mm2"), "mm²"),
                "length": _number(w.get("length_m"), "m"),
                "colour": str(w.get("colour") or "not given"),
                "via": str(w.get("via_words") or w.get("via") or ""),
            }
        )
    return rows


def _quantity(value: Any) -> str:
    """A model value as text: a quantity formatted, a ``param://`` said as written."""
    if value is None:
        return ""
    return format_quantity(value) if is_quantity(value) else str(value)


def _wires_from_model(product: Any, circuit: Any, cid: str, log: Any) -> list[dict[str, str]]:
    """The circuit's connections as the model says them (before its rule has run)."""
    rows = []
    for n, conn in enumerate(circuit.connections, start=1):
        via = conn.via
        rows.append(
            {
                "id": f"{cid}-{n}",
                "from": end_words(product, conn.from_, log),
                "to": end_words(product, conn.to, log),
                "conductor": str(conn.conductor or "not given"),
                "csa": "from the table",
                "length": _quantity(conn.length) or "not given",
                "colour": str(conn.colour or "the region's colour"),
                "via": entry_words(product, via.id, log) if via is not None else "",
            }
        )
    return rows


def _protection_words(product: Any, record: dict[str, Any] | None, prot: Any, log: Any) -> str:
    if record is not None:
        words = (record.get("protection") or {}).get("words")
        if words:
            return str(words)
    if prot is None:
        return "no protective device named"
    text = str(prot)
    if text == "supply":
        return "the supply's own protective device"
    if text.startswith("device://"):
        return f"the {device_name(product, text.split('://', 1)[1], log)}"
    if text.startswith("part://"):
        return f"the {part_name(product, text.split('://', 1)[1], log)}"
    return text


def _check_rows(build_dir: Path) -> list[dict[str, str]]:
    """The ``electrical`` rows of ``build/checks/checks.json``, failing ones first."""
    path = Path(build_dir) / "checks" / "checks.json"
    if not path.is_file():
        return []
    try:
        results = json.loads(path.read_text(encoding="utf-8")).get("results", [])
    except (OSError, ValueError):
        return []
    order = {"fail": 0, "choice": 1, "warn": 2, "needs-human": 3, "later": 4, "skip": 5}
    rows = [
        {
            "id": str(r.get("id", "")),
            "status": str(r.get("status", "")),
            "title": str(r.get("title") or r.get("subject") or ""),
            "message": str(r.get("persona_message") or r.get("message") or ""),
        }
        for r in results
        if r.get("kind") == DOMAIN
    ]
    return sorted(rows, key=lambda r: (order.get(r["status"], 6), r["id"]))


def wiring_report_data(sctx: SectionContext) -> dict[str, Any]:
    """What the section shows: the scope line, each circuit, the tables, the check rows."""
    product = sctx.product
    build_dir = sctx.build_dir
    shown = []
    for cid, raw in sorted(circuits(product).items()):
        c = sctx.proxy(raw, f"circuit://{cid}")
        record = read_connections(build_dir, cid)
        wires = (
            _wires_from_build(record) if record else _wires_from_model(product, c, cid, sctx.log)
        )
        boundary = [str(b.get("words", "")) for b in (record or {}).get("boundary", [])]
        voltage = c.voltage
        shown.append(
            {
                "id": cid,
                "title": circuit_title(c),
                "purpose": PURPOSE_WORDS.get(str(c.purpose), str(c.purpose)),
                "voltage": f"{_quantity(voltage)}{' DC' if c.dc else ''}" if voltage else "",
                "protection": _protection_words(product, record, c.protection, sctx.log),
                "notes": c.notes or "",
                "svg": inline_svg(read_diagram(build_dir, cid), f"wiring-{cid}"),
                "wires": wires,
                "boundary": [b for b in boundary if b],
                "built": record is not None,
            }
        )
    schedule = [
        {
            "wire": r.get("wire", ""),
            "circuit": _words(product, r.get("circuit", "")),
            "from": _words(product, r.get("from", "")),
            "to": _words(product, r.get("to", "")),
            "conductor": r.get("conductor", ""),
            "csa": _number(r.get("cross_section_mm2"), "mm²"),
            "length": _number(r.get("length_m"), "m"),
            "colour": r.get("colour") or "not given",
            "via": _words(product, r.get("via", "")),
        }
        for r in read_table(build_dir, SCHEDULE_CSV)
    ]
    cables = [
        {
            "label": r.get("label") or r.get("conductor", ""),
            "csa": _number(r.get("cross_section_mm2"), "mm²"),
            "insulation": r.get("insulation") or "not given",
            "total": _number(r.get("total_length_m"), "m"),
            "wires": _count(r.get("wires", "")),
        }
        for r in read_table(build_dir, CABLES_CSV)
    ]
    return {
        "scope_line": _scope_line(product),
        "circuits": shown,
        "schedule": schedule,
        "cables": cables,
        "labels": len(read_table(build_dir, LABELS_CSV)),
        "rows": _check_rows(build_dir),
    }


def wiring_report_reads(product: Any) -> list[str]:
    """The ``elec`` rules' outputs the section shows: each circuit's, and the tables'."""
    return built_keys(product) if has_content(product) else []


def show_wiring(product: Any) -> bool:
    """On the page when the product has wiring, or its scope says where the wiring stands."""
    return has_content(product) or DOMAIN in product.manifest.scope


REPORT_SECTIONS = (
    ReportSection(
        "wiring",
        "Wiring",
        group="Product",
        fragment="owner/wiring.html.j2",
        data=wiring_report_data,
        reads=wiring_report_reads,
        show=show_wiring,
    ),
)
