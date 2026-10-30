"""Evidence keys (D25): the artifact key behind a URI at a point in time.

A sign-off records the keys of everything it cites.  When any of them changes the
requirement reverts to ``needs-human``.  Keys come from the build manifest (parts,
assemblies, docs, drawings, BOM), from the calc runner (module source + inputs + result),
or from the model itself (requirements, parameters, decisions).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napkin2factory.core.graph.hashing import sha256_file, sha256_json
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.loader import Product
from napkin2factory.core.uris import Uri, UriError


def evidence_key(
    product: Product, build_dir: Path, uri: str, calc_records: dict[str, Any] | None = None
) -> str:
    """Current key for an evidence URI (``"missing"`` when it cannot be resolved)."""
    manifest = Manifest.load(build_dir)
    calc_records = calc_records or {}
    try:
        u = Uri.parse(uri)
    except UriError:
        return "missing"
    base = str(u.base)
    if u.scheme == "calc":
        rec = calc_records.get(base)
        if rec is not None:
            return str(rec.get("key", "missing"))
        return sha256_file(product.paths.calcs / f"{u.id.split('.')[0]}.py")
    if u.scheme in ("part", "asm", "doc", "drawing"):
        entry = manifest.entries.get(f"{u.scheme}:{u.id}")
        return entry.output_hash if entry else "missing"
    if u.scheme == "bom":
        entry = manifest.entries.get("bom")
        return entry.output_hash if entry else "missing"
    if u.scheme in ("req", "param", "dec", "iface"):
        try:
            obj = product.resolve(u.base)
        except KeyError:
            return "missing"
        if u.scheme == "param":
            from napkin2factory.core.units import format_quantity

            return sha256_json(format_quantity(product.parameter_value(u.id)))
        return sha256_json(obj.model_dump(mode="json") if hasattr(obj, "model_dump") else str(obj))
    if u.scheme == "rule":
        return "rulepack"
    return "missing"
