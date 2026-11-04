"""Wiring model family accessors and validation; split from model/__init__.py (S-184)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napkin2factory.calckit import wiring
from napkin2factory.core.uris import Uri
from napkin2factory.domains.electrical.model.schemas import (
    CIRCUIT_FOLDER,
    CONDUCTOR_FOLDER,
    DEVICE_FOLDER,
    ENTRY_KIND,
    RULE,
    SUPPLY_FOLDER,
    Circuit,
    Connection,
    Device,
    EndRef,
    ProductConductor,
    Supply,
)

# ---- reading the families ----------------------------------------------------------------


def supply(product: Any) -> Supply | None:
    """The product's supply, or ``None``."""
    sup: Supply | None = product.families.get("supply", {}).get("supply")
    if sup is not None and sup.region is None:
        manifest = getattr(product, "manifest", None)
        if manifest is not None and getattr(manifest, "region", None) is not None:
            sup.region = manifest.region  # W7: default to manifest region
    return sup


def devices(product: Any) -> dict[str, Device]:
    """The product's devices by id."""
    return dict(product.families.get("device", {}))


def circuits(product: Any) -> dict[str, Circuit]:
    """The product's circuits by id."""
    return dict(product.families.get("circuit", {}))


def product_conductors(product: Any) -> dict[str, ProductConductor]:
    """The product's own conductor rows by id."""
    return dict(product.families.get("conductor", {}))


def has_content(product: Any) -> bool:
    """True when the product holds anything under ``model/electrical/``."""
    return any(product.families.get(f) for f in ("supply", "device", "circuit", "conductor"))


def devices_of_part(product: Any, pid: str) -> list[Device]:
    """The devices naming ``part://<pid>``, by id."""
    return [d for _, d in sorted(devices(product).items()) if d.part.id == pid]


def resolve_end(product: Any, end: EndRef) -> Device | Supply | str | None:
    """What an end names: a :class:`Device`, the :class:`Supply`, an ``asm://`` id, or None.

    ``part://<id>`` resolves to the one device naming the part; with none or several it is
    ``None`` (:func:`validate_refs` reports why).
    """
    if end.scheme == "device":
        return devices(product).get(end.id)
    if end.scheme == "part":
        named = devices_of_part(product, end.id)
        return named[0] if len(named) == 1 else None
    if end.scheme == "supply":
        return supply(product) if end.id == "supply" else None
    return end.id if end.id in product.assemblies else None


def wired_devices(product: Any) -> set[str]:
    """Ids of the devices some connection reaches (directly or by the part shorthand)."""
    out: set[str] = set()
    for c in circuits(product).values():
        for conn in c.connections:
            for end in conn.ends():
                hit = resolve_end(product, end)
                if isinstance(hit, Device):
                    out.add(hit.id)
    return out


def conductor_ids(product: Any) -> list[str]:
    """Every conductor id a connection may name: the calc kit's table, then the product's."""
    return [c.id for c in wiring.all_conductors()] + sorted(product_conductors(product))


def placed(product: Any, pid: str) -> int | None:
    """How many times the product's assemblies place ``part://<pid>``; ``None`` if unknown.

    Counted from the top assemblies down, quantities multiplied through every level (as the
    parts list counts).  Unknown when no assembly lists the part as a child (it may be loose
    hardware of a joint) or the tree has no top.
    """
    asms = product.assemblies
    if not any(c.part is not None and c.part.id == pid for a in asms.values() for c in a.children):
        return None
    used = {c.asm.id for a in asms.values() for c in a.children if c.asm is not None}
    tops = [a for a in sorted(asms) if a not in used]
    if not tops:
        return None

    def count(aid: str, stack: tuple[str, ...]) -> int:
        total = 0
        for c in asms[aid].children:
            if c.part is not None and c.part.id == pid:
                total += c.qty
            elif c.asm is not None and c.asm.id in asms and c.asm.id not in stack:
                total += c.qty * count(c.asm.id, (*stack, aid))
        return total

    return sum(count(t, (t,)) for t in tops)


# ---- validate_refs -----------------------------------------------------------------------


def _file(product: Any, uri: str, fallback: str) -> Path:
    return Path(product.files.get(uri, product.root / fallback))


def _datasheet(product: Any, pid: str) -> str:
    part = product.parts.get(pid)
    source = getattr(part, "source", None)
    url = getattr(source, "url", None) if source is not None else None
    return f" ({url})" if url else ""


