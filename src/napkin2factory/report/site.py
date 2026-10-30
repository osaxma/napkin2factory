"""``site`` run: ``build/site/index.html`` points at the latest report (M6 adds versions)."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from napkin2factory.core.graph.hashing import sha256_file

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext, RunResult


def build_site(ctx: RunContext) -> RunResult:
    """Copy the latest report to ``build/site/index.html``."""
    from napkin2factory.core.graph.rules import RunResult

    src = ctx.build_dir / "report" / "index.html"
    out = ctx.build_dir / "site" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, out)
    return RunResult(reads=["rule:report"], outputs=[out], output_hash=sha256_file(out))
