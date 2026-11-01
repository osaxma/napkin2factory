"""Requirement evaluators: one per ``verify.kind`` (§4.2 semantics, D9, D25).

``evaluate_requirement`` returns a CheckResult whose status follows the rules: a computed
verdict is ``pass``/``fail``; ``manual`` is ``needs-human``; a safety requirement whose
computation passes is still ``needs-human`` until a valid sign-off makes it ``signed``;
a non-safety ``needs-human`` with a valid sign-off becomes ``pass``.

``rule`` (form requirements, v0.2) reads the rule-pack rows of the same check run
(:attr:`EvalContext.rule_results`, filled by the engine before requirements are
evaluated): any ``fail`` row for the targeted rule fails the requirement; ``warn`` rows
never fail it (the row reads ``warn``); no applicable part is ``skip`` while the parts are
not built yet, and ``needs-human`` once they are (no part declares a style role, so a
person sets roles or signs it off — review gate A, C3).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from napkin2factory.core.checks.calcs import CalcError, CalcRecord, run_calc
from napkin2factory.core.checks.evidence import evidence_key
from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.loader import Product
from napkin2factory.core.model import Requirement, Signoff
from napkin2factory.core.units import UnitError, compare, format_quantity, parse_quantity

PROP_UNITS = {"bbox": "mm", "centroid": "mm", "volume": "mm**3", "area": "mm**2", "mass": "kg"}


class EvalContext:
    """Everything evaluators need: product, build dir, caches."""

    def __init__(self, product: Product, build_dir: Path) -> None:
        self.product = product
        self.build_dir = build_dir
        self.calc_records: dict[str, CalcRecord] = {}
        self.interference: dict[str, Any] = {}
        self.interfaces: dict[str, Any] = {}
        self.rollups: dict[str, Any] | None = None
        #: Rule-pack rows of this check run (``rule://<pack>/<rule>@<part>``), for ``rule``.
        self.rule_results: list[CheckResult] = []
        self._props: dict[str, dict[str, Any]] = {}

    def props(self, uri: str) -> dict[str, Any] | None:
        """props.json for a part/asm URI (cached)."""
        if uri not in self._props:
            scheme, ident = uri.split("://", 1)
            p = (
                self.build_dir
                / ("parts" if scheme == "part" else "assemblies")
                / ident
                / "props.json"
            )
            self._props[uri] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None  # type: ignore[assignment]
        return self._props[uri]

    def rollups_data(self) -> dict[str, Any] | None:
        """rollups.json (cached)."""
        if self.rollups is None:
            p = self.build_dir / "bom" / "rollups.json"
            self.rollups = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
        return self.rollups

    def calc(self, uri: str) -> CalcRecord:
        """Run (once) and cache a calc."""
        base = uri.split("#")[0]
        if base not in self.calc_records:
            self.calc_records[base] = run_calc(self.product, base)
        return self.calc_records[base]


def prop_quantity(props: dict[str, Any], selector: tuple[str, ...]) -> Any:
    """``("props","bbox","x")`` → quantity in the right unit."""
    cur: Any = props
    for key in selector[1:]:
        if not isinstance(cur, dict) or key not in cur:
            raise KeyError(f"no property {'.'.join(selector)}")
        cur = cur[key]
    unit = PROP_UNITS.get(selector[1], "") if len(selector) > 1 else ""
    if isinstance(cur, bool) or not isinstance(cur, (int, float)):
        raise KeyError(f"{'.'.join(selector)} is not a number")
    return parse_quantity(cur, unit or None)


#: The ``skip`` message of a ``rule`` requirement whose rule applies to no part yet.
NO_APPLICABLE_PART = "no part this rule applies to yet"


#: The ``needs-human`` message of a ``rule`` requirement no part applies to once the
#: product's parts are built (review gate A, C3).
NO_STYLED_PART = (
    "no part declares a style role yet; add `role:` to the body/door/stand/controls/trim "
    "parts or sign off by hand"
)


def _design_built(ctx: EvalContext) -> bool:
    """The Design gate's part condition: there are parts with geometry, all of them built."""
    parts = list(ctx.product.parts_with_geometry())
    return bool(parts) and all(ctx.props(p.uri) is not None for p in parts)


