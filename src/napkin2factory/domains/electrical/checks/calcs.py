"""The wiring's figures (E6, E11, DoD 8): the model read once, every number from the calc kit.

:func:`read_wiring` reads what the checks need into plain records (:class:`Wiring`),
through a reader: the check stage passes ``sctx.proxy`` and ``sctx.log``, so each field
used is a recorded read of the ``checks`` rule (D5); the ``circuit`` verify kind passes
none (its evidence keys stand for what it read).  Everything after that computes on the
records, unit-safe (``core.units``):

* a load device's current: its rated current, else its rated power over its rated voltage
  (or the circuit's), by the calc kit's ``power.element_current`` (DoD 8);
* a circuit's load current: the sum of its load devices' currents (``None`` when one is
  not known, or the circuit reaches no load: a control or sensing conductor's current is
  "not known" unless a device declares it, and an unknown never fails a check);
* the supply's rating: given (a quantity or a ``param://``), else the site's protective
  device's, else the rated current of the protective device the product ships;
* the supply margin: the rating minus the power circuits' load on it;
* a conductor's rated current: the calc kit's ``conductors.yaml`` or the product's row;
* earth paths: :mod:`napkin2factory.domains.electrical.checks.nets` walks the nets.

A figure carries its words ("computed from 500 W at 230 V", "given") so the row can say
where a number comes from (N5).
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from napkin2factory.calckit import power, wiring
from napkin2factory.core.units import Quantity, UnitError, magnitude_in
from napkin2factory.core.uris import Uri
from napkin2factory.domains.electrical.model import (
    circuits,
    devices,
    parse_end,
    product_conductors,
    supply,
)

#: A reader: ``read(obj, uri)`` returns the object, or a proxy recording each field used.
Reader = Callable[[Any, str], Any]
#: A quantity from the shared registry (pint is untyped).
Qty = Any

#: The table of which materials conduct, for the earth-path check (S-158).
CONDUCTION_TABLE = Path(__file__).with_name("conduction.yaml")
#: Terminal names that carry the protective earth.
EARTH_TERMINALS = ("PE",)


class _NoLog:
    """A read log that keeps nothing (the verify kind's reads are its evidence keys)."""

    def add(self, key: str) -> None:
        """Ignore ``key``."""


def _plain(obj: Any, uri: str) -> Any:
    return obj


# ---- the records ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Figure:
    """A number and where it comes from: ``words`` ("given", "computed from 500 W at 230 V")."""

    value: Qty
    words: str

    def amps(self) -> float:
        """The figure in amperes."""
        return magnitude_in(self.value, "A")


@dataclass(frozen=True)
class DeviceRec:
    """A device as the checks read it (S-154: devices address instances)."""

    id: str
    part: str
    words: str
    role: str
    terminals: tuple[str, ...]
    voltage: Qty | None
    current: Qty | None
    power: Qty | None
    category: str | None
    coil: tuple[str, ...]
    inductive: bool
    safety: str | None
    through: tuple[tuple[str, str], ...]
    klass: str | None
    declared: bool = True


@dataclass(frozen=True)
class WireRec:
    """One connection of a circuit, its ends as node keys (``device://<id>#<terminal>``)."""

    circuit: str
    n: int
    a: str
    b: str
    a_words: str
    b_words: str
    conductor: str | None
    via: str | None

    @property
    def words(self) -> str:
        """``connection 3 (Switch terminal 2 to Heater terminal L)``."""
        return f"connection {self.n} ({self.a_words} to {self.b_words})"


@dataclass(frozen=True)
class CircuitRec:
    """A circuit as the checks read it."""

    id: str
    words: str
    purpose: str
    protection: str | None
    voltage: Qty | None
    dc: bool
    wires: tuple[WireRec, ...]
    earth: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True)
class SupplyRec:
    """The supply as the checks read it."""

    voltage: Qty | None
    dc: bool
    rating: Figure | None
    upstream: str | None
    protection: str | None
    region: str | None
    terminals: tuple[str, ...]
    rating_param: str | None = None


