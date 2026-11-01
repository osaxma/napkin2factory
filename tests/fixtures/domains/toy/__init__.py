"""The toy domain: the domain contract's worked example (FOUNDATION F1, docs/domains.md).

It registers one of everything a domain can bring, each as small as it can be, so
``tests/unit/test_domain_contract.py`` can prove every registry sees it, and a new domain
can copy it.  A *toy thing* (``model/toy/<id>.yaml``) names a part and a ``glow``; the toy
rule family writes ``build/toy/<id>.json`` after the part is built; the ``toy_glow`` verify
kind compares that glow with a limit; the ``toy`` check stage writes one row per thing; a
Verify gate row, a report section, a doc helper, an owner word, an interface kind, a process,
a finish, a requirement category, a build-unit driver, a style role, a napkin screen (with
the card field it reads and its phase) and a module-context contribution complete the set.
It imports the core's public API only, never its internals.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from napkin2factory.concepts.screens import CardField
from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.checks.stage import check_rows_state
from napkin2factory.core.domain import (
    CheckStage,
    ContextContribution,
    Domain,
    GateRow,
    HelperContext,
    InterfaceKind,
    ModelFamily,
    Process,
    ReportSection,
    RuleFamily,
    Screen,
    StageContext,
    StyleRoleSpec,
    VerifyKind,
)
from napkin2factory.core.graph.hashing import sha256_json
from napkin2factory.core.graph.rules import Rule, RuleBuild, RunContext, RunResult
from napkin2factory.core.model.base import Model, PartUri, Slug
from napkin2factory.core.model.interfaces import InterfaceSpec
from napkin2factory.core.units import compare, format_quantity, parse_quantity

ROOT = Path(__file__).resolve().parent


# ---- the model family: model/toy/<id>.yaml ------------------------------------------------


class ToyThing(Model):
    """A toy thing: a name, the part it sits on, and how brightly it glows."""

    id: Slug
    name: str
    part: PartUri
    glow: int = 1


def validate_toy(product: Any, problems: Any) -> None:
    """Each toy thing's part exists (the family's own cross-reference check)."""
    for thing in product.families.get("toy", {}).values():
        if thing.part.id not in product.parts:
            problems.add(
                product.files[f"toy://{thing.id}"],
                f"toy://{thing.id}",
                f"names {thing.part}, which is not a part",
                "name an existing part",
                rule="toy",
            )


def things(product: Any) -> dict[str, ToyThing]:
    """The product's toy things by id."""
    return dict(product.families.get("toy", {}))


# ---- the rule family: toy:<id>, after the parts ---------------------------------------------


def toy_rules(b: RuleBuild) -> list[Rule]:
    """One ``toy:<id>`` rule per toy thing, after its part's rule."""
    return [
        Rule(
            id=f"toy:{tid}",
            kind="toy",
            produces=f"toy://{tid}",
            inputs={},  # the core adds the family's code hash
            run=_make_run(tid),
            description=f"the glow record of toy://{tid}",
            depends_on=[f"part:{t.part.id}"],
        )
        for tid, t in sorted(things(b.product).items())
    ]


def _make_run(tid: str) -> Any:
    def run(ctx: RunContext) -> RunResult:
        thing = things(ctx.product)[tid]
        reads = [f"toy://{tid}#glow", f"toy://{tid}#name", str(thing.part)]
        record = {"id": tid, "name": thing.name, "glow": thing.glow, "part": str(thing.part)}
        out = ctx.build_dir / "toy" / f"{tid}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
        return RunResult(reads=reads, outputs=[out], output_hash=sha256_json(record))

    return run


def toy_static_reads(product: Any, rule: Rule) -> list[str]:
    """Before the first build: the thing's fields and its part."""
    tid = rule.id.split(":", 1)[1]
    return [f"toy://{tid}#glow", f"toy://{tid}#name", str(things(product)[tid].part)]


# ---- the verify kind: toy_glow --------------------------------------------------------------


def evaluate_glow(ctx: Any, req: Any, res: CheckResult, evidence: dict[str, str]) -> str | None:
    """``toy_glow``: the built glow of a toy thing against ``op``/``value``."""
    v = req.verify
    path = ctx.build_dir / "toy" / f"{v.target.id}.json"
    if not path.is_file():
        res.message = f"{v.target} has not been built"
        return "skip"
    record = json.loads(path.read_text(encoding="utf-8"))
    glow = parse_quantity(record["glow"])
    ok = compare(glow, v.op, v.value)
    res.message = f"glow = {format_quantity(glow)} {v.op} {format_quantity(v.value)}"
    evidence[str(v.target)] = sha256_json(record)
    return "pass" if ok else "fail"


# ---- the check stage: one row per toy thing -------------------------------------------------


