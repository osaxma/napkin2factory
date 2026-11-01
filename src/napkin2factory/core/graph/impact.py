"""``n2f impact`` (GRAND_PLAN §6.3): what a hypothetical edit would touch, before anything changes.

Given edits (from a change request or ``--set``), compute: rules whose recorded reads
intersect the edited keys, transitively through the DAG; requirements whose verify targets
are affected, with hypothetical verdicts where they can be evaluated from declared values;
parts touched (revision bumps implied); docs with affected reads; interfaces whose parties
are affected, and which of them are ports (a joint between modules, P4, P12); sign-offs that
would be invalidated; and a cost delta from declared costs.  Nothing in the model changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.core.expr import referenced_names
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.graph.rules import Rule, build_rules
from napkin2factory.core.loader import Product
from napkin2factory.core.model import Edit
from napkin2factory.core.units import UnitError, compare, format_quantity, parse_quantity
from napkin2factory.core.uris import Uri, display_uri


@dataclass
class ReqImpact:
    """A requirement's predicted state after the edit."""

    id: str
    title: str
    why: str
    verdict: str  # would-pass | would-fail | re-check | estimate
    detail: str = ""
    safety: bool = False


@dataclass
class ImpactReport:
    """Structured impact (stored in the ECR) plus a persona summary."""

    edits: list[dict[str, Any]]
    edited_keys: list[str]
    rules: list[str]
    rule_reasons: dict[str, str]
    parts: list[str]
    assemblies: list[str]
    drawings: list[str]
    docs: list[str]
    interfaces: list[str]
    requirements: list[ReqImpact]
    signoffs_invalidated: list[str]
    cost_delta: float
    cost_note: str
    firm: bool  # True when the graph has been built at least once (otherwise estimates)
    kind: str = "parametric"
    tasks: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    ports: list[dict[str, Any]] = field(default_factory=list)  # P12: the ports it crosses

    def to_dict(self) -> dict[str, Any]:
        """JSON form."""
        d = dict(self.__dict__)
        d["requirements"] = [r.__dict__ for r in self.requirements]
        return d


def next_rev(rev: str) -> str:
    """``A`` → ``B``, ``Z`` → ``AA``, ``3`` → ``4``."""
    if rev.isdigit():
        return str(int(rev) + 1)
    if not rev:
        return "A"
    chars = list(rev.upper())
    i = len(chars) - 1
    while i >= 0:
        if chars[i] != "Z":
            chars[i] = chr(ord(chars[i]) + 1)
            return "".join(chars)
        chars[i] = "A"
        i -= 1
    return "A" + "".join(chars)


def parse_set(text: str) -> Edit:
    """``param://x=50mm`` or ``req://REQ-001#verify.value=250 mm`` → Edit."""
    if "=" not in text:
        raise ValueError(f"--set expects <uri>=<value>, got {text!r}")
    target, value = text.split("=", 1)
    return Edit(set=Uri.parse(target.strip()), to=value.strip())


def dependent_params(product: Product, slug: str) -> list[str]:
    """Parameters whose expressions depend on ``slug`` (transitively)."""
    out: list[str] = []
    changed = True
    seen = {slug}
    while changed:
        changed = False
        for name, p in product.parameters.items():
            if name in seen or not p.expr:
                continue
            if set(referenced_names(p.expr)) & seen:
                seen.add(name)
                out.append(name)
                changed = True
    return out


def _edit_keys(product: Product, edits: list[Edit]) -> tuple[list[str], dict[str, Any]]:
    """Keys touched by the edits and value overrides for hypothetical evaluation."""
    keys: list[str] = []
    overrides: dict[str, Any] = {}
    for e in edits:
        u = e.set
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
    """The impact of ``edits`` on the current build state (nothing is modified)."""
    build_dir = build_dir or product.paths.build
    manifest = Manifest.load(build_dir)
    rules = build_rules(product)
    edited_keys, overrides = _edit_keys(product, edits)
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
    for rule in rules:
        entry = manifest.entries.get(rule.id)
        if rule.kind == "validate":
            affected[rule.id] = "always re-validates"
            continue
        reads = entry.reads if entry is not None else _static_reads(product, rule)
        hits = [
            k
            for k in reads
            if k in edited
            or Uri_base(k) in edited
            or k in produced_affected
            or Uri_base(k) in produced_affected
        ]
        if hits:
            affected[rule.id] = ", ".join(hits[:4]) + (" …" if len(hits) > 4 else "")
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
    cost_delta, cost_note = _cost_delta(product, edits, build_dir)
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
        firm=firm,
        kind=kind,
        tasks=list(tasks or []),
        notes=notes,
        ports=ports,
    )


