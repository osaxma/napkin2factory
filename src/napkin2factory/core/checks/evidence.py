"""Evidence keys (D25): the artifact key behind a URI at a point in time.

Parts key on their geometry and assemblies on their placements, so a revision-label bump at
``n2f ecr close`` does not void a sign-off made on the same geometry (S-040).

A part's key is ``inv:`` plus its geometric invariants (volume, area, bounding box, centroid,
face, edge and solid counts, and the rounded feature list), compared within a tolerance by
:func:`keys_match`, never the tessellation: the kernel meshes the same bent sheet differently
on Linux and macOS, so a mesh hash voided every sign-off recorded on the other platform
(S-121, B-0073; D14 asked for tolerance-compared geometry from the start). An assembly's key
is ``inv:`` plus its rounded placements. The hashes v0.3 and v0.4 wrote (``sha256:…``) are
still accepted for one version through :func:`legacy_keys`, so a sign-off made before S-121
stays valid until the evidence really changes.

A sign-off records the keys of everything it cites.  When any of them changes the
requirement reverts to ``needs-human``.  Keys come from the build manifest (parts,
assemblies, docs, drawings, BOM), from the calc runner (module source + inputs + result),
or from the model itself (requirements, parameters, decisions).
"""

from __future__ import annotations

import json
import math
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


#: Relative tolerance for comparing two ``inv:`` keys' numbers (S-121).  Platform float noise
#: in the kernel's volume and area integration is around 1e-10; a real change to a part is
#: never that small.
INVARIANT_RTOL = 1e-6
#: Decimals kept for feature coordinates and placements inside an ``inv:`` key (mm, quaternion).
_FEATURE_DECIMALS = 3
_PLACEMENT_DECIMALS = 4

INV_PREFIX = "inv:"


def _placements_key(path: Path) -> str:
    """``sha256:`` of ``instances.json`` as v0.3 wrote it (the placement fields only).

    Kept for :func:`legacy_keys`; new keys come from :func:`_asm_key`.
    """
    if not path.is_file():
        return "missing"
    data = json.loads(path.read_text(encoding="utf-8"))
    kept = [{k: inst[k] for k in _PLACEMENT_KEYS if k in inst} for inst in data]
    return sha256_text(json.dumps(kept, indent=2, sort_keys=True) + "\n")


def _rounded(value: Any, decimals: int) -> Any:
    """``value`` with every float rounded (nested lists and dicts walked)."""
    if isinstance(value, float):
        return round(value, decimals) + 0.0
    if isinstance(value, list):
        return [_rounded(v, decimals) for v in value]
    if isinstance(value, dict):
        return {k: _rounded(v, decimals) for k, v in value.items()}
    return value


def _inv(payload: dict[str, Any]) -> str:
    return INV_PREFIX + json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _part_key(part_dir: Path) -> str:
    """``inv:`` key of a built part: its invariants plus its rounded features (S-121)."""
    props_path = part_dir / "props.json"
    features_path = part_dir / "features.json"
    if not props_path.is_file():
        return "missing"
    props = json.loads(props_path.read_text(encoding="utf-8"))
    bbox = props.get("bbox", {})
    centroid = props.get("centroid", {})
    features: Any = None
    if features_path.is_file():
        features = _rounded(
            json.loads(features_path.read_text(encoding="utf-8")), _FEATURE_DECIMALS
        )
    return _inv(
        {
            "volume": props.get("volume"),
            "area": props.get("area"),
            "bbox": [bbox.get("x"), bbox.get("y"), bbox.get("z")],
            "centroid": [centroid.get("x"), centroid.get("y"), centroid.get("z")],
            "counts": [props.get("face_count"), props.get("edge_count"), props.get("solid_count")],
            "features": sha256_json(features) if features is not None else None,
        }
    )


