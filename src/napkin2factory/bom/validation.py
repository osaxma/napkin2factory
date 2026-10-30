"""BOM validation tiers (D15): structural → URL resolves (offline-skippable) → curated catalog.

Results land in ``build/bom/validation.json``; unverified sources render as visible
warnings in the BOM, never hidden.  URL checks use HEAD with a short timeout and are
cached in ``build/bom/url-cache.json`` for seven days.  ``N2F_OFFLINE=1`` (or
``n2f build --offline``) skips the network tier and marks it ``skipped``.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import yaml

from napkin2factory.catalog import CATALOG_DIR
from napkin2factory.core.loader import Product

CACHE_TTL = 7 * 24 * 3600


def load_catalog() -> dict[tuple[str, str], dict[str, Any]]:
    """``(vendor lower, mpn lower)`` → entry over every catalog YAML."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for p in sorted(CATALOG_DIR.glob("*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for e in data.get("catalog", []):
            out[(str(e["vendor"]).lower(), str(e["mpn"]).lower())] = dict(e)
    return out


def _url_ok(url: str, cache: dict[str, Any], offline: bool) -> tuple[str, str]:
    """``(status, note)`` with status ok | failed | skipped."""
    if offline:
        return "skipped", "offline"
    now = time.time()
    hit = cache.get(url)
    if hit and now - float(hit.get("at", 0)) < CACHE_TTL:
        return str(hit["status"]), f"cached {int((now - hit['at']) / 3600)} h ago"
    try:
        import httpx

        resp = httpx.head(
            url,
            follow_redirects=True,
            timeout=5.0,
            headers={"User-Agent": "napkin2factory/0.1 (BOM link check)"},
        )
        if resp.status_code == 405:
            resp = httpx.get(
                url,
                follow_redirects=True,
                timeout=8.0,
                headers={"User-Agent": "napkin2factory/0.1 (BOM link check)"},
            )
        status = "ok" if resp.status_code < 400 else "failed"
        note = f"HTTP {resp.status_code}"
    except Exception as exc:
        status, note = "failed", f"{type(exc).__name__}"
    cache[url] = {"status": status, "at": now, "note": note}
    return status, note


def validate_bom(product: Product, build_dir: Path, offline: bool | None = None) -> dict[str, Any]:
    """Run the tiers for every COTS part; custom parts get a structural row only."""
    offline = bool(int(os.environ.get("N2F_OFFLINE", "0"))) if offline is None else offline
    catalog = load_catalog()
    cache_path = build_dir / "bom" / "url-cache.json"
    cache: dict[str, Any] = (
        json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    )
    rows: dict[str, Any] = {}
    for part in product.parts.values():
        row: dict[str, Any] = {
            "uri": part.uri,
            "kind": part.kind,
            "tiers": {},
            "status": "ok",
            "notes": [],
        }
        if part.kind == "custom":
            missing = [
                k
                for k, ok in (
                    ("process", part.process != "none"),
                    ("material", part.material is not None),
                    ("tolerance_class", part.tolerance_class is not None),
                )
                if not ok
            ]
            row["tiers"]["structural"] = "ok" if not missing else "missing: " + ", ".join(missing)
            row["status"] = "ok" if not missing else "incomplete"
            rows[part.uri] = row
            continue
        src = part.source
        if src is None or not src.vendor or not src.mpn:
            row["tiers"]["structural"] = "missing"
            row["status"] = "missing"
            row["notes"].append("no vendor/part number")
            rows[part.uri] = row
            continue
        row["tiers"]["structural"] = "ok"
        entry = catalog.get((src.vendor.lower(), src.mpn.lower()))
        row["tiers"]["catalog"] = "matched" if entry else "not in catalog"
        if entry:
            row["catalog_name"] = entry.get("name")
        if src.url:
            status, note = _url_ok(src.url, cache, offline)
            row["tiers"]["url"] = status
            row["notes"].append(f"link {status} ({note})")
        else:
            row["tiers"]["url"] = "no url"
        if src.verified:
            row["status"] = "verified"
        elif row["tiers"].get("url") == "failed":
            row["status"] = "link-failed"
        elif entry:
            row["status"] = "catalog"
        else:
            row["status"] = "unverified"
        rows[part.uri] = row
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for r in rows.values():
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"offline": offline, "parts": rows, "counts": counts, "catalog_entries": len(catalog)}
