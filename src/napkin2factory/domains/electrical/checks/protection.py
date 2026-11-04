"""Circuit and conductor protection rows; split from stage.py (S-184)."""

from __future__ import annotations

from napkin2factory.core.units import magnitude_in
from napkin2factory.domains.electrical.checks import nets
from napkin2factory.domains.electrical.checks.calcs import (
    ConductorLoad,
    Figure,
    Wiring,
    circuit_load,
    conductor_loads,
    protective_device_id,
    protective_rating,
    protective_words,
    supply_protection,
)
from napkin2factory.domains.electrical.checks.rows import (
    PROTECTED,
    _a,
    _cap,
    _list,
    _rating,
    _Rows,
)


def _feeds(w: Wiring, cid: str) -> str:
    loads = [f"the {d.words}" for d in w.circuit_devices(cid) if d.role == "load"]
    return f" (feeding {_list(loads)})" if loads else ""


def _protection_row(rows: _Rows, w: Wiring, cid: str) -> None:
    c = w.circuits[cid]
    if c.purpose not in PROTECTED:
        return
    subject, home = rows.circuit_subject(cid)
    name = _cap(c.words)
    if c.protection is None:
        rows.add(
            "protection",
            cid,
            subject,
            "fail",
            f"{name}{_feeds(w, cid)} names no protective device.",
            home=home,
            circuit=cid,
        )
        return
    rated = protective_rating(w, cid)
    by = protective_words(w, cid)
    if c.protection == "supply" and rated is None:
        rows.add(
            "protection",
            cid,
            subject,
            "fail",
            f"{name}{_feeds(w, cid)} is protected by the supply's own device, but the "
            "supply's rating is not given.",
            home=home,
            circuit=cid,
            fix="give the supply's rating, or name the breaker or fuse that protects the circuit",
        )
        return
    load = circuit_load(w, cid).total
    if (
        rated is not None
        and load is not None
        and magnitude_in(load.value, "A") > magnitude_in(rated.value, "A")
    ):
        rows.add(
            "protection",
            cid,
            subject,
            "fail",
            f"{name}{_feeds(w, cid)} draws {_a(load.value)} ({load.words}), above the "
            f"rating of {by} ({_rating(rated.value)}).",
            home=home,
            circuit=cid,
            fix="use a protective device rated for the circuit's load, or lower the load",
        )
        return
    rating = f" ({_rating(rated.value)})" if rated is not None else ""
    rows.add(
        "protection",
        cid,
        subject,
        "pass",
        f"{name} is protected by {by}{rating}.",
        home=home,
        circuit=cid,
    )


