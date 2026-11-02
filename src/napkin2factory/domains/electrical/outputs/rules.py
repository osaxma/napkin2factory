"""The ``elec`` rules (ELECTRICAL_STAGE E5): one per circuit, then the schedule.

``elec:<circuit>`` reads its circuit, the supply, the devices its connections reach, their
parts' names, the cable entries it crosses and the conductor rows it names, all through the
recording accessor (``ctx.proxy``) or ``ctx.log.add`` (D5), and writes under
``build/electrical/<circuit>/``: ``connections.json`` (the circuit's record, the wave-2
contract), ``diagram.svg`` and ``<circuit>.kicad_sch`` (a text export, never source, E1).
Its output hash is ``sha256_json(record)``, so a read of ``circuit://<circuit>`` changes when
any connection, device, conductor, entry or word of the circuit does.

``elec-schedule`` runs after every circuit's rule and writes ``schedule.csv``,
``labels.csv`` and ``cables.csv`` from the circuits' records; it produces the key
``rule:elec-schedule``.  Its id is not ``elec:_schedule``: the core values a ``rule:<x>`` key
as the output hash of the rule whose id is ``<x>``, so the key the checks and the manuals
record is the rule's own id (S-156).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from napkin2factory.calckit import wiring
from napkin2factory.core.graph.hashing import sha256_file, sha256_json, sha256_text
from napkin2factory.core.units import magnitude_in
from napkin2factory.domains.electrical.model import (
    Circuit,
    Device,
    Supply,
    circuits,
    devices,
    parse_end,
    product_conductors,
    supply,
)
from napkin2factory.domains.electrical.outputs.diagram import circuit_svg
from napkin2factory.domains.electrical.outputs.export_kicad import kicad_schematic
from napkin2factory.domains.electrical.outputs.schedule import write_tables

if TYPE_CHECKING:  # an installed domain is imported while the core's schemas load (S-153)
    from napkin2factory.core.graph.rules import Rule, RuleBuild, RunContext, RunResult

#: The folder under ``build/`` (the family's ``output_dir``).
OUT = "electrical"
#: The aggregate rule: its id, and the key a reader records for its three tables (S-156).
SCHEDULE_RULE = "elec-schedule"
SCHEDULE_KEY = f"rule:{SCHEDULE_RULE}"
#: The calc-kit tables a record takes numbers from (cross-sections, labels, colours): an
#: input of every rule, so a corrected row reruns them (the domain's code hash does not
#: cover the calc kit).
_TABLES = ("conductors.yaml", "wire_colours.yaml")
#: What a value the model does not give reads as, in the files (never a guess).
NOT_GIVEN = "not given"


def _tables_hash() -> str:
    data = Path(wiring.__file__).resolve().parent / "data"
    return sha256_text("".join(sha256_file(data / name) for name in _TABLES))


def elec_rules(b: RuleBuild) -> list[Rule]:
    """One ``elec:<circuit>`` rule per circuit, then ``elec-schedule``; none without circuits.

    ``depends_on`` names the part rules of the parts the circuit's devices and entries name
    (those that have a shape, so a rule exists): the order is the family's (``after``), the
    list is for the build graph.
    """
    from napkin2factory.core.graph.rules import Rule

    product = b.product
    circs = circuits(product)
    if not circs:
        return []
    built = {r.id for r in b.rules}
    tables = _tables_hash()
    rules: list[Rule] = []
    for cid, circuit in sorted(circs.items()):
        deps = sorted(
            f"part:{pid}" for pid in _parts_of(product, circuit) if f"part:{pid}" in built
        )
        rules.append(
            Rule(
                id=f"elec:{cid}",
                kind="elec",
                produces=f"circuit://{cid}",
                inputs={"tables": tables},  # the core adds the family's code hash
                run=_make_circuit_run(cid),
                description=f"wiring diagram and connection record of circuit://{cid}",
                depends_on=deps,
            )
        )
    ids = sorted(circs)
    rules.append(
        Rule(
            id=SCHEDULE_RULE,
            kind="elec",
            produces=SCHEDULE_KEY,
            # which circuits there are: a circuit added or removed reruns the schedule, which
            # reads only the circuits it knew of last time (their records' hashes)
            inputs={"circuits": sha256_text(",".join(ids))},
            run=_run_schedule,
            description="cable schedule, terminal labels and the cable to buy, every circuit",
            depends_on=[f"elec:{cid}" for cid in ids],
        )
    )
    return rules


def _parts_of(product: Any, circuit: Circuit) -> set[str]:
    """The parts the circuit's devices name and the parties of the entries it crosses."""
    devs = devices(product)
    out: set[str] = set()
    for conn in circuit.connections:
        for end in conn.ends():
            if end.scheme == "device" and end.id in devs:
                out.add(devs[end.id].part.id)
            elif end.scheme == "part":
                out.add(end.id)
        if conn.via is not None and conn.via.id in product.interfaces:
            out |= {p.id for p in product.interfaces[conn.via.id].parties if p.scheme == "part"}
    return out


