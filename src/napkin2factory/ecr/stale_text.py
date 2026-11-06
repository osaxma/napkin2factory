"""Words that may still give a changed parameter's old size (gate L, S-281).

A parameter moves and the drawing follows, but a part's free text (``material.spec``,
``manufacturer_notes``, ``description``) is typed by hand: it can keep saying the old size
and the manufacturer reads it. ``find`` lists, for each changed parameter, the text fields of
the parts and assemblies that read it whose words hold the old value as a number, so the
author checks them. It only reads; it never edits the model.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from napkin2factory.core.loader import Product

_QTY = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([^\d\s=][^\s]*)?\s*$")
_NUM = r"\d+(?:\.\d+)?"
_SIZE = re.compile(rf"(?<![\d.]){_NUM}(?:\s*[x×]\s*{_NUM})+(?![\d.])")
#: Fields that hold ids and links, not words a manufacturer reads.
_SKIP_KEYS = {"id", "rev", "geometry", "kind", "process", "interfaces", "satisfies"}
_URI = re.compile(r"^\w+://")


def _fields(node: Any, path: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if not path and key in _SKIP_KEYS:
                continue
            out += _fields(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for value in node:
            out += _fields(value, path)
    elif isinstance(node, str) and path and not _URI.match(node):
        out.append((path, node))
    return out


def _numbers_match(a: str, b: float) -> bool:
    try:
        return abs(float(a) - b) < 1e-9
    except ValueError:
        return False


def holds(text: str, number: float, unit: str) -> bool:
    """Whether ``text`` gives ``number`` with its unit, or inside an ``a x b`` size."""
    for size in _SIZE.finditer(text):
        if any(_numbers_match(n, number) for n in re.findall(_NUM, size.group())):
            return True
    if not unit:
        return False
    pattern = rf"(?<![\d.])({_NUM})\s*{re.escape(unit)}(?![A-Za-z0-9])"
    return any(_numbers_match(m.group(1), number) for m in re.finditer(pattern, text))


def find(product: Product, parameters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Text fields that still hold a changed parameter's old value, by part and field."""
    out: list[dict[str, Any]] = []
    objects: list[Any] = [*product.parts.values(), *product.assemblies.values()]
    for row in parameters:
        m = _QTY.match(str(row.get("before") or ""))
        if m is None or row.get("before") == row.get("after"):
            continue
        number, unit = float(m.group(1)), m.group(2) or ""
        for obj in objects:
            path = product.files.get(obj.uri)
            if path is None or not path.is_file():
                continue
            raw = path.read_text(encoding="utf-8")
            if f"param://{row['id']}" not in raw:
                continue
            data = yaml.safe_load(raw) or {}
            for field, text in _fields(data):
                if holds(text, number, unit):
                    out.append(
                        {
                            "object": obj.uri,
                            "field": field,
                            "text": text,
                            "parameter": row["id"],
                            "old": str(row["before"]),
                            "new": str(row.get("after") or "(removed)"),
                        }
                    )
    return out


def lines(items: list[dict[str, Any]]) -> list[str]:
    """The owner's reading of ``find``'s result, one line per field."""
    return [
        f'- `{i["object"].split("://")[-1]}`, {i["field"]}: "{i["text"]}" '
        f"(`{i['parameter']}` was {i['old']}, now {i['new']})"
        for i in items
    ]
