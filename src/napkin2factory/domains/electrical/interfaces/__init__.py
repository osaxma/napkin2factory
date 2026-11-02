"""The ``cable-entry`` interface kind (ELECTRICAL_STAGE E4): where wiring crosses a box.

A cable entry joins the box (the party that gets the hole) to the gland or bushing in it.
Its spec subclasses the core's ``BoltPatternSpec`` (S-144), so the core cuts the hole in
every party that has a shape, matches the parties' holes and lines the joint up, exactly as
for a bolt pattern; a bought gland with no shape is skipped with the core's own sentence.
Then :func:`check_cable_entry` runs and the worse status wins: every circuit the entry
``passes`` exists and has a connection going ``via`` it.

An entry is one hole at its frame's origin (S-155): ``count`` is 1 and the pattern stays
``rect`` (the core's one-hole case); a ``circle`` pattern places its holes on a pitch
circle, so a one-hole circle without one is refused with the fix.  A module supplied from
elsewhere (``build: external``) lists its cable entries under ``ports:``; the model's
``validate_refs`` refuses a conductor that reaches such a module through anything else.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from napkin2factory.core.domain import InterfaceKind
from napkin2factory.core.model.base import uri_of
from napkin2factory.core.model.interfaces import BoltPatternSpec

#: A circuit named under ``passes:`` (the scheme is the electrical domain's ``circuit``).
CircuitUri = uri_of("circuit")


class CableEntrySpec(BoltPatternSpec):
    """A cable entry: one hole (``diameter``) and the circuits that pass it (``passes``)."""

    count: int = 1
    passes: list[CircuitUri] = Field(default_factory=list)

    @model_validator(mode="after")
    def _one_hole(self) -> CableEntrySpec:
        if self.count != 1:
            raise ValueError(
                f"a cable entry is one hole (count: {self.count}); declare one entry per hole"
            )
        if self.pattern == "circle" and self.pitch_circle is None:
            raise ValueError(
                "a cable entry is one hole at its frame's origin: leave `pattern:` out (a "
                "circle pattern places its holes on a pitch circle, which one hole has not)"
            )
        return self


def _party_words(product: Any, party: Any) -> str:
    table = product.parts if party.scheme == "part" else product.assemblies
    obj = table.get(party.id)
    # lower case, as the core's own sentence before it says the parties ("cut in box")
    return str(getattr(obj, "name", None) or party.id).lower()


def _circuit_words(circuit: Any) -> str:
    return f"the {circuit.name or circuit.id} circuit"


def check_cable_entry(product: Any, iface: Any, build_dir: Path) -> dict[str, Any]:
    """The entry's own check, after the core's hole checks (S-144).

    Fails when a circuit it lists does not exist or has no connection going ``via`` it;
    warns when it lists none.  The message says the joint in the owner's words: the box,
    the gland and the circuits that cross there.
    """
    from napkin2factory.domains.electrical.model import circuits

    first, second = (_party_words(product, p) for p in iface.parties)
    joint = f"{first} to {second}"
    known = circuits(product)
    listed = [str(u) for u in iface.spec.passes]
    if not listed:
        return {
            "status": "warn",
            "message": f"{joint}: no circuit passes through this entry yet; list the circuits "
            "that cross here under `passes:`",
        }
    problems: list[str] = []
    crossing: list[str] = []
    for uri in listed:
        cid = uri.removeprefix("circuit://")
        circuit = known.get(cid)
        if circuit is None:
            problems.append(f"{uri} is listed under `passes:` but does not exist")
            continue
        if not any(c.via is not None and c.via.id == iface.id for c in circuit.connections):
            problems.append(
                f"{_circuit_words(circuit)} is listed under `passes:`, but none of its "
                f"connections goes `via: {iface.uri}`; add it to the connection that crosses "
                "here, or remove the circuit from `passes:`"
            )
            continue
        crossing.append(_circuit_words(circuit))
    if problems:
        return {"status": "fail", "message": f"{joint}: " + "; ".join(problems)}
    return {"status": "pass", "message": f"{joint}: carries " + " and ".join(crossing)}


KIND = InterfaceKind("cable-entry", "Cable entry", spec=CableEntrySpec, check=check_cable_entry)

#: The interface kinds the domain registers.
INTERFACE_KINDS = (KIND,)