def elec_static_reads(product: Any, rule: Rule) -> list[str]:
    """The reads ``n2f impact`` assumes for an ``elec`` rule before the first build.

    A circuit's rule: every field of its circuit and of the supply, every field of the
    devices it reaches (all devices' ``part`` when it uses the ``part://`` shorthand), their
    parts' names, the entries it crosses, the parameters the supply names and the product's
    conductor rows.  The schedule: every circuit's record.
    """
    if rule.id == SCHEDULE_RULE:
        return [f"circuit://{cid}" for cid in sorted(circuits(product))]
    cid = rule.id.split(":", 1)[1]
    circuit = circuits(product).get(cid)
    if circuit is None:
        return []
    reads = [f"circuit://{cid}#{f}" for f in Circuit.model_fields if f != "id"]
    sup = supply(product)
    if sup is not None:
        reads += [f"supply://supply#{f}" for f in Supply.model_fields if f != "id"]
        reads += [f"param://{u}" for u in _supply_params(sup)]
    devs = devices(product)
    named: set[str] = set()
    for conn in circuit.connections:
        for end in conn.ends():
            if end.scheme == "device":
                named.add(end.id)
            elif end.scheme == "part":
                named |= {d for d, dev in devs.items() if dev.part.id == end.id}
                reads += [f"device://{d}#part" for d in sorted(devs)]
            elif end.scheme == "asm":
                reads += [f"asm://{end.id}#name", f"asm://{end.id}#build"]
        if conn.via is not None:
            reads.append(f"iface://{conn.via.id}")
        if _param(conn.length):
            reads.append(str(conn.length))
        if conn.conductor is not None and conn.conductor in product_conductors(product):
            reads.append(f"conductor://{conn.conductor}")
    for did in sorted(named & set(devs)):
        reads += [f"device://{did}#{f}" for f in Device.model_fields if f != "id"]
        reads.append(f"part://{devs[did].part.id}#name")
    for prot in (circuit.protection, None if sup is None else sup.protection):
        scheme, _, ident = str(prot).partition("://")
        if scheme == "part":
            reads.append(f"part://{ident}#name")
        elif scheme == "device" and ident in devs:
            reads += [f"device://{ident}#part", f"device://{ident}#instance"]
            reads.append(f"part://{devs[ident].part.id}#name")
    return list(dict.fromkeys(reads))


def _supply_params(sup: Supply) -> list[str]:
    out = []
    for value in (sup.voltage, sup.rating):
        if _param(value):
            out.append(str(value).removeprefix("param://"))
    return out


def _param(value: Any) -> bool:
    """A ``param://`` reference where a quantity may stand."""
    return getattr(value, "scheme", None) == "param"