@dataclass(frozen=True)
class ConductorRec:
    """A conductor row: the calc kit's or the product's."""

    id: str
    label: str
    ampacity: Qty | None
    source: str
    own: bool = False

    @property
    def basis(self) -> str:
        """Where its rated current comes from, in owner words (N5)."""
        return "given" if self.own else "from the table"


@dataclass
class Wiring:
    """Everything the wiring checks read, as plain records."""

    supply: SupplyRec | None
    devices: dict[str, DeviceRec]
    circuits: dict[str, CircuitRec]
    parts: dict[str, str] = field(default_factory=dict)
    conductive: dict[str, tuple[bool | None, str]] = field(default_factory=dict)
    joints: dict[str, tuple[str, tuple[str, ...]]] = field(default_factory=dict)
    entries: dict[str, str] = field(default_factory=dict)
    conductors: dict[str, ConductorRec] = field(default_factory=dict)
    homes: dict[str, str | None] = field(default_factory=dict)

    def device_of(self, node: str) -> DeviceRec | None:
        """The device a node key (``device://<id>#<terminal>``) belongs to."""
        if not node.startswith("device://"):
            return None
        return self.devices.get(node.removeprefix("device://").split("#", 1)[0])

    def circuit_devices(self, cid: str) -> list[DeviceRec]:
        """The devices a circuit's connections reach, in first-reached order."""
        out: dict[str, DeviceRec] = {}
        for w in self.circuits[cid].wires:
            for node in (w.a, w.b):
                dev = self.device_of(node)
                if dev is not None:
                    out.setdefault(dev.id, dev)
        return list(out.values())


# ---- reading the model -----------------------------------------------------------------------


def _quantity(product: Any, value: Any, unit: str, log: Any, field: str = "") -> Qty | None:
    """A quantity field's value in ``unit``'s dimension, else ``None``.

    A ``param://`` is resolved and logged as a read.
    """
    if value is None:
        return None
    param_id: str | None = None
    if isinstance(value, Uri):
        param_id = value.id
        log.add(f"param://{value.id}")
        try:
            value = product.parameter_value(value.id)
        except KeyError:
            return None
        except ValueError as exc:
            if isinstance(exc, UnitError):
                field_part = f" for {field}" if field else ""
                raise ValueError(
                    f"parameter {param_id} has wrong dimension{field_part}: {exc}"
                ) from exc
            return None
    if value is None:
        return None
    try:
        magnitude_in(value, unit)
    except UnitError as exc:
        if param_id is not None:
            field_part = f" for {field}" if field else ""
            raise ValueError(
                f"parameter {param_id} has wrong dimension{field_part}: {exc}"
            ) from exc
        return None
    except (AttributeError, TypeError, ValueError):
        return None
    return value


def _part_name(read: Reader, product: Any, pid: str) -> str:
    part = product.parts.get(pid)
    if part is None:
        return pid
    name = read(part, f"part://{pid}").name
    return str(name) if name else pid