def crossed_ports(product: Product, iface_ids: list[str]) -> list[dict[str, Any]]:
    """The ports among ``iface_ids`` (P12): joints some assembly lists under ``ports:``.

    Each names the modules listing it and, per party, the build unit it is built into;
    ``between_units`` is true when the two sides are built in different units, so a change
    there is an interface change touching both.
    """
    from napkin2factory.core.build_units import BuildUnits

    listed: dict[str, list[str]] = {}
    for a in product.assemblies.values():
        for u in a.ports:
            listed.setdefault(u.id, []).append(a.uri)
    if not listed:
        return []
    units = BuildUnits(product)
    out = []
    for iid in iface_ids:
        if iid not in listed:
            continue
        sides = []
        for party in product.interfaces[iid].parties:
            uid = units.unit_of(units.tree.home(str(party)))
            sides.append(
                {
                    "part": str(party),
                    "unit": f"asm://{uid}" if uid else None,
                    "unit_name": product.assemblies[uid].name if uid else None,
                }
            )
        out.append(
            {
                "interface": f"iface://{iid}",
                "port_of": sorted(listed[iid]),
                "sides": sides,
                "between_units": len({s["unit"] for s in sides}) > 1,
            }
        )
    return out


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
    produced = [r.produces for r in build_rules(product) if r.produces and "://" in r.produces]
    return produced + [
        "bom://rollups",
        "bom://build-plan",
        "rule:checks",
        "rule:report",
    ]


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
    return False


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


def summarize(report: ImpactReport, product: Product) -> str:
    """Markdown summary in persona vocabulary (owner by default).

    The owner reads edited URIs without their ``scheme://`` prefix (``display_uri``); the
    stored impact (``to_dict``) keeps them whole.
    """
    persona = product.operator.persona
    lines = [f"# Impact of {len(report.edits)} change(s)", ""]
    for e in report.edits:
        lines.append(f"- set `{display_uri(e['set'], persona)}` to **{e['to']}**")
    lines.append("")
    if not report.firm:
        lines.append(
            "> Not built yet here: this is the full list, not the exact one. "
            "Run `n2f build` once and re-run impact for the exact set."
        )
        lines.append("")
    if report.cost_delta:
        sign = "+" if report.cost_delta > 0 else ""
        lines.append(f"**Cost:** {sign}{report.cost_delta:.2f} USD per unit ({report.cost_note}).")
    else:
        lines.append(f"**Cost:** no change from declared costs ({report.cost_note}).")
    lines.append("")
    lines.append("## What gets rebuilt" if persona == "engineer" else "## What changes")
    if report.parts:
        lines.append(
            f"- {len(report.parts)} part(s): "
            + ", ".join(
                f"`{p}` (rev {product.parts[p].rev} → {next_rev(product.parts[p].rev)})"
                for p in report.parts
            )
        )
    if report.assemblies:
        lines.append(
            f"- {len(report.assemblies)} assembly(ies): "
            + ", ".join(f"`{a}`" for a in report.assemblies)
        )
    if report.drawings:
        lines.append(
            f"- {len(report.drawings)} drawing(s): " + ", ".join(f"`{d}`" for d in report.drawings)
        )
    if report.docs:
        lines.append(
            f"- {len(report.docs)} manual page(s): " + ", ".join(f"`{d}`" for d in report.docs)
        )
    if report.interfaces:
        lines.append(
            f"- {len(report.interfaces)} interface(s) to re-verify: "
            + ", ".join(f"`{i}`" for i in report.interfaces)
        )
    between = [p for p in report.ports if p["between_units"]]
    if between:
        lines.append(
            f"- {len(between)} joint(s) between units, so both sides are checked again: "
            + "; ".join(
                f"`{display_uri(p['interface'], persona)}` ("
                + " and ".join(s["unit_name"] or "no unit" for s in p["sides"])
                + ")"
                for p in between
            )
        )
    if "bom" in report.rules:
        lines.append("- the bill of materials")
    if not (report.parts or report.assemblies or report.docs or "bom" in report.rules):
        lines.append("- nothing is rebuilt: no artifact reads what you are changing")
    lines.append("")
    if report.requirements:
        lines.append("## Requirements")
        lines.append(
            "_✓ would pass · ✗ would fail · ? needs a person to re-check · "
            "~ known only after the rebuild_"
        )
        for r in report.requirements:
            badge = {
                "would-pass": "✓ would pass",
                "would-fail": "✗ WOULD FAIL",
                "re-check": "? re-check",
                "estimate": "~ after rebuild",
            }[r.verdict]
            safety = " **(safety)**" if r.safety else ""
            lines.append(
                f"- {r.id} {r.title}{safety}: {badge}" + (f" — {r.detail}" if r.detail else "")
            )
        lines.append("")
    if report.signoffs_invalidated:
        lines.append("## Sign-offs that must be redone")
        for s in report.signoffs_invalidated:
            lines.append(f"- {s}: the evidence it was signed against changes")
        lines.append("")
    if report.kind == "design":
        lines.append("## Designer tasks")
        for t in report.tasks:
            lines.append(f"- [ ] {t}")
        lines.append("")
        lines.append(
            "Geometry-dependent verdicts above are estimates until the designer's work is "
            "rebuilt and checked."
        )
        lines.append("")
    if persona == "engineer":
        lines.append("## Rules")
        for rid in report.rules:
            lines.append(f"- `{rid}` ← {report.rule_reasons.get(rid, '')}")
        lines.append("")
    for n in report.notes:
        lines.append(f"_{n}_")
    return "\n".join(lines).rstrip() + "\n"
