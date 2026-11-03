"""The wiring's topology (E3, E6): nets derived from the connections, earth, and who is live.

A node is a terminal, written as its connection end (``device://<id>#<terminal>``,
``supply://supply#L``, ``asm://<module>#<terminal>``).  Edges:

* every connection (a conductor);
* the terminals of a device whose role is ``earth`` (a stud or a bar: one piece of metal)
  and the ``through`` pairs of a ``passthrough`` device (a terminal block), always joined;
* the ``through`` pairs of every other device: a contact, closed unless the walk opens it.
  A device with a ``coil`` closes its contacts only while its coil has power.

Sources are the supply's terminals and the terminals of a module supplied from elsewhere
(``asm://``), the protective earth left out.  A device has power when two of its terminals
reach two different sources (line and neutral, two lines, plus and minus).  The walk does
not model a device that makes power of its own (a transformer, a power supply): its
outputs are not sources, so what hangs on them reads as having no power [revisit].

:func:`live` answers "with these contacts opened (and these forced closed), which loads and
which coils have power?", iterating to a fixed point (opening a contact can only take power
away).  The interlock and limit checks are built on it (S-158).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from napkin2factory.domains.electrical.checks.calcs import EARTH_TERMINALS, Wiring


def _terminal(node: str) -> str:
    return node.rsplit("#", 1)[-1]


class _Union:
    """Union-find over node keys."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def join(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


@dataclass
class Topology:
    """The nets of one product's wiring and what the walks need."""

    wires: list[tuple[str, str]] = field(default_factory=list)
    joins: list[tuple[str, str]] = field(default_factory=list)
    contacts: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    coils: dict[str, tuple[str, ...]] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    earth: set[str] = field(default_factory=set)
    loads: dict[str, list[str]] = field(default_factory=dict)

    def components(self, closed: set[str]) -> _Union:
        """The nets with the contacts of ``closed`` devices closed."""
        u = _Union()
        for a, b in self.wires + self.joins:
            u.join(a, b)
        for did in closed:
            for a, b in self.contacts.get(did, []):
                u.join(a, b)
        return u

    def wire_net(self, a: str, b: str) -> bool:
        """True when two terminals are joined by conductors alone (no contact between)."""
        u = self.components(set())
        return u.find(a) == u.find(b)


def topology(w: Wiring) -> Topology:
    """The nets of the product's wiring: every circuit's connections together."""
    t = Topology()
    for c in w.circuits.values():
        for wire in c.wires:
            t.wires.append((wire.a, wire.b))
    for dev in w.devices.values():
        nodes = [f"device://{dev.id}#{term}" for term in dev.terminals]
        if dev.role == "earth":
            t.joins += list(zip(nodes, nodes[1:], strict=False))
        elif dev.role == "passthrough":
            t.joins += [
                (f"device://{dev.id}#{a}", f"device://{dev.id}#{b}") for a, b in dev.through
            ]
        elif dev.through:
            t.contacts[dev.id] = [
                (f"device://{dev.id}#{a}", f"device://{dev.id}#{b}") for a, b in dev.through
            ]
        if dev.coil and dev.through and dev.role not in ("earth", "passthrough"):
            t.coils[dev.id] = tuple(f"device://{dev.id}#{c}" for c in dev.coil)
    roots: set[str] = set()
    if w.supply is not None:
        for term in w.supply.terminals:
            node = f"supply://supply#{term}"
            if term in EARTH_TERMINALS:
                roots.add(node)
            else:
                t.sources[node] = node
    for a, b in t.wires:
        for node in (a, b):
            if node.startswith("asm://"):
                if _terminal(node) in EARTH_TERMINALS:
                    roots.add(node)
                else:
                    t.sources[node] = node
    for dev in w.devices.values():
        if dev.role == "supply":
            roots |= {f"device://{dev.id}#{e}" for e in EARTH_TERMINALS if e in dev.terminals}
    u = t.components(set())
    earth_roots = {u.find(r) for r in roots}
    nodes = {n for pair in t.wires + t.joins for n in pair} | roots
    t.earth = {n for n in nodes if u.find(n) in earth_roots}
    for src in [s for s in t.sources if s in t.earth]:
        del t.sources[src]  # a terminal joined to earth is no source of power
    for c in w.circuits.values():
        if c.purpose != "power":
            continue
        for dev in w.circuit_devices(c.id):
            if dev.role == "load":
                t.loads[dev.id] = [
                    f"device://{dev.id}#{term}"
                    for term in dev.terminals
                    if f"device://{dev.id}#{term}" not in t.earth and term not in EARTH_TERMINALS
                ]
    return t


@dataclass(frozen=True)
class Live:
    """What has power in one state of the contacts: loads, coils, closed contacts."""

    loads: frozenset[str]
    coils: frozenset[str]
    closed: frozenset[str]


def _powered(u: _Union, sources: dict[str, str], nodes: list[str] | tuple[str, ...]) -> bool:
    reach = {n: {sources[s] for s in sources if u.find(s) == u.find(n)} for n in nodes}
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            if any(x != y for x in reach[a] for y in reach[b]):
                return True
    return False


