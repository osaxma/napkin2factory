"""What the owner's view shares: the build files it reads and the words it says things in.

The ``elec`` family (``outputs/``, M2) writes the files under ``build/electrical/``; the
owner's view only reads them (the wave-2 contract, S-159).  A file that is not there yet
reads as nothing: the section and the helpers then say what the model says.

Keys the readers record, so an edit of the wiring reruns them (D5):

* ``circuit://<id>`` — the output hash of rule ``elec:<id>`` (its ``connections.json``,
  diagram and words);
* :data:`SCHEDULE_KEY` — the output hash of rule ``elec-schedule`` (the three tables).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from napkin2factory.domains.electrical.model import EndRef, circuits, parse_end

#: The folder under ``build/`` the ``elec`` family writes (its ``output_dir``).
OUTPUT_DIR = "electrical"
#: The aggregate rule that writes the three tables (S-156: its id is the key's own).
SCHEDULE_RULE = "elec-schedule"
#: Its output hash, as a recorded read: the core values ``rule:<rule id>`` from the build
#: manifest (``core/graph/values.py``, S-156).
SCHEDULE_KEY = f"rule:{SCHEDULE_RULE}"
#: The three tables ``elec-schedule`` writes.
SCHEDULE_CSV = "schedule.csv"
LABELS_CSV = "labels.csv"
CABLES_CSV = "cables.csv"


def out_dir(build_dir: Path) -> Path:
    """``build/electrical/``."""
    return Path(build_dir) / OUTPUT_DIR


def circuit_key(cid: str) -> str:
    """``circuit://<id>``: the circuit's build output as a recorded read."""
    return f"circuit://{cid}"


def built_keys(product: Any) -> list[str]:
    """Every build key the owner's view reads: each circuit's output, then the tables'."""
    return [circuit_key(c) for c in sorted(circuits(product))] + [SCHEDULE_KEY]


def read_connections(build_dir: Path, cid: str) -> dict[str, Any] | None:
    """``build/electrical/<cid>/connections.json``, or ``None`` before it is built."""
    path = out_dir(build_dir) / cid / "connections.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def read_diagram(build_dir: Path, cid: str) -> str:
    """``build/electrical/<cid>/diagram.svg`` as text, or ``""`` before it is built."""
    path = out_dir(build_dir) / cid / "diagram.svg"
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else ""
    except OSError:
        return ""


def read_table(build_dir: Path, name: str) -> list[dict[str, str]]:
    """One of the tables (``schedule.csv`` …) as rows keyed by its header; ``[]`` if absent."""
    path = out_dir(build_dir) / name
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            return [dict(row) for row in csv.DictReader(fh)]
    except (OSError, csv.Error):
        return []


# ---- words ---------------------------------------------------------------------------------


def _record(log: Any, *keys: str) -> None:
    if log is not None:
        for key in keys:
            log.add(key)


def part_name(product: Any, pid: str, log: Any = None) -> str:
    """A part's own name (its id when it has none or does not exist); ``log`` records it."""
    _record(log, f"part://{pid}#name")
    part = product.parts.get(pid)
    return str(getattr(part, "name", None) or pid)


def device_name(product: Any, did: str, log: Any = None) -> str:
    """A device as the owner reads it: its part's name, with its instance words if any."""
    dev = product.families.get("device", {}).get(did)
    _record(log, f"device://{did}#part", f"device://{did}#instance")
    if dev is None:
        return did
    name = part_name(product, dev.part.id, log)
    return f"{name} ({dev.instance})" if dev.instance else name


def end_words(product: Any, end: str | EndRef, log: Any = None) -> str:
    """A connection end in words: "Switch terminal 2", "the supply terminal L"."""
    ref = parse_end(end) if isinstance(end, str) else end
    if ref.scheme == "device":
        who = device_name(product, ref.id, log)
    elif ref.scheme == "part":
        named = [d for d in product.families.get("device", {}).values() if d.part.id == ref.id]
        who = (
            device_name(product, named[0].id, log)
            if len(named) == 1
            else part_name(product, ref.id, log)
        )
    elif ref.scheme == "supply":
        who = "the supply"  # as the elec record says it (S-157)
    else:
        _record(log, f"asm://{ref.id}#name")
        asm = product.assemblies.get(ref.id)
        who = str(getattr(asm, "name", None) or ref.id)
    return f"{who} terminal {ref.terminal}"


def entry_words(product: Any, iface_id: str, log: Any = None) -> str:
    """A cable entry in words: its name, else "the cable entry <id>"."""
    _record(log, f"iface://{iface_id}#name")
    iface = product.interfaces.get(iface_id)
    name = getattr(iface, "name", None) if iface is not None else None
    return str(name) if name else f"the cable entry {iface_id}"


def circuit_title(circuit: Any) -> str:
    """A circuit's owner words: its name, else its id."""
    return str(circuit.name or circuit.id)