def read_wiring(product: Any, read: Reader | None = None, log: Any = None) -> Wiring:
    """Read the product's wiring model into :class:`Wiring` (each field through ``read``)."""
    read = read or _plain
    log = log if log is not None else _NoLog()
    part_names: dict[str, str] = {}

    def pname(pid: str) -> str:
        if pid not in part_names:
            part_names[pid] = _part_name(read, product, pid)
        return part_names[pid]

    devs: dict[str, DeviceRec] = {}
    for did, raw in sorted(devices(product).items()):
        d = read(raw, f"device://{did}")
        pid = d.part.id
        instance = d.instance
        words = f"{pname(pid)} ({instance})" if instance else pname(pid)
        rating = d.rating
        volts = amps = watts = None
        if rating is not None:
            volts = _quantity(product, rating.voltage, "V", log, "voltage")
            amps = _quantity(product, rating.current, "A", log, "current")
            watts = _quantity(product, rating.power, "W", log, "power")
        contact = d.contact
        devs[did] = DeviceRec(
            id=did,
            part=pid,
            words=words,
            role=str(d.role),
            terminals=tuple(d.terminals),
            voltage=volts,
            current=amps,
            power=watts,
            category=contact.category if contact is not None else None,
            coil=tuple(d.coil),
            inductive=bool(d.inductive),
            safety=d.safety,
            through=tuple((str(p[0]), str(p[1])) for p in d.through),
            klass=d.class_,
            declared=bool(d.terminals),
        )
    by_part: dict[str, list[str]] = {}
    for dev in devs.values():
        by_part.setdefault(dev.part, []).append(dev.id)

    sup_raw = supply(product)
    sup: SupplyRec | None = None
    if sup_raw is not None:
        s = read(sup_raw, "supply://supply")
        volts = _quantity(product, s.voltage, "V", log, "voltage")
        rating_q = _quantity(product, s.rating, "A", log, "rating")
        prot = s.protection
        upstream: str | None = None
        prot_ref: str | None = None
        rating: Figure | None = Figure(rating_q, "given") if rating_q is not None else None
        if isinstance(prot, Uri):
            prot_ref = f"{prot.scheme}://{prot.id}"
        elif prot is not None:
            upstream = str(prot.upstream)
            up_q = _quantity(product, prot.rating, "A", log, "rating")
            if rating is None and up_q is not None:
                rating = Figure(up_q, f"the rating of {upstream}")
        rating_ref = s.rating
        sup = SupplyRec(
            voltage=volts,
            dc=bool(s.dc),
            rating=rating,
            upstream=upstream,
            protection=prot_ref,
            region=s.region,
            terminals=tuple(s.terminal_names()),
            rating_param=rating_ref.id if isinstance(rating_ref, Uri) else None,
        )
        if sup.rating is None and prot_ref is not None:
            pdev = _protective_device(devs, by_part, prot_ref)
            if pdev is not None and pdev.current is not None:
                rated = Figure(pdev.current, f"the rating of the {pdev.words}")
                sup = dataclasses.replace(sup, rating=rated)

    asm_names: dict[str, str] = {}

    def node(text: str) -> tuple[str, str]:
        end = parse_end(text)
        if end.scheme == "part":
            named = by_part.get(end.id, [])
            if len(named) == 1:
                end = parse_end(f"device://{named[0]}#{end.terminal}")
        key = str(end)
        if end.scheme == "device":
            dev = devs.get(end.id)
            return key, f"{dev.words if dev else end.id} terminal {end.terminal}"
        if end.scheme == "supply":
            return key, f"the supply's {end.terminal}"
        if end.scheme == "asm":
            if end.id not in asm_names:
                asm = product.assemblies.get(end.id)
                asm_names[end.id] = (
                    str(read(asm, f"asm://{end.id}").name or end.id) if asm else end.id
                )
            return key, f"the {asm_names[end.id]}'s {end.terminal}"
        return key, f"{pname(end.id)} terminal {end.terminal}"

    circs: dict[str, CircuitRec] = {}
    entries: dict[str, str] = {}
    joints: dict[str, tuple[str, tuple[str, ...]]] = {}

    def joint(jid: str) -> None:
        iface = product.interfaces.get(jid)
        if iface is None or jid in joints:
            return
        i = read(iface, f"iface://{jid}")
        parties = tuple(str(p.id) for p in i.parties if getattr(p, "scheme", "part") == "part")
        names = " to ".join(pname(p) for p in parties)
        joints[jid] = (str(i.name or names or jid), parties)

    for cid, raw in sorted(circuits(product).items()):
        c = read(raw, f"circuit://{cid}")
        name = c.name
        words = f"the {name} circuit" if name else f"the {cid} circuit"
        own_v = _quantity(product, c.voltage, "V", log, "voltage")
        prot = c.protection
        prot_ref = None if prot is None else ("supply" if prot == "supply" else str(prot))
        wires = []
        for n, conn in enumerate(c.connections, start=1):
            a, a_words = node(conn.from_)
            b, b_words = node(conn.to)
            via = conn.via.id if conn.via is not None else None
            if via is not None and via not in entries:
                joint(via)
                entries[via] = joints[via][0] if via in joints else via
            wires.append(WireRec(cid, n, a, b, a_words, b_words, conn.conductor, via))
        earth = []
        for path in c.earth:
            for jid in path.bonded_via:
                joint(jid.id)
            earth.append((path.part.id, tuple(j.id for j in path.bonded_via)))
        circs[cid] = CircuitRec(
            id=cid,
            words=words,
            purpose=str(c.purpose),
            protection=prot_ref,
            voltage=own_v,
            dc=bool(c.dc),
            wires=tuple(wires),
            earth=tuple(earth),
        )

    out = Wiring(sup, devs, circs, entries=entries, joints=joints)
    out.conductors = _conductors(product, read, log, circs)
    out.conductive = _custom_parts(product, read)
    for pid in out.conductive:
        pname(pid)
    for dev in devs.values():
        pname(dev.part)
    out.parts = part_names
    return out


