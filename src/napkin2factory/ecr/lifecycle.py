"""Change-request lookups shared by the verbs (decisions D7, D22, D23).

The state machine is ``draft → approved → closed`` or ``draft | approved → aborted``, edited in
place (``live.py``, v0.8). The patch-based steps this module used to hold (``new_ecr``,
``run_impact``, ``approve``, ``reject``, ``close``) went with schema 2 (S-261): the migration
carries every request filed the old way into the live flow (``upgrade.py``).

Split across state.py, apply.py (in-place YAML editing), revisions.py and live.py (S-248).
"""

from __future__ import annotations

from typing import Any

from napkin2factory.core.loader import Product
from napkin2factory.ecr.state import EcrError, _ecr_path, _require, next_ecr_id


def ecr_table(product: Product) -> list[dict[str, Any]]:
    """Rows for ``n2f ecr list``."""
    return [
        {
            "id": e.id,
            "title": e.title,
            "kind": e.kind,
            "status": e.status,
            "released_in": e.released_in or "",
        }
        for e in product.ecrs.values()
    ]


__all__ = [
    "EcrError",
    "_ecr_path",
    "_require",
    "ecr_table",
    "next_ecr_id",
]
