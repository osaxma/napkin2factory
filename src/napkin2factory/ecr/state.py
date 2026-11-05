"""Shared change-request state machine helpers: errors, paths, transitions and ID generation.

Split from lifecycle.py (S-248).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from napkin2factory.core.errors import N2FError
from napkin2factory.core.loader import Product
from napkin2factory.core.model import TRANSITIONS, Ecr
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip


class EcrError(N2FError):
    """A change request cannot take this step; the message says why and what to do."""

    exit_code = 3


def _ecr_path(product: Product, ecr_id: str) -> Path:
    return product.paths.changes / f"{ecr_id}.yaml"


def _require(product: Product, ecr_id: str) -> Ecr:
    ecr_id = ecr_id.replace("ecr://", "")
    if ecr_id not in product.ecrs:
        known = ", ".join(sorted(product.ecrs)) or "none yet"
        raise EcrError(
            f"change request {ecr_id} does not exist (known: {known}); `n2f ecr new` creates one"
        )
    return product.ecrs[ecr_id]


def _transition(product: Product, ecr: Ecr, to: str, **fields: Any) -> None:
    if not ecr.can_transition(to):
        allowed = ", ".join(TRANSITIONS[ecr.status]) or "nothing (it is final)"
        raise EcrError(f"{ecr.id} is {ecr.status}; from there it can only go to: {allowed}")
    path = _ecr_path(product, ecr.id)
    data = load_roundtrip(path)
    data["status"] = to
    for k, v in fields.items():
        data[k] = v
    dump_roundtrip(path, data)


def next_ecr_id(product: Product) -> str:
    """``ECR-001``, or one past the highest existing id."""
    nums = [int(m.group(1)) for e in product.ecrs for m in [re.match(r"ECR-(\d{3})", e)] if m]
    return f"ECR-{(max(nums) + 1) if nums else 1:03d}"


__all__ = [
    "EcrError",
    "_ecr_path",
    "_require",
    "_transition",
    "next_ecr_id",
]