def validate_refs(product: Any, problems: Any) -> None:
    """Every reference of the wiring model resolves (F15); each problem names file and fix.

    Runs after the core's own cross-checks, once for the whole domain (registered on the
    ``supply`` family; the other families register none).
    """
    sup = supply(product)
    devs = devices(product)
    circs = circuits(product)
    _validate_supply_family(product, problems, sup)
    _validate_devices(product, problems, devs)
    _validate_conductors(product, problems)
    if circs and sup is None:
        problems.add(
            product.root / SUPPLY_FOLDER / "supply.yaml",
            "supply://supply",
            f"{len(circs)} circuit(s) exist but the product has no supply",
            "add model/electrical/supply.yaml with the supply's voltage, phases, rating and "
            "protection",
            rule=RULE,
        )
    known_conductors = set(conductor_ids(product)) if circs else set()
    for _, circuit in sorted(circs.items()):
        _validate_circuit(product, problems, circuit, known_conductors)


def _validate_supply_family(product: Any, problems: Any, sup: Supply | None) -> None:
    if sup is None:
        return
    file = _file(product, "supply://supply", f"{SUPPLY_FOLDER}/supply.yaml")
    prot = sup.protection
    if isinstance(prot, Uri):
        _check_protective(product, problems, file, "supply://supply", prot)

    manifest = getattr(product, "manifest", None)
    manifest_region = getattr(manifest, "region", None) if manifest is not None else None
    if sup.region is None and manifest_region is not None:
        sup.region = manifest_region  # W7: default to manifest region
    elif sup.region is not None and manifest_region is not None and sup.region != manifest_region:
        problems.add(
            file,
            "supply://supply",
            f"supply region {sup.region!r} disagrees with product region {manifest_region!r}",
            "use the same region in both, or omit 'region:' from the supply file so it defaults "
            "to the product's",
            rule=RULE,
        )

    if sup.region is not None:
        try:
            wiring.conductors(sup.region)
        except ValueError as exc:
            problems.add(
                file,
                "supply://supply",
                str(exc),
                "name a region the calc kit rates (" + ", ".join(_regions()) + "), or add your "
                "own conductor rows under model/electrical/conductors/ with their source",
                severity="warn",
                rule=RULE,
            )

    if sup.earthing is not None:
        try:
            wiring.earthing(sup.earthing, region=sup.region)
        except ValueError as exc:
            problems.add(
                file,
                "supply://supply",
                str(exc),
                "choose an earthing arrangement on file"
                + (f" for region {sup.region!r}" if sup.region is not None else ""),
                rule=RULE,
            )


def _regions() -> list[str]:
    return sorted({c.region for c in wiring.all_conductors()})


def _check_protective(product: Any, problems: Any, file: Path, subject: str, ref: Uri) -> None:
    if ref.scheme == "part" and ref.id not in product.parts:
        problems.add(
            file,
            subject,
            f"its protection names {ref}, which is not a part",
            f"add model/parts/{ref.id}.yaml for the protective device, or name an existing part",
            rule=RULE,
        )
    elif ref.scheme == "device" and ref.id not in devices(product):
        problems.add(
            file,
            subject,
            f"its protection names {ref}, which is not a device",
            f"add model/electrical/devices/{ref.id}.yaml naming the protective device's part, "
            f"or name one of: {', '.join(sorted(devices(product))) or 'no device yet'}",
            rule=RULE,
        )


def _validate_devices(product: Any, problems: Any, devs: dict[str, Device]) -> None:
    by_part: dict[str, list[str]] = {}
    for did, dev in sorted(devs.items()):
        file = _file(product, dev.uri, f"{DEVICE_FOLDER}/{did}.yaml")
        if dev.part.id not in product.parts:
            problems.add(
                file,
                dev.uri,
                f"names {dev.part}, which is not a part",
                f"name an existing part, or add model/parts/{dev.part.id}.yaml (the part this "
                "device is: one parts-list line)",
                rule=RULE,
            )
            continue
        by_part.setdefault(dev.part.id, []).append(did)
        if not dev.terminals and dev.role != "passthrough":
            problems.add(
                file,
                dev.uri,
                "its terminals are not sourced yet, so no connection to it can be checked",
                "read them from the datasheet named on the part"
                + _datasheet(product, dev.part.id)
                + " and list them under `terminals:`; never guess them",
                severity="warn",
                rule=RULE,
            )
    for pid, named in sorted(by_part.items()):
        if len(named) < 2:
            continue
        count = placed(product, pid)
        listed = ", ".join(f"device://{d}" for d in named)
        files = [_file(product, f"device://{d}", f"{DEVICE_FOLDER}/{d}.yaml") for d in named]
        if count is None:
            problems.add(
                files[-1],
                f"part://{pid}",
                f"{len(named)} devices name part://{pid} ({listed}), but no assembly places "
                "the part, so how many there are cannot be counted",
                f"list part://{pid} with its qty in the assembly that holds it, or keep one "
                "device per placed part",
                severity="warn",
                rule=RULE,
            )
        elif len(named) > count:
            problems.add(
                files[-1],
                f"part://{pid}",
                f"{len(named)} devices name part://{pid} ({listed}), but the product places it "
                f"{_times(count)}",
                f"keep one device per placed part: remove {len(named) - count} of these files, "
                f"or raise the part's qty in its assembly",
                rule=RULE,
            )