def _protective_device(
    devs: dict[str, DeviceRec], by_part: dict[str, list[str]], ref: str
) -> DeviceRec | None:
    scheme, _, ident = ref.partition("://")
    if scheme == "device":
        return devs.get(ident)
    named = by_part.get(ident, [])
    return devs.get(named[0]) if len(named) == 1 else None


def _conductors(
    product: Any, read: Reader, log: Any, circs: dict[str, CircuitRec]
) -> dict[str, ConductorRec]:
    used = {w.conductor for c in circs.values() for w in c.wires if w.conductor}
    own = product_conductors(product)
    out: dict[str, ConductorRec] = {}
    for cid in sorted(used):
        if cid in own:
            r = read(own[cid], f"conductor://{cid}")
            amp = _quantity(product, r.ampacity, "A", log, "ampacity")
            out[cid] = ConductorRec(cid, str(r.label), amp, str(r.source), own=True)
            continue
        try:
            row = wiring.conductor(cid)
        except ValueError:
            continue  # validation names it; nothing to check against
        out[cid] = ConductorRec(cid, row.label, row.ampacity, row.source)
    return out


# ---- which parts conduct ---------------------------------------------------------------------


@lru_cache(maxsize=1)
def conduction_rows() -> tuple[tuple[str, frozenset[str], str], ...]:
    """``(class, keywords, source)`` rows of ``conduction.yaml``, conductive first."""
    from napkin2factory.core.yamlio import read_yaml

    data = read_yaml(CONDUCTION_TABLE)
    rows = [
        (str(r["class"]), frozenset(str(k).lower() for k in r["keywords"]), str(r["source"]))
        for r in data["rows"]
    ]
    return tuple(sorted(rows, key=lambda r: r[0] != "conductive"))


def conducts(material: str) -> bool | None:
    """True when a material's words name a conductor, False an insulator, None unknown.

    Whole words of the name and spec (``polycarbonate`` is not ``carbon``); a conductive
    word wins over an insulating one (earthing a part that need not be is the safe error).
    """
    words = set(re.findall(r"[a-z0-9]+", material.lower()))
    for klass, keywords, _ in conduction_rows():
        if words & keywords:
            return klass == "conductive"
    return None


def _custom_parts(product: Any, read: Reader) -> dict[str, tuple[bool | None, str]]:
    """Each part made here: does its material conduct (None: unknown), and the material."""
    out: dict[str, tuple[bool | None, str]] = {}
    for pid, raw in sorted(product.parts.items()):
        p = read(raw, f"part://{pid}")
        if p.kind != "custom":
            continue
        mat = p.material
        if mat is None:
            out[pid] = (None, "")
            continue
        text = " ".join(t for t in (mat.name, mat.spec) if t)
        out[pid] = (conducts(text), str(mat.name))
    return out


# ---- currents and margins --------------------------------------------------------------------


def _amps(q: Qty) -> str:
    return f"{magnitude_in(q, 'A'):.1f} A"


def _fmt(q: Qty, unit: str) -> str:
    return f"{magnitude_in(q, unit):g} {unit}"


