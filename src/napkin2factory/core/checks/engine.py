"""``checks`` run: evaluators, rule packs, interfaces, interference, counts, hardware, docs, BOM.

Writes ``build/checks/checks.json`` (results, matrix, summary) and ``calcs.json``.  The
read set is everything a verdict depends on (parts, assemblies, docs, BOM, requirements,
sign-offs, calcs) so a change to any of them re-runs the checks.
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
from napkin2factory.core.style import STYLE_FORM_KEY

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext, RunResult


def checks_reads(product: Product) -> list[str]:
    """Everything the checks depend on."""
    reads: list[str] = []
    for r in product.requirements.values():
        reads.append(f"req://{r.id}#verify")
        reads.append(f"req://{r.id}#safety")
        if r.verify is not None and r.verify.target is not None:
            t = r.verify.target
            if t.scheme in ("part", "asm", "iface", "calc", "param"):
                reads.append(str(t.base))
            if t.scheme == "bom":
                reads.append(str(t))
    for p in product.parts_with_geometry():
        reads.append(p.uri)
    for p in product.parts.values():
        reads.append(f"{p.uri}#role")  # the form pack picks parts by styling role
    for a in product.assemblies.values():
        reads.append(a.uri)
    for i in product.interfaces:
        reads.append(f"iface://{i}")
    for d in product.docs:
        reads.append(f"doc://{d}")
    reads.append("bom://rollups")
    reads.append(STYLE_FORM_KEY)  # the form pack reads thresholds from style.yaml
    reads += [
        "set://reqs",
        "set://parts",
        "set://asms",
        "set://docs",
        "set://signoffs",
        "set://ifaces",
    ]
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


def build_matrix(product: Product, results: list[CheckResult]) -> dict[str, Any]:
    """Requirements × status and rules × parts."""
    req_rows = []
    for r in product.requirements.values():
        res = next((x for x in results if x.id == f"req://{r.id}"), None)
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


def run_all_checks(ctx: RunContext) -> RunResult:
    """The ``checks`` rule body."""
    from napkin2factory.core.graph.rules import RunResult

    product, build_dir = ctx.product, ctx.build_dir
    ectx = EvalContext(product, build_dir)
    results: list[CheckResult] = []
    for iface in product.interfaces.values():
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
    for aid in product.assemblies:
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
    from napkin2factory.rulepacks.runner import run_rulepacks

    # rule-pack rows first: `rule` requirements (form requirements) read them
    rule_rows = run_rulepacks(product, build_dir)
    ectx.rule_results = rule_rows
    for req in product.requirements.values():
        results.append(evaluate_requirement(ectx, req))
    results += rule_rows
    results += instance_count_checks(product, build_dir)
    results += hardware_checks(product)  # P9: joint hardware per build unit
    results += doc_staleness(product, build_dir)
    results += bom_validation_checks(build_dir)
    persona = product.operator.persona
    for r in results:
        r.persona_message = (
            f"{OWNER_WORDS[r.status]}: {r.message}" if persona == "owner" else r.message
        )
    summary = summarize(results)
    payload: dict[str, Any] = {
        "status": "ok" if summary["fail"] == 0 else "fail",
        "summary": summary,
        "results": [r.to_dict() for r in results],
        "matrix": build_matrix(product, results),
        "calcs": {k: v.to_dict() for k, v in ectx.calc_records.items()},
    }
    out_dir = build_dir / "checks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "checks.json"
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    calcs_out = out_dir / "calcs.json"
    calcs_out.write_text(
        json.dumps(payload["calcs"], indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
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
        outputs=[out, calcs_out],
        output_hash=sha256_json(
            {"summary": summary, "results": [(r["id"], r["status"]) for r in payload["results"]]}
        ),
        payload=payload,
    )
