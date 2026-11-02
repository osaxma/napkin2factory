"""The ``electrical`` check stage (E6 as refined by S-154; E11): the wiring's rows of ``n2f check``.

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
    EARTH_TERMINALS,
    DeviceRec,
    Wiring,
    circuit_load,
    circuit_voltage,
    conductor_loads,
    on_supply,
    protective_rating,
    protective_words,
    read_wiring,
    supply_load,
)
from napkin2factory.domains.electrical.checks.pack import rule
from napkin2factory.domains.electrical.model import circuits, has_content

if TYPE_CHECKING:  # an installed domain is imported while the core's schemas load (S-153)
    from napkin2factory.core.checks.results import CheckResult
    from napkin2factory.core.domain import StageContext

#: The ``kind`` of every row this stage writes (the Verify gate row counts them).
ROW_KIND = "electrical"
#: A row's id: ``elec-rule://<rule>@<what it is about>``.
ROW_SCHEME = "elec-rule"
#: The circuit purposes that need a protective device (a sensing loop or an earth bond
#: carries no supply current to protect; S-158).
PROTECTED = ("power", "control")


def row_id(rule_id: str, at: str) -> str:
    """The id of a wiring row: ``elec-rule://<rule>@<at>``."""
    return f"{ROW_SCHEME}://{rule_id}@{at}"


def _a(q: Any) -> str:
    return f"{magnitude_in(q, 'A'):.1f} A"


def _rating(q: Any) -> str:
    return f"{magnitude_in(q, 'A'):g} A"