def circuit_voltage(w: Wiring, cid: str) -> tuple[Qty | None, bool]:
    """A circuit's working voltage and whether it is DC: its own, else the supply's."""
    c = w.circuits[cid]
    if c.voltage is not None:
        return c.voltage, c.dc
    if w.supply is None:
        return None, False
    return w.supply.voltage, w.supply.dc


def device_current(dev: DeviceRec, volts: Qty | None) -> Figure | None:
    """A load device's current: its rated current, else ``P / V`` (``power.element_current``).

    The voltage is the device's rated voltage, else the circuit's (the rated current at the
    rated power, as a rating plate prints it).
    """
    if dev.current is not None:
        return Figure(dev.current, "given")
    if dev.power is None:
        return None
    v = dev.voltage if dev.voltage is not None else volts
    if v is None or magnitude_in(v, "V") <= 0:
        return None
    current = power.element_current(dev.power, v)
    return Figure(current, f"computed from {_fmt(dev.power, 'W')} at {_fmt(v, 'V')}")


@dataclass(frozen=True)
class Load:
    """A circuit's load: the total (``None`` when unknown), each load's figure, the unknown."""

    total: Figure | None
    parts: tuple[tuple[DeviceRec, Figure], ...]
    unknown: tuple[DeviceRec, ...]


def circuit_load(w: Wiring, cid: str) -> Load:
    """The current a circuit's load devices draw, summed (``None`` if one is not known)."""
    volts, _ = circuit_voltage(w, cid)
    known: list[tuple[DeviceRec, Figure]] = []
    unknown: list[DeviceRec] = []
    for dev in w.circuit_devices(cid):
        if dev.role != "load":
            continue
        fig = device_current(dev, volts)
        if fig is None:
            unknown.append(dev)
        else:
            known.append((dev, fig))
    if unknown or not known:
        return Load(None, tuple(known), tuple(unknown))
    total = sum((f.value for _, f in known), Quantity(0.0, "A"))
    words = known[0][1].words if len(known) == 1 else "the sum of its loads"
    return Load(Figure(total.to("A"), words), tuple(known), tuple(unknown))


def on_supply(w: Wiring, cid: str) -> bool:
    """True for a power circuit drawing from the supply at the supply's own voltage."""
    c = w.circuits[cid]
    if c.purpose != "power" or w.supply is None:
        return False
    if c.voltage is None or w.supply.voltage is None:
        return True
    return bool(
        c.dc == w.supply.dc
        and abs(magnitude_in(c.voltage, "V") - magnitude_in(w.supply.voltage, "V")) < 1e-6
    )


@dataclass(frozen=True)
class SupplyLoad:
    """The power circuits' load on the supply: total, by load, the unknown, the circuits."""

    total: Qty
    loads: tuple[tuple[DeviceRec, Figure], ...]
    unknown: tuple[DeviceRec, ...]
    circuits: tuple[str, ...]


def supply_load(w: Wiring) -> SupplyLoad:
    """The current the power circuits on the supply draw (each load device counted once)."""
    seen: dict[str, tuple[DeviceRec, Figure]] = {}
    unknown: dict[str, DeviceRec] = {}
    cids = tuple(cid for cid in w.circuits if on_supply(w, cid))
    for cid in cids:
        load = circuit_load(w, cid)
        for dev, fig in load.parts:
            seen.setdefault(dev.id, (dev, fig))
        for dev in load.unknown:
            unknown.setdefault(dev.id, dev)
    total = sum((f.value for _, f in seen.values()), Quantity(0.0, "A"))
    return SupplyLoad(total.to("A"), tuple(seen.values()), tuple(unknown.values()), cids)


def supply_margin(w: Wiring) -> Figure | None:
    """The supply's rating minus the power circuits' load (``None`` when either is unknown)."""
    if w.supply is None or w.supply.rating is None:
        return None
    load = supply_load(w)
    if load.unknown or not load.loads:
        return None
    margin = (w.supply.rating.value - load.total).to("A")
    return Figure(margin, f"{_amps(w.supply.rating.value)} rating less {_amps(load.total)} load")