# ---- elec:<circuit> ----------------------------------------------------------------------


def _make_circuit_run(cid: str) -> Any:
    def run(ctx: RunContext) -> RunResult:
        from napkin2factory.core.graph.rules import RunResult

        record = circuit_record(ctx, cid)
        folder = ctx.build_dir / OUT / cid
        folder.mkdir(parents=True, exist_ok=True)
        paths = {
            folder / "connections.json": json.dumps(record, indent=2, ensure_ascii=False) + "\n",
            folder / "diagram.svg": circuit_svg(record),
            folder / f"{cid}.kicad_sch": kicad_schematic(record),
        }
        for path, text in paths.items():
            path.write_text(text, encoding="utf-8")
        return RunResult(reads=[], outputs=list(paths), output_hash=sha256_json(record))

    return run


class _Reader:
    """The model, read for one circuit through the recording accessor (D5)."""

    def __init__(self, ctx: RunContext) -> None:
        self.ctx = ctx
        self.product = ctx.product
        raw = supply(self.product)
        self.supply = None if raw is None else ctx.proxy(raw, "supply://supply")
        self.region: str | None = None if self.supply is None else self.supply.region
        self._devices: dict[str, Any] = {}

    def device(self, did: str) -> Any:
        """``device://<did>`` through the proxy (one per id)."""
        if did not in self._devices:
            self._devices[did] = self.ctx.proxy(devices(self.product)[did], f"device://{did}")
        return self._devices[did]

    def part_name(self, pid: str) -> str:
        """The part's name (records ``part://<pid>#name``)."""
        part = self.product.parts.get(pid)
        if part is None:
            return pid
        return str(self.ctx.proxy(part, f"part://{pid}").name)

    def quantity(self, value: Any, unit: str) -> float | None:
        """A quantity or ``param://`` reference in ``unit`` (a parameter is a recorded read)."""
        if value is None:
            return None
        if _param(value):
            self.ctx.log.add(f"param://{value.id}")
            try:
                value = self.product.parameter_value(value.id)
            except Exception:  # a broken parameter is validate's to report
                return None
        try:
            return round(float(magnitude_in(value, unit)), 6)
        except Exception:
            return None

    def resolve(self, end_text: str) -> tuple[str, str, str]:
        """An end as ``(node uri, terminal, scheme)``: the part shorthand names its device."""
        end = parse_end(end_text)
        if end.scheme == "part":
            named = [
                did
                for did in sorted(devices(self.product))
                if self.device(did).part.id == end.id  # records device://<did>#part
            ]
            if len(named) == 1:
                return f"device://{named[0]}", end.terminal, "device"
        return end.base, end.terminal, end.scheme


def circuit_record(ctx: RunContext, cid: str) -> dict[str, Any]:
    """The circuit's record (``connections.json``, the wave-2 contract), every read recorded."""
    r = _Reader(ctx)
    c = ctx.proxy(circuits(ctx.product)[cid], f"circuit://{cid}")
    purpose = str(c.purpose)
    dc = bool(c.dc)
    voltage = r.quantity(c.voltage, "V")
    if voltage is None and r.supply is not None:
        voltage = r.quantity(r.supply.voltage, "V")
    connections = list(c.connections)  # records circuit://<cid>#connections
    devs: dict[str, dict[str, Any]] = {}
    entries: dict[str, dict[str, Any]] = {}
    modules: dict[str, dict[str, Any]] = {}
    wires: list[dict[str, Any]] = []
    for n, conn in enumerate(connections, start=1):
        ends = []
        for text in (conn.from_, conn.to):
            uri, terminal, scheme = r.resolve(text)
            ends.append((uri, terminal, _end_words(r, uri, terminal, scheme, devs, modules)))
        (a_uri, a_term, a_words), (b_uri, b_term, b_words) = ends
        cond = _conductor(r, conn.conductor)
        via = None if conn.via is None else str(conn.via)
        via_words = None
        if via is not None:
            entry = _entry(r, conn.via.id, entries)
            via_words = entry["name"]
        wires.append(
            {
                "id": f"{cid}-{n}",
                "from": f"{a_uri}#{a_term}",
                "from_words": a_words,
                "to": f"{b_uri}#{b_term}",
                "to_words": b_words,
                "conductor": conn.conductor,
                "conductor_label": cond["label"],
                "csa_mm2": cond["csa_mm2"],
                "insulation": cond["insulation"],
                "length_m": r.quantity(conn.length, "m"),
                "colour": _colour(conn.colour, r.region, (a_term, b_term), purpose, dc),
                "via": via,
                "via_words": via_words,
            }
        )
    for module in modules.values():
        module["words"] += ": " + ", ".join(module.pop("terminals"))
    return {
        "circuit": cid,
        "name": c.name or cid.replace("-", " ").capitalize(),
        "purpose": purpose,
        "voltage_v": voltage,
        "dc": dc,
        "protection": _protection(r, c.protection),
        "devices": list(devs.values()),
        "wires": wires,
        "entries": list(entries.values()),
        "boundary": list(modules.values()),
    }


