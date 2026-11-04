"""The ``circuit`` verify kind: a circuit's figure against a requirement (``docs/domains.md`` §3.3).

``verify: {kind: circuit, target: "circuit://<id>#props.<figure>", op: "<", value: 16 A}``,
the figure one of :data:`SELECTORS`.  The figure sits under ``props.`` because the core
checks that a selector names a declared field of the object and leaves ``#props.*`` to
the build ("computed, not declared", ``core/loader.py``); ``#load_current`` alone is refused
there (S-158, B-0139):

* ``load_current`` — the current the circuit's loads draw (A);
* ``supply_margin`` — the supply's rating less every power circuit's load on it (A); compare
  it with ``0 A`` (a requirement's ``value`` is a quantity, never a ``param://``);
* ``conductor_margin`` — the smallest margin of the circuit's conductors over its load
  current (A);
* ``earth_paths`` — how many parts the circuit earths (a count).

A figure that is not known (a load with no rating) is ``skip``, never a fail.  The evidence
is the circuit's ``elec:`` output as the core keys it (``circuit://<id>``: the rule's output
hash in the build manifest), plus the records the figure also reads (the supply and its
rating's parameter, the load devices), so a sign-off holds until one of them changes.
A safety requirement is refused: the wiring's safety is a person's to judge (E6), so it is
checked with ``manual``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from napkin2factory.core.units import Quantity, UnitError, compare, format_quantity, magnitude_in
from napkin2factory.domains.electrical.checks import nets
from napkin2factory.domains.electrical.checks.calcs import (
    Figure,
    Wiring,
    circuit_load,
    conductor_margin,
    read_wiring,
    supply_load,
    supply_margin,
)

if TYPE_CHECKING:  # an installed domain is imported while the core's schemas load (S-153)
    from napkin2factory.core.checks.results import CheckResult

#: The figures a ``circuit://<id>#props.<figure>`` target may select.
SELECTORS = ("load_current", "supply_margin", "conductor_margin", "earth_paths")
WORDS = {
    "load_current": "load current",
    "supply_margin": "supply margin",
    "conductor_margin": "smallest conductor margin",
    "earth_paths": "parts it earths",
}


def selected(target: Any) -> str:
    """The figure a target selects (``props.load_current`` → ``load_current``), or ``""``."""
    sel = tuple(target.selector) if target is not None else ()
    return sel[1] if len(sel) == 2 and sel[0] == "props" else ""


def check_circuit_verify(verify: Any) -> None:
    """The target selects one of :data:`SELECTORS` (a ``ValueError`` lists them)."""
    target = verify.target
    if selected(target) not in SELECTORS:
        cid = target.id if target is not None else "<id>"
        raise ValueError(
            f"{target}: a circuit requirement selects one of its figures; write "
            + ", ".join(f"circuit://{cid}#props.{s}" for s in SELECTORS)
        )


def _sha(obj: Any) -> str:
    from napkin2factory.core.graph.hashing import sha256_json

    return sha256_json(obj.model_dump(mode="json"))


def _evidence(ctx: Any, w: Wiring, cid: str, sel: str, evidence: dict[str, str]) -> None:
    from napkin2factory.core.graph.manifest import Manifest
    from napkin2factory.domains.electrical.model import circuits, devices, supply

    manifest = Manifest.load(ctx.build_dir)

    def circuit_key(c: str) -> str:
        entry = manifest.entries.get(f"elec:{c}")  # S-158: as the core keys circuit://
        return entry.output_hash if entry else "missing"

    product = ctx.product
    evidence[f"circuit://{cid}"] = circuit_key(cid)
    if sel == "earth_paths":
        return
    own = [cid]
    if sel == "supply_margin":
        own = list(supply_load(w).circuits)
        sup = supply(product)
        if sup is not None:
            evidence["supply://supply"] = _sha(sup)
        if w.supply is not None and w.supply.rating_param:
            from napkin2factory.core.graph.hashing import sha256_json

            pid = w.supply.rating_param
            evidence[f"param://{pid}"] = sha256_json(format_quantity(product.parameter_value(pid)))
    devs = devices(product)
    for c in own:
        if c != cid and c in circuits(product):
            evidence[f"circuit://{c}"] = circuit_key(c)
        for dev, _ in circuit_load(w, c).parts:
            evidence[f"device://{dev.id}"] = _sha(devs[dev.id])


def figure(w: Wiring, cid: str, sel: str) -> Figure | None:
    """A circuit's figure (``None`` when not known)."""
    if sel == "load_current":
        return circuit_load(w, cid).total
    if sel == "supply_margin":
        return supply_margin(w)
    t = nets.topology(w)
    if sel == "conductor_margin":
        return conductor_margin(w, cid, t.earth, t)
    n = nets.circuit_earth_count(w, t, cid)
    return Figure(Quantity(float(n), ""), "counted from the connections")


def _show(q: Any, sel: str) -> str:
    if sel == "earth_paths":
        return f"{magnitude_in(q, ''):g}"
    return f"{magnitude_in(q, 'A'):.1f} A"


def evaluate_circuit(ctx: Any, req: Any, res: CheckResult, evidence: dict[str, str]) -> str | None:
    """A circuit's figure against the requirement's ``op`` and ``value``."""
    v = req.verify
    cid = v.target.id
    sel = selected(v.target)
    if req.safety:
        res.message = (
            "a safety requirement of the wiring is judged by a person, never by a figure: "
            "check it with `verify: {kind: manual}` and the electrician's sign-off"
        )
        return "fail"
    w = read_wiring(ctx.product)
    if cid not in w.circuits:
        known = ", ".join(sorted(w.circuits)) or "none yet"
        res.message = f"there is no circuit {cid!r} (the circuits: {known})"
        return "fail"
    name = w.circuits[cid].words
    fig = figure(w, cid, sel)
    _evidence(ctx, w, cid, sel, evidence)
    if fig is None:
        res.message = (
            f"the {WORDS[sel]} of {name} is not known (a load or a conductor has no rating), "
            "so it is not checked"
        )
        return "skip"
    value = v.value
    if sel == "earth_paths" and not isinstance(value, Quantity):
        value = Quantity(float(value), "")
    try:
        ok = compare(fig.value, v.op, value)
    except UnitError as exc:
        res.message = f"{name}'s {WORDS[sel]} cannot be compared with {v.value}: {exc}"
        return "fail"
    res.message = (
        f"{name}'s {WORDS[sel]} is {_show(fig.value, sel)} ({fig.words}); "
        f"the requirement: {v.op} {_show(value, sel)}"
    )
    res.detail["figure"] = {
        "name": sel,
        "value": magnitude_in(fig.value, "" if sel == "earth_paths" else "A"),
        "words": fig.words,
    }
    return "pass" if ok else "fail"
