"""``checks`` run (M3 placeholder recording its true read set; M4 implements evaluation)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from napkin2factory.core.graph.hashing import sha256_json

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext, RunResult


def checks_reads(ctx: RunContext) -> list[str]:
    """Everything the checks depend on: parts, assemblies, docs' reads, requirements, BOM."""
    product = ctx.product
    reads: list[str] = []
    for r in product.requirements.values():
        reads.append(f"req://{r.id}#verify")
        reads.append(f"req://{r.id}#safety")
        if r.verify is not None and r.verify.target is not None:
            t = r.verify.target
            if t.scheme in ("part", "asm", "iface", "calc"):
                reads.append(str(t.base))
            if t.scheme == "bom":
                reads.append(str(t))
    for p in product.parts_with_geometry():
        reads.append(p.uri)
    for a in product.assemblies.values():
        reads.append(a.uri)
    for d in product.docs:
        reads.append(f"doc://{d}")
    reads.append("bom://rollups")
    for s in product.signoffs.values():
        reads.append(f"signoff:{s.requirement.id}")
    seen: dict[str, None] = {}
    for k in reads:
        seen.setdefault(k, None)
    return list(seen)


def run_all_checks(ctx: RunContext) -> RunResult:
    """Placeholder: write checks.json with every requirement marked ``skip`` (M4 fills in)."""
    from napkin2factory.core.graph.rules import RunResult

    payload: dict[str, Any] = {
        "status": "placeholder",
        "results": [
            {
                "id": r.id,
                "subject": f"req://{r.id}",
                "status": "skip",
                "message": "checks arrive at M4",
            }
            for r in ctx.product.requirements.values()
        ],
    }
    out = ctx.build_dir / "checks" / "checks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return RunResult(
        reads=checks_reads(ctx), outputs=[out], output_hash=sha256_json(payload), payload=payload
    )