def _conductor_row(rows: _Rows, w: Wiring, t: nets.Topology, cid: str) -> None:
    c = w.circuits[cid]
    loads = conductor_loads(w, cid, t.earth, t)
    if not loads:
        return
    subject, home = rows.circuit_subject(cid)
    name = _cap(c.words)
    load = circuit_load(w, cid)
    if load.total is None:
        verb = "has" if len(load.unknown) == 1 else "have"
        why = (
            f"{_list([f'the {d.words}' for d in load.unknown])} {verb} no rating"
            if load.unknown
            else "no device in it declares the current it draws"
        )
        rows.add(
            "conductor-current",
            cid,
            subject,
            "skip",
            f"The current in {c.words}'s conductors is not known ({why}), so their size is "
            "not checked.",
            home=home,
            circuit=cid,
        )
        return
    current = load.total
    thin = [r for r in loads if r.margin is not None and magnitude_in(r.margin, "A") < 0]
    unnamed = [r for r in loads if r.wire.conductor is None]
    unrated = [r for r in loads if r.wire.conductor is not None and r.rated is None]
    detail = {"current_a": round(current.amps(), 3)}
    if thin:

        def _thin_words(r: ConductorLoad) -> str:
            label = w.conductors[r.wire.conductor or ""].label
            base = f"{r.wire.words} is {label}, rated {_a(r.rated)}"
            if r.current is not None and abs(r.current.to("A").magnitude - current.amps()) > 1e-3:
                return f"{base} (carries {_a(r.current)})"
            return base

        said = _list([_thin_words(r) for r in thin])
        rows.add(
            "conductor-current",
            cid,
            subject,
            "fail",
            f"{name} carries {_a(current.value)} ({current.words}), but {said}.",
            home=home,
            circuit=cid,
            detail=detail,
        )
        return
    if unnamed or unrated:
        said = _list(
            [f"{r.wire.words} names no conductor" for r in unnamed]
            + [
                f"{r.wire.words} uses {w.conductors[r.wire.conductor or ''].label}, whose rated "
                "current is not on file"
                for r in unrated
            ]
        )
        rows.add(
            "conductor-current",
            cid,
            subject,
            "warn",
            f"{name} carries {_a(current.value)} ({current.words}); {said}, so "
            f"{'it is' if len(unnamed) + len(unrated) == 1 else 'they are'} not checked.",
            home=home,
            circuit=cid,
            fix=(
                "name each connection's conductor from the table on file, or add the "
                "product's own conductor with its rated current and its source"
            ),
            detail=detail,
        )
        return
    worst = min(loads, key=lambda r: magnitude_in(r.margin, "A"))
    rows.add(
        "conductor-current",
        cid,
        subject,
        "pass",
        f"{name} carries {_a(current.value)} ({current.words}); every conductor is rated for "
        f"it (the least margin: {_a(worst.margin)}, {worst.wire.words}).",
        home=home,
        circuit=cid,
        detail=detail,
    )


def _protected_by(
    w: Wiring, t: nets.Topology, cid: str
) -> list[tuple[ConductorLoad, Figure | None, str]]:
    """Each rated-or-not conductor of a circuit with the device that protects it.

    Downstream of the circuit's own device: that device (its rating ``None`` when not
    given).  On the supply side of it (a lead from the supply's terminal block to a fuse):
    the supply's own device, when nothing else of the product stands between; a lead fed
    through another of the product's devices is left out [revisit] (S-178).  A conductor
    no source reaches even with every contact closed (a controller's output to a relay's
    input) carries no supply current and is left out too.
    """
    c = w.circuits[cid]
    rated, by = protective_rating(w, cid), protective_words(w, cid)
    sup_rated, sup_by = supply_protection(w)
    feed: set[str] = set()
    direct: set[str] = set()
    pid = protective_device_id(w, cid)
    if pid is not None:
        feed = nets.line_side(t, pid)
        protective = {d.id for d in w.devices.values() if d.role == "protection"}
        direct = nets.fed_unprotected(t, protective)
    powered = nets.fed_unprotected(t, set())
    out: list[tuple[ConductorLoad, Figure | None, str]] = []
    for r in conductor_loads(w, cid, t.earth, t):
        ends = (r.wire.a, r.wire.b)
        if not any(n in powered for n in ends):
            continue
        if c.protection != "supply" and any(n in feed for n in ends):
            if any(n in direct for n in ends):
                out.append((r, sup_rated, sup_by))
            continue
        out.append((r, rated, by))
    return out


def _wires_said(group: list[ConductorLoad], w: Wiring) -> str:
    """``connection 1 (…) and connection 2 (…) are 0.75 mm² PVC, rated 8.5 A (from the table)``."""
    row = w.conductors[group[0].wire.conductor or ""]
    verb = "is" if len(group) == 1 else "are"
    assert group[0].rated is not None
    return (
        f"{_list([g.wire.words for g in group])} {verb} {row.label}, rated "
        f"{_rating(group[0].rated)} ({row.basis})"
    )