def toy_checks(sctx: StageContext) -> list[CheckResult]:
    """A toy thing passes when it was built and glows at all."""
    rows = []
    for tid, thing in sorted(things(sctx.product).items()):
        built = (sctx.build_dir / "toy" / f"{tid}.json").is_file()
        status = "pass" if built and thing.glow > 0 else ("skip" if not built else "fail")
        rows.append(
            CheckResult(
                id=f"toy://{tid}",
                subject=str(thing.part),
                status=status,
                kind="toy",
                title=f"{thing.name} glows",
                message="it glows" if status == "pass" else "not built yet or dark",
            )
        )
    return rows


def toy_check_reads(product: Any) -> list[str]:
    """The rows read the things' rule outputs."""
    return [f"toy://{tid}" for tid in things(product)]


# ---- the gate row, the report section, the doc helper, the context ---------------------------


def toy_row(product: Any, build_dir: Path) -> Any:
    """Under Verify: "Toy things: 1 check: 1 OK"; nothing when the product has no toy thing."""
    if not things(product):
        return None
    return check_rows_state(build_dir, "toy", {"pass": "OK", "fail": "needs attention"})


def toy_report_data(product: Any, build_dir: Path) -> dict[str, Any]:
    """What the toy section shows: every toy thing with its glow."""
    return {
        "things": [{"id": t.id, "name": t.name, "glow": t.glow} for t in things(product).values()]
    }


def toy_report_reads(product: Any) -> list[str]:
    """The section shows the things' names and glows."""
    return [f"toy://{tid}#{f}" for tid in things(product) for f in ("name", "glow")]


def toy_helper(h: HelperContext) -> Any:
    """``toy("widget").name`` in a manual page: records ``toy://widget#name`` (D5)."""

    def toy(tid: str) -> Any:
        tid = tid.replace("toy://", "")
        if tid not in things(h.product):
            raise h.error(f"toy('{tid}') does not exist")
        return h.proxy(things(h.product)[tid], f"toy://{tid}")

    return toy


def toy_context(product: Any, aid: str, members: list[str]) -> list[str]:
    """The toy things whose part this module holds."""
    parts = {
        c.part.id for a in members for c in product.assemblies[a].children if c.part is not None
    }
    return [
        f"- toy://{t.id}: {t.name} on {t.part} (glow {t.glow})"
        for t in things(product).values()
        if t.part.id in parts
    ]


# ---- the interface kind and the screen ------------------------------------------------------


class ToySpec(InterfaceSpec):
    """A toy joint: how firmly it snaps."""

    snap: str = "firm"


def check_toy_joint(product: Any, iface: Any, build_dir: Path) -> dict[str, Any]:
    """A toy joint passes when it snaps firmly."""
    firm = iface.spec.snap == "firm"
    return {"status": "pass" if firm else "fail", "message": f"it snaps {iface.spec.snap}"}


#: The card field the toy screen reads (F8): ``n2f concept new`` writes it into a skeleton.
TOYS = CardField("envelope", "toys", None, "a count", "5", "how many toys it holds")


def toy_screen(card: Any, massing: Any, values: Any) -> list[Any]:
    """A napkin screen: an estimate of the toy count from the card's ``envelope.toys``."""
    from napkin2factory.core.model import RuleRow

    toys = card.envelope.get("toys")
    if toys is None:
        return []
    n = int(getattr(toys, "magnitude", toys))  # the card reads numbers as quantities
    values.estimate.add("toy_count", n, f"{n} toys", "from the card", "toy screen")
    return [RuleRow(id="toy-count", title="Enough toys", status="pass", message=f"{n} toys")]


DOMAIN = Domain(
    name="toy",
    title="Toy things (the contract's worked example)",
    root=ROOT,
    families=(ModelFamily("toy", schema=ToyThing, folder="model/toy", validate_refs=validate_toy),),
    rule_families=(
        RuleFamily(
            "toy",
            toy_rules,
            after=("part",),
            produces="toy://",
            output_dir="toy",
            static_reads=toy_static_reads,
        ),
    ),
    verify_kinds=(VerifyKind("toy_glow", evaluate_glow, target_schemes=("toy",), compares=True),),
    check_stages=(CheckStage("toy", toy_checks, after=("interface",), reads=toy_check_reads),),
    gate_rows=(GateRow(gate="verify", title="Toy things", row=toy_row),),
    report_sections=(
        ReportSection(
            "toy",
            "Toy things",
            group="Product",
            fragment="toy.html.j2",
            data=toy_report_data,
            reads=toy_report_reads,
        ),
    ),
    doc_helpers={"toy": toy_helper},
    vocabulary={"owner": {"toy": "toy thing"}},
    interface_kinds=(
        InterfaceKind("toy-joint", "Toy snap joint", spec=ToySpec, check=check_toy_joint),
    ),
    processes=(Process("toy-cast", "Toy casting"),),
    finishes=("toy-glitter",),
    categories=("fun",),
    drivers={"toy-swapped": "swapped between toys"},
    style_roles=(StyleRoleSpec("toy-shell", "a toy's shell", styled=True, aliases=("casing",)),),
    screens=(Screen("toy", toy_screen, title="Toy count", fields=(TOYS,), phase="estimate"),),
    context=(ContextContribution("toy", "Toy things on its parts", toy_context),),
)
