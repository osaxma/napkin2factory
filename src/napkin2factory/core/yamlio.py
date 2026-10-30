"""YAML reading and comment-preserving writing (ruamel for edits, PyYAML for reads)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from ruamel.yaml import YAML


def read_yaml(path: Path) -> Any:
    """Load a YAML file; returns ``{}`` for an empty file."""
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return {} if data is None else data


def write_yaml(path: Path, data: Any) -> None:
    """Write YAML with stable key order (for generated files)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True, default_flow_style=False)


def _ruamel() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096  # never re-wrap flow mappings: a one-value edit must be a one-line diff
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def load_roundtrip(path: Path) -> Any:
    """Load with ruamel so comments and key order survive an edit."""
    with Path(path).open("r", encoding="utf-8") as fh:
        return _ruamel().load(fh)


def dump_roundtrip(path: Path, data: Any) -> None:
    """Write a ruamel document back, preserving comments and order."""
    with Path(path).open("w", encoding="utf-8") as fh:
        _ruamel().dump(data, fh)


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Split front matter (between two ``---`` lines) from a Markdown body."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n---", 1)
    if len(parts) != 2:
        return {}, text
    head = parts[0][3:]
    body = parts[1]
    if body.startswith("\n"):
        body = body[1:]
    meta = yaml.safe_load(head) or {}
    if not isinstance(meta, dict):
        return {}, text
    return meta, body