def live(
    t: Topology,
    opened: set[str] | frozenset[str] = frozenset(),
    forced: set[str] | frozenset[str] = frozenset(),
) -> Live:
    """Loads and coils with power when ``opened`` devices' contacts are open.

    ``forced`` devices' contacts stay closed whatever their coil (a welded contact, a
    controller stuck on).  Every other contact is closed, a coil-driven one only while its
    coil has power: start with all closed and open the coil-driven ones whose coil has no
    power until nothing changes.
    """
    closed = {d for d in t.contacts if d not in opened} | (set(forced) & set(t.contacts))
    while True:
        u = t.components(closed)
        coils = {d for d, nodes in t.coils.items() if _powered(u, t.sources, nodes)}
        keep = {d for d in closed if d not in t.coils or d in forced or d in coils}
        if keep == closed:
            break
        closed = keep
    loads = {d for d, nodes in t.loads.items() if _powered(u, t.sources, nodes)}
    return Live(frozenset(loads), frozenset(coils), frozenset(closed))


def switched_coils(t: Topology, dev_id: str) -> set[str]:
    """Coil-driven devices a device's contact drives, directly and in turn.

    Directly: a coil wired straight to the contact (no other contact between).
    """
    u = t.components(set())
    out: set[str] = set()
    frontier = [dev_id]
    while frontier:
        d = frontier.pop()
        ends = {u.find(n) for pair in t.contacts.get(d, []) for n in pair}
        for other, coil in t.coils.items():
            if other in out or other == d:
                continue
            if any(u.find(c) in ends for c in coil):
                out.add(other)
                frontier.append(other)
    return out


def wired_to(t: Topology, dev_id: str, nodes: tuple[str, ...] | list[str]) -> bool:
    """True when a device's contact is wired straight to one of ``nodes`` (no contact between)."""
    u = t.components(set())
    ends = {u.find(n) for pair in t.contacts.get(dev_id, []) for n in pair}
    return any(u.find(n) in ends for n in nodes)


def line_side(t: Topology, dev_id: str) -> set[str]:
    """The nodes on the supply side of a device's contacts (a fuse's, a breaker's).

    With the device open and every other contact closed, the side of each of its contacts
    whose net reaches a source feeds it; the nodes of those nets are its line side.  A
    contact with both sides or neither reaching a source says nothing (the walk cannot
    tell which side feeds it), so an empty set means "every conductor is downstream".
    """
    pairs = t.contacts.get(dev_id, [])
    if not pairs:
        return set()
    u = t.components({d for d in t.contacts if d != dev_id})
    fed = {u.find(s) for s in t.sources}
    roots = set()
    for a, b in pairs:
        ra, rb = u.find(a), u.find(b)
        if (ra in fed) != (rb in fed):
            roots.add(ra if ra in fed else rb)
    return {n for n in _nodes(t) if u.find(n) in roots}


def fed_unprotected(t: Topology, protective: set[str]) -> set[str]:
    """The nodes that reach a source with every ``protective`` device open.

    What only the supply's own protective device stands between and the supply; with none
    open, every node the supply can reach at all.
    """
    u = t.components({d for d in t.contacts if d not in protective})
    fed = {u.find(s) for s in t.sources}
    return {n for n in _nodes(t) if u.find(n) in fed}


def _nodes(t: Topology) -> set[str]:
    return (
        {n for pair in t.wires + t.joins for n in pair}
        | {n for pairs in t.contacts.values() for pair in pairs for n in pair}
        | set(t.sources)
    )


# ---- earth -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EarthPath:
    """How one part reaches earth: ``wired``, ``bonded`` or ``none``.

    ``wired``: an earth conductor reaches a device naming it; ``bonded``: only through
    joints, a claim a person verifies.
    """

    part: str
    how: str
    circuits: tuple[str, ...]
    joints: tuple[str, ...] = ()
    via_part: str | None = None


def earth_paths(w: Wiring, t: Topology) -> dict[str, EarthPath]:
    """How every part with a device or an earth entry reaches earth, by part id."""
    by_part: dict[str, set[str]] = {}
    for c in w.circuits.values():
        for wire in c.wires:
            for node in (wire.a, wire.b):
                dev = w.device_of(node)
                if dev is not None and node in t.earth:
                    by_part.setdefault(dev.part, set()).add(c.id)
    out: dict[str, EarthPath] = {
        pid: EarthPath(pid, "wired", tuple(sorted(cids))) for pid, cids in by_part.items()
    }
    claims = [(c.id, pid, joints) for c in w.circuits.values() for pid, joints in c.earth]
    changed = True
    while changed:
        changed = False
        for cid, pid, joints in claims:
            if pid in out:
                continue
            for jid in joints:
                parties = w.joints.get(jid, ("", ()))[1]
                other = next((q for q in parties if q != pid and q in out), None)
                if other is not None:
                    out[pid] = EarthPath(pid, "bonded", (cid,), tuple(joints), other)
                    changed = True
                    break
    for cid, pid, joints in claims:
        out.setdefault(pid, EarthPath(pid, "none", (cid,), tuple(joints)))
    return out


def circuit_earth_count(w: Wiring, t: Topology, cid: str) -> int:
    """How many parts a circuit earths: by its own earth conductors, or by its earth entries."""
    paths = earth_paths(w, t)
    return sum(1 for p in paths.values() if p.how != "none" and cid in p.circuits)
