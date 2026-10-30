"""Content hashes for files, code, and recorded-read values."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    """``sha256:<hex>`` of raw bytes."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """``sha256:<hex>`` of a string (UTF-8)."""
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    """``sha256:<hex>`` of a file's bytes; ``missing`` if it does not exist."""
    p = Path(path)
    if not p.is_file():
        return "missing"
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def sha256_json(obj: Any) -> str:
    """Hash of a JSON-serialisable object with sorted keys."""
    return sha256_text(json.dumps(obj, sort_keys=True, default=str))


def sha256_tree(root: Path, suffixes: tuple[str, ...] = (".yaml", ".yml", ".md", ".py")) -> str:
    """Hash of every matching file under ``root`` (relative path + content), sorted."""
    h = hashlib.sha256()
    root = Path(root)
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix in suffixes and "__pycache__" not in p.parts:
                h.update(str(p.relative_to(root)).encode())
                h.update(sha256_file(p).encode())
    return "sha256:" + h.hexdigest()


def combine(parts: dict[str, str]) -> str:
    """Post-run key: sha256 over sorted ``name=hash`` lines."""
    lines = "\n".join(f"{k}={v}" for k, v in sorted(parts.items()))
    return sha256_text(lines)