def _conductor_protection_row(rows: _Rows, w: Wiring, t: nets.Topology, cid: str) -> None:
    """Gate G blocker 1 (S-178): each conductor rated at least its protective device.

    I_n <= I_z: a device rated above a conductor lets through, without opening, a current the
    conductor is not rated for.  Below it: ``fail`` (arithmetic); a device with no rating:
    ``warn``.  A circuit that needs no device, or names none (the protection row fails it),
    has no row.
    """
    c = w.circuits[cid]
    if c.purpose not in PROTECTED or c.protection is None:
        return
    if c.protection == "supply" and protective_rating(w, cid) is None:
        return  # the protection row fails it: the supply's rating is not given
    judged = _protected_by(w, t, cid)
    if not judged:
        return
    subject, home = rows.circuit_subject(cid)
    name = _cap(c.words)
    below: dict[tuple[str, str], list[ConductorLoad]] = {}
    devices: dict[str, Figure] = {}
    unrated_device: dict[str, list[ConductorLoad]] = {}
    unknown: list[ConductorLoad] = []
    worst: tuple[float, ConductorLoad, str, Figure] | None = None
    for r, rated, by in judged:
        if r.rated is None:
            unknown.append(r)
            continue
        if rated is None:
            unrated_device.setdefault(by, []).append(r)
            continue
        devices[by] = rated
        spare = magnitude_in(r.rated, "A") - magnitude_in(rated.value, "A")
        if spare < -1e-9:
            below.setdefault((by, r.wire.conductor or ""), []).append(r)
        if worst is None or spare < worst[0]:
            worst = (spare, r, by, rated)
    detail = {"protected_by": {by: magnitude_in(f.value, "A") for by, f in devices.items()}}
    if below:
        said = "; ".join(
            f"{_wires_said(group, w)}, below {by} that protects "
            f"{'it' if len(group) == 1 else 'them'} ({_rating(devices[by].value)}, given)"
            for (by, _), group in below.items()
        )
        many = sum(len(g) for g in below.values())
        least = min(magnitude_in(g.rated, "A") for gs in below.values() for g in gs)
        most = max(magnitude_in(devices[by].value, "A") for by, _ in below)
        rows.add(
            "conductor-protection",
            cid,
            subject,
            "fail",
            f"In {c.words}, {said}: the device lets through, without opening, more current "
            f"than {'the conductor is' if many == 1 else 'the conductors are'} rated for.",
            home=home,
            circuit=cid,
            fix=(
                f"use conductors rated at least {most:g} A, or a protective device rated no "
                f"more than {least:g} A; a licensed electrician decides"
            ),
            detail=detail,
        )
        return
    if unrated_device or unknown:
        found = [
            f"{name} is protected by {by}, whose rating is not given, so whether it protects "
            f"{'its conductor' if len(group) == 1 else 'its conductors'} is not checked"
            for by, group in unrated_device.items()
        ]
        if unknown:
            words = _list(
                [
                    f"{r.wire.words} names no conductor"
                    if r.wire.conductor is None
                    else f"{r.wire.words} uses {w.conductors[r.wire.conductor].label}, whose "
                    "rated current is not on file"
                    for r in unknown
                ]
            )
            lead = "" if found else f"In {c.words}, "
            found.append(
                f"{lead}{words}, so {'it is' if len(unknown) == 1 else 'they are'} "
                f"not checked against the device that protects "
                f"{'it' if len(unknown) == 1 else 'them'}"
            )
        fix = (
            "give the protective device's rated current, read from its datasheet; "
            "a licensed electrician decides"
            if unrated_device
            else "name each connection's conductor from the table on file, or add the "
            "product's own conductor with its rated current and its source; a licensed "
            "electrician decides"
        )
        rows.add(
            "conductor-protection",
            cid,
            subject,
            "warn",
            "; ".join(found) + ".",
            home=home,
            circuit=cid,
            fix=fix,
            detail=detail,
        )
        return
    assert worst is not None
    _, r, by, rated = worst
    rows.add(
        "conductor-protection",
        cid,
        subject,
        "pass",
        f"Every conductor of {c.words} is rated at least as high as the device that protects "
        f"it (the closest: {_wires_said([r], w)}, under {by}, rated {_rating(rated.value)}, "
        "given).",
        home=home,
        circuit=cid,
        detail=detail,
    )
