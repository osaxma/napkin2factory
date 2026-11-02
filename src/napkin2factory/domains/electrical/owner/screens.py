"""The wiring's napkin screen (ELECTRICAL_STAGE E8): does the site's supply carry the product?

Moved from an example product's own pack (``model/screens/``, S-168), the path any
product's screen takes to a domain: the same rule ``circuit-available``, the same
numbers and the same row and estimate words, in generic words ("the product", never a
part).  It reads the power the product draws (``envelope.power``, or the power a product's
own screen derived and left in ``values.shared["power"]``, labelled by
``values.shared["power_label"]``) against the site's ``circuit`` (``230V-16A``), else the
usual circuits of its ``region`` (``calckit.power``).

It runs in phase ``check``, after every ``estimate`` screen, so a power a product's screen
derives (from a planned heat-up, say) is the one it checks; domain screens run before a
product's own within a phase (docs/domains.md §3.11), so its row comes right before the
product's own check rows, where the product's pack had it (S-168).  A card that says nothing
about power or supply gets no row and no note (E12).

:data:`SUPPLY_HEADROOM` is the margin it checks (``rating ≥ headroom × current``), the one a
product's promotion writes into its supply requirement; :data:`CIRCUIT` and :data:`REGION`
are the card fields, public so a product's hooks read the same ones.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from napkin2factory.calckit import power as pw
from napkin2factory.concepts.screens import TO_CHECK, CardField, ScreenValues, fmt, reads
from napkin2factory.core.domain import Screen
from napkin2factory.core.model.concepts import ConceptCard, RuleRow

if TYPE_CHECKING:  # the rule runner imports the loader, which imports this domain (S-161)
    from napkin2factory.rulepacks.concept_checks import ConceptFacts, Outcome

# ``hint=False``: a new card's skeleton names these only when the card already gives one, so
# a product with no supply never reads a wiring word (E12, S-168)
#: The power the product draws.
POWER = CardField("envelope", "power", "W", "a power", "2.5 kW", "the power", hint=False)
#: The circuit it plugs into, ``<volts>V-<amps>A``.
CIRCUIT = CardField(
    "site", "circuit", None, "words", "230V-16A", "the circuit it plugs into", hint=False
)
#: Where it will be used (the key of the calc kit's circuit table).
REGION = CardField("site", "region", None, "words", "EU", "where it will be used", hint=False)

#: ``rating ≥ headroom × current``: the calc kit's margin (NEC 210.20 uses 1.25) [verify].
SUPPLY_HEADROOM: float = float(pw.CIRCUIT_HEADROOM_MIN)

#: The rule, worded like a pack (S-022); ``params.headroom`` is :data:`SUPPLY_HEADROOM`.
SUPPLY_RULE: dict[str, Any] = {
    "id": "circuit-available",
    "title": "The supply on site carries it",
    "severity": "fail",
    "check": "circuit_available",
    "params": {"headroom": SUPPLY_HEADROOM},
    "message": "{power} draws {current}; with {margin} headroom it needs {needed}, more "
    "than {circuit}",
    "pass_message": "{power} draws {current}: {circuit}",
    "warn_message": "no circuit table for region {region} — confirm the supply",
}


def _power_text(power: Any) -> str:
    w = float(power.to("W").magnitude)
    return f"{w / 1000:.3g} kW" if w >= 1000 else f"{w:.0f} W"


def _article(label: str | None) -> str:
    return "an" if (label or "x")[0] in "8aeiouAEIOU" or (label or "").startswith("11") else "a"


def circuit_available(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """The product's current, with headroom, fits the site's circuit.

    An explicit ``site.circuit`` (``240V-13A``) is checked directly; otherwise the region
    table picks the smallest class (``calckit.power.circuit_for_power``).  An unknown region
    is a warning, never a failure.
    """
    from napkin2factory.rulepacks.concept_checks import Outcome, parse_circuit

    power = facts.shared.get("power")
    if power is None:
        return Outcome("skip", message="no power to check: give the card the power it draws")
    headroom = float(params.get("headroom", SUPPLY_HEADROOM))
    circuit = CIRCUIT.raw(facts.card)
    region = REGION.raw(facts.card)
    parsed = parse_circuit(circuit) if isinstance(circuit, str) else None
    # the current is an estimate; the card's own power and circuit are given (gate A, C1)
    relies = ["estimate"]
    if parsed is not None or facts.shared.get("power_label") == "card":
        relies.append("given")
    values: dict[str, Any] = {
        "power": _power_text(power),
        "margin": f"{(headroom - 1) * 100:.0f} %",
        "region": region,
    }
    if parsed is not None:
        volts, amps = parsed
        current = pw.element_current(power, volts)
        needed = headroom * float(current.to("A").magnitude)
        values.update(
            current=f"{float(current.to('A').magnitude):.1f} A at {volts.magnitude:g} V",
            needed=f"{needed:.1f} A",
            circuit=f"the {circuit} circuit on site",
        )
        if needed <= float(amps.to("A").magnitude) + 1e-9:
            values["circuit"] = f"fits the {circuit} circuit on site"
            return Outcome("pass", values, [], relies)
        return Outcome("violated", values, [values], relies)
    if not isinstance(region, str) or not region.strip():
        return Outcome(
            "skip", message="no supply on the card (a circuit like 240V-13A, or a region)"
        )
    verdict = pw.circuit_for_power(region, power, headroom=headroom)
    if verdict.status == "unknown_region":
        return Outcome("warn", values, [], relies)
    amps_now = float(verdict.current.to("A").magnitude)
    values.update(current=f"{amps_now:.1f} A", needed=f"{headroom * amps_now:.1f} A")
    if verdict.status == "ok":
        values["circuit"] = f"needs {_article(verdict.label)} {verdict.label}"
        return Outcome("pass", values, [], relies)
    values["circuit"] = f"any circuit on file for {region}"
    return Outcome("violated", values, [values], relies)


def _says_supply(card: ConceptCard, values: ScreenValues) -> bool:
    """True when the card (or a screen before this one) says anything about power or supply."""
    return any(f.raw(card) is not None for f in (POWER, CIRCUIT, REGION)) or (
        values.shared.get("power") is not None
    )


@reads(POWER, CIRCUIT, REGION, phase="check")
def supply(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """The product's current on the site's circuit, or the usual circuit of its region."""
    if not _says_supply(card, values):
        return []  # nothing about power or supply: no row, no note (E12)
    card_power = POWER.quantity(card)
    if card_power is not None:
        values.given.add("power", card_power, fmt(card_power, "W"), "on the card", "envelope.power")
    _supply_values(card, values)
    from napkin2factory.rulepacks.concept_checks import ConceptFacts, rule_rows

    facts = ConceptFacts(card, values.computed.raw, values.estimate.raw, massing, values.shared)
    return rule_rows(
        [SUPPLY_RULE],
        {"circuit_available": circuit_available},
        facts,
        "the wiring's supply screen",
    )


def _supply_values(card: ConceptCard, values: ScreenValues) -> None:
    from napkin2factory.rulepacks.concept_checks import parse_circuit

    est, given, extra, notes = values.estimate, values.given, values.shared, values.notes
    power = extra.get("power")
    if power is None:
        power = POWER.quantity(card)
        if power is not None:
            extra["power"], extra["power_label"] = power, "card"
        elif POWER.raw(card) is not None:
            return  # a power of the wrong kind: the runner already says so
        else:
            notes.append("no power on the card: give the power it draws to check the supply")
            return
    circuit = CIRCUIT.raw(card)
    region = REGION.raw(card)
    parsed = parse_circuit(circuit) if isinstance(circuit, str) else None
    if parsed is not None:
        volts, _amps = parsed
        current = pw.element_current(power, volts)
        est.add(
            "current",
            current,
            fmt(current, "A"),
            "from the power and the circuit's voltage",
            f"power.element_current at {volts.magnitude:g} V",
        )
        given.add(
            "circuit_class",
            f"the {circuit} circuit",
            f"the {circuit} circuit",
            "on the card",
            "site.circuit",
        )
        return
    if isinstance(circuit, str) and circuit.strip():
        notes.append(
            f"the circuit {circuit.strip()!r} is not written like 240V-13A, so the usual "
            "circuits of the region are used instead"
        )
    if not isinstance(region, str) or not region.strip():
        notes.append(
            "say which circuit it plugs into (like 230V-16A) or where it will be used (SA, EU, "
            "UK, US or AU) to check the supply"
        )
        return
    verdict = pw.circuit_for_power(region, power)
    if verdict.status == "unknown_region":
        notes.append(f"no list of the usual circuits in {region} yet: confirm the supply by hand")
        return
    est.add(
        "current",
        verdict.current,
        fmt(verdict.current, "A"),
        f"from the power and the usual {region} supply voltage",
        "power.circuit_for_power",
    )
    if verdict.status == "ok":
        label = str(verdict.label)
        est.add(
            "circuit_class",
            label,
            label,
            f"the smallest {region} circuit on file that carries it; {TO_CHECK}",
            f"power.circuit_for_power ({region} table) [verify]",
        )
    else:
        notes.append(
            f"none of the usual {region} circuits on file carries {fmt(verdict.current, 'A')}"
        )


SCREENS = (Screen("supply", supply, title="The supply carries it"),)
