"""``build/.n2f/manifest.json``: what each rule read and produced, written atomically."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory import __version__

MANIFEST_REL = Path(".n2f") / "manifest.json"


@dataclass
class Entry:
    """One rule's record after a successful run."""

    key: str
    reads: list[str]
    outputs: dict[str, str]  # relative path → sha256
    output_hash: str  # hash over the outputs' hashes (what downstream rules depend on)
    duration: float
    version: str = __version__
    rule_version: int = 1
    inputs: dict[str, str] = field(default_factory=dict)  # declared input hashes at run time
    values: dict[str, str] = field(default_factory=dict)  # value of every read at run time
    # P5: the reads made only while resolving an interface (the joint's business, not the
    # rule's own reach); recorded for the reach check, never part of the key
    iface_reads: list[str] = field(default_factory=list)


@dataclass
class Manifest:
    """All entries, keyed by rule id."""

    entries: dict[str, Entry] = field(default_factory=dict)
    build_id: str = ""

    @classmethod
    def load(cls, build_dir: Path) -> Manifest:
        """Read the manifest or return an empty one (a corrupt file counts as empty)."""
        path = build_dir / MANIFEST_REL
        for stale in path.parent.glob(".manifest-*.tmp") if path.parent.is_dir() else []:
            stale.unlink(missing_ok=True)
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            import sys

            print(f"warning: {path} is unreadable; everything will be rebuilt", file=sys.stderr)
            return cls()
        entries = {}
        for rid, e in data.get("entries", {}).items():
            try:
                entries[rid] = Entry(**e)
            except TypeError:
                continue
        return cls(entries=entries, build_id=str(data.get("build_id", "")))

    def save(self, build_dir: Path) -> None:
        """Write atomically (temp file + rename) so an interrupted build never corrupts it."""
        path = build_dir / MANIFEST_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "schema": 1,
            "build_id": self.build_id,
            "entries": {rid: asdict(e) for rid, e in sorted(self.entries.items())},
        }
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".manifest-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def forget(self, rule_id: str) -> None:
        """Drop one entry."""
        self.entries.pop(rule_id, None)