def protective_device_id(w: Wiring, cid: str) -> str | None:
    """The id of the product's device protecting a circuit (``None``: the supply's, or none)."""
    ref = w.circuits[cid].protection
    if ref is None or ref == "supply":
        return None
    scheme, _, ident = ref.partition("://")
    if scheme == "device":
        return ident if ident in w.devices else None
    named = [d for d in w.devices.values() if d.part == ident]
    return named[0].id if len(named) == 1 else None


def protective_rating(w: Wiring, cid: str) -> Figure | None:
    """The rated current of the device protecting a circuit (the supply's for ``supply``)."""
    ref = w.circuits[cid].protection
    if ref is None:
        return None
    if ref == "supply":
        return w.supply.rating if w.supply is not None else None
    did = protective_device_id(w, cid)
    dev = w.devices.get(did) if did is not None else None
    if dev is None or dev.current is None:
        return None
    return Figure(dev.current, f"the rating of the {dev.words}")


def supply_protection(w: Wiring) -> tuple[Figure | None, str]:
    """The supply's own protective device: its rating (``None`` unknown) and its words."""
    if w.supply is None:
        return None, "the supply's own protective device"
    return w.supply.rating, w.supply.upstream or "the supply's own protective device"


def protective_words(w: Wiring, cid: str) -> str:
    """The device protecting a circuit, in owner words."""
    ref = w.circuits[cid].protection
    if ref == "supply":
        up = w.supply.upstream if w.supply is not None else None
        return up or "the supply's own protective device"
    if ref is None:
        return "nothing"
    scheme, _, ident = ref.partition("://")
    if scheme == "device" and ident in w.devices:
        return f"the {w.devices[ident].words}"
    return f"the {w.parts.get(ident, ident)}"


@dataclass(frozen=True)
class ConductorLoad:
    """One conductor of a circuit against its rated current."""

    wire: WireRec
    rated: Qty | None
    margin: Qty | None
    current: Qty | None = None


