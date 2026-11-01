"""The runner of the concept rule packs: their ``params`` and one row per rule (N5).

Split from ``concept_checks.py`` (F15, S-131), which keeps importing every name here, so
callers need no change. :func:`rule_rows` turns check outcomes into
:class:`~napkin2factory.core.model.concepts.RuleRow` rows with the rule's wording; a
product's own screen (``model/screens/``, F10) uses it for its rules too.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from napkin2factory.core.model.concepts import ConceptCard, RuleRow
from napkin2factory.rulepacks.runner import RulePack, load_packs

if TYPE_CHECKING:
    from napkin2factory.concepts.massing import MassingResult
    from napkin2factory.rulepacks.concept_checks import CheckFn, ConceptFacts

CONCEPT_SCOPE = "concept"


def _fmt(template: str, values: dict[str, Any]) -> str:
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        return template


def concept_packs(packs: list[RulePack] | None = None) -> list[RulePack]:
    """The shipped packs that apply to concept cards (``applies_to: {scope: concept}``)."""
    return [
        p
        for p in (packs if packs is not None else load_packs())
        if p.applies_to.get("scope") == CONCEPT_SCOPE
    ]


def rule_params(rule_id: str, packs: list[RulePack] | None = None) -> dict[str, Any]:
    """The YAML ``params`` of one concept rule (empty when the rule is absent)."""
    for pack in concept_packs(packs):
        for rule in pack.rules:
            if rule.get("id") == rule_id:
                return dict(rule.get("params") or {})
    return {}


def circuit_headroom(packs: list[RulePack] | None = None) -> float:
    """``headroom`` of a concept rule ``circuit-available`` (``rating ≥ headroom × current``).

    The one supply margin of the napkin stage: a product's supply screen checks it and
    promotion writes the supply requirement as ``power ≤ V·I / headroom`` from the same
    number (review gate A, B1). No shipped pack has the rule (it is a product's, F10), so this
    is :data:`calckit.power.CIRCUIT_HEADROOM_MIN`, the constant a product's screen should
    read too, unless a concept pack passed in says otherwise.
    """
    from napkin2factory.calckit import power as pw

    params = rule_params("circuit-available", packs)
    return float(params.get("headroom", pw.CIRCUIT_HEADROOM_MIN))


def rule_rows(
    rules: list[dict[str, Any]],
    checks: dict[str, CheckFn],
    facts: ConceptFacts,
    source: str = "the pack",
) -> list[RuleRow]:
    """One :class:`RuleRow` per rule, each evaluated by its named check in ``checks``.

    ``rules`` are pack-shaped dicts (id, title, severity, check, params, message,
    pass_message, warn_message). A check may pick a variant of the wording (its outcome's
    ``variant``, say ``door``: ``title_door``, ``message_door``… where the rule has them).
    Titles and messages may say ``{space}``: the product's word for the space it must fit
    (``facts.shared["space_words"]``, else "space"; S-137). A product's own screen (F10)
    states its rules the same way and calls this.
    """
    from napkin2factory.concepts.screens.base import SPACE_WORDS

    # the product's word for the space it must fit (S-137), for every title and message
    words = {"space": str(facts.shared.get("space_words") or SPACE_WORDS)}
    rows: list[RuleRow] = []
    for rule in rules:
        rid = str(rule["id"])
        title = _fmt(str(rule.get("title", rid)), words)
        severity: Literal["fail", "warn"] = (
            "warn" if str(rule.get("severity", "fail")) == "warn" else "fail"
        )
        fn = checks.get(str(rule.get("check")))
        if fn is None:
            rows.append(
                RuleRow(
                    id=rid,
                    title=title,
                    severity=severity,
                    status="skip",
                    message=f"unknown check {rule.get('check')!r} in {source}",
                )
            )
            continue
        out = fn(facts, dict(rule.get("params") or {}))

        def said(key: str, default: str, out: Any = out) -> str:
            """The rule's wording for ``key``, its check's variant first (``message_door``)."""
            variant = getattr(out, "variant", None)  # an outcome built before variants
            if variant and f"{key}_{variant}" in rule:
                return str(rule[f"{key}_{variant}"])
            return str(rule.get(key, default))

        title = _fmt(said("title", rid), words)
        if out.status == "skip":
            status, message = "skip", _fmt(out.message or "not checked", words)
        elif out.status == "violated":
            template = said("message", rid)
            status = severity
            message = "; ".join(_fmt(template, {**words, **v}) for v in out.violations) or _fmt(
                template, {**words, **out.values}
            )
        elif out.status == "warn":
            status = "warn"
            message = out.message or _fmt(
                said("warn_message", said("message", rid)), {**words, **out.values}
            )
        else:
            status = "pass"
            message = out.message or _fmt(said("pass_message", "ok"), {**words, **out.values})
        relies = sorted({r for r in out.relies_on if r in ("computed", "estimate", "given")})
        rows.append(
            RuleRow(
                id=rid,
                title=title,
                severity=severity,
                status=status,  # type: ignore[arg-type]
                message=message,
                relies_on=relies,  # type: ignore[arg-type]
            )
        )
    return rows


def run_concept_rules(
    card: ConceptCard,
    computed: dict[str, Any],
    estimates: dict[str, Any],
    massing: MassingResult | None = None,
    shared: dict[str, Any] | None = None,
    packs: list[RulePack] | None = None,
) -> list[RuleRow]:
    """Evaluate every concept pack's rules on one card; one :class:`RuleRow` per rule."""
    from napkin2factory.rulepacks.concept_checks import CONCEPT_CHECKS, ConceptFacts

    facts = ConceptFacts(card, computed, estimates, massing, dict(shared or {}))
    rows: list[RuleRow] = []
    for pack in concept_packs(packs):
        rows += rule_rows(pack.rules, CONCEPT_CHECKS, facts, pack.path.name)
    return rows
