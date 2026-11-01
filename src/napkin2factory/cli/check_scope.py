"""``n2f check --scope asm://<id>``: one module's checks (P12, M4).

Builds what the assembly needs (``n2f build --asm``), then runs the checks whose home is that
assembly or below it, and writes them to ``build/checks/scope/<id>/checks.json``: the full
matrix in ``build/checks/`` is never touched.  The option lives here (one verb or option per
module, S-103 §4); ``cli/check.py`` hands over.
"""

from __future__ import annotations

from typing import Any

from napkin2factory.cli.build_asm import assembly_id
from napkin2factory.core.loader import Product


def scoped_checks(product: Product, scope: str) -> dict[str, Any]:
    """Build ``asm://<id>`` alone and return its module's check document."""
    from napkin2factory.core.checks.engine import run_scoped_checks
    from napkin2factory.core.graph.runner import run_build

    aid = assembly_id(product, scope)
    run_build(product, target="geometry", quiet=True, only_asm=aid)
    return run_scoped_checks(product, product.paths.build, aid)
