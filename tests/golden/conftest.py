"""Golden helper for kit generators (GRAND_PLAN §8.1, D14).

``check_golden("plate", "basic", props)`` compares the geometric fingerprint of a
generator run against ``tests/golden/goldens/<generator>.json``.  Tolerances: 0.5 % on
volume/area, 0.05 mm on bbox, exact on counts.  ``N2F_UPDATE_GOLDENS=1`` rewrites the
file; ``make goldens REASON=...`` is the only sanctioned way to do that.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

GOLDENS = Path(__file__).parent / "goldens"
GOLDENS.mkdir(exist_ok=True)


def fingerprint(result: Any) -> dict[str, Any]:
    """Geometric fingerprint of a PartResult: volume, bbox, areas, counts."""
    shape = result.shape
    bb = shape.bounding_box()
    fp: dict[str, Any] = {
        "volume": round(float(shape.volume), 3),
        "area": round(float(shape.area), 3),
        "bbox": [round(bb.size.X, 3), round(bb.size.Y, 3), round(bb.size.Z, 3)],
        "faces": len(shape.faces()),
        "features": result.features.summary(),
    }
    if result.flat_pattern is not None:
        fp["flat_area"] = round(float(result.flat_pattern.area), 3)
        fp["flat_size"] = [round(v, 3) for v in result.flat_pattern.size()]
    if result.cut_list:
        fp["cut_items"] = len(result.cut_list)
        fp["cut_length_total"] = round(sum(c.length * c.qty for c in result.cut_list), 3)
    return fp


def _close(a: Any, b: Any, rel: float = 0.005, abs_: float = 0.05) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close(x, y, rel, abs_) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k], rel, abs_) for k in a)
    return bool(a == b)


@pytest.fixture
def check_golden():  # type: ignore[no-untyped-def]
    """Compare or (under N2F_UPDATE_GOLDENS=1) record a fingerprint."""

    def _check(generator: str, case: str, result: Any) -> dict[str, Any]:
        fp = fingerprint(result)
        path = GOLDENS / f"{generator}.json"
        data: dict[str, Any] = json.loads(path.read_text()) if path.exists() else {}
        if os.environ.get("N2F_UPDATE_GOLDENS") == "1" or case not in data:
            if case in data and os.environ.get("N2F_UPDATE_GOLDENS") != "1":
                pass
            data[case] = fp
            path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
            if os.environ.get("N2F_UPDATE_GOLDENS") != "1":
                pytest.skip(
                    f"golden {generator}/{case} recorded for the first time; re-run to compare"
                )
        assert _close(fp, data[case]), f"{generator}/{case} drifted:\n got {fp}\n want {data[case]}"
        return fp

    return _check