def _asm_key(asm_dir: Path) -> str:
    """``inv:`` key of a built assembly: rounded placements plus instance counts (S-121)."""
    path = asm_dir / "instances.json"
    if not path.is_file():
        return "missing"
    data = json.loads(path.read_text(encoding="utf-8"))
    props_path = asm_dir / "props.json"
    props = json.loads(props_path.read_text(encoding="utf-8")) if props_path.is_file() else {}
    kept = [
        {k: _rounded(inst[k], _PLACEMENT_DECIMALS) for k in _PLACEMENT_KEYS if k in inst}
        for inst in data
    ]
    kept.sort(key=lambda inst: json.dumps(inst, sort_keys=True))
    return _inv({"placements": kept, "counts": props.get("instance_counts")})


def _numbers_close(a: Any, b: Any) -> bool:
    """Two JSON values agree: numbers within :data:`INVARIANT_RTOL`, the rest exactly."""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return math.isclose(float(a), float(b), rel_tol=INVARIANT_RTOL, abs_tol=1e-9)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_numbers_close(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_numbers_close(a[k], b[k]) for k in a)
    return bool(a == b)


def keys_match(recorded: str, current: str) -> bool:
    """True when a recorded evidence key still describes ``current`` (S-121).

    ``inv:`` keys compare their numbers within a tolerance (the kernel's float noise differs
    between platforms); any other key compares as text.
    """
    if recorded == current:
        return True
    if recorded.startswith(INV_PREFIX) and current.startswith(INV_PREFIX):
        try:
            a = json.loads(recorded[len(INV_PREFIX) :])
            b = json.loads(current[len(INV_PREFIX) :])
        except ValueError:
            return False
        return _numbers_close(a, b)
    return False


def legacy_keys(product: Product, build_dir: Path, uri: str) -> list[str]:
    """The keys v0.3 and v0.4 wrote for ``uri``.

    Parts: the mesh hash; assemblies: exact placements. A sign-off recorded before S-121
    stays valid until its evidence really changes. Remove with the next schema bump (F7).
    """
    try:
        u = Uri.parse(uri)
    except UriError:
        return []
    if u.scheme == "part":
        part = product.parts.get(u.id)
        if part is None or not part.has_geometry:
            return []
        part_dir = build_dir / "parts" / u.id
        props_path = part_dir / "props.json"
        if not props_path.is_file():
            return []
        props = json.loads(props_path.read_text(encoding="utf-8"))
        return [
            sha256_json(
                {
                    "tess": props.get("tess_hash"),
                    "features": sha256_file(part_dir / "features.json"),
                }
            )
        ]
    if u.scheme == "asm":
        asm_dir = build_dir / "assemblies" / u.id
        if not (asm_dir / "instances.json").is_file():
            return []
        props = (
            json.loads((asm_dir / "props.json").read_text(encoding="utf-8"))
            if (asm_dir / "props.json").is_file()
            else {}
        )
        return [
            sha256_json(
                {
                    "instances": _placements_key(asm_dir / "instances.json"),
                    "counts": props.get("instance_counts"),
                }
            )
        ]
    return []


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
        # geometry identity, not the manifest hash: a revision bump must not void a sign-off;
        # invariants, not the mesh: the mesh differs by platform (S-121)
        return _part_key(build_dir / "parts" / u.id)
    if u.scheme == "asm":
        return _asm_key(build_dir / "assemblies" / u.id)
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

        record = resolve_interface(product, product.interfaces[u.id]).model_dump(mode="json")
        # the joint's display name is a label, not evidence (as a part's role, N7; S-118)
        record.pop("name", None)
        return sha256_json(record)
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
    return _domain_key(product, manifest, u)


def _domain_key(product: Product, manifest: Manifest, u: Uri) -> str:
    """A domain scheme's key (F1): its rule's output hash, else the declared object's record."""
    from napkin2factory.core.registry import registry

    reg = registry()
    family = reg.produced_scheme(u.scheme)
    if family is not None:
        entry = manifest.entries.get(f"{family.name}:{u.id}")
        return entry.output_hash if entry else "missing"
    for fam in reg.model_families():
        if fam.uri_scheme == u.scheme:
            obj = product.families.get(fam.name, {}).get(u.id)
            return sha256_json(obj.model_dump(mode="json")) if obj is not None else "missing"
    return "missing"
