"""Helpers a manual page calls for the wiring (F5, docs/domains.md §3.7).

* ``circuit("power")`` — the circuit as a page prints it: ``.name`` (its owner words),
  ``.purpose``, ``.protection``, ``.devices`` (each ``.name``, ``.role``, ``.terminals``),
  ``.wires`` (each ``.id``, ``.from_words``, ``.to_words``, ``.conductor``, ``.csa``,
  ``.length``, ``.colour``, ``.via``) and ``.table`` (the wires as a Markdown table).
  ``{{ circuit("power") }}`` prints its name.
* ``cable_schedule()``, ``terminal_labels()``, ``cables_to_buy()`` — the rows of
  ``build/electrical/schedule.csv``, ``labels.csv`` and ``cables.csv`` as dicts keyed by
  their header (``row.wire``, ``row.label`` …).

Every read is recorded (D5): a model field through ``h.proxy`` (``circuit://power#name``),
a build file by its rule's key with ``h.log.add`` (``circuit://power``, the schedule rule's
key).  The ``elec`` family runs before the manuals (``before=("doc",)``, S-143), so a page
using these is stale after a wiring edit and fresh after one build.

The build folder is ``h.product.paths.build``: the contract's ``HelperContext`` has no
``build_dir`` (B-0142).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from napkin2factory.core.domain import HelperContext
from napkin2factory.core.units import format_quantity, is_quantity
from napkin2factory.domains.electrical.model import circuits, devices
from napkin2factory.domains.electrical.owner.common import (
    CABLES_CSV,
    LABELS_CSV,
    SCHEDULE_CSV,
    SCHEDULE_KEY,
    circuit_key,
    device_name,
    end_words,
    entry_words,
    read_connections,
    read_table,
)
from napkin2factory.domains.electrical.owner.vocabulary import PURPOSE_WORDS, ROLE_WORDS


def _build_dir(h: HelperContext) -> Path:
    return Path(h.product.paths.build)


class Row(dict[str, Any]):
    """A table row a page reads by key or by attribute (``row.wire`` or ``row["wire"]``)."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(f"no column {name!r}; columns: {', '.join(self)}") from exc


def _wire_rows(h: HelperContext, cid: str, model: Any) -> list[Row]:
    """The circuit's wires: from its ``connections.json`` when built, else from the model."""
    h.log.add(circuit_key(cid))
    record = read_connections(_build_dir(h), cid)
    if record is not None:
        return [
            Row(
                id=w.get("id", ""),
                from_words=w.get("from_words") or w.get("from", ""),
                to_words=w.get("to_words") or w.get("to", ""),
                conductor=w.get("conductor_label") or w.get("conductor") or "not given",
                csa=_number(w.get("csa_mm2"), "mm²"),
                length=_number(w.get("length_m"), "m"),
                colour=w.get("colour") or "not given",
                via=w.get("via_words") or "",
            )
            for w in record.get("wires", [])
        ]
    rows = []
    product = h.product
    for n, conn in enumerate(model.connections, start=1):
        via = conn.via
        rows.append(
            Row(
                id=f"{cid}-{n}",
                from_words=end_words(product, str(conn.from_), h.log),
                to_words=end_words(product, str(conn.to), h.log),
                conductor=str(conn.conductor or "not given"),
                csa="from the table",
                length=_given(conn.length),
                colour=str(conn.colour) if conn.colour else "the region's colour",
                via=entry_words(product, str(via).split("://", 1)[1], h.log) if via else "",
            )
        )
    return rows


def _given(value: Any) -> str:
    """A model value as written: a quantity formatted, a ``param://`` as named, else "not given"."""
    if value is None:
        return "not given"
    return format_quantity(value) if is_quantity(value) else str(value)


def _number(value: Any, unit: str) -> str:
    if value is None or value == "":
        return "not given"
    try:
        return f"{float(value):g} {unit}"
    except (TypeError, ValueError):
        return str(value)


def _markdown_table(rows: list[Row]) -> str:
    head = "| Wire | From | To | Conductor | Cross-section | Length | Colour | Through |\n"
    head += "|---|---|---|---|---:|---:|---|---|\n"
    body = "".join(
        f"| {r.id} | {r.from_words} | {r.to_words} | {r.conductor} | {r.csa} | {r.length} "
        f"| {r.colour} | {r.via} |\n"
        for r in rows
    )
    return head + body


