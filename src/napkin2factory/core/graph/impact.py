"""``n2f impact`` (GRAND_PLAN §6.3): what a hypothetical edit would touch, before anything changes.

Given edits (from a change request or ``--set``), compute: rules whose recorded reads
intersect the edited keys, transitively through the DAG; requirements whose verify targets
are affected, with hypothetical verdicts where they can be evaluated from declared values;
parts touched (revision bumps implied); docs with affected reads; interfaces whose parties
are affected, and which of them are ports (a joint between modules, P4, P12); sign-offs that
would be invalidated; and a cost delta from declared costs.  Nothing in the model changes.

A live change request's impact (the folder against its baseline, v0.8 R6) is built on these
pieces in :mod:`napkin2factory.ecr.live_impact`; the patch dry run of S-180 went with schema 2
(S-261).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napkin2factory.core.graph.impact_common import (
    EditError,
    ImpactReport,
    PatchImpact,
    ReqImpact,
    dependent_params,
    next_rev,
    parse_set,
)
from napkin2factory.core.graph.impact_patch import (
    _COLLECTIONS,
    _NOUNS,
    _changed_fields,
    _dump,
    _object_changes,
    _objects_of,
    _patch_keys,
    _scope_changes,
    crossed_ports,
)
from napkin2factory.core.graph.impact_reads import (
    Uri_base,
    Uri_refs,
    _cost_delta,
    _edit_matcher,
    _evidence_affected,
    _hypothetical_verdict,
    _most_specific,
    _static_reads,
    asm_static_reads,
    asmsheet_static_reads,
    bom_static_reads,
    doc_static_reads,
    drawing_static_reads,
    hyp_after_rebuild,
    hyp_bom_rollup,
    hyp_calc,
    hyp_manual,
    hyp_param_bound,
    part_static_reads,
)
from napkin2factory.core.graph.impact_summary import (
    _domain_outputs,
    _grouped,
    _part_words,
    _patch_lines,
    summarize,
)
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.graph.rules import build_rules
from napkin2factory.core.loader import Product
from napkin2factory.core.model import Edit
from napkin2factory.core.units import UnitError, parse_quantity
from napkin2factory.core.uris import Uri


def _edit_keys(product: Product, edits: list[Edit]) -> tuple[list[str], dict[str, Any]]:
    """Keys touched by the edits and value overrides for hypothetical evaluation."""
    keys: list[str] = []
    overrides: dict[str, Any] = {}
    for e in edits:
        u = e.set
        added = _membership_if_new(product, u)
        if added is not None:
            keys.append(added)
        if u.scheme == "param" and not u.selector:
            keys.append(f"param://{u.id}")
            try:
                overrides[f"param://{u.id}"] = (
                    parse_quantity(e.to, product.parameters[u.id].unit or None)
                    if u.id in product.parameters
                    else e.to
                )
            except UnitError:
                overrides[f"param://{u.id}"] = e.to
            for dep in dependent_params(product, u.id):
                keys.append(f"param://{dep}")
        else:
            keys.append(str(u))
            if u.scheme == "part" and u.selector[:1] == ("cost",):
                keys.append(f"part://{u.id}#cost")
            overrides[str(u)] = e.to
            # rules record the fields they read (part://x#material, asm://y#children, …), so a
            # selector edit touches exactly the rules that read that field (gate-1 B3)
            if u.selector:
                keys.append(f"{u.base}#{u.selector[0]}")
    seen: dict[str, None] = {}
    for k in keys:
        seen.setdefault(k, None)
    return list(seen), overrides


def _families_added_to(edited_keys: list[str]) -> dict[str, str]:
    """Rule family → the ``set://<family>`` key it answers to, for each family a file is added to.

    The domain that registers a family makes its rules from it at every build and declares
    their dependence itself (inputs; its rules record no listing, S-165), so impact names
    all of that domain's rules: conservative, a superset of what the build reruns.
    """
    from napkin2factory.core.graph.recording import membership_key
    from napkin2factory.core.registry import registry

    out: dict[str, str] = {}
    for d in registry().domains:
        if d.in_place:  # the system's own rules record the listing (S-165)
            continue
        for fam in d.families:
            key = membership_key(fam.name)
            if key in edited_keys:
                for rf in d.rule_families:
                    out.setdefault(rf.name, key)
    return out


def _membership_if_new(product: Product, u: Uri) -> str | None:
    """The membership key an edit touches when it names an object that does not exist yet.

    ``--set tally://b#count=2`` with no ``model/tally/b.yaml`` is that file added: every rule
    that listed the family reads ``set://tally`` and reruns when the file arrives (S-165).
    """
    from napkin2factory.core.graph.recording import MEMBERSHIP, membership_key
    from napkin2factory.core.graph.values import MEMBERSHIP_BY_SCHEME
    from napkin2factory.core.registry import registry

    if u.scheme in MEMBERSHIP_BY_SCHEME:
        key = MEMBERSHIP_BY_SCHEME[u.scheme]
        return None if u.id in getattr(product, MEMBERSHIP[key]) else key
    for fam in registry().model_families():
        if fam.uri_scheme == u.scheme:
            objects = product.families.get(fam.name, {})
            return None if dict.__contains__(objects, u.id) else membership_key(fam.name)
    return None


def _hypothetical_params(product: Product, overrides: dict[str, Any]) -> dict[str, Any]:
    """Parameter values with overrides applied and expressions re-evaluated."""
    from napkin2factory.core.expr import evaluate

    values: dict[str, Any] = {}

    def get(slug: str, stack: tuple[str, ...] = ()) -> Any:
        if slug in values:
            return values[slug]
        key = f"param://{slug}"
        p = product.parameters[slug]
        if key in overrides:
            v = overrides[key]
            v = parse_quantity(v, p.unit or None) if isinstance(v, (str, int, float)) else v
        elif p.expr is None:
            v = product.parameter_value(slug)
        else:
            v = evaluate(p.expr, {}, lookup=lambda s: get(s, (*stack, slug)))
            if p.unit and hasattr(v, "to"):
                v = v.to(p.unit)
        values[slug] = v
        return v

    for slug in product.parameters:
        try:
            get(slug)
        except Exception as exc:  # report, don't crash an impact run
            values[slug] = f"invalid: {exc}"
    return values


def compute_impact(
    product: Product,
    edits: list[Edit],
    build_dir: Path | None = None,
    kind: str = "parametric",
    tasks: list[str] | None = None,
) -> ImpactReport:
    """The impact of hypothetical ``edits`` on this build.  Nothing is modified."""
    return _impact(product, edits, build_dir or product.paths.build, kind, tasks)


def _impact(
    product: Product,
    edits: list[Edit],
    build_dir: Path,
    kind: str,
    tasks: list[str] | None,
    extra_keys: list[str] | None = None,
    seeded: dict[str, str] | None = None,
    patch: PatchImpact | None = None,
) -> ImpactReport:
    """:func:`compute_impact` on one model; ``seeded``: rules known to rerun, with why."""
    manifest = Manifest.load(build_dir)
    rules = build_rules(product)
    edited_keys, overrides = _edit_keys(product, edits)
    for k in extra_keys or []:
        if k not in edited_keys:
            edited_keys.append(k)
    edited = set(edited_keys)
    firm = bool(manifest.entries)
    affected: dict[str, str] = {}
    produced_affected: set[str] = set()
    notes: list[str] = []
    if not firm:
        notes.append(
            "the product has never been built here, so the rebuild set is the full build; "
            "run `n2f build` once for an exact list"
        )
    touches = _edit_matcher(edited_keys, {p for r in rules for p in r.produced})
    added_to = _families_added_to(edited_keys)
    for rule in rules:
        entry = manifest.entries.get(rule.id)
        if rule.kind == "validate":
            affected[rule.id] = "always re-validates"
            continue
        if seeded and rule.id in seeded:  # the build's own dry run of the patched copy
            affected[rule.id] = seeded[rule.id]
            for produced in rule.produced:
                produced_affected.add(produced)
                produced_affected.add(produced.split("#")[0])
            continue
        if rule.kind in added_to:
            # its domain makes its rules from the family and records no listing (S-165)
            affected[rule.id] = added_to[rule.kind]
            for produced in rule.produced:
                produced_affected.add(produced)
                produced_affected.add(produced.split("#")[0])
            continue
        reads = entry.reads if entry is not None else _static_reads(product, rule)
        hits = [
            k
            for k in reads
            if touches(k) or k in produced_affected or Uri_base(k) in produced_affected
        ]
        if hits:
            shown = _most_specific(hits)
            affected[rule.id] = ", ".join(shown[:4]) + (" …" if len(shown) > 4 else "")
            for produced in rule.produced:
                produced_affected.add(produced)
                produced_affected.add(produced.split("#")[0])
    parts = sorted(r.split(":", 1)[1] for r in affected if r.startswith("part:"))
    asms = sorted(r.split(":", 1)[1] for r in affected if r.startswith("asm:"))
    drawings = sorted(r.split(":", 1)[1] for r in affected if r.startswith("drawing:"))
    docs = sorted(r.split(":", 1)[1] for r in affected if r.startswith("doc:"))
    affected_part_uris = {f"part://{p}" for p in parts} | {f"asm://{a}" for a in asms}
    affected_params = {k for k in edited if k.startswith("param://")}
    interfaces = sorted(
        i.id
        for i in product.interfaces.values()
        if any(str(p) in affected_part_uris for p in i.parties)
        or any(f"param://{u.id}" in affected_params for u in Uri_refs(i))
        or any(f"param://{s}" in affected_params for s in i.expression_slugs())
    )
    ports = crossed_ports(product, interfaces)
    hyp = _hypothetical_params(product, overrides) if affected_params else {}
    reqs: list[ReqImpact] = []
    for r in product.requirements.values():
        why = []
        if any(
            str(a) in affected_part_uris or str(a) in affected_params
            for a in (r.allocation if isinstance(r.allocation, list) else [])
        ):
            why.append("allocated to something that changes")
        if r.verify is not None and r.verify.target is not None:
            t = r.verify.target
            if (
                str(t.base) in affected_part_uris
                or str(t.base) in affected_params
                or (t.scheme == "bom" and "bom" in affected)
                or (t.scheme == "iface" and t.id in interfaces)
                or (t.scheme == "calc" and affected_params)
            ):
                why.append(f"verified against {t.base}")
        if f"req://{r.id}" in edited or any(k.startswith(f"req://{r.id}#") for k in edited):
            why.append("the change request edits this requirement")
        if not why:
            continue
        verdict, detail = _hypothetical_verdict(product, r, overrides, hyp, affected, build_dir)
        reqs.append(ReqImpact(r.id, r.title, "; ".join(why), verdict, detail, r.safety))
    signoffs = sorted(
        s.requirement.id
        for s in product.signoffs.values()
        if any(_evidence_affected(str(e), affected, affected_params) for e in s.evidence)
        or s.requirement.id in {q.id for q in reqs}
    )
    cost_delta, cost_note, cost_complete = _cost_delta(product, edits, build_dir, patch=patch)
    return ImpactReport(
        edits=[{"set": str(e.set), "to": e.to} for e in edits],
        edited_keys=edited_keys,
        rules=[r.id for r in rules if r.id in affected],
        rule_reasons=affected,
        parts=parts,
        assemblies=asms,
        drawings=drawings,
        docs=docs,
        interfaces=interfaces,
        requirements=reqs,
        signoffs_invalidated=signoffs,
        cost_delta=cost_delta,
        cost_note=cost_note,
        cost_complete=cost_complete,
        firm=firm,
        kind=kind,
        tasks=list(tasks or []),
        notes=notes,
        ports=ports,
    )


__all__ = [
    "EditError",
    "ImpactReport",
    "PatchImpact",
    "ReqImpact",
    "Uri_base",
    "Uri_refs",
    "_COLLECTIONS",
    "_NOUNS",
    "_changed_fields",
    "_cost_delta",
    "_domain_outputs",
    "_dump",
    "_edit_keys",
    "_edit_matcher",
    "_evidence_affected",
    "_families_added_to",
    "_grouped",
    "_hypothetical_params",
    "_hypothetical_verdict",
    "_impact",
    "_membership_if_new",
    "_most_specific",
    "_object_changes",
    "_objects_of",
    "_part_words",
    "_patch_keys",
    "_patch_lines",
    "_scope_changes",
    "_static_reads",
    "asm_static_reads",
    "asmsheet_static_reads",
    "bom_static_reads",
    "compute_impact",
    "crossed_ports",
    "dependent_params",
    "doc_static_reads",
    "drawing_static_reads",
    "hyp_after_rebuild",
    "hyp_bom_rollup",
    "hyp_calc",
    "hyp_manual",
    "hyp_param_bound",
    "next_rev",
    "parse_set",
    "part_static_reads",
    "summarize",
]