def rule_verdict(ctx: EvalContext, rule_uri: str) -> tuple[str, str, list[str]]:
    """``rule`` verify: (status, message, subjects of the rows read) for one rule URI.

    ``fail`` when any part has a ``fail`` row, ``warn`` when the worst row is a warning,
    ``pass`` when at least one part passed, else ``skip`` (the rule applies to no part yet,
    or every applicable part was skipped — the skip reasons are quoted). A rule that no
    loaded pack defines is a ``fail`` with a hint.
    """
    rows = [r for r in ctx.rule_results if r.id.partition("@")[0] == rule_uri]
    if not rows:
        from napkin2factory.rulepacks.runner import load_packs

        pack_id, _, rule_id = rule_uri.removeprefix("rule://").partition("/")
        packs = load_packs([ctx.product.paths.model / "rulepacks"])
        known = {f"rule://{p.id}/{r['id']}" for p in packs for r in p.rules}
        if rule_uri not in known:
            return (
                "fail",
                f"no rule {rule_id!r} in a pack {pack_id!r}: check the target "
                "(`docs/checks.md` lists the packs and rules)",
                [],
            )
        return "skip", NO_APPLICABLE_PART, []
    subjects = sorted({r.subject for r in rows})
    by_status: dict[str, list[CheckResult]] = {}
    for r in rows:
        by_status.setdefault(r.status, []).append(r)

    def listing(items: list[CheckResult]) -> str:
        return "; ".join(f"{r.subject.removeprefix('part://')}: {r.message}" for r in items)

    if by_status.get("fail"):
        return "fail", listing(by_status["fail"]), subjects
    if by_status.get("warn"):
        return "warn", "worth a look — " + listing(by_status["warn"]), subjects
    passed = by_status.get("pass", [])
    if passed:
        names = ", ".join(r.subject.removeprefix("part://") for r in passed)
        return "pass", f"{len(passed)} part(s) meet it ({names})", subjects
    reasons = listing(by_status.get("skip", []))
    return "skip", NO_APPLICABLE_PART + (f" ({reasons})" if reasons else ""), subjects


def _compare(value: Any, op: str, limit: Any) -> tuple[bool, str]:
    ok = compare(value, op, limit)
    return ok, f"{format_quantity(value)} {op} {format_quantity(limit)}"


def _signoff_state(
    ctx: EvalContext, req: Requirement, evidence: dict[str, str]
) -> tuple[Signoff | None, bool, str]:
    """(signoff, valid, why)."""
    so = ctx.product.signoffs.get(req.id)
    if so is None:
        return None, False, "no sign-off"
    if not so.evidence_keys:
        return so, False, "sign-off has no recorded evidence keys; re-sign with `n2f signoff`"
    stale = []
    for uri, key in so.evidence_keys.items():
        now = evidence.get(uri) or evidence_key(
            ctx.product, ctx.build_dir, uri, {k: v.to_dict() for k, v in ctx.calc_records.items()}
        )
        if now != key:
            stale.append(uri)
    if stale:
        return so, False, "evidence changed since signing: " + ", ".join(stale)
    return so, True, "sign-off valid" + (" (EXAMPLE, not a review)" if so.example else "")


