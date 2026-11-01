"""``checks`` run: evaluators, rule packs, interfaces, interference, counts, hardware, docs, BOM.

Writes ``build/checks/checks.json`` (results, matrix, summary), ``calcs.json`` and
``choices.json`` (F12: the rows that are or were a choice; a decided one reads ``pass`` with
its decision, :mod:`napkin2factory.core.checks.choices`).  The read set is everything a
verdict depends on (parts, assemblies, docs, BOM, requirements, sign-offs, calcs, the decisions
that resolve choices) so a change to any of them re-runs the checks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from napkin2factory.core.checks.evaluators import EvalContext, evaluate_requirement
from napkin2factory.core.checks.hardware import hardware_checks
from napkin2factory.core.checks.interface import check_interface, coordinate_placement_warnings
from napkin2factory.core.checks.interference import check_interference
from napkin2factory.core.checks.results import OWNER_WORDS, CheckResult, summarize
from napkin2factory.core.graph.hashing import sha256_json
from napkin2factory.core.loader import Product
from napkin2factory.core.reach import REACH_KEY
from napkin2factory.core.style import STYLE_FORM_KEY

if TYPE_CHECKING:
    from napkin2factory.core.domain import StageContext
    from napkin2factory.core.graph.rules import RunContext, RunResult


def checks_reads(product: Product) -> list[str]:
    """Everything the checks depend on."""
    reads: list[str] = []
    for r in product.requirements.values():
        reads.append(f"req://{r.id}#verify")
        reads.append(f"req://{r.id}#safety")
        if r.verify is not None and r.verify.target is not None:
            t = r.verify.target
            if t.scheme == "bom":
                reads.append(str(t))
            elif t.scheme != "rule":  # a rule's rows are the checks' own (no value to read)
                reads.append(str(t.base))
    for p in product.parts_with_geometry():
        reads.append(p.uri)
    for p in product.parts.values():
        reads.append(f"{p.uri}#role")  # the form pack picks parts by styling role
        reads.append(f"{p.uri}#name")  # messages name parts (hardware, joints)
    for a in product.assemblies.values():
        reads.append(a.uri)
        # The asm rule's output hash does not move with `spare:`, `loose:`, `build:` or
        # `driver:`; the hardware stage and the units read them, so record the fields
        # (B2, as bom/build_plan.py does; S-117).
        for field in ("name", "children", "build", "driver", "ports"):
            reads.append(f"{a.uri}#{field}")
    for i in product.interfaces:
        reads.append(f"iface://{i}")
    for d in product.docs:
        reads.append(f"doc://{d}")
    reads.append("bom://rollups")
    reads.append(STYLE_FORM_KEY)  # the form pack reads thresholds from style.yaml
    reads.append(REACH_KEY)  # P5: scopes, exports and the recorded reads of parts and assemblies
    reads += [
        "set://reqs",
        "set://parts",
        "set://asms",
        "set://docs",
        "set://signoffs",
        "set://ifaces",
    ]
    from napkin2factory.core.checks.choices import decision_reads
    from napkin2factory.core.registry import registry

    reads += decision_reads(product)  # F12: a new decision may resolve a choice
    for stage in registry().check_stages():  # what each registered stage's rows depend on
        if stage.reads is not None:
            reads += stage.reads(product)
    seen: dict[str, None] = {}
    for k in reads:
        seen.setdefault(k, None)
    return list(seen)


def doc_staleness(product: Product, build_dir: Path) -> list[CheckResult]:
    """A page is stale when any recorded read's value differs from the value at render time."""
    from napkin2factory.core.graph.manifest import Manifest
    from napkin2factory.core.graph.values import value_of

    manifest = Manifest.load(build_dir)
    out: list[CheckResult] = []
    for did, doc in product.docs.items():
        reads_path = build_dir / "docs" / did / "reads.json"
        if not reads_path.is_file():
            out.append(
                CheckResult(
                    id=f"doc://{did}",
                    subject=f"doc://{did}",
                    status="fail",
                    kind="doc",
                    title=doc.meta.title,
                    message="page has not been rendered; run `n2f build --target docs`",
                )
            )
            continue
        data = json.loads(reads_path.read_text(encoding="utf-8"))
        stale = [
            k
            for k, v in data.get("values", {}).items()
            if value_of(product, manifest, build_dir, k) != v
        ]
        if stale:
            out.append(
                CheckResult(
                    id=f"doc://{did}",
                    subject=f"doc://{did}",
                    status="fail",
                    kind="doc",
                    title=doc.meta.title,
                    message="stale: "
                    + ", ".join(stale[:5])
                    + (" …" if len(stale) > 5 else "")
                    + " changed since the page was rendered; run `n2f build`",
                    detail={"stale": stale},
                )
            )
        else:
            out.append(
                CheckResult(
                    id=f"doc://{did}",
                    subject=f"doc://{did}",
                    status="pass",
                    kind="doc",
                    title=doc.meta.title,
                    message=f"current ({len(data.get('reads', []))} recorded reads)",
                )
            )
    return out


