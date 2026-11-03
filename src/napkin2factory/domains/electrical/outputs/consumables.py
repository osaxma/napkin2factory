"""Consumable lines the electrical domain adds to the bill of materials (S-188).

Groups wires per conductor by reusing :func:`cable_rows` on records built via
:func:`circuit_record`, computing total cut length in metres as a BOM consumable line (E5, S-188).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from napkin2factory.core.domain import BomLine
from napkin2factory.domains.electrical.model.refs import circuits
from napkin2factory.domains.electrical.outputs.rules import circuit_record
from napkin2factory.domains.electrical.outputs.schedule import NOT_GIVEN, cable_rows


class _RecordContext:
    """Lightweight context adapting product and reader for circuit_record (S-188)."""

    def __init__(self, product: Any, reader: Callable[[str], Any]) -> None:
        self.product = product
        self.reader = reader
        self.log = self

    def proxy(self, obj: Any, uri: str) -> Any:
        return obj

    def add(self, key: str) -> None:
        self.reader(key)


def electrical_bom_lines(product: Any, reader: Callable[[str], Any]) -> list[BomLine]:
    """Every conductor to buy as a BOM consumable line (S-188).

    Groups wires per conductor (reusing :func:`cable_rows`), computes the total length in
    metres (``None`` if any wire's length is missing), and returns a :class:`BomLine` with
    ``unit="m"`` and ``unit_cost=None``.
    """
    circ_map = circuits(product)
    if not circ_map:
        return []
    ctx = _RecordContext(product, reader)
    records = [circuit_record(cast(Any, ctx), cid) for cid in sorted(circ_map)]
    rows = cable_rows(records)
    out: list[BomLine] = []
    for r in rows:
        cid = r["conductor"]
        total_str = r["total_length_m"]
        qty = None if total_str == NOT_GIVEN else float(total_str)
        bits = [r["label"]]
        if r["cross_section_mm2"] != NOT_GIVEN:
            bits.append(f"{r['cross_section_mm2']} mm²")
        if r["insulation"] != NOT_GIVEN:
            bits.append(r["insulation"])
        name = ", ".join(b for b in bits if b and b != NOT_GIVEN) or cid
        out.append(
            BomLine(
                id=cid,
                name=name,
                quantity=qty,
                unit="m",
                unit_cost=None,
                domain="electrical",
                source="",
            )
        )
    return out