def _times(n: int) -> str:
    return {0: "nowhere", 1: "once", 2: "twice"}.get(n, f"{n} times")


def _validate_conductors(product: Any, problems: Any) -> None:
    rows = product_conductors(product)
    if not rows:
        return
    table = {c.id for c in wiring.all_conductors()}
    for rid in sorted(rows):
        if rid in table:
            problems.add(
                _file(product, f"conductor://{rid}", f"{CONDUCTOR_FOLDER}/{rid}.yaml"),
                f"conductor://{rid}",
                f"the calc kit's conductor table already has a row {rid!r}",
                "give your row another id (a product row adds a conductor, it does not "
                "replace the table's)",
                rule=RULE,
            )


def _validate_circuit(
    product: Any, problems: Any, circuit: Circuit, known_conductors: set[str]
) -> None:
    file = _file(product, circuit.uri, f"{CIRCUIT_FOLDER}/{circuit.id}.yaml")
    subject = circuit.uri
    prot = circuit.protection
    if isinstance(prot, Uri):
        _check_protective(product, problems, file, subject, prot)
    for path in circuit.earth:
        if path.part.id not in product.parts:
            problems.add(
                file,
                subject,
                f"its earth list names {path.part}, which is not a part",
                "name an existing part",
                rule=RULE,
            )
        for joint in path.bonded_via:
            if joint.id not in product.interfaces:
                problems.add(
                    file,
                    subject,
                    f"{path.part} is bonded via {joint}, which is not an interface",
                    f"add model/interfaces/{joint.id}.yaml, or name the joint that exists",
                    rule=RULE,
                )
    entries: set[str] = set()
    for n, conn in enumerate(circuit.connections, start=1):
        where = f"connection {n} ({conn.from_} to {conn.to})"
        for end in conn.ends():
            _validate_end(product, problems, file, subject, where, end, conn)
        if conn.conductor is not None and conn.conductor not in known_conductors:
            problems.add(
                file,
                subject,
                f"{where} names conductor {conn.conductor!r}, which is not on file",
                "use one of the calc kit's conductors ("
                + ", ".join(sorted(c.id for c in wiring.all_conductors()))
                + ") or add model/electrical/conductors/"
                + f"{conn.conductor}.yaml with its source",
                rule=RULE,
            )
        if conn.via is not None and str(conn.via) not in entries:
            entries.add(str(conn.via))  # one problem per entry, however many conductors cross
            _validate_via(product, problems, file, subject, where, circuit, conn.via)


def _validate_via(
    product: Any, problems: Any, file: Path, subject: str, where: str, circuit: Circuit, via: Uri
) -> None:
    iface = product.interfaces.get(via.id)
    if iface is None:
        problems.add(
            file,
            subject,
            f"{where} goes via {via}, which is not an interface",
            f"add model/interfaces/{via.id}.yaml with `kind: {ENTRY_KIND}`, or name an "
            "existing cable entry",
            rule=RULE,
        )
        return
    if iface.kind != ENTRY_KIND:
        problems.add(
            file,
            subject,
            f"{where} goes via {via}, a {iface.kind} joint, not a cable entry",
            f"name a `kind: {ENTRY_KIND}` interface (the hole and gland the conductor passes)",
            rule=RULE,
        )
        return
    passes = {str(u) for u in getattr(iface.spec, "passes", [])}
    if circuit.uri not in passes:
        problems.add(
            product.files.get(iface.uri, product.root / f"model/interfaces/{via.id}.yaml"),
            iface.uri,
            f"{circuit.uri} goes through this cable entry ({where}), but `passes:` does not "
            "list it",
            f"add {circuit.uri} to `passes:` in model/interfaces/{via.id}.yaml",
            rule=RULE,
        )


