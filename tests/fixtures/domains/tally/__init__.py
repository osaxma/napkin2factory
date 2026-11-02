"""The tally domain: a test domain that lists its family, for the graph's membership reads.

Installed beside the toy domain on the toy product (``tests/unit/test_graph_family_reads.py``).
A *tally* (``model/tally/<id>.yaml``) has a name and a count.  The rule ``tally:sum`` adds the
counts of every tally, the rule ``tally:joint`` reads one field of the toy product's joint,
the check stage ``tally`` writes one row per tally, and the doc helper ``tally_folder`` says
which build folder a page renders in.  The stage records nothing about the
family's listing itself: the core does (S-165).  The domain's own rule holds the ids as an
input, as ``docs/domains.md`` §3.1 says a domain's rules do.
It imports the core's public API only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.domain import (
    CheckStage,
    Domain,
    HelperContext,
    ModelFamily,
    RuleFamily,
    StageContext,
)
from napkin2factory.core.graph.hashing import sha256_json
from napkin2factory.core.graph.rules import Rule, RuleBuild, RunContext, RunResult
from napkin2factory.core.model.base import Model, Slug

ROOT = Path(__file__).resolve().parent

#: The toy product's joint (``tests/fixtures/products/toy/model/interfaces/plate-peg.yaml``).
JOINT = "plate-peg"


class Tally(Model):
    """A tally: a name and a count."""

    id: Slug
    name: str
    count: int = 1


def tally_rules(b: RuleBuild) -> list[Rule]:
    """``tally:sum`` (every tally's count) and ``tally:joint`` (one field of the joint)."""
    ids = sorted(b.product.families.get("tally", {}))  # its own family: the ids are an input
    return [
        Rule(
            id="tally:sum", kind="tally", produces=None, inputs={"ids": sha256_json(ids)}, run=_sum
        ),
        Rule(id="tally:joint", kind="tally", produces=None, inputs={}, run=_joint),
    ]


def _write(ctx: RunContext, name: str, record: dict[str, Any]) -> RunResult:
    out = ctx.build_dir / "tally" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    return RunResult(reads=[], outputs=[out], output_hash=sha256_json(record))


def _sum(ctx: RunContext) -> RunResult:
    """Lists the family the plain way: ``product.families["tally"]``."""
    total = 0
    for tid, raw in sorted(ctx.product.families.get("tally", {}).items()):
        total += ctx.proxy(raw, f"tally://{tid}").count
    return _write(ctx, "sum", {"total": total})


def _joint(ctx: RunContext) -> RunResult:
    """Reads one field of the joint (``iface://plate-peg#spec.snap``)."""
    joint = ctx.proxy(ctx.product.interfaces[JOINT], f"iface://{JOINT}")
    return _write(ctx, "joint", {"snap": joint.spec.snap})


def tally_static_reads(product: Any, rule: Rule) -> list[str]:
    """Before the first build: the family's listing, or the joint's field."""
    return ["set://tally"] if rule.id == "tally:sum" else [f"iface://{JOINT}#spec.snap"]


def tally_checks(sctx: StageContext) -> list[CheckResult]:
    """One row per tally, listing the family the plain way."""
    rows = []
    for tid, raw in sorted(sctx.product.families.get("tally", {}).items()):
        t = sctx.proxy(raw, f"tally://{tid}")
        rows.append(
            CheckResult(
                id=f"tally://{tid}",
                subject=f"tally://{tid}",
                status="pass",
                kind="tally",
                title=f"{t.name} counted",
                message=f"{t.count} counted",
            )
        )
    return rows


def tally_folder_helper(h: HelperContext) -> Any:
    """``{{ tally_folder() }}``: the name of the build folder the page renders in (S-164)."""

    def tally_folder() -> str:
        return str(h.build_dir.name)

    return tally_folder


DOMAIN = Domain(
    name="tally",
    title="Tallies",
    root=ROOT,
    families=(ModelFamily("tally", schema=Tally, folder="model/tally"),),
    rule_families=(
        RuleFamily("tally", tally_rules, output_dir="tally", static_reads=tally_static_reads),
    ),
    check_stages=(CheckStage("tally", tally_checks, whole_product=True),),
    doc_helpers={"tally_folder": tally_folder_helper},
)
