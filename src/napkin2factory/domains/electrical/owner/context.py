"""What ``n2f context asm://<id>`` adds for the wiring (F1, docs/domains.md §3.12).

A one-module simulation (v0.4, S-116) edits only its module's files, so it needs the wiring
that touches the module and nothing else: the circuits that reach a device sitting in the
module (or the module itself, when it is supplied from elsewhere and wired to by its
terminals), each with its file and its connections in owner words, an end outside the module
marked so; then the cable entries on the module's parts or among its ports.  A circuit with
no device in the module is another module's and is not listed.
"""

from __future__ import annotations

from typing import Any

from napkin2factory.core.domain import ContextContribution
from napkin2factory.core.units import format_quantity, is_quantity
from napkin2factory.domains.electrical.model import (
    CIRCUIT_FOLDER,
    ENTRY_KIND,
    EndRef,
    circuits,
    devices,
)
from napkin2factory.domains.electrical.owner.common import (
    circuit_title,
    end_words,
    entry_words,
)
from napkin2factory.domains.electrical.owner.vocabulary import PURPOSE_WORDS


def _module_parts(product: Any, members: list[str]) -> set[str]:
    return {
        c.part.id
        for a in members
        if a in product.assemblies
        for c in product.assemblies[a].children
        if c.part is not None
    }


def _inside(product: Any, end: EndRef, parts: set[str], members: list[str]) -> bool:
    """True when the end is a terminal of a device on the module's parts, or of the module."""
    if end.scheme == "device":
        dev = devices(product).get(end.id)
        return dev is not None and dev.part.id in parts
    if end.scheme == "part":
        return end.id in parts
    if end.scheme == "asm":
        return end.id in members
    return False  # the supply is the site's, never inside a module


def _file(product: Any, cid: str) -> str:
    path = product.files.get(f"circuit://{cid}")
    if path is None:
        return f"{CIRCUIT_FOLDER}/{cid}.yaml"
    try:
        return str(path.relative_to(product.root))
    except ValueError:
        return str(path)


def wiring_context(product: Any, aid: str, members: list[str]) -> list[str]:
    """Markdown lines for the module ``aid``: its circuits, then its cable entries."""
    parts = _module_parts(product, members)
    lines: list[str] = []
    for cid, circuit in sorted(circuits(product).items()):
        ends = [(conn, conn.ends()) for conn in circuit.connections]
        if not any(_inside(product, e, parts, members) for _, pair in ends for e in pair):
            continue
        purpose = PURPOSE_WORDS.get(circuit.purpose, circuit.purpose)
        lines.append(
            f"- circuit://{cid}: {circuit_title(circuit)} ({purpose} circuit), "
            f"in {_file(product, cid)}"
        )
        for conn, (a, b) in ends:
            words = []
            for end in (a, b):
                said = end_words(product, end)
                if end.scheme != "supply" and not _inside(product, end, parts, members):
                    said += " (outside this module)"
                words.append(said)
            length: Any = conn.length
            if length is not None:
                length = format_quantity(length) if is_quantity(length) else str(length)
            extra = [x for x in (conn.conductor, length) if x]
            if conn.via is not None:
                extra.append(f"through {entry_words(product, conn.via.id)}")
            tail = f" — {', '.join(extra)}" if extra else ""
            lines.append(f"  - {words[0]} to {words[1]}{tail}")
    ports = {
        str(p) for a in members if a in product.assemblies for p in product.assemblies[a].ports
    }
    for iid, iface in sorted(product.interfaces.items()):
        if iface.kind != ENTRY_KIND:
            continue
        on_module = any(
            (p.scheme == "part" and p.id in parts) or (p.scheme == "asm" and p.id in members)
            for p in iface.parties
        )
        if not on_module and iface.uri not in ports:
            continue
        passes = [str(c) for c in getattr(iface.spec, "passes", [])]
        crossing = ", ".join(
            circuit_title(circuits(product)[c.split("://", 1)[1]])
            for c in passes
            if c.split("://", 1)[1] in circuits(product)
        )
        role = "a port of this module" if iface.uri in ports else "a cable entry on its parts"
        lines.append(
            f"- iface://{iid}: {entry_words(product, iid)} ({role})"
            + (f", carries {crossing}" if crossing else ", carries no circuit yet")
        )
    return lines


CONTEXT = (ContextContribution("electrical", "Wiring in this module", wiring_context),)
