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
from napkin2factory.core.vcs import Vcs
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip


class EcrError(N2FError):
    """A change request cannot take this step; the message says why and what to do."""

    exit_code = 3
    next_step = "run `n2f ecr list` to see the change requests and where each stands"


def _ecr_path(product: Product, ecr_id: str) -> Path:
    return product.paths.changes / f"{ecr_id}.yaml"


def _require(product: Product, ecr_id: str) -> Ecr:
    ecr_id = ecr_id.replace("ecr://", "")
    if ecr_id not in product.ecrs:
        known = ", ".join(sorted(product.ecrs)) or "none yet"
        where = f" --dir {product.root}" if product.root != Path.cwd() else ""
        raise EcrError(
            f"change request {ecr_id} does not exist (known: {known}); `n2f ecr start` opens one",
            next=f"n2f ecr list{where}",
        )
    return product.ecrs[ecr_id]


def _transition(product: Product, ecr: Ecr, to: str, **fields: Any) -> None:
    if not ecr.can_transition(to):
        allowed_list = TRANSITIONS.get(ecr.status, ())
        allowed = ", ".join(allowed_list) or "nothing (it is final)"
        raise EcrError(
            f"{ecr.id} is {ecr.status}; from there it can only go to: {allowed}",
            next=f"choose one of: {', '.join(allowed_list)}" if allowed_list else "",
        )
    path = _ecr_path(product, ecr.id)
    data = load_roundtrip(path)
    data["status"] = to
    for k, v in fields.items():
        data[k] = v
    dump_roundtrip(path, data)


def next_ecr_id(product: Product) -> str:
    """One past the highest ``ECR-nnn`` ever used: in ``changes/``, the markers and the history.

    A rollback removes a request's file but not its checkpoints, so the id must not be read
    from ``changes/`` alone: a reused id would make "ECR-001" mean two requests (S-273).
    """
    seen = list(product.ecrs)
    vcs = Vcs(product.root)
    if vcs.is_repo_root():
        seen += list(vcs.list_refs("ecr"))
        seen += [s.label for s in vcs.snapshots()]
    nums = [int(n) for text in seen for n in re.findall(r"ECR-(\d{3,})", text)]
    return f"ECR-{(max(nums) + 1) if nums else 1:03d}"


__all__ = [
    "EcrError",
    "_ecr_path",
    "_require",
    "_transition",
    "next_ecr_id",
]