def conductor_loads(
    w: Wiring,
    cid: str,
    earth: set[str],
    t: Any = None,
) -> list[ConductorLoad]:
    """Each non-earth conductor of a circuit with its rated current and margin.

    The current in each conductor is derived from the loads downstream of it (S-214):
    walking the circuit's connections from each load terminal back toward the supply,
    a conductor feeding one device carries that device's current; a shared conductor
    carries the sum.  ``margin`` is ``None`` when the current or the rating is not known.
    Conductors on the earth net carry no load current and are left out.
    """
    c = w.circuits[cid]
    loads = [d for d in w.circuit_devices(cid) if d.role == "load"]
    if not loads:
        out: list[ConductorLoad] = []
        for wire in c.wires:
            if wire.a in earth or wire.b in earth:
                continue
            row = w.conductors.get(wire.conductor or "")
            rated = row.ampacity if row is not None else None
            out.append(ConductorLoad(wire, rated, None, None))
        return out

    volts, _ = circuit_voltage(w, cid)
    dev_currents: dict[str, Qty | None] = {}
    for d in loads:
        fig = device_current(d, volts)
        dev_currents[d.id] = fig.value if fig is not None else None

    load_terminals: dict[str, set[str]] = {}
    for d in loads:
        terms: set[str] = set()
        for term in d.terminals:
            node = f"device://{d.id}#{term}"
            if node not in earth and term not in EARTH_TERMINALS:
                terms.add(node)
        load_terminals[d.id] = terms

    if t is None:
        from napkin2factory.domains.electrical.checks.nets import topology

        t = topology(w)

    from napkin2factory.domains.electrical.checks.nets import _Union

    roots = set(t.sources.keys())
    u_ext = _Union()
    for c_other in w.circuits.values():
        if c_other.id == cid:
            continue
        for wire in c_other.wires:
            u_ext.join(wire.a, wire.b)
    for dev in w.devices.values():
        if dev.role == "earth":
            nodes = [f"device://{dev.id}#{term}" for term in dev.terminals]
            for a, b in zip(nodes, nodes[1:], strict=False):
                u_ext.join(a, b)
        elif dev.through:
            for a, b in dev.through:
                u_ext.join(f"device://{dev.id}#{a}", f"device://{dev.id}#{b}")

    source_components = {u_ext.find(r) for r in roots}
    source_nodes: set[str] = set()
    for wire in c.wires:
        for node in (wire.a, wire.b):
            term = node.rsplit("#", 1)[-1]
            if node in earth or term in EARTH_TERMINALS:
                continue
            if node in roots or u_ext.find(node) in source_components:
                source_nodes.add(node)
    all_load_terms = {node for terms in load_terminals.values() for node in terms}
    source_nodes -= all_load_terms

    adj: dict[str, list[tuple[str, WireRec | None]]] = {}
    for wire in c.wires:
        if wire.a in earth or wire.b in earth:
            continue
        adj.setdefault(wire.a, []).append((wire.b, wire))
        adj.setdefault(wire.b, []).append((wire.a, wire))

    for dev in w.circuit_devices(cid):
        if dev.role == "load":
            # Current does not pass through a load to feed other devices (S-214)
            continue
        if dev.through:
            for a_term, b_term in dev.through:
                na = f"device://{dev.id}#{a_term}"
                nb = f"device://{dev.id}#{b_term}"
                if na not in earth and nb not in earth:
                    adj.setdefault(na, []).append((nb, None))
                    adj.setdefault(nb, []).append((na, None))
        elif dev.role == "passthrough":
            nodes = [
                f"device://{dev.id}#{term}"
                for term in dev.terminals
                if f"device://{dev.id}#{term}" not in earth
            ]
            for i, na in enumerate(nodes):
                for nb in nodes[i + 1 :]:
                    adj.setdefault(na, []).append((nb, None))
                    adj.setdefault(nb, []).append((na, None))

    dev_wires: dict[str, set[int]] = {}
    for d in loads:
        fed_wires: set[int] = set()

        def _walk(current: str, visited: set[str], path: list[int]) -> None:
            if current in source_nodes:
                fed_wires.update(path)
                return
            for nxt, wire in adj.get(current, []):
                if nxt in visited:
                    continue
                nxt_path = path + [wire.n] if wire is not None else path
                visited.add(nxt)
                _walk(nxt, visited, nxt_path)
                visited.remove(nxt)

        for term_node in load_terminals.get(d.id, set()):
            _walk(term_node, {term_node}, [])

        dev_wires[d.id] = fed_wires

    any_traced = any(bool(s) for s in dev_wires.values())

    out: list[ConductorLoad] = []
    circuit_total_load = circuit_load(w, cid).total
    fallback_qty = circuit_total_load.value if circuit_total_load is not None else None

    for wire in c.wires:
        if wire.a in earth or wire.b in earth:
            continue
        row = w.conductors.get(wire.conductor or "")
        rated = row.ampacity if row is not None else None

        if not any_traced:
            carried = fallback_qty
        else:
            fed_devs = [d for d in loads if wire.n in dev_wires.get(d.id, set())]
            if not fed_devs:
                carried = Quantity(0.0, "A")
            elif any(dev_currents[d.id] is None for d in fed_devs):
                carried = None
            else:
                carried = sum(
                    (dev_currents[d.id] for d in fed_devs if dev_currents[d.id] is not None),
                    Quantity(0.0, "A"),
                ).to("A")

        margin = None
        if rated is not None and carried is not None:
            margin = (rated - carried).to("A")
        out.append(ConductorLoad(wire, rated, margin, carried))
    return out


def conductor_margin(
    w: Wiring,
    cid: str,
    earth: set[str],
    t: Any = None,
) -> Figure | None:
    """The smallest margin of a circuit's conductors (``None`` when one is not known)."""
    rows = conductor_loads(w, cid, earth, t)
    if not rows or any(r.margin is None for r in rows):
        return None
    worst = min(rows, key=lambda r: magnitude_in(r.margin, "A"))
    assert worst.margin is not None and worst.rated is not None
    label = w.conductors[worst.wire.conductor or ""].label
    return Figure(worst.margin, f"{label}, rated {_amps(worst.rated)}, at {worst.wire.words}")
