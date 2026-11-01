"""Evidence keys (D25): the artifact key behind a URI at a point in time.

Parts key on their geometry (tessellation hash + features) and assemblies on their
placements, so a revision-label bump at ``n2f ecr close`` does not void a sign-off made on
the same geometry (S-040).

A sign-off records the keys of everything it cites.  When any of them changes the
requirement reverts to ``needs-human``.  Keys come from the build manifest (parts,
assemblies, docs, drawings, BOM), from the calc runner (module source + inputs + result),
or from the model itself (requirements, parameters, decisions).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napkin2factory.core.graph.hashing import sha256_file, sha256_json, sha256_text
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.loader import Product
from napkin2factory.core.uris import Uri, UriError

# The placement fields an assembly key covers: where each occurrence is.  How it was placed
# (``label``, ``via``, added in v0.4) is left out, so the same placements keep the same key and
# a sign-off made under v0.3 stays valid after the upgrade (P14, S-106).
_PLACEMENT_KEYS = ("node", "parent", "rotation", "translation", "uri")


def _placements_key(path: Path) -> str:
    """``sha256:`` of ``instances.json`` as v0.3 wrote it (the placement fields only)."""
    import json

    if not path.is_file():
        return "missing"
    data = json.loads(path.read_text(encoding="utf-8"))
    kept = [{k: inst[k] for k in _PLACEMENT_KEYS if k in inst} for inst in data]
    return sha256_text(json.dumps(kept, indent=2, sort_keys=True) + "\n")


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
    if u.scheme == "part":
        part = product.parts.get(u.id)
        if part is None:
            return "missing"
        if not part.has_geometry:
            # a bought or reference part without geometry: its record is the evidence
            # (source, cost, notes), minus the revision label (S-050) and the styling role
            # (N7: a picture's colour is not evidence; the field arrived after v0.1's
            # sign-offs, so keeping it in the record voided them all)
            record = part.model_dump(mode="json", exclude={"rev", "role"})
            return sha256_json(record)
        # geometry identity, not the manifest hash: a revision bump must not void a sign-off
        part_dir = build_dir / "parts" / u.id
        props_path = part_dir / "props.json"
        if not props_path.is_file():
            return "missing"
        import json

        props = json.loads(props_path.read_text(encoding="utf-8"))
        return sha256_json(
            {"tess": props.get("tess_hash"), "features": sha256_file(part_dir / "features.json")}
        )
    if u.scheme == "asm":
        asm_dir = build_dir / "assemblies" / u.id
        if not (asm_dir / "instances.json").is_file():
            return "missing"
        import json

        props = (
            json.loads((asm_dir / "props.json").read_text(encoding="utf-8"))
            if (asm_dir / "props.json").is_file()
            else {}
        )
        return sha256_json(
            {
                "instances": _placements_key(asm_dir / "instances.json"),
                "counts": props.get("instance_counts"),
            }
        )
    if u.scheme in ("doc", "drawing"):
        entry = manifest.entries.get(f"{u.scheme}:{u.id}")
        return entry.output_hash if entry else "missing"
    if u.scheme == "bom" and u.id == "build-plan":  # the plan, not the rollups (S-117)
        return sha256_file(build_dir / "bom" / "build-plan.json")
    if u.scheme == "bom":
        entry = manifest.entries.get("bom")
        return entry.output_hash if entry else "missing"
    if u.scheme == "iface":
        if u.id not in product.interfaces:
            return "missing"
        from napkin2factory.geometry.accessors import resolve_interface

        return sha256_json(
            resolve_interface(product, product.interfaces[u.id]).model_dump(mode="json")
        )
    if u.scheme in ("req", "param", "dec"):
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
