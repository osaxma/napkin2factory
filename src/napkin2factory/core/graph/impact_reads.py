"""Static read sets, rule matching and hypothetical verdicts; split from impact.py (S-184)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napkin2factory.core.graph.rules import Rule, build_rules
from napkin2factory.core.loader import Product
from napkin2factory.core.model import Edit
from napkin2factory.core.units import UnitError, compare, format_quantity, parse_quantity
from napkin2factory.core.uris import Uri


def _edit_matcher(edited_keys: list[str], outputs: set[str]) -> Any:
    """``touches(read)``: does a recorded read see one of the edited keys (gate E B1, S-138)?

    A read and an edit of the same object touch when one's field path starts with the
    other's: an edit of ``iface://x#spec.depth`` touches the reads ``iface://x#spec.depth``,
    ``iface://x#spec`` and ``iface://x`` (the object read whole, as the parts read their
    interfaces and the checks a decided choice's ``dec://``), never ``iface://x#name``.  A
    bare key that a rule produces (``part://x``, a domain family's ``<scheme>://x``) is that
    rule's output hash, not the object: it is reached through the rules the edit reruns, not
    matched here.
    """
    by_base: dict[str, list[tuple[str, ...]]] = {}
    for key in edited_keys:
        base, _, sel = key.partition("#")
        by_base.setdefault(base, []).append(tuple(sel.split(".")) if sel else ())

    def touches(read: str) -> bool:
        base, _, sel = read.partition("#")
        edits = by_base.get(base)
        if not edits:
            return False
        path = tuple(sel.split(".")) if sel else ()
        for edit in edits:
            if not path and edit and base in outputs:
                continue
            n = min(len(path), len(edit))
            if path[:n] == edit[:n]:
                return True
        return False

    return touches


def _most_specific(hits: list[str]) -> list[str]:
    """The reason's keys: a whole-object hit is left out when a field of it hit too.

    ``manifest://scope`` and ``manifest://scope#electrical`` both see an edit of
    ``manifest://scope#electrical.note``; the field says which entry it is.
    """
    return [
        k
        for k in hits
        if not any(o != k and o.startswith(k + ("." if "#" in k else "#")) for o in hits)
    ]


def Uri_base(key: str) -> str:  # noqa: N802 - reads like the Uri API
    """``part://x#props.mass`` → ``part://x``; non-URI keys unchanged."""
    return key.split("#", 1)[0]


def Uri_refs(obj: Any) -> list[Uri]:  # noqa: N802
    """Every Uri object inside a pydantic model (for interface spec param refs)."""
    out: list[Uri] = []

    def walk(v: Any) -> None:
        if isinstance(v, Uri):
            out.append(v)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif hasattr(v, "model_fields"):
            for name in type(v).model_fields:
                walk(getattr(v, name))

    walk(obj)
    return out


def _static_reads(product: Product, rule: Rule) -> list[str]:
    """Conservative read set for a rule that has never run (before the first build).

    Each rule family declares its own (``RuleFamily.static_reads``); a family that declares
    none (checks, report, site) reads every artifact a rule produces.
    """
    from napkin2factory.core.registry import registry

    reg = registry()
    family = next((f for f in reg.rule_families() if f.name == rule.kind), None)
    if family is not None and family.static_reads is not None:
        return list(family.static_reads(product, rule))
    # every rule that produces a model artifact (a URI; not validate's or a sheet's rule key)
    from napkin2factory.core.graph.recording import membership_key

    produced = [r.produces for r in build_rules(product) if r.produces and "://" in r.produces]
    return (
        produced
        + [
            "bom://rollups",
            "bom://build-plan",
            "rule:checks",
            "rule:report",
        ]
        # what a check stage or a report section may list (S-165)
        + [membership_key(f.name) for f in reg.model_families()]
    )


# ---- the mechanical families' static read sets (registered in place, F2) -----------------


def part_static_reads(product: Product, rule: Rule) -> list[str]:
    """A part reads its parameters, its interfaces and theirs, and frame-expression slugs."""
    pid = rule.id.split(":", 1)[1]
    part = product.parts[pid]
    reads = [f"param://{u.id}" for u in Uri_refs(part) if u.scheme == "param"]
    reads += [f"iface://{u.id}" for u in part.interfaces]
    reads += [
        f"param://{u.id}"
        for i in part.interfaces
        for u in Uri_refs(product.interfaces[i.id])
        if u.scheme == "param"
    ]
    # P2: slugs named inside frame expressions are reads too (S-106)
    reads += [
        f"param://{s}" for i in part.interfaces for s in product.interfaces[i.id].expression_slugs()
    ]
    return reads


def asm_static_reads(product: Product, rule: Rule) -> list[str]:
    """An assembly reads its children and every parameter."""
    aid = rule.id.split(":", 1)[1]
    return [c.uri for c in product.assemblies[aid].children] + [
        f"param://{p}" for p in product.parameters
    ]


def drawing_static_reads(product: Product, rule: Rule) -> list[str]:
    """A drawing reads its part."""
    return [f"part://{rule.id.split(':', 1)[1]}"]


def bom_static_reads(product: Product, rule: Rule) -> list[str]:
    """The BOM reads every part, its cost, every assembly's children and every interface."""
    return (
        [f"{p.uri}#cost" for p in product.parts.values()]
        + [p.uri for p in product.parts.values()]
        + [f"{a.uri}#children" for a in product.assemblies.values()]
        + [f"iface://{i}" for i in product.interfaces]  # the build plan's hardware (P9)
    )


def asmsheet_static_reads(product: Product, rule: Rule) -> list[str]:
    """An assembly sheet reads its unit's assembly and its step of the plan."""
    aid = rule.id.split(":", 1)[1]
    return [f"asm://{aid}", f"bom://build-plan#units.{aid}"]


def doc_static_reads(product: Product, rule: Rule) -> list[str]:
    """A manual page reads what it declares and every parameter."""
    did = rule.id.split(":", 1)[1]
    return [str(d) for d in product.docs[did].meta.depends_on] + [
        f"param://{p}" for p in product.parameters
    ]


def _hypothetical_verdict(
    product: Product,
    r: Any,
    overrides: dict[str, Any],
    hyp: dict[str, Any],
    affected: dict[str, str],
    build_dir: Path,
) -> tuple[str, str]:
    """Would ``r`` pass after the edit? Its verify kind answers (``VerifyKind.hypothetical``)."""
    from napkin2factory.core.registry import UnknownName, registry

    v = r.verify
    if v is None:
        return "re-check", "no verify method"
    try:
        kind = registry().verify_kind(v.kind)
    except UnknownName:
        return "re-check", ""
    if kind.hypothetical is None:
        return "estimate", "known after the rebuild"
    return kind.hypothetical(product, r, overrides, hyp, affected, build_dir)


# ---- the mechanical verify kinds' answers (registered in place, F2) ----------------------


def hyp_manual(*_: Any) -> tuple[str, str]:
    """A person signs it off again."""
    return "re-check", "a person must sign this off (again, if it was signed)"


def hyp_after_rebuild(*_: Any) -> tuple[str, str]:
    """Geometry decides; known after the rebuild."""
    return "estimate", "depends on geometry; known after the rebuild"


def hyp_calc(*_: Any) -> tuple[str, str]:
    """The calculation re-runs at ``n2f check``."""
    return "estimate", "the calculation re-runs with the new values at `n2f check`"


def hyp_param_bound(
    product: Product,
    r: Any,
    overrides: dict[str, Any],
    hyp: dict[str, Any],
    affected: dict[str, str],
    build_dir: Path,
) -> tuple[str, str]:
    """Compare the hypothetical parameter value with the (possibly edited) limit."""
    v = r.verify
    if v.target is None or not v.op or v.value is None:
        return "re-check", ""
    slug = v.target.id
    value = hyp.get(slug, product.parameter_value(slug) if slug in product.parameters else None)
    limit = overrides.get(f"req://{r.id}#verify.value", v.value)
    if isinstance(limit, str):
        try:
            limit = parse_quantity(limit)
        except UnitError:
            return "re-check", f"cannot read the new limit {limit!r}"
    if value is None or isinstance(value, str):
        return "re-check", "parameter could not be evaluated"
    try:
        ok = compare(value, v.op, limit)
    except UnitError as exc:
        return "re-check", str(exc)
    return (
        "would-pass" if ok else "would-fail"
    ), f"{format_quantity(value)} {v.op} {format_quantity(limit)}"


def hyp_bom_rollup(
    product: Product,
    r: Any,
    overrides: dict[str, Any],
    hyp: dict[str, Any],
    affected: dict[str, str],
    build_dir: Path,
) -> tuple[str, str]:
    """The declared total cost plus the declared cost delta of the edit."""
    v = r.verify
    if v.target is None or not v.op or v.value is None or v.target.selector != ("total_cost",):
        return "re-check", ""
    delta, _ = _cost_delta(
        product,
        [
            Edit(set=Uri.parse(k), to=val)
            for k, val in overrides.items()
            if k.startswith("part://") and "#cost" in k
        ],
        build_dir,
    )
    rollups_path = build_dir / "bom" / "rollups.json"
    if not rollups_path.is_file():
        return "estimate", "BOM not built yet"
    import json

    total = (
        float(json.loads(rollups_path.read_text(encoding="utf-8")).get("total_cost", 0.0)) + delta
    )
    limit = v.value
    ok = compare(parse_quantity(total, "USD"), v.op, limit)
    return (
        "would-pass" if ok else "would-fail"
    ), f"{total:.2f} USD {v.op} {format_quantity(limit)} (declared costs)"


def _evidence_affected(evidence: str, affected: dict[str, str], affected_params: set[str]) -> bool:
    base = Uri_base(evidence)
    scheme, ident = base.split("://", 1)
    if scheme in ("part", "asm", "doc", "drawing"):
        return f"{scheme}:{ident}" in affected
    if scheme == "bom":
        return "bom" in affected
    if scheme == "calc":
        return bool(affected_params)
    from napkin2factory.core.registry import registry

    family = registry().produced_scheme(scheme)  # a domain's rule output (F1)
    return family is not None and f"{family.name}:{ident}" in affected


def _cost_delta(product: Product, edits: list[Edit], build_dir: Path) -> tuple[float, str]:
    """Delta from declared unit costs × quantities; geometry-driven costs are not estimated."""
    import json

    rollups_path = build_dir / "bom" / "rollups.json"
    qty: dict[str, int] = {}
    if rollups_path.is_file():
        data = json.loads(rollups_path.read_text(encoding="utf-8"))
        qty = {k: int(v["total_qty"]) for k, v in data.get("parts", {}).items()}
    delta = 0.0
    touched = False
    for e in edits:
        u = e.set
        if u.scheme == "part" and u.selector == ("cost", "unit") and u.id in product.parts:
            part = product.parts[u.id]
            old = float(part.cost.unit.to("USD").magnitude) if part.cost else 0.0
            try:
                new = float(parse_quantity(e.to, "USD").to("USD").magnitude)
            except UnitError:
                continue
            delta += (new - old) * qty.get(part.uri, 1)
            touched = True
    if touched:
        return round(delta, 2), "from declared unit costs × quantities"
    return (
        0.0,
        "no declared costs change; cost effects of geometry changes are not estimated "
        "(re-quote after rebuild)",
    )