class CircuitView:
    """One circuit as a manual page prints it; each attribute records what it reads."""

    def __init__(self, h: HelperContext, cid: str) -> None:
        """The circuit ``cid`` (it exists) read through the page's recording accessor."""
        self._h = h
        self.id = cid
        self._model = h.proxy(circuits(h.product)[cid], f"circuit://{cid}")

    @property
    def name(self) -> str:
        """The circuit's owner words: its ``name``, else its id."""
        return str(self._model.name or self.id)

    @property
    def purpose(self) -> str:
        """Power, control, sensing or earth, in words."""
        p = str(self._model.purpose)
        return PURPOSE_WORDS.get(p, p)

    @property
    def protection(self) -> str:
        """What protects the circuit, in words."""
        text = str(self._model.protection or "")
        if not text:
            return "no protective device named"
        if text == "supply":
            return "the supply's own protective device"
        scheme, _, ident = text.partition("://")
        if scheme == "device":
            return f"the {device_name(self._h.product, ident, self._h.log)}"
        if scheme == "part":
            self._h.log.add(f"part://{ident}#name")
            part = self._h.product.parts.get(ident)
            return f"the {getattr(part, 'name', None) or ident}"
        return text

    @property
    def wires(self) -> list[Row]:
        """The circuit's wires, in its connection order."""
        return _wire_rows(self._h, self.id, self._model)

    @property
    def table(self) -> str:
        """The wires as a Markdown table."""
        return _markdown_table(self.wires)

    @property
    def devices(self) -> list[Row]:
        """The devices the circuit's connections reach, in the order first met."""
        seen: list[str] = []
        for conn in self._model.connections:
            for end in conn.ends():
                hit = None
                if end.scheme == "device":
                    hit = end.id
                elif end.scheme == "part":
                    named = [d for d in devices(self._h.product).values() if d.part.id == end.id]
                    hit = named[0].id if len(named) == 1 else None
                if hit is not None and hit not in seen:
                    seen.append(hit)
        out = []
        for did in seen:
            dev = self._h.proxy(devices(self._h.product)[did], f"device://{did}")
            out.append(
                Row(
                    id=did,
                    name=device_name(self._h.product, did, self._h.log),
                    role=ROLE_WORDS.get(str(dev.role), str(dev.role)),
                    terminals=", ".join(str(t) for t in dev.terminals) or "not sourced yet",
                )
            )
        return out

    def __str__(self) -> str:
        """``{{ circuit("power") }}`` prints the circuit's name."""
        return self.name


def circuit_helper(h: HelperContext) -> Any:
    """``circuit("<id>")``: the circuit as a page prints it (every read recorded, D5)."""

    def circuit(cid: str) -> CircuitView:
        cid = cid.replace("circuit://", "")
        if cid not in circuits(h.product):
            raise h.error(
                f"circuit('{cid}') does not exist; circuits: "
                + (", ".join(sorted(circuits(h.product))) or "none")
            )
        return CircuitView(h, cid)

    return circuit


def _table_helper(name: str) -> Callable[[HelperContext], Any]:
    def factory(h: HelperContext) -> Any:
        def rows() -> list[Row]:
            # the whole table is the schedule rule's output; each circuit's key too, so a
            # page is stale after any wiring edit even before that rule exists
            h.log.add(SCHEDULE_KEY)
            for cid in sorted(circuits(h.product)):
                h.log.add(circuit_key(cid))
            return [Row(r) for r in read_table(_build_dir(h), name)]

        return rows

    return factory


cable_schedule_helper = _table_helper(SCHEDULE_CSV)
cable_schedule_helper.__doc__ = "``cable_schedule()``: one row per wire (``schedule.csv``)."
terminal_labels_helper = _table_helper(LABELS_CSV)
terminal_labels_helper.__doc__ = "``terminal_labels()``: one row per wire end (``labels.csv``)."
cables_to_buy_helper = _table_helper(CABLES_CSV)
cables_to_buy_helper.__doc__ = "``cables_to_buy()``: one row per conductor (``cables.csv``)."


DOC_HELPERS: dict[str, Callable[[HelperContext], Any]] = {
    "circuit": circuit_helper,
    "cable_schedule": cable_schedule_helper,
    "terminal_labels": terminal_labels_helper,
    "cables_to_buy": cables_to_buy_helper,
}