def instance_count_checks(product: Product, build_dir: Path) -> list[CheckResult]:
    """D18: geometry instance counts equal YAML quantities, per assembly."""
    out: list[CheckResult] = []
    for aid, asm in product.assemblies.items():
        p = build_dir / "assemblies" / aid / "props.json"
        if not p.is_file():
            out.append(
                CheckResult(
                    id=f"count://{aid}",
                    subject=asm.uri,
                    status="skip",
                    kind="count",
                    title=f"{asm.name}: instance counts",
                    message="not built",
                )
            )
            continue
        props = json.loads(p.read_text(encoding="utf-8"))
        declared, actual = props.get("declared_counts", {}), props.get("instance_counts", {})
        if declared == actual:
            out.append(
                CheckResult(
                    id=f"count://{aid}",
                    subject=asm.uri,
                    status="pass",
                    kind="count",
                    title=f"{asm.name}: instance counts",
                    message=f"{props.get('instances', 0)} instances match the declared quantities",
                    evidence_keys={asm.uri: props.get("tess_hash", "")},
                )
            )
        else:
            diffs = [
                f"{k}: placed {actual.get(k, 0)}, declared {declared.get(k, 0)}"
                for k in sorted(set(declared) | set(actual))
                if declared.get(k) != actual.get(k)
            ]
            out.append(
                CheckResult(
                    id=f"count://{aid}",
                    subject=asm.uri,
                    status="fail",
                    kind="count",
                    title=f"{asm.name}: instance counts",
                    message="; ".join(diffs),
                    detail={"declared": declared, "actual": actual},
                )
            )
        if props.get("notes"):
            out.append(
                CheckResult(
                    id=f"layout://{aid}",
                    subject=asm.uri,
                    status="warn",
                    kind="count",
                    title=f"{asm.name}: layout",
                    message="; ".join(props["notes"]),
                )
            )
    bom_only = [p for p in product.parts.values() if not p.has_geometry]
    for p_ in bom_only:
        out.append(
            CheckResult(
                id=f"geometry://{p_.id}",
                subject=p_.uri,
                status="warn",
                kind="count",
                title=f"{p_.name}: no 3D",
                message="BOM-only part: absent from the 3D model and the drawings",
            )
        )
    return out


def bom_validation_checks(build_dir: Path) -> list[CheckResult]:
    """Rows from validation.json as check results (unverified sources stay visible)."""
    p = build_dir / "bom" / "validation.json"
    if not p.is_file():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    out: list[CheckResult] = []
    for uri, row in data.get("parts", {}).items():
        status = row["status"]
        mapped = {
            "ok": "pass",
            "verified": "pass",
            "catalog": "warn",
            "unverified": "warn",
            "link-failed": "warn",
            "missing": "fail",
            "incomplete": "fail",
        }.get(status, "warn")
        msg = {
            "catalog": "matches the curated catalog; vendor link not opened by a human",
            "unverified": "vendor link not verified",
            "link-failed": "vendor link did not resolve",
            "missing": "no vendor/part number",
            "incomplete": str(row["tiers"].get("structural")),
        }.get(status, "sourcing " + status)
        out.append(
            CheckResult(
                id=f"bom://validation@{uri.split('://')[1]}",
                subject=uri,
                status=mapped,
                kind="bom",
                title="sourcing",
                message=msg,
                detail=row,
            )
        )
    return out


def build_matrix(
    product: Product, results: list[CheckResult], only_present: bool = False
) -> dict[str, Any]:
    """Requirements × status and rules × parts (``only_present``: the requirements checked)."""
    req_rows = []
    for r in product.requirements.values():
        res = next((x for x in results if x.id == f"req://{r.id}"), None)
        if res is None and only_present:
            continue  # a module's checks (--scope) leave the other requirements out
        req_rows.append(
            {
                "id": r.id,
                "title": r.title,
                "category": r.category,
                "priority": r.priority,
                "safety": r.safety,
                "kind": r.verify.kind if r.verify else None,
                "status": res.status if res else "skip",
                "message": res.message if res else "",
            }
        )
    rule_cells: dict[str, dict[str, str]] = {}
    rule_titles: dict[str, str] = {}
    for x in results:
        if x.kind == "rule":
            rid, _, pid = x.id.partition("@")
            rule_cells.setdefault(pid, {})[rid] = x.status
            rule_titles[rid] = x.title
    return {
        "requirements": req_rows,
        "rules": {"parts": sorted(rule_cells), "rules": rule_titles, "cells": rule_cells},
    }