def _end_words(
    r: _Reader,
    uri: str,
    terminal: str,
    scheme: str,
    devs: dict[str, dict[str, Any]],
    modules: dict[str, dict[str, Any]],
) -> str:
    """The end in words ("Switch terminal 2"), noting its device or module on the way."""
    ident = uri.split("://", 1)[1]
    if scheme == "device" and ident in devices(r.product):
        if uri not in devs:
            d = r.device(ident)
            pid = d.part.id
            devs[uri] = {
                "uri": uri,
                "part": f"part://{pid}",
                "name": r.part_name(pid),
                "instance": d.instance,
                "role": d.role,
                "terminals": list(d.terminals),
            }
        info = devs[uri]
        name = info["name"] + (f" ({info['instance']})" if info["instance"] else "")
        return f"{name} terminal {terminal}"
    if scheme == "supply":
        return f"the supply terminal {terminal}"
    if scheme == "asm" and ident in r.product.assemblies:
        if ident not in modules:
            asm = r.ctx.proxy(r.product.assemblies[ident], f"asm://{ident}")
            name = str(asm.name)
            modules[ident] = {
                "assembly": f"asm://{ident}",
                "name": name,
                "words": f"to the {name[:1].lower() + name[1:]}, supplied from elsewhere",
                "terminals": [],
            }
        if terminal not in modules[ident]["terminals"]:
            modules[ident]["terminals"].append(terminal)
        return f"{modules[ident]['name']} terminal {terminal}"
    return f"{uri} terminal {terminal}"


def _conductor(r: _Reader, cid: str | None) -> dict[str, Any]:
    """Label, cross-section (mm²) and insulation of a conductor id, or not given."""
    blank: dict[str, Any] = {"label": NOT_GIVEN, "csa_mm2": None, "insulation": NOT_GIVEN}
    if cid is None:
        return blank
    own = product_conductors(r.product)
    if cid in own:
        row = r.ctx.proxy(own[cid], f"conductor://{cid}")
        csa = row.csa
        return {
            "label": str(row.label),
            "csa_mm2": None if csa is None else round(float(magnitude_in(csa, "mm**2")), 6),
            "insulation": row.insulation or NOT_GIVEN,
        }
    try:
        table = wiring.conductor(cid)  # the table's hash is an input of the rule
    except ValueError:
        return blank
    return {
        "label": table.label,
        "csa_mm2": round(float(magnitude_in(table.csa, "mm**2")), 6),
        "insulation": table.insulation,
    }


