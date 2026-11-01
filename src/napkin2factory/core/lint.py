"""``n2f lint``: requirement quality and model hygiene rules (REVIEW C4 + GRAND_PLAN M1).

Lint is stricter than validate.  Validate asks "does this load and do references
resolve"; lint asks "is this a model an engineer would accept".  Each rule has an id
so a finding can be looked up and so a failing fixture exists per rule.
"""

from __future__ import annotations

import re

from napkin2factory.core.errors import Problems
from napkin2factory.core.loader import Product
from napkin2factory.core.units import UnitError, parse_quantity

#: Kinds whose statement need not carry a number (binary checks).
_BINARY_KINDS = frozenset({"manual", "interference", "interface", "rule"})
_NUMBER_WITH_UNIT = re.compile(
    r"(?<![\w-])[-+]?\d+(?:\.\d+)?\s*(?:[A-Za-z°µ]+(?:/[A-Za-z]+)?|%)(?![\w-])"
)
_WEAK_WORDS = (
    "should be nice",
    "as needed",
    "appropriate",
    "adequate",
    "reasonable",
    "good enough",
)


def lint(product: Product) -> Problems:
    """Run every lint rule; errors fail ``n2f lint``, warnings do not."""
    problems = Problems()
    paths = product.paths
    rf = paths.requirements

    for r in product.requirements.values():
        subject = f"req://{r.id}"
        # L1: measurable statement with a unit, unless a binary check.
        kind = r.verify.kind if r.verify else None
        if kind not in _BINARY_KINDS:
            parsed = []
            for n in _NUMBER_WITH_UNIT.findall(r.statement):
                try:
                    parsed.append(parse_quantity(n.strip()))
                except UnitError:
                    continue
            bare_number = re.search(r"(?<![\w.-])\d+(?:\.\d+)?(?![\w.-])", r.statement)
            if not parsed and not (kind == "count" and bare_number):
                problems.add(
                    rf,
                    subject,
                    "statement has no measurable value with a unit",
                    "write the limit into the statement, e.g. 'stays below 60 degC', "
                    "or use a binary verify kind (manual/interference/interface/rule)",
                    rule="L1-measurable",
                )
        if any(w in r.statement.lower() for w in _WEAK_WORDS):
            problems.add(
                rf,
                subject,
                "statement uses vague wording",
                "replace words like 'appropriate' or 'adequate' with a number",
                severity="warn",
                rule="L1-measurable",
            )
        # L2: verify present.
        if r.verify is None:
            problems.add(
                rf,
                subject,
                "no verify block",
                "add verify: {kind: …, target: …, op: …, value: …} or {kind: manual}",
                rule="L2-verify",
            )
        # L3: allocation present (list or 'unallocated').
        if r.allocation is None:
            problems.add(
                rf,
                subject,
                "no allocation",
                "list the parts/parameters that satisfy it, or write allocation: unallocated",
                rule="L3-allocation",
            )
        elif r.allocation == "unallocated":
            problems.add(
                rf,
                subject,
                "explicitly unallocated",
                "allocate it before release",
                severity="warn",
                rule="L3-allocation",
            )
        # L4: safety requirements have verify (and usually manual or calc).
        if r.safety and r.verify is None:
            problems.add(
                rf,
                subject,
                "safety requirement without a verify method",
                "safety requirements need verify and a human sign-off at release",
                rule="L4-safety-verify",
            )
        if r.safety and r.category != "safety":
            problems.add(
                rf,
                subject,
                f"safety: true but category is {r.category}",
                "set category: safety",
                severity="warn",
                rule="L4-safety-verify",
            )
        # L5: verify value unit matches the statement's unit dimension where both exist.
        if r.verify and r.verify.value is not None:
            nums = _NUMBER_WITH_UNIT.findall(r.statement)
            dims = set()
            for n in nums:
                try:
                    dims.add(parse_quantity(n.strip()).dimensionality)
                except UnitError:
                    pass
            if dims and r.verify.value.dimensionality not in dims:
                problems.add(
                    rf,
                    subject,
                    "verify.value's unit does not match any value in the statement",
                    "make the statement and the verify block agree",
                    severity="warn",
                    rule="L5-units-agree",
                )

    # L6: every decision links something.
    for d in product.decisions.values():
        if not d.links:
            problems.add(
                paths.decisions,
                f"dec://{d.id}",
                "decision links nothing",
                "add links: [req://…, param://…, part://…] so the decision is traceable",
                rule="L6-decision-links",
            )

    # L7: COTS parts have a source; L8: custom parts have tolerance_class, process, material.
    for p in product.parts.values():
        f = product.files[p.uri]
        if p.kind == "reference":
            continue  # owner-supplied or existing: nothing to buy or make
        if p.kind == "cots":
            if p.source is None:
                problems.add(
                    f,
                    p.uri,
                    "COTS part without a source",
                    "add source: {vendor, mpn, url, verified: false}",
                    rule="L7-cots-source",
                )
            elif not p.source.url:
                problems.add(
                    f,
                    p.uri,
                    "COTS source has no url",
                    "add the vendor page url (mark verified: false if unchecked)",
                    severity="warn",
                    rule="L7-cots-source",
                )
            if p.cost is None:
                problems.add(
                    f,
                    p.uri,
                    "COTS part has no cost",
                    "add cost: {unit: … USD}",
                    severity="warn",
                    rule="L7-cots-source",
                )
        else:
            if p.tolerance_class is None:
                problems.add(
                    f,
                    p.uri,
                    "custom part without tolerance_class",
                    "add tolerance_class: ISO2768-m (f/m/c/v); it goes on the drawing title block",
                    rule="L8-tolerance-class",
                )
            if p.process == "none":
                problems.add(
                    f,
                    p.uri,
                    "custom part without a manufacturing process",
                    "set process: sheet-metal | machining | welding | cut-block | cut-sheet "
                    "| 3d-print",
                    rule="L8-custom-process",
                )
            if p.material is None:
                problems.add(
                    f,
                    p.uri,
                    "custom part without material",
                    "add material: {name, spec}",
                    rule="L8-custom-material",
                )
            if p.cost is None:
                problems.add(
                    f,
                    p.uri,
                    "custom part without a cost estimate",
                    "add cost: {unit: … USD, basis: estimate}",
                    severity="warn",
                    rule="L8-cost",
                )

    # L9: every part with geometry belongs to at least one assembly, when assemblies exist.
    if product.assemblies:
        used = {c.uri for a in product.assemblies.values() for c in a.children}
        for p in product.parts.values():
            if p.uri not in used:
                problems.add(
                    product.files[p.uri],
                    p.uri,
                    "part is not used by any assembly",
                    "add it to an assembly's children or delete it",
                    severity="warn",
                    rule="L9-orphan-part",
                )

    # L13: every sub-assembly says why it is built on its own (P7); a grouping is a phantom.
    if product.assemblies:
        from napkin2factory.core.tree import AssemblyTree

        tops = set(AssemblyTree(product.assemblies).tops())
        for a in product.assemblies.values():
            if a.id in tops:
                if a.build == "phantom":
                    problems.add(
                        product.files[a.uri],
                        a.uri,
                        "the top assembly is always built; `build: phantom` is ignored here",
                        "remove `build: phantom` from the top assembly",
                        severity="warn",
                        rule="L13-assembly-driver",
                    )
                continue
            if a.build == "unit" and not a.driver:
                problems.add(
                    product.files[a.uri],
                    a.uri,
                    "sub-assembly built as a unit of its own, but nothing says why",
                    "add `driver: [built-as-unit]` (or tested-as-unit, serviced-as-unit, "
                    "separate-process-or-supplier, varies, agent-context), or "
                    "`build: phantom` if it only groups parts",
                    severity="warn",
                    rule="L13-assembly-driver",
                )

    # L10: draft parametric change requests should carry edits.
    for e in product.ecrs.values():
        if e.kind == "parametric" and not e.edits:
            problems.add(
                product.files[e.uri],
                e.uri,
                "parametric change request has no edits",
                "add edits: [{set: param://…, to: …}]",
                severity="warn",
                rule="L10-ecr-edits",
            )
        if e.kind == "design" and not e.tasks and not e.patch:
            problems.add(
                product.files[e.uri],
                e.uri,
                "design change request has neither tasks nor a patch",
                "list tasks for the designer, or point patch: at a unified diff",
                severity="warn",
                rule="L10-ecr-edits",
            )

    # L11: operator file present with a persona (intake gate).
    if not paths.operator.is_file():
        problems.add(
            paths.operator,
            "operator.yaml",
            "operator.yaml is missing",
            "run intake, or copy the template",
            rule="L11-operator",
        )

    # L12: form requirements need parts with a style role, or they stay unchecked.
    form_reqs = [
        r
        for r in product.requirements.values()
        if r.verify is not None
        and r.verify.kind == "rule"
        and str(r.verify.target).startswith("rule://form-v0/")
    ]
    if form_reqs and not _any_styled_part(product):
        problems.add(
            rf,
            ", ".join(f"req://{r.id}" for r in form_reqs),
            "form requirements exist (`rule://form-v0/…`) but no custom part declares a "
            "style `role:` — they will stay unchecked",
            "give the body, door, stand, controls and trim parts `role:` "
            "(model/parts/<id>.yaml), or sign the rows off by hand",
            severity="warn",
            rule="L12-form-needs-roles",
        )

    # L14: a joint closed later names a unit above the one where its parts meet (S-118).
    if any(i.closed_in is not None for i in product.interfaces.values()):
        from napkin2factory.core.build_units import BuildUnits

        units = BuildUnits(product)
        for iface in product.interfaces.values():
            if iface.closed_in is None or units.closed_later(iface.id) is not None:
                continue
            problems.add(
                product.paths.interfaces / f"{iface.id}.yaml",
                iface.uri,
                f"closed_in: {iface.closed_in} is not a unit built after the one where the "
                "joint's parts meet, so it is ignored",
                "name the unit whose step closes the joint (an assembly above the one that "
                "holds both parts, built as a unit), or remove the field",
                severity="warn",
                rule="L14-closed-in",
            )

    return problems


def _any_styled_part(product: Product) -> bool:
    """True when some custom part has a role the form pack checks (explicit or by its id)."""
    from napkin2factory.core.model.style import STYLED_ROLES, role_for

    return any(role_for(p) in STYLED_ROLES for p in product.custom_parts())
