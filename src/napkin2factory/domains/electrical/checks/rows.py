"""Row accumulator, earth, entry and device checks; split from stage.py (S-184)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from napkin2factory.core.units import magnitude_in
from napkin2factory.domains.electrical.checks import nets
from napkin2factory.domains.electrical.checks.calcs import (
    EARTH_TERMINALS,
    DeviceRec,
    Wiring,
    circuit_voltage,
    on_supply,
)
from napkin2factory.domains.electrical.checks.pack import rule

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


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


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


# ---- earth -------------------------------------------------------------------------------------


def _carries_mains(w: Wiring, t: nets.Topology, cid: str) -> bool:
    """True when a circuit has a conductor (not an earth one) above extra-low voltage.

    A circuit whose voltage is not known counts as mains (the safe error).
    """
    if all(x.a in t.earth or x.b in t.earth for x in w.circuits[cid].wires):
        return False
    return _band(w, cid) != "elv"


def _class_two_row(
    rows: _Rows, w: Wiring, t: nets.Topology, pid: str, material: str, mains: list[str]
) -> None:
    """Gate G blocker 2 (S-178): Class II devices in a part that conducts.

    The product's own conductors are single-insulated wherever nothing says otherwise, so
    every device being Class II does not make the product so; a person judges it (E6: warn).
    """
    name = w.parts.get(pid, pid)
    through: dict[str, set[str]] = {}
    for cid in mains:
        for x in w.circuits[cid].wires:
            if x.via is None or x.a in t.earth or x.b in t.earth:
                continue
            if pid in w.joints.get(x.via, ("", ()))[1]:
                through.setdefault(x.via, set()).add(cid)
    if through:
        where = _list(
            [
                f"{_list([w.circuits[c].words for c in sorted(cids)])} at the cable entry "
                f"“{w.entries.get(jid, jid)}”"
                for jid, cids in sorted(through.items())
            ]
        )
        runs = f"the product's own mains conductors pass through it ({where})"
    else:
        circuits_said = _list([w.circuits[c].words for c in mains])
        runs = (
            "nothing in the wiring says that the product's own mains conductors "
            f"({circuits_said}) stay out of it"
        )
    rows.add(
        "earth-path",
        pid,
        f"part://{pid}",
        "warn",
        f"Every device is Class II or III, but the {name} is {material}, which conducts, "
        f"and {runs}: whether the product as a whole is Class II is a licensed "
        "electrician's call.",
        home=rows.part_home(pid),
        fix=(
            "have the product's own wiring confirmed double-insulated wherever it runs in "
            "the part, or run an earth conductor to it (an earth stud on the part); a "
            "licensed electrician decides"
        ),
    )


def _earth_rows(rows: _Rows, w: Wiring, t: nets.Topology) -> None:
    devs = list(w.devices.values())
    class_two = bool(devs) and all(d.klass in ("II", "III") for d in devs)
    mains_ids = [c for c in w.circuits if _carries_mains(w, t, c)]
    maybe = [pid for pid, (conductive, _) in w.conductive.items() if conductive is not False]
    if class_two and not (mains_ids and maybe):
        why = (
            "every circuit runs at extra-low voltage"
            if not mains_ids
            else "no part made here conducts"
        )
        rows.add(
            "earth-path",
            "product",
            "supply://supply",
            "pass",
            "Every device is Class II or III (double-insulated, or extra-low voltage), and "
            f"{why}, so no part needs a path to earth.",
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
        if conductive and class_two:
            _class_two_row(rows, w, t, pid, material, mains_ids)
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