def evaluate_requirement(ctx: EvalContext, req: Requirement) -> CheckResult:
    """Evaluate one requirement into a CheckResult."""
    v = req.verify
    res = CheckResult(
        id=f"req://{req.id}",
        subject=f"req://{req.id}",
        status="skip",
        message="",
        kind="requirement",
        safety=req.safety,
        title=req.title,
    )
    if v is None:
        res.status, res.message = "fail", "no verify method; add one (n2f lint says how)"
        return res
    evidence: dict[str, str] = {}
    computed: str | None = None
    try:
        if v.kind == "manual":
            computed = None
            res.message = v.note or "needs a human check"
        elif v.kind == "param_bound":
            assert v.target is not None and v.op and v.value is not None
            value = ctx.product.parameter_value(v.target.id)
            ok, txt = _compare(value, v.op, v.value)
            computed, res.message = ("pass" if ok else "fail"), txt
            evidence[str(v.target)] = evidence_key(ctx.product, ctx.build_dir, str(v.target))
        elif v.kind == "geometry_prop":
            assert v.target is not None and v.op and v.value is not None
            props = ctx.props(str(v.target.base))
            if props is None:
                computed, res.message = "skip", f"{v.target.base} has not been built"
            elif props.get("instances") == 0:
                # an empty module stub (P10, S-112): a size of 0 mm would pass every budget
                # and say nothing, so the row waits until the assembly has parts
                computed, res.message = (
                    "skip",
                    "it has no parts yet, so there is nothing to measure",
                )
            else:
                value = prop_quantity(props, v.target.selector)
                ok, txt = _compare(value, v.op, v.value)
                computed, res.message = (
                    ("pass" if ok else "fail"),
                    f"{'.'.join(v.target.selector[1:])} = {txt}",
                )
                evidence[str(v.target.base)] = evidence_key(
                    ctx.product, ctx.build_dir, str(v.target.base)
                )
        elif v.kind == "bom_rollup":
            assert v.target is not None and v.op and v.value is not None
            from napkin2factory.bom.rollups import rollup_value

            data = ctx.rollups_data()
            if data is None:
                computed, res.message = "skip", "BOM has not been built"
            else:
                value = rollup_value(data, v.target.selector[0])
                ok, txt = _compare(value, v.op, v.value)
                computed, res.message = (
                    ("pass" if ok else "fail"),
                    f"{v.target.selector[0]} = {txt}",
                )
                if not data.get("cost_complete", True) and v.target.selector[0] == "total_cost":
                    res.message += " (some parts have no declared cost)"
                evidence["bom://rollups"] = evidence_key(
                    ctx.product, ctx.build_dir, "bom://rollups"
                )
        elif v.kind == "calc":
            assert v.target is not None and v.op and v.value is not None
            rec = ctx.calc(str(v.target))
            ok, txt = _compare(rec.value, v.op, v.value)
            computed, res.message = ("pass" if ok else "fail"), f"{v.target} = {txt}"
            evidence[rec.uri] = rec.key
            res.detail["calc"] = rec.to_dict()
        elif v.kind == "interference":
            assert v.target is not None
            rep = ctx.interference.get(v.target.id)
            if rep is None:
                computed, res.message = "skip", f"{v.target} has not been built"
            else:
                computed = "pass" if rep["interferences"] == [] else "fail"
                res.message = (
                    f"{rep['pairs_checked']} pair(s) checked, {len(rep['allowed_contacts'])} "
                    f"allowed contact(s), {len(rep['interferences'])} interference(s)"
                )
                res.detail["interference"] = rep
                evidence[str(v.target)] = evidence_key(ctx.product, ctx.build_dir, str(v.target))
        elif v.kind == "interface":
            assert v.target is not None
            rep = ctx.interfaces.get(v.target.id)
            if rep is None:
                computed, res.message = "skip", f"{v.target} was not checked"
            else:
                computed, res.message = (
                    rep["status"] if rep["status"] in ("pass", "fail", "skip") else "fail",
                    rep["message"],
                )
                for party in ctx.product.interfaces[v.target.id].parties:
                    evidence[str(party)] = evidence_key(ctx.product, ctx.build_dir, str(party))
        elif v.kind == "count":
            assert v.target is not None and v.op and v.value is not None
            count = _count_of(ctx, str(v.target.base))
            if count is None:
                computed, res.message = "skip", f"{v.target.base} count unavailable (build first)"
            else:
                ok, txt = _compare(parse_quantity(count), v.op, v.value)
                computed, res.message = ("pass" if ok else "fail"), f"count = {txt}"
                for aid in ctx.product.assemblies:
                    evidence[f"asm://{aid}"] = evidence_key(
                        ctx.product, ctx.build_dir, f"asm://{aid}"
                    )
        elif v.kind == "rule":
            assert v.target is not None
            computed, res.message, subjects = rule_verdict(ctx, str(v.target.base))
            if computed == "skip" and not subjects and _design_built(ctx):
                # no part opted in: a person decides, never a silent skip (gate A, C3)
                computed, res.message = None, NO_STYLED_PART
            for subject in subjects:
                evidence[subject] = evidence_key(ctx.product, ctx.build_dir, subject)
    except (CalcError, UnitError, KeyError, AssertionError) as exc:
        res.status, res.message = "fail", f"could not evaluate: {exc}"
        res.evidence_keys = evidence
        return res
    res.evidence_keys = evidence
    so, valid, why = _signoff_state(ctx, req, evidence)
    res.detail["signoff"] = {
        "present": so is not None,
        "valid": valid,
        "why": why,
        "example": bool(so and so.example),
        "by": so.by if so else None,
    }
    if computed == "fail":
        res.status = "fail"
    elif computed == "skip":
        res.status = "skip"
    elif computed == "warn" and not req.safety:
        res.status = "warn"  # a warning never fails a requirement (D10)
    elif req.safety:
        res.status = "signed" if valid else "needs-human"
        if valid and so is not None and so.example:
            res.message = "EXAMPLE SIGN-OFF, NOT A REVIEW — " + res.message
        if not valid and computed == "pass":
            res.message += (
                " — passes by computation; safety requirements also need a human sign-off"
            )
        if not valid and so is not None:
            res.message += f" ({why})"
    elif computed is None:  # manual, non-safety
        res.status = "pass" if valid else "needs-human"
        if not valid and so is not None:
            res.message += f" ({why})"
    else:
        res.status = "pass"
    return res


def _count_of(ctx: EvalContext, uri: str) -> int | None:
    from napkin2factory.bom.rollups import top_assemblies

    total = 0
    found = False
    for aid in top_assemblies(ctx.product):
        props = ctx.props(f"asm://{aid}")
        if props is None:
            continue
        found = True
        counts = props.get("instance_counts", {})
        if uri in counts:
            total += int(counts[uri])
        elif uri in props.get("declared_counts", {}):
            total += int(props["declared_counts"][uri])
    if not found:
        data = ctx.rollups_data()
        if data and uri in data.get("parts", {}):
            return int(data["parts"][uri]["total_qty"])
        return None
    data = ctx.rollups_data()
    if total == 0 and data and uri in data.get("parts", {}):
        return int(data["parts"][uri]["total_qty"])  # BOM-only parts (no geometry)
    return total
