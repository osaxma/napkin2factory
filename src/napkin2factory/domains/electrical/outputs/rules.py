"""The ``elec:<circuit>`` rules (E5). Stub until M2: no circuit makes a rule yet."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # an installed domain is imported while the core's schemas load (S-153)
    from napkin2factory.core.graph.rules import Rule, RuleBuild


def elec_rules(b: RuleBuild) -> list[Rule]:
    """One ``elec:<circuit>`` rule per circuit, writing under ``build/electrical/<circuit>/``.

    Stub (M1): returns no rule. M2 fills it: each rule reads its circuit, the devices and
    the cable entries it names through ``ctx.proxy`` (D5) and writes the diagram, the
    connection table and the circuit's share of the schedule and the labels.
    """
    return []


def elec_static_reads(product: Any, rule: Rule) -> list[str]:
    """The reads ``n2f impact`` assumes for an ``elec:`` rule before the first build (stub)."""
    return []