def _list(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _the(words: str) -> str:
    return words if words.startswith("the ") else f"the {words}"


class _Rows:
    """The rows of one run, each kept only when ``sctx.keep`` takes its home."""

    def __init__(self, sctx: StageContext, w: Wiring) -> None:
        self.sctx = sctx
        self.w = w
        self.out: list[CheckResult] = []

    def add(
        self,
        rule_id: str,
        at: str,
        subject: str,
        status: str,
        finding: str,
        *,
        home: str | None,
        circuit: str | None = None,
        fix: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> CheckResult | None:
        from napkin2factory.core.checks.results import CheckResult

        if not self.sctx.keep(home):
            return None
        r = rule(rule_id)
        message = finding
        if status in ("fail", "warn"):
            message = f"{finding} What to do: {fix or r.fix}."
        row = CheckResult(
            id=row_id(rule_id, at),
            subject=subject,
            status=status,
            message=message,
            kind=ROW_KIND,
            title=r.title,
            detail={
                "rule": f"electrical-v0/{rule_id}",
                **({"circuit": circuit} if circuit else {}),
                **(detail or {}),
            },
        )
        self.out.append(row)
        return row

    # ---- homes (where a row belongs for `n2f check --scope`) --------------------------------

    def part_home(self, pid: str) -> str | None:
        return self.sctx.modules.tree.home(f"part://{pid}")  # type: ignore[no-any-return]

    def circuit_home(self, cid: str) -> str | None:
        """The one assembly holding every device of the circuit, else ``None`` (the product)."""
        tree = self.sctx.modules.tree
        homes: set[str] = set()
        for dev in self.w.circuit_devices(cid):
            home = tree.home(f"part://{dev.part}")
            if home is None:
                return None
            homes.add(home)
        low = tree.lowest_common(homes) if homes else []
        return low[0] if len(low) == 1 else None

    def circuit_subject(self, cid: str) -> tuple[str, str | None]:
        home = self.circuit_home(cid)
        return (f"asm://{home}" if home else f"circuit://{cid}"), home


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


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


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
                f"the electrician makes the {_rating(rating)} circuit serve this product alone; "
                "a licensed electrician decides"
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
                "product alone, and the manual says nothing else may be plugged into it",
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


# ---- each circuit ------------------------------------------------------------------------------


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
    loads = conductor_loads(w, cid, t.earth)
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
        said = _list(
            [
                f"{r.wire.words} is {w.conductors[r.wire.conductor or ''].label}, rated "
                f"{_a(r.rated)}"
                for r in thin
            ]
        )
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


# ---- earth -------------------------------------------------------------------------------------


def _earth_rows(rows: _Rows, w: Wiring, t: nets.Topology) -> None:
    devs = list(w.devices.values())
    if devs and all(d.klass in ("II", "III") for d in devs):
        rows.add(
            "earth-path",
            "product",
            "supply://supply",
            "pass",
            "Every device is Class II or III (double-insulated, or extra-low voltage), so no "
            "part needs a path to earth.",
            home=None,
        )
        return
    paths = nets.earth_paths(w, t)
    mains = [w.circuits[c].words for c in w.circuits if on_supply(w, c)] or [
        w.circuits[c].words for c in w.circuits
    ]
    for pid, (conductive, material) in sorted(w.conductive.items()):
        if conductive is False:
            continue
        name = w.parts.get(pid, pid)
        path = paths.get(pid)
        subject, home = f"part://{pid}", rows.part_home(pid)
        if path is not None and path.how == "wired":
            via = _list([w.circuits[c].words for c in path.circuits])
            rows.add(
                "earth-path",
                pid,
                subject,
                "pass",
                f"The {name} reaches earth through an earth conductor of {via}.",
                home=home,
                circuit=path.circuits[0],
            )
            continue
        if path is not None and path.how == "bonded":
            joints = _list([w.joints[j][0] for j in path.joints if j in w.joints])
            other = w.parts.get(path.via_part or "", path.via_part or "")
            rows.add(
                "earth-bonded",
                pid,
                subject,
                "warn",
                f"The {name} reaches earth only through {joints} (bonded to the {other}), as "
                f"{w.circuits[path.circuits[0]].words} says.",
                home=home,
                circuit=path.circuits[0],
            )
            continue
        if conductive is None:
            what = f"its material ({material})" if material else "no material is given for it"
            rows.add(
                "earth-path",
                pid,
                subject,
                "warn",
                f"Whether the {name} conducts is not known ({what}), and no circuit "
                "connects it to earth.",
                home=home,
                fix=(
                    "name its material; if it conducts, run an earth conductor to it; a "
                    "licensed electrician decides"
                ),
            )
            continue
        claimed = ""
        if path is not None:  # an earth entry whose joints reach no earthed part
            joints = _list([w.joints[j][0] for j in path.joints if j in w.joints]) or "no joint"
            claimed = (
                f" {_cap(w.circuits[path.circuits[0]].words)} bonds it through {joints}, but "
                "no part on the other side reaches earth."
            )
        rows.add(
            "earth-path",
            pid,
            subject,
            "fail",
            f"The {name} is {material}, which conducts, and none of the circuits "
            f"({_list(mains)}) connects it to the supply's earth.{claimed}",
            home=home,
            circuit=path.circuits[0] if path is not None else None,
        )


# ---- cable entries -----------------------------------------------------------------------------


def _band(w: Wiring, cid: str) -> str | None:
    """``elv`` or ``mains`` by the circuit's voltage (S-154 point 4), ``None`` unknown."""
    volts, dc = circuit_voltage(w, cid)
    if volts is None:
        return None
    limit = rule("entry-voltage").param("elv-dc" if dc else "elv-ac")
    return "elv" if magnitude_in(volts, "V") <= magnitude_in(limit, "V") else "mains"


def _entry_rows(rows: _Rows, w: Wiring, t: nets.Topology) -> None:
    by_entry: dict[str, dict[str, set[str]]] = {}
    for c in w.circuits.values():
        for wire in c.wires:
            if wire.via is None or wire.a in t.earth or wire.b in t.earth:
                continue  # earth conductors may share any entry
            band = _band(w, c.id) or "unknown"
            by_entry.setdefault(wire.via, {}).setdefault(band, set()).add(c.id)
    for jid, bands in sorted(by_entry.items()):
        name = w.entries.get(jid, jid)
        home = rows.sctx.modules.closing.get(jid)
        subject = f"iface://{jid}"

        def said(band: str, bands: dict[str, set[str]] = bands) -> str:
            return _list([w.circuits[c].words for c in sorted(bands.get(band, set()))])

        if "elv" in bands and "mains" in bands:
            rows.add(
                "entry-voltage",
                jid,
                subject,
                "warn",
                f"The cable entry “{name}” carries extra-low-voltage conductors "
                f"({said('elv')}) beside mains ones ({said('mains')}).",
                home=home,
            )
            continue
        kind = "extra-low-voltage" if "elv" in bands else "mains"
        if "unknown" in bands and len(bands) == 1:
            kind = "unknown-voltage"
        rows.add(
            "entry-voltage",
            jid,
            subject,
            "pass",
            f"The cable entry “{name}” carries {kind} conductors only "
            f"({_list([w.circuits[c].words for b in bands.values() for c in sorted(b)])}).",
            home=home,
        )


# ---- devices: interlocks, limits, contacts, terminals --------------------------------------------


def _device_rows(rows: _Rows, w: Wiring, t: nets.Topology) -> None:
    base = nets.live(t)
    stuck = _controller_side(w, t, base)
    for dev in w.devices.values():
        subject, home = f"part://{dev.part}", rows.part_home(dev.part)
        if not dev.declared and dev.role != "passthrough":
            rows.add(
                "terminals-unsourced",
                dev.id,
                subject,
                "warn",
                f"The {dev.words}'s terminals are not listed yet, so nothing wired to it is "
                "checked.",
                home=home,
            )
        if dev.safety == "interlock":
            _safety_row(rows, w, t, dev, base, "interlock-series", set(), subject, home)
        elif dev.safety == "limit":
            forced = stuck - {dev.id}
            _safety_row(rows, w, t, dev, base, "limit-independent", forced, subject, home)
        _contact_row(rows, w, t, dev, subject, home)


def _controller_side(w: Wiring, t: nets.Topology, base: nets.Live) -> set[str]:
    """The controller and the switching devices it drives: what a limit must not rely on.

    A controller is a control device with a contact, no safety job and no contact in a power
    circuit (it drives coils, it carries no load), whose opening takes power from a coil.
    Its side is the controllers and every coil-driven device that loses power when they all
    open (S-158).
    """
    in_power = {
        n for c in w.circuits.values() if c.purpose == "power" for x in c.wires for n in (x.a, x.b)
    }
    candidates = {
        d.id
        for d in w.devices.values()
        if d.role == "control"
        and d.safety is None
        and d.id in t.contacts
        and not any(n in in_power for pair in t.contacts[d.id] for n in pair)
    }
    controllers = {d for d in candidates if base.coils - nets.live(t, opened={d}).coils}
    if not controllers:
        return set()
    return controllers | set(base.coils - nets.live(t, opened=controllers).coils)


def _safety_row(
    rows: _Rows,
    w: Wiring,
    t: nets.Topology,
    dev: DeviceRec,
    base: nets.Live,
    rule_id: str,
    forced: set[str],
    subject: str,
    home: str | None,
) -> None:
    job = "interlock" if rule_id == "interlock-series" else "limit device"
    if dev.id not in t.contacts:
        rows.add(
            rule_id,
            dev.id,
            subject,
            "warn",
            f"Which of the {dev.words}'s terminals its contact joins is not given, so the "
            f"check cannot open the {job}.",
            home=home,
            fix=(
                "say in the device's file which terminals its contact joins; a licensed "
                "electrician decides"
            ),
        )
        return
    if not base.loads:
        rows.add(
            rule_id,
            dev.id,
            subject,
            "warn",
            f"No load gets power even with every contact closed, so the check cannot tell "
            f"whether opening the {dev.words} stops one.",
            home=home,
        )
        return
    state = nets.live(t, opened={dev.id}, forced=forced)
    still = sorted(base.loads & state.loads)
    stopped = sorted(base.loads - state.loads)
    loads = _list([_load_in(w, d) for d in still])
    if still:
        if rule_id == "limit-independent" and forced:
            held = _list([f"the {w.devices[d].words}" for d in sorted(forced)])
            finding = (
                f"With {held} stuck on (the controller's side), opening the {dev.words} "
                f"leaves {loads} with power: it switches the same device the controller does."
            )
        else:
            verb = "gets" if len(still) == 1 else "get"
            finding = f"With the {dev.words} open, {loads} still {verb} power."
        rows.add(rule_id, dev.id, subject, "warn", finding, home=home)
        return
    rows.add(
        rule_id,
        dev.id,
        subject,
        "pass",
        f"Opening the {dev.words} stops {_list([f'the {w.devices[d].words}' for d in stopped])}"
        + (" even with the controller's side stuck on." if forced else "."),
        home=home,
    )


def _load_in(w: Wiring, did: str) -> str:
    """``the Heater (the Heater circuit)``: a load and the power circuit that feeds it."""
    feeding = [
        c.words
        for c in w.circuits.values()
        if c.purpose == "power" and any(d.id == did for d in w.circuit_devices(c.id))
    ]
    words = f"the {w.devices[did].words}"
    return f"{words} ({_list(feeding)})" if feeding else words


def _categories(rule_id: str, name: str) -> set[str]:
    return {c.strip() for c in str(rule(rule_id).param(name)).split(",")}


def _contact_row(
    rows: _Rows, w: Wiring, t: nets.Topology, dev: DeviceRec, subject: str, home: str | None
) -> None:
    if dev.id not in t.contacts:
        return
    coils = [
        e
        for e in w.devices.values()
        if e.id != dev.id
        and e.coil
        and nets.wired_to(t, dev.id, [f"device://{e.id}#{c}" for c in e.coil])
    ]
    inductive = [
        e
        for e in w.devices.values()
        if e.id != dev.id
        and e.inductive
        and nets.wired_to(
            t,
            dev.id,
            [f"device://{e.id}#{x}" for x in e.terminals if x not in EARTH_TERMINALS],
        )
    ]
    if not coils and not inductive:
        return
    need: set[str] = set()
    if coils:
        need = _categories("contact-category", "coil")
    if inductive:
        ind = _categories("contact-category", "inductive")
        need = need & ind if need else ind
    what = _list(
        [f"the coil of the {e.words}" for e in coils] + [f"the {e.words}" for e in inductive]
    )
    wanted = " or ".join(sorted(need))
    if dev.category in need:
        rows.add(
            "contact-category",
            dev.id,
            subject,
            "pass",
            f"The {dev.words}'s contact switches {what}; it is rated {dev.category}.",
            home=home,
        )
        return
    rated = f"is rated {dev.category}" if dev.category else "has no category given"
    rows.add(
        "contact-category",
        dev.id,
        subject,
        "warn",
        f"The {dev.words}'s contact switches {what} and {rated}; such a contact needs {wanted}.",
        home=home,
    )
