"""The electrical check stage (E6, S-154, E11, S-184): wiring rows of ``n2f check``.

One row per rule and what it is about, id ``elec-rule://<rule>@<circuit, part, entry,
device or supply>`` (unique, stable while the thing keeps its id), kind ``electrical``
(the Verify gate's "Wiring checks" row counts them).  The model is read once through
``sctx.proxy`` (:func:`~napkin2factory.domains.electrical.checks.calcs.read_wiring`), so
each field used is a recorded read of the ``checks`` rule (D5).  ``fail`` only for
arithmetic and topology that is certain; everything a wiring code would judge is ``warn``
and its message ends with what to do and that a licensed electrician decides; an unknown
(a load with no rating, a conductor with no rated current) never fails.  Each row's
message names the part, the circuit and what to do (DoD 3), in owner words.

``--scope asm://<id>`` (§4): a circuit's rows belong to the assembly its devices share
(their subject is that ``asm://``), a part's to its home, an entry's to where it closes, the
supply's to the whole product; :func:`electrical_checks` keeps a row only when
``sctx.keep`` says so.  A product without ``model/electrical/``, or whose wiring is left for
later, has no row at all (E12, F11).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from napkin2factory.calckit import power
from napkin2factory.core.units import magnitude_in
from napkin2factory.domains.electrical.checks import nets
from napkin2factory.domains.electrical.checks.calcs import (
    DeviceRec,
    Wiring,
    read_wiring,
    supply_load,
)
from napkin2factory.domains.electrical.checks.pack import rule
from napkin2factory.domains.electrical.checks.protection import (
    _conductor_protection_row,
    _conductor_row,
    _feeds,
    _protected_by,
    _protection_row,
    _wires_said,
)
from napkin2factory.domains.electrical.checks.rows import (
    PROTECTED,
    ROW_KIND,
    ROW_SCHEME,
    _a,
    _band,
    _cap,
    _carries_mains,
    _categories,
    _class_two_row,
    _contact_row,
    _controller_side,
    _device_rows,
    _earth_rows,
    _entry_rows,
    _list,
    _load_in,
    _rating,
    _Rows,
    _safety_row,
    _the,
    row_id,
)
from napkin2factory.domains.electrical.model import circuits, has_content, supply

if TYPE_CHECKING:  # an installed domain is imported while the core's schemas load (S-153)
    from napkin2factory.core.checks.results import CheckResult
    from napkin2factory.core.domain import StageContext


def electrical_checks(sctx: StageContext) -> list[CheckResult]:
    """The wiring rows of ``n2f check`` (E6, E11), read through ``sctx.proxy``."""
    product = sctx.product
    if not has_content(product):
        return []
    entry = product.manifest.scope.get("electrical")
    if entry is not None and entry.state == "later":
        return []  # the wiring is not designed here yet (F11): no row
    w = read_wiring(product, sctx.proxy, sctx.log)
    t = nets.topology(w)
    rows = _Rows(sctx, w)
    _supply_rows(rows, w)
    for cid in w.circuits:
        _protection_row(rows, w, cid)
        _conductor_row(rows, w, t, cid)
        _conductor_protection_row(rows, w, t, cid)
    _earth_rows(rows, w, t)
    _entry_rows(rows, w, t)
    _device_rows(rows, w, t)
    return rows.out


def electrical_check_reads(product: Any) -> list[str]:
    """Keys the rows depend on that are not model fields: each circuit's ``elec:`` output."""
    return [f"circuit://{cid}" for cid in sorted(circuits(product))]


# ---- the supply --------------------------------------------------------------------------------


def _load_words(loads: tuple[tuple[DeviceRec, Any], ...]) -> str:
    return _list([f"the {d.words}: {_a(f.value)}, {f.words}" for d, f in loads])


def _supply_rows(rows: _Rows, w: Wiring) -> None:
    sup = w.supply
    if sup is None:
        return
    if sup.upstream is not None:
        rating = f" (rated {_rating(sup.rating.value)})" if sup.rating is not None else ""
        rows.add(
            "upstream-protection",
            "supply",
            "supply://supply",
            "warn",
            f"The supply is protected by {sup.upstream}{rating}, a device of the site, not of "
            "the product.",
            home=None,
        )
    load = supply_load(w)
    if not load.circuits:
        return
    names = _list([w.circuits[c].words for c in load.circuits])
    draw = "draws" if len(load.circuits) == 1 else "together draw"
    if sup.rating is None:
        rows.add(
            "supply-load",
            "supply",
            "supply://supply",
            "warn",
            f"The supply's rating is not given, so the load of {names} cannot be checked "
            "against it.",
            home=None,
            fix="give the supply's rating (the breaker of the circuit it plugs into)",
        )
        return
    rating = sup.rating.value
    total = load.total
    detail = {
        "load_a": round(magnitude_in(total, "A"), 3),
        "rating_a": magnitude_in(rating, "A"),
        "circuits": list(load.circuits),
    }
    over = magnitude_in(total, "A") > magnitude_in(rating, "A")
    loads_words = f" ({_load_words(load.loads)})" if load.loads else ""
    if over:
        rows.add(
            "supply-load",
            "supply",
            "supply://supply",
            "fail",
            f"{_cap(names)} {draw} {_a(total)}{loads_words}, above the supply's "
            f"{_rating(rating)} ({sup.rating.words}).",
            home=None,
            detail=detail,
        )
        return
    if load.unknown:
        missing = _list([f"the {d.words}" for d in load.unknown])
        rows.add(
            "supply-load",
            "supply",
            "supply://supply",
            "warn",
            f"{_cap(missing)} {'has' if len(load.unknown) == 1 else 'have'} no rating, so the "
            f"load of {names} on the supply's {_rating(rating)} is not known "
            f"(the rest draw {_a(total)}).",
            home=None,
            fix="give each load its rated power or current, read from its rating plate",
            detail=detail,
        )
        return
    if not load.loads:
        return
    rows.add(
        "supply-load",
        "supply",
        "supply://supply",
        "pass",
        f"{_cap(names)} {draw} {_a(total)}{loads_words} of the supply's {_rating(rating)} "
        f"({sup.rating.words}).",
        home=None,
        detail=detail,
    )
    _headroom_row(rows, w, total, rating, load)