def _entry(r: _Reader, iid: str, entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The cable entry's record: its name and whether it is a port of an external module."""
    uri = f"iface://{iid}"
    if uri in entries:
        return entries[uri]
    iface = r.product.interfaces.get(iid)
    if iface is None:
        entries[uri] = {"uri": uri, "name": iid, "external": False}
        return entries[uri]
    # the interface whole: the core values any iface:// read as the whole joint, so a
    # field read would rerun on edits that `n2f impact` does not match to it (gate E)
    r.ctx.log.add(uri)
    external = False
    for party in iface.parties:
        if party.scheme == "asm" and party.id in r.product.assemblies:
            asm = r.ctx.proxy(r.product.assemblies[party.id], f"asm://{party.id}")
            external = external or asm.build == "external"
    name = iface.name or _party_names(r, iface)
    entries[uri] = {"uri": uri, "name": name, "external": external}
    return entries[uri]


def _party_names(r: _Reader, iface: Any) -> str:
    names = []
    for p in iface.parties:
        if p.scheme == "part":
            names.append(r.part_name(p.id))
        elif p.id in r.product.assemblies:
            names.append(str(r.ctx.proxy(r.product.assemblies[p.id], f"asm://{p.id}").name))
        else:
            names.append(p.id)
    return " to ".join(names)


#: The colour table's role for a terminal marking (``wire_colours.yaml``).
_TERMINAL_ROLES = {"PE": "PE", "N": "N", "L": "L", "L1": "L1", "L2": "L2", "L3": "L3"}
_ROLE_ORDER = ("PE", "N", "L", "L1", "L2", "L3")


def _colour(
    own: str | None, region: str | None, terminals: tuple[str, str], purpose: str, dc: bool
) -> str:
    """The connection's own colour, else the region's for its terminals' role, else not given.

    The role comes from the terminal markings (``PE`` before ``N`` before a line); a control
    circuit's other conductors take the region's control colour (AC or DC).
    """
    if own:
        return own
    if region is None:
        return NOT_GIVEN
    roles = [_TERMINAL_ROLES[t] for t in terminals if t in _TERMINAL_ROLES]
    role = next((x for x in _ROLE_ORDER if x in roles), None)
    if role is None and purpose == "control":
        role = "control-dc" if dc else "control-ac"
    if role is None:
        return NOT_GIVEN
    try:
        return wiring.colour(region, role).colour
    except ValueError:
        return NOT_GIVEN


def _protection(r: _Reader, ref: Any) -> dict[str, Any]:
    """The circuit's protection: its reference and the device in words."""
    if ref is None:
        return {"ref": None, "words": NOT_GIVEN}
    text = str(ref)
    if text == "supply":
        prot = None if r.supply is None else r.supply.protection
        if prot is None:
            return {"ref": "supply", "words": "the supply's protective device (" + NOT_GIVEN + ")"}
        upstream = getattr(prot, "upstream", None)
        if upstream is not None:
            return {"ref": "supply", "words": str(upstream)}
        return {"ref": "supply", "words": _protective_words(r, str(prot))}
    return {"ref": text, "words": _protective_words(r, text)}


def _protective_words(r: _Reader, text: str) -> str:
    scheme, _, ident = text.partition("://")
    if scheme == "part":
        return r.part_name(ident)
    if scheme == "device" and ident in devices(r.product):
        d = r.device(ident)
        return r.part_name(d.part.id) + (f" ({d.instance})" if d.instance else "")
    return text


# ---- elec-schedule -----------------------------------------------------------------------


def _run_schedule(ctx: RunContext) -> RunResult:
    from napkin2factory.core.graph.rules import RunResult

    records = []
    for cid in sorted(circuits(ctx.product)):
        ctx.log.add(f"circuit://{cid}")  # the circuit rule's output hash: its record
        path = ctx.build_dir / OUT / cid / "connections.json"
        records.append(json.loads(path.read_text(encoding="utf-8")))
    rows, outputs = write_tables(records, ctx.build_dir / OUT)
    return RunResult(reads=[], outputs=outputs, output_hash=sha256_json(rows))
