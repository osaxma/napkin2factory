"""A text schematic export (``.kicad_sch``, an s-expression), never source (E1, S-157).

Written by ``elec:<circuit>`` next to the diagram, from the same record, for a person who
wants to open the circuit in a desktop schematic tool.  Nothing here runs such a tool, and
nothing reads the file back: the YAML model stays the source.  The file is deliberately
small: one library symbol per node (a box with a pin per terminal), the placed symbols in a
row, and for every wire a short wire stub and a label at each of its two pins, named after
the wire, so the tool joins the two ends by name (how a schematic tool reads a net label)
rather than by a drawn route.  The identifiers are UUIDs derived from the names, so the
same record always gives the same file.
"""

from __future__ import annotations

import uuid
from typing import Any

#: The schematic file format version the text follows (the tool's 2023 format).
VERSION = "20231120"
_NS = uuid.UUID("6f1c3d2a-5b8e-4f60-9a71-0c2d4e6f8a10")
GRID = 2.54  # the tool's 100 mil grid, in mm


def _q(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _uid(*names: str) -> str:
    return str(uuid.uuid5(_NS, "/".join(names)))


def _n(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _nodes(record: dict[str, Any]) -> list[tuple[str, str, list[str]]]:
    """``(uri, name, terminals)`` per node, in first-appearance order along the wires."""
    names = {d["uri"]: d["name"] for d in record.get("devices", [])}
    names.update({m["assembly"]: m.get("name", m["assembly"]) for m in record.get("boundary", [])})
    terms = {d["uri"]: list(d.get("terminals") or []) for d in record.get("devices", [])}
    order: dict[str, list[str]] = {}
    for w in record.get("wires", []):
        for end in (w["from"], w["to"]):
            base, _, t = end.partition("#")
            row = order.setdefault(base, list(terms.get(base, [])))
            if t not in row:
                row.append(t)
    return [
        (u, names.get(u, "Supply" if u.startswith("supply://") else u), r) for u, r in order.items()
    ]


def kicad_schematic(record: dict[str, Any]) -> str:
    """The circuit as ``.kicad_sch`` text (balanced s-expressions; symbols, wires, labels)."""
    cid = str(record.get("circuit", ""))
    nodes = _nodes(record)
    lib: list[str] = []
    placed: list[str] = []
    pin_at: dict[tuple[str, str], tuple[float, float]] = {}
    for i, (uri, name, terminals) in enumerate(nodes):
        sym = f"n2f:{uri.replace('://', '-')}"
        h = GRID * (len(terminals) + 1)
        pins = " ".join(
            f"(pin passive line (at -5.08 {_n(-GRID * (k + 1))} 0) (length 2.54) "
            f"(name {_q(t)} (effects (font (size 1.27 1.27)))) "
            f"(number {_q(str(k + 1))} (effects (font (size 1.27 1.27)))))"
            for k, t in enumerate(terminals)
        )
        lib.append(
            f"(symbol {_q(sym)} (in_bom yes) (on_board no) "
            f'(property "Reference" "X" (at 0 2.54 0) (effects (font (size 1.27 1.27)))) '
            f'(property "Value" {_q(name)} (at 0 5.08 0) (effects (font (size 1.27 1.27)))) '
            f"(symbol {_q(sym.split(':', 1)[1] + '_0_1')} "
            f"(rectangle (start -2.54 0) (end 7.62 {_n(-h)}) (stroke (width 0.254) (type default)) "
            f"(fill (type none)))) "
            f"(symbol {_q(sym.split(':', 1)[1] + '_1_1')} {pins}))"
        )
        x, y = 25.4 + i * 30.48, 25.4
        placed.append(
            f"(symbol (lib_id {_q(sym)}) (at {_n(x)} {_n(y)} 0) (unit 1) (in_bom yes) "
            f"(on_board no) (uuid {_q(_uid(cid, uri))}) "
            f'(property "Reference" {_q(f"X{i + 1}")} (at {_n(x)} {_n(y - 2.54)} 0) '
            f"(effects (font (size 1.27 1.27)))) "
            f'(property "Value" {_q(name)} (at {_n(x)} {_n(y - 5.08)} 0) '
            f"(effects (font (size 1.27 1.27)))))"
        )
        for k, t in enumerate(terminals):
            # the pin's free end, in sheet coordinates (the sheet's y grows downwards)
            pin_at[(uri, t)] = (x - 5.08, y + GRID * (k + 1))
    wires: list[str] = []
    for w in record.get("wires", []):
        for side, end in (("a", w["from"]), ("b", w["to"])):
            base, _, t = end.partition("#")
            px, py = pin_at[(base, t)]
            lx = px - GRID
            wires.append(
                f"(wire (pts (xy {_n(px)} {_n(py)}) (xy {_n(lx)} {_n(py)})) "
                f"(stroke (width 0) (type default)) (uuid {_q(_uid(cid, w['id'], side, 'w'))}))"
            )
            wires.append(
                f"(label {_q(w['id'])} (at {_n(lx)} {_n(py)} 0) "
                f"(effects (font (size 1.27 1.27)) (justify right)) "
                f"(uuid {_q(_uid(cid, w['id'], side, 'l'))}))"
            )
    lines = [
        f'(kicad_sch (version {VERSION}) (generator "napkin2factory")',
        f"  (uuid {_q(_uid(cid))})",
        '  (paper "A3")',
        f"  (title_block (title {_q(str(record.get('name') or cid))}) "
        f'(comment 1 "Exported from the product\'s wiring model; the model is the source."))',
        "  (lib_symbols",
        *(f"    {s}" for s in lib),
        "  )",
        *(f"  {s}" for s in placed),
        *(f"  {s}" for s in wires),
        '  (sheet_instances (path "/" (page "1")))',
        ")",
    ]
    return "\n".join(lines) + "\n"