def collect_results(
    product: Product, build_dir: Path, within: str | None = None, log: Any = None
) -> tuple[list[CheckResult], EvalContext]:
    """Every check row, each with its module (P12); ``within`` keeps one module's rows only.

    ``within`` (an assembly id, ``n2f check --scope``) keeps the rows whose home is that
    assembly or one below it: its parts' rules, the requirements allocated to it or its parts,
    the joints that close inside it (both stages; its ports close in the parent), interference,
    counts and hardware of its assemblies, and its reach rows.  Documents and sourcing are the
    whole product's and are left out.  The costly checks are skipped outside the scope.
    ``log`` (the ``checks`` rule's) receives what the stages read through ``sctx.proxy``.
    """
    from napkin2factory.core.checks.modules import RowModules
    from napkin2factory.core.domain import StageContext
    from napkin2factory.core.registry import registry

    modules = RowModules(product)
    below = modules.tree.below(within) if within is not None else None

    def keep(home: str | None) -> bool:
        return below is None or (home is not None and home in below)

    ectx = EvalContext(product, build_dir)
    sctx = StageContext(product, build_dir, ectx, keep, within, modules)
    if log is not None:
        sctx.log = log  # the stages' recorded reads are the checks rule's (D5, S-138)
    results: list[CheckResult] = []
    for stage in registry().check_stages():  # F3: each stage's rows, in stage order
        if stage.whole_product and within is not None:
            continue  # documents and sourcing are the whole product's
        results += stage.run(sctx)
    modules.annotate(results)
    from napkin2factory.core.checks.choices import resolve

    # F12: a choice is keyed on its evidence now and reads `pass` once decided (S-130)
    resolve(product, build_dir, results, {k: v.to_dict() for k, v in ectx.calc_records.items()})
    if within is not None:
        results = [r for r in results if modules.inside(r, within)]
    return results, ectx


# ---- the mechanical check stages (registered in place by domains/mechanical, F2) ----------


def interface_stage(sctx: StageContext) -> list[CheckResult]:
    """Each joint: holes line up or faces are recorded, then placement (P1, P3)."""
    product, build_dir, ectx = sctx.product, sctx.build_dir, sctx.ectx
    results: list[CheckResult] = []
    for iface in product.interfaces.values():
        if not sctx.keep(sctx.modules.closing.get(iface.id)):
            continue
        rep = check_interface(product, iface, build_dir)
        ectx.interfaces[iface.id] = rep.to_dict()
        results.append(
            CheckResult(
                id=f"iface://{iface.id}",
                subject=f"iface://{iface.id}",
                status=rep.status,
                kind="interface",
                title=f"{iface.kind} between {', '.join(str(p) for p in iface.parties)}",
                message=rep.message,
                detail=rep.to_dict(),
                # P3: the world frames of every occurrence pair, per assembly
                evidence={"alignment": rep.alignment["assemblies"]}
                if rep.alignment.get("assemblies")
                else {},
            )
        )
    results += coordinate_placement_warnings(product, build_dir)  # P1
    return results


def interference_stage(sctx: StageContext) -> list[CheckResult]:
    """Parts of each assembly do not overlap (declared mating faces may touch, D29)."""
    product, build_dir, ectx = sctx.product, sctx.build_dir, sctx.ectx
    results: list[CheckResult] = []
    for aid in product.assemblies:
        if not sctx.keep(aid):
            continue
        irep = check_interference(product, aid, build_dir)
        ectx.interference[aid] = irep.to_dict()
        status = (
            "skip"
            if irep.notes and irep.pairs_checked == 0 and not irep.allowed_contacts
            else ("pass" if irep.ok else "fail")
        )
        msg = (
            f"{irep.pairs_checked} pair(s) checked, {len(irep.allowed_contacts)} allowed "
            f"contact(s), {len(irep.interferences)} interference(s)"
            + (
                ": "
                + "; ".join(
                    f"{i['a']} ∩ {i['b']} = {i.get('volume')} mm³" for i in irep.interferences
                )
                if irep.interferences
                else ""
            )
        )
        results.append(
            CheckResult(
                id=f"interference://{aid}",
                subject=f"asm://{aid}",
                status=status,
                kind="interference",
                title="parts do not overlap",
                message=msg,
                detail=irep.to_dict(),
                evidence={"allowed-contact": irep.allowed_contacts},
            )
        )
    return results