def _validate_end(
    product: Any,
    problems: Any,
    file: Path,
    subject: str,
    where: str,
    end: EndRef,
    conn: Connection,
) -> None:
    if end.scheme == "device":
        dev = devices(product).get(end.id)
        if dev is None:
            problems.add(
                file,
                subject,
                f"{where} names {end.base}, which is not a device",
                f"add model/electrical/devices/{end.id}.yaml, or name one of: "
                + (", ".join(sorted(devices(product))) or "no device yet"),
                rule=RULE,
            )
            return
        _check_terminal(problems, file, subject, where, end, dev.terminals, dev.uri)
    elif end.scheme == "part":
        named = devices_of_part(product, end.id)
        if not named:
            problems.add(
                file,
                subject,
                f"{where} names {end.base}, but no device names that part",
                f"add model/electrical/devices/{end.id}.yaml with `part: part://{end.id}`, "
                "or name the device: device://<id>#<terminal>",
                rule=RULE,
            )
        elif len(named) > 1:
            problems.add(
                file,
                subject,
                f"{where} names {end.base}, but {len(named)} devices name that part ("
                + ", ".join(d.uri for d in named)
                + "), so it cannot say which",
                "name the device instead: one of "
                + ", ".join(f"{d.uri}#{end.terminal}" for d in named),
                rule=RULE,
            )
        else:
            _check_terminal(problems, file, subject, where, end, named[0].terminals, named[0].uri)
    elif end.scheme == "supply":
        sup = supply(product)
        if end.id != "supply":
            problems.add(
                file,
                subject,
                f"{where} names {end.base}; the supply is supply://supply",
                f"write supply://supply#{end.terminal}",
                rule=RULE,
            )
        elif sup is not None:
            _check_terminal(
                problems, file, subject, where, end, sup.terminal_names(), "supply://supply"
            )
    else:
        _validate_module_end(product, problems, file, subject, where, end, conn)


def _check_terminal(
    problems: Any,
    file: Path,
    subject: str,
    where: str,
    end: EndRef,
    terminals: list[str],
    owner: str,
) -> None:
    if not terminals:
        return  # not sourced yet: the device's own warning says so
    if end.terminal not in terminals:
        problems.add(
            file,
            subject,
            f"{where}: {owner} has no terminal {end.terminal!r}; its terminals are "
            + ", ".join(terminals),
            f"write one of {owner}'s terminals after '#', or add {end.terminal!r} to its "
            "`terminals:` if the datasheet has it",
            rule=RULE,
        )


def _validate_module_end(
    product: Any,
    problems: Any,
    file: Path,
    subject: str,
    where: str,
    end: EndRef,
    conn: Connection,
) -> None:
    """An ``asm://`` end: a module supplied from elsewhere, reached through one of its ports.

    The module's own wiring is not modelled here (F11, E4); its ports are the whole contract,
    so a conductor reaching it must cross one (DoD 5).  The error names the module's file.
    """
    asm = product.assemblies.get(end.id)
    if asm is None:
        problems.add(
            file,
            subject,
            f"{where} names {end.base}, which is not an assembly",
            f"add model/assemblies/{end.id}.yaml with `build: external` and its `ports:`, or "
            "name a device: device://<id>#<terminal>",
            rule=RULE,
        )
        return
    if asm.build != "external":
        problems.add(
            file,
            subject,
            f"{where} names {end.base}, a module built here; only a module supplied from "
            "elsewhere is wired to as a whole",
            "name the device inside it that the conductor reaches: device://<id>#<terminal>",
            rule=RULE,
        )
        return
    ports = [str(p) for p in asm.ports]
    asm_file = product.files.get(asm.uri, product.root / f"model/assemblies/{end.id}.yaml")
    listed = ", ".join(ports) or "none yet"
    if conn.via is None:
        found = "names no `via:`"
        fix = f"give the connection `via:` one of the module's ports ({listed})"
    elif str(conn.via) not in ports:
        found = f"goes via {conn.via}, which is not one of its ports ({listed})"
        fix = (
            f"add {conn.via} to `ports:` in model/assemblies/{end.id}.yaml (the cable entry "
            f"must name {asm.uri} as a party), or route the connection via one of its ports"
        )
    else:
        return
    problems.add(
        asm_file,
        asm.uri,
        f"{subject} reaches this module supplied from elsewhere ({where}), but {found}",
        fix,
        rule=RULE,
    )
