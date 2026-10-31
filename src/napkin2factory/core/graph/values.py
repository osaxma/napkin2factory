"""``value_of(key)``: the current value behind a recorded read, as a hashable string.

The needs-run decision (§6.1) recomputes a rule's key from its *last recorded read set*
against current values.  This module is the single place that knows how to turn a key
like ``param://x``, ``part://x#props.mass`` or ``bom://rollups#total_cost`` into a string.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from napkin2factory.core.graph.hashing import sha256_file, sha256_json
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.loader import Product
from napkin2factory.core.units import format_quantity, is_quantity
from napkin2factory.core.uris import Uri, UriError

RULE_FOR_SCHEME = {"part": "part:", "asm": "asm:", "doc": "doc:", "drawing": "drawing:"}

#: Membership keys (gate-1 B1): the *set* of ids of a kind, so adding or removing an
#: object changes every rule that enumerates it.
MEMBERSHIP: dict[str, str] = {
    "set://parts": "parts",
    "set://asms": "assemblies",
    "set://reqs": "requirements",
    "set://params": "parameters",
    "set://docs": "docs",
    "set://decs": "decisions",
    "set://ecrs": "ecrs",
    "set://signoffs": "signoffs",
    "set://ifaces": "interfaces",
}


def membership_value(product: Product, key: str) -> str:
    """Hash of the sorted ids (parts also carry whether they have geometry)."""
    attr = MEMBERSHIP[key]
    coll = getattr(product, attr)
    if key == "set://parts":
        return sha256_json(sorted((p.id, p.has_geometry, p.kind) for p in coll.values()))
    return sha256_json(sorted(coll))


def _fmt(v: Any) -> str:
    if is_quantity(v):
        # shortest round-trip repr: 200.0004 mm must not key the same as 200 mm (gate-1 C3)
        text = format_quantity(v)
        unit = text.split(" ", 1)[1] if " " in text else ""
        return f"{float(v.magnitude)!r} {unit}".strip()
    if hasattr(v, "model_dump"):
        return sha256_json(v.model_dump(mode="json"))
    if isinstance(v, (dict, list)):
        return sha256_json(v)
    return str(v)


def _json_field(path: Path, selector: tuple[str, ...]) -> str:
    if not path.is_file():
        return "unbuilt"
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return "corrupt"  # a half-written file forces a rerun instead of a traceback
    for key in selector:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return "missing"
    return _fmt(data)


def value_of(
    product: Product,
    manifest: Manifest,
    build_dir: Path,
    key: str,
    overrides: dict[str, Any] | None = None,
) -> str:
    """Current value for a dependency key; ``overrides`` lets impact ask "what if"."""
    overrides = overrides or {}
    if key in overrides:
        return _fmt(overrides[key])
    if key.startswith("rule:"):
        entry = manifest.entries.get(key[len("rule:") :])
        return entry.output_hash if entry else "unbuilt"
    if key in MEMBERSHIP:
        return membership_value(product, key)
    if key in ("style:geometry", "style:look"):
        from napkin2factory.core.errors import N2FError
        from napkin2factory.core.style import geometry_fingerprint, load_style, look_fingerprint

        try:
            if key == "style:look":
                return sha256_json(look_fingerprint(product.paths.root))
            return sha256_json(geometry_fingerprint(load_style(product.paths.root)))
        except N2FError:
            return "invalid"
    if key.startswith("signoff:"):
        return sha256_file(product.paths.signoffs / f"{key[len('signoff:') :]}.yaml")
    if key.startswith("manifest://product"):
        sel = key.split("#", 1)[1] if "#" in key else ""
        obj: Any = product.manifest.product
        for part in sel.split(".") if sel else []:
            obj = getattr(obj, part, None)
        return _fmt(obj)
    try:
        uri = Uri.parse(key)
    except UriError:
        return "unknown:" + key
    if uri.scheme == "param":
        if f"param://{uri.id}" in overrides:
            return _fmt(overrides[f"param://{uri.id}"])
        try:
            return _fmt(product.parameter_value(uri.id))
        except Exception:
            return "invalid"
    if uri.scheme == "iface":
        from napkin2factory.geometry.accessors import resolve_interface

        if uri.id not in product.interfaces:
            return "missing"
        try:
            return sha256_json(
                resolve_interface(product, product.interfaces[uri.id]).model_dump(mode="json")
            )
        except Exception:
            return "invalid"
    if uri.scheme in ("part", "asm"):
        if uri.selector and uri.selector[0] == "props":
            sub = "parts" if uri.scheme == "part" else "assemblies"
            return _json_field(build_dir / sub / uri.id / "props.json", uri.selector[1:])
        if uri.selector:
            try:
                return _fmt(product.select(uri))
            except KeyError:
                return "missing"
        entry = manifest.entries.get(f"{uri.scheme}:{uri.id}")
        return entry.output_hash if entry else "unbuilt"
    if uri.scheme == "doc":
        entry = manifest.entries.get(f"doc:{uri.id}")
        return entry.output_hash if entry else "unbuilt"
    if uri.scheme == "drawing":
        entry = manifest.entries.get(f"drawing:{uri.id}")
        return entry.output_hash if entry else "unbuilt"
    if uri.scheme == "bom":
        if uri.selector:
            return _json_field(build_dir / "bom" / f"{uri.id}.json", uri.selector)
        entry = manifest.entries.get("bom")
        return entry.output_hash if entry else "unbuilt"
    if uri.scheme == "calc":
        mod = uri.id.split(".", 1)[0]
        return sha256_file(product.paths.calcs / f"{mod}.py")
    if uri.scheme in ("req", "dec", "ecr"):
        try:
            return _fmt(product.select(uri))
        except KeyError:
            return "missing"
    if uri.scheme == "rule":
        return "rulepack"
    return "unknown"