def requirements_stage(sctx: StageContext) -> list[CheckResult]:
    """Every requirement, then the rule-pack rows (``rule`` requirements read them first)."""
    from napkin2factory.rulepacks.runner import run_rulepacks

    product, ectx = sctx.product, sctx.ectx
    rule_rows = run_rulepacks(product, sctx.build_dir)
    ectx.rule_results = rule_rows
    results = [
        evaluate_requirement(ectx, req)
        for req in product.requirements.values()
        if sctx.within is None or sctx.modules.requirement_in(req, sctx.within)
    ]
    return results + rule_rows


def count_stage(sctx: StageContext) -> list[CheckResult]:
    """Instance counts equal the declared quantities (D18)."""
    return instance_count_checks(sctx.product, sctx.build_dir)


def hardware_stage(sctx: StageContext) -> list[CheckResult]:
    """Joint hardware per build unit (P9), then bolts into both ends of a spacer (F12)."""
    from napkin2factory.core.checks.hardware import spacer_bolt_checks

    units = sctx.modules.units
    return hardware_checks(sctx.product, units) + spacer_bolt_checks(sctx.product, units)


def reach_stage(sctx: StageContext) -> list[CheckResult]:
    """Scoped parameters are read only where they may be (P5)."""
    from napkin2factory.core.graph.manifest import Manifest
    from napkin2factory.core.reach import reach_checks

    return reach_checks(sctx.product, Manifest.load(sctx.build_dir))


def docs_stage(sctx: StageContext) -> list[CheckResult]:
    """Manual pages are current (no recorded read changed since rendering)."""
    return doc_staleness(sctx.product, sctx.build_dir)


def sourcing_stage(sctx: StageContext) -> list[CheckResult]:
    """Bought parts' sourcing, from the BOM validation."""
    return bom_validation_checks(sctx.build_dir)


def run_all_checks(ctx: RunContext) -> RunResult:
    """The ``checks`` rule body."""
    from napkin2factory.core.graph.rules import RunResult

    product, build_dir = ctx.product, ctx.build_dir
    results, ectx = collect_results(product, build_dir, log=ctx.log)
    payload = check_payload(product, results, ectx)
    out_dir = build_dir / "checks"
    out = _write(out_dir / "checks.json", payload)
    calcs_out = _write(out_dir / "calcs.json", payload["calcs"])
    from napkin2factory.core.checks.choices import write_choices

    choices_out = write_choices(build_dir, payload["results"])  # None: no choice (F16)
    reads = checks_reads(product)
    for rec in ectx.calc_records.values():
        reads += rec.reads
    for s in product.signoffs.values():
        reads.append(f"signoff:{s.requirement.id}")
    seen: dict[str, None] = {}
    for k in reads:
        seen.setdefault(k, None)
    return RunResult(
        reads=list(seen),
        outputs=[out, calcs_out] + ([choices_out] if choices_out else []),
        output_hash=sha256_json(
            {
                "summary": payload["summary"],
                "results": [(r["id"], r["status"]) for r in payload["results"]],
            }
        ),
        payload=payload,
    )


def _write(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return path


def scope_dir(build_dir: Path, aid: str) -> Path:
    """Where ``n2f check --scope asm://<aid>`` writes: never ``build/checks/checks.json`` (P12)."""
    return build_dir / "checks" / "scope" / aid


def run_scoped_checks(product: Product, build_dir: Path, aid: str) -> dict[str, Any]:
    """One module's checks (P12), written to ``build/checks/scope/<aid>/checks.json``."""
    results, ectx = collect_results(product, build_dir, within=aid)
    payload = check_payload(product, results, ectx, scoped=True)
    payload["scope"] = f"asm://{aid}"
    _write(scope_dir(build_dir, aid) / "checks.json", payload)
    return payload


def check_payload(
    product: Product, results: list[CheckResult], ectx: EvalContext, scoped: bool = False
) -> dict[str, Any]:
    """The ``checks.json`` document: verdict, summary, rows, the matrix by module, calcs."""
    persona = product.operator.persona
    for r in results:
        r.persona_message = (
            f"{OWNER_WORDS[r.status]}: {r.message}" if persona == "owner" else r.message
        )
    summary = summarize(results)
    rows = [r.to_dict() for r in results]
    matrix = build_matrix(product, results, only_present=scoped)
    from napkin2factory.core.checks.modules import module_groups

    matrix["modules"] = module_groups(product, rows)
    return {
        "status": "ok" if summary["fail"] == 0 else "fail",
        "summary": summary,
        "results": rows,
        "matrix": matrix,
        "calcs": {k: v.to_dict() for k, v in ectx.calc_records.items()},
    }