def _next_circuit(w: Wiring, rating_a: float) -> dict[str, Any] | None:
    """The next larger circuit class on file for the supply's region and voltage."""
    sup = w.supply
    if sup is None or sup.region is None:
        return None
    rows = power.circuit_rows(sup.region)
    if sup.voltage is not None:
        volts = magnitude_in(sup.voltage, "V")
        rows = [r for r in rows if abs(float(r["voltage"]) - volts) < 1e-6]
    bigger = [r for r in rows if float(r["rating_a"]) > rating_a + 1e-9]
    if not bigger:
        return None
    return min(bigger, key=lambda r: (float(r["rating_a"]), r["kind"] != "dedicated"))


def _headroom_row(rows: _Rows, w: Wiring, total: Any, rating: Any, load: Any) -> None:
    """E11: above a cited fraction of the rating but fitting, the owner chooses."""
    from napkin2factory.core.checks.choices import Option, offer

    sup = w.supply
    assert sup is not None
    fraction = float(rule("supply-headroom").param("fraction"))
    load_a, rating_a = magnitude_in(total, "A"), magnitude_in(rating, "A")
    share = "half" if abs(fraction - 0.5) < 1e-9 else f"{fraction:.0%}"
    evidence = [
        "supply://supply",
        *([f"param://{sup.rating_param}"] if sup.rating_param else []),
        *[f"circuit://{c}" for c in load.circuits],
        *[f"device://{d.id}" for d, _ in load.loads],
    ]
    detail = {
        "load_a": round(load_a, 3),
        "rating_a": rating_a,
        "fraction": fraction,
        "evidence": evidence,
    }
    if load_a <= fraction * rating_a:
        rows.add(
            "supply-headroom",
            "supply",
            "supply://supply",
            "pass",
            f"{_a(total)} of the {_rating(rating)} circuit: no more than {share} of it, so "
            "the circuit has room to spare.",
            home=None,
            detail=detail,
        )
        return
    problem = (
        f"{_a(total)} of the {_rating(rating)} circuit ({_load_words(load.loads)}): more "
        f"than {share} of it."
    )
    # `dedicated: true` is the `dedicated` pick made in the model, so the row passes and a
    # decided choice leaves "not yet in the design" (S-171).
    sctx = rows.sctx
    if bool(sctx.proxy(supply(sctx.product), "supply://supply").dedicated):
        rows.add(
            "supply-headroom",
            "supply",
            "supply://supply",
            "pass",
            f"{_a(total)} of the {_rating(rating)} circuit, more than {share} of it; the "
            "circuit serves this product alone, so nothing else may be plugged into it (the "
            "electrician confirms).",
            home=None,
            detail={**detail, "dedicated": True},
        )
        return
    nxt = _next_circuit(w, rating_a)
    if nxt is None:
        rows.add(
            "supply-headroom",
            "supply",
            "supply://supply",
            "warn",
            f"{problem} No larger circuit is on file for the supply's region, so the one way "
            "left is to keep this circuit for the product alone.",
            home=None,
            fix=(
                f"the electrician makes the {_rating(rating)} circuit serve this product alone "
                "and the supply says so (`dedicated: true` in the wiring's supply file); a "
                "licensed electrician decides"
            ),
            detail=detail,
        )
        return
    row = rows.add(
        "supply-headroom",
        "supply",
        "supply://supply",
        "fail",
        problem,
        home=None,
        detail=detail,
    )
    if row is None:
        return
    nxt_a = float(nxt["rating_a"])
    offer(
        row,
        [
            Option(
                "dedicated",
                f"a dedicated {_rating(rating)} circuit; nothing else may be plugged into it",
                f"the electrician fits or confirms a {_rating(rating)} circuit that serves this "
                "product alone, the supply says so (`dedicated: true` in the wiring's supply "
                "file), and the manual says nothing else may be plugged into it",
            ),
            Option(
                "larger",
                f"a {nxt['label']}: room for a bigger load later; the electrician fits thicker "
                "cable",
                f"the supply's rating becomes {nxt_a:g} A, and the electrician fits a "
                f"{nxt_a:g} A circuit with cable sized for it",
            ),
        ],
        blocks="none",
        problem=problem,
    )


__all__ = [
    "PROTECTED",
    "ROW_KIND",
    "ROW_SCHEME",
    "_Rows",
    "_a",
    "_band",
    "_cap",
    "_carries_mains",
    "_categories",
    "_class_two_row",
    "_conductor_protection_row",
    "_conductor_row",
    "_contact_row",
    "_controller_side",
    "_device_rows",
    "_earth_rows",
    "_entry_rows",
    "_feeds",
    "_headroom_row",
    "_list",
    "_load_in",
    "_load_words",
    "_next_circuit",
    "_protected_by",
    "_protection_row",
    "_rating",
    "_safety_row",
    "_supply_rows",
    "_the",
    "_wires_said",
    "electrical_check_reads",
    "electrical_checks",
    "row_id",
]
