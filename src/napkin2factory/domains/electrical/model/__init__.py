"""The wiring model (ELECTRICAL_STAGE E2, E3): supply, devices, circuits, product conductors.

Four model families under ``model/electrical/`` (S-153, how the folders are laid out):

* ``supply`` — ``model/electrical/supply.yaml``, ``supply://supply``: the one supply the
  product plugs into (voltage, phases, frequency, rating, earthing, region, protection).
* ``device`` — ``model/electrical/devices/<id>.yaml``, ``device://<id>``: a powered or
  wired thing, naming the part it is (one part stays one parts-list line, E2).
* ``circuit`` — ``model/electrical/circuits/<id>.yaml``, ``circuit://<id>``: a list of
  connections between terminals (E3), its protection and its earth paths.
* ``conductor`` — ``model/electrical/conductors/<id>.yaml``, ``conductor://<id>``: the
  product's own conductor rows, beside the calc kit's table (E3: a product may add rows).

A connection end is ``device://<id>#<terminal>`` (S-154: connections name devices, not
parts); ``part://<id>#<terminal>`` is a shorthand when exactly one device names the part;
``supply://supply#L`` is a terminal of the supply; ``asm://<module>#<terminal>`` is a
terminal of a module supplied from elsewhere (``build: external``), reached through one of
its ports.  Terminals are free names (``L``, ``PE``, ``A1``, ``13``, ``+``, ``TC-``), so an
end is parsed here, not as a core URI (whose fragment reads ``1`` as an instance number).

:func:`validate_refs` checks every cross-reference and names the file, the thing and the fix.
Everything a wiring code would judge is left to the checks (E6); this module only refuses
what cannot be read: a part that does not exist, a terminal the device does not have, a
conductor nobody has on file, a cable entry the circuit does not pass.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field, PlainSerializer, field_validator, model_validator

from napkin2factory.calckit import wiring
from napkin2factory.core.model.base import (
    IfaceUri,
    Model,
    PartUri,
    Quantity,
    Slug,
    uri_of,
)
from napkin2factory.core.units import UnitError, is_quantity, magnitude_in, parse_quantity
from napkin2factory.core.uris import SLUG, Uri, UriError

#: The rule name every problem of this module carries (``n2f validate --json``).
RULE = "electrical"
#: Where each family's files live, relative to the product root (S-153).
SUPPLY_FOLDER = "model/electrical"
DEVICE_FOLDER = "model/electrical/devices"
CIRCUIT_FOLDER = "model/electrical/circuits"
CONDUCTOR_FOLDER = "model/electrical/conductors"
#: The interface kind a connection's ``via`` must name (E4).
ENTRY_KIND = "cable-entry"

ROLES = ("supply", "load", "control", "protection", "sensor", "earth", "passthrough")
PURPOSES = ("power", "control", "sensing", "earth")
#: Utilisation categories a contact rating may name (IEC 60947-4-1 and -5-1), plus
#: ``resistive`` as makers print it on a relay's sheet (S-154, point 6).
CONTACT_CATEGORIES = (
    "resistive",
    "AC-1",
    "AC-3",
    "AC-12",
    "AC-14",
    "AC-15",
    "DC-1",
    "DC-12",
    "DC-13",
)


# ---- small value types ------------------------------------------------------------------


def _quantity_of(dimension: str, unit: str, words: str) -> Any:
    """A validator: a quantity in ``unit``'s dimension, or a ``param://`` reference."""

    def check(v: Any) -> Any:
        if isinstance(v, Uri) or (isinstance(v, str) and v.strip().startswith("param://")):
            try:
                u = v if isinstance(v, Uri) else Uri.parse(v.strip())
            except UriError as exc:
                raise ValueError(str(exc)) from exc
            if u.scheme != "param":
                raise ValueError(f"{u}: only param:// references are allowed here")
            return u
        if isinstance(v, bool):
            raise ValueError(f"{words} is a quantity like '{dimension}', not a yes or no")
        try:
            q = v if is_quantity(v) else parse_quantity(v)
            magnitude_in(q, unit)
        except (UnitError, ValueError, TypeError) as exc:
            raise ValueError(
                f"{words} is a quantity like '{dimension}' or a param:// reference, got {v!r}"
            ) from exc
        return q

    return check


def _ser_qp(v: Any) -> str:
    from napkin2factory.core.units import format_quantity

    return str(v) if isinstance(v, Uri) else format_quantity(v)


def _qp(example: str, unit: str, words: str) -> Any:
    return Annotated[
        Any,
        BeforeValidator(_quantity_of(example, unit, words)),
        PlainSerializer(_ser_qp, return_type=str),
    ]


Volts = _qp("230 V", "V", "a voltage")
Amps = _qp("16 A", "A", "a current")
Watts = _qp("2 kW", "W", "a power")
Length = _qp("0.6 m", "m", "a length")

DeviceUri = uri_of("device")
#: A protective device: a part the product ships, or the device file that names it.
ProtectiveUri = uri_of("part", "device")

_END_RE = re.compile(
    rf"^(?P<scheme>device|part|supply|asm)://(?P<id>{SLUG})#(?P<terminal>[^\s#]+)$"
)
_TERMINAL_RE = re.compile(r"^[^\s#]+$")


def _end(v: Any) -> str:
    if not isinstance(v, str) or not _END_RE.match(v.strip()):
        raise ValueError(
            f"{v!r} is not a connection end; write device://<id>#<terminal> (or "
            "part://<id>#<terminal> when one device names that part, supply://supply#L for "
            "the supply, asm://<module>#<terminal> for a module supplied from elsewhere)"
        )
    return v.strip()


#: A connection end: ``<scheme>://<id>#<terminal>`` (:func:`parse_end` splits it).
End = Annotated[str, BeforeValidator(_end)]


@dataclass(frozen=True)
class EndRef:
    """A parsed connection end: ``scheme`` (device, part, supply, asm), ``id``, ``terminal``."""

    scheme: str
    id: str
    terminal: str

    @property
    def base(self) -> str:
        """``<scheme>://<id>`` without the terminal."""
        return f"{self.scheme}://{self.id}"

    def __str__(self) -> str:
        return f"{self.scheme}://{self.id}#{self.terminal}"


def parse_end(text: str) -> EndRef:
    """Split a connection end into its scheme, id and terminal (it was validated on load)."""
    m = _END_RE.match(text.strip())
    if m is None:
        raise ValueError(f"{text!r} is not a connection end")
    return EndRef(m.group("scheme"), m.group("id"), m.group("terminal"))


def _protection_ref(v: Any) -> Any:
    if v == "supply":
        return "supply"
    try:
        u = v if isinstance(v, Uri) else Uri.parse(str(v).strip())
    except UriError as exc:
        raise ValueError(
            f"{v!r}: name the protective device (part://<id> or device://<id>), or write "
            "`supply` when the supply's own device protects this circuit"
        ) from exc
    if u.scheme not in ("part", "device") or u.selector or u.instance is not None:
        raise ValueError(
            f"{v!r}: a circuit's protection is part://<id>, device://<id> or the word `supply`"
        )
    return u


#: A circuit's protection: ``part://`` or ``device://`` (a device the product ships), or the
#: word ``supply`` (the supply's own device, S-154 point 2).
CircuitProtection = Annotated[Any, BeforeValidator(_protection_ref), PlainSerializer(str)]


# ---- supply ------------------------------------------------------------------------------


class UpstreamProtection(Model):
    """The site's protective device, not a part of the product (S-154 point 2).

    ``upstream`` says it in the owner's words ("the 16 A breaker of the dedicated circuit");
    ``rating`` is its rated current, which the electrician confirms.
    """

    upstream: str
    rating: Amps | None = None


def _supply_protection(v: Any) -> Any:
    if v is None or isinstance(v, (UpstreamProtection, Uri)):
        return v
    if isinstance(v, dict):
        return UpstreamProtection.model_validate(v)
    if v == "supply":
        raise ValueError(
            "the supply's protection is {upstream: <words>, rating: 16 A} (the site's device) "
            "or part://<id> (a protective device the product ships)"
        )
    return _protection_ref(v)


def _ser_supply_protection(v: Any) -> Any:
    return v.model_dump(exclude_none=True) if isinstance(v, UpstreamProtection) else str(v)


#: The supply's protection: the site's device (:class:`UpstreamProtection`) or a part or
#: device the product ships (S-154 point 2).
SupplyProtection = Annotated[
    Any, BeforeValidator(_supply_protection), PlainSerializer(_ser_supply_protection)
]


class Supply(Model):
    """``model/electrical/supply.yaml`` (E3): what the product plugs into.

    ``rating`` is the supply circuit's current rating (a quantity or ``param://``);
    ``earthing`` an arrangement of the calc kit's ``earthing.yaml`` (TN-S, TN-C-S, TT, IT);
    ``region`` the key into the calc kit's circuit and conductor tables; ``protection`` the
    device that protects the supply: the site's (``{upstream, rating}``) or a part the
    product ships.  ``dc: true`` is a DC supply (no frequency).  ``terminals`` defaults to
    L, N, PE for one phase, L1, L2, L3, N, PE for three, and +, -, PE for DC.
    """

    id: Literal["supply"] = "supply"
    voltage: Volts
    phases: Literal[1, 3] = 1
    frequency: Quantity | None = None
    dc: bool = False
    rating: Amps | None = None
    earthing: str | None = None
    region: str | None = None
    protection: SupplyProtection = None
    terminals: list[str] | None = None
    notes: str | None = None

    @field_validator("earthing")
    @classmethod
    def _known_earthing(cls, v: str | None) -> str | None:
        if v is not None:
            wiring.earthing(v)  # a ValueError listing the known arrangements
        return v

    @field_validator("frequency")
    @classmethod
    def _hertz(cls, v: Any) -> Any:
        if v is not None:
            try:
                magnitude_in(v, "Hz")
            except UnitError as exc:
                raise ValueError(f"the frequency is a quantity like '50 Hz', got {v}") from exc
        return v

    @model_validator(mode="after")
    def _dc_has_no_frequency(self) -> Supply:
        if self.dc and self.frequency is not None:
            raise ValueError("a DC supply has no frequency: remove `frequency:` or `dc: true`")
        if self.dc and self.phases != 1:
            raise ValueError("a DC supply has no phases: remove `phases:`")
        _unique_terminals(self.terminals or [])
        return self

    def terminal_names(self) -> list[str]:
        """The supply's terminals: declared, else by phases (or DC)."""
        if self.terminals is not None:
            return list(self.terminals)
        if self.dc:
            return ["+", "-", "PE"]
        return ["L", "N", "PE"] if self.phases == 1 else ["L1", "L2", "L3", "N", "PE"]


# ---- devices -----------------------------------------------------------------------------


def _unique_terminals(names: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for t in names:
        if not isinstance(t, str) or not _TERMINAL_RE.match(t):
            raise ValueError(f"terminal {t!r}: a terminal is a name without spaces or '#'")
        if t in seen:
            raise ValueError(f"terminal {t!r} is listed twice")
        seen.append(t)
    return seen


class Rating(Model):
    """A device's rating: its voltage, and its current or power (quantities or ``param://``)."""

    voltage: Volts | None = None
    current: Amps | None = None
    power: Watts | None = None


class Contact(Model):
    """A switching contact's rating (S-154 point 6): ``current`` and its ``category``."""

    current: Amps | None = None
    category: str | None = None

    @field_validator("category")
    @classmethod
    def _known(cls, v: str | None) -> str | None:
        if v is not None and v not in CONTACT_CATEGORIES:
            raise ValueError(
                f"unknown contact category {v!r}; known: {', '.join(CONTACT_CATEGORIES)}"
            )
        return v


class Device(Model):
    """``model/electrical/devices/<id>.yaml`` (E2): a wired thing and the part it is.

    ``part`` must exist; several devices may name one part only when the product places it
    that many times (S-154 point 1), each with its ``instance`` words ("the control
    probe").  ``terminals`` are the device's own markings; ``[]`` until they are read from
    its datasheet (a warning, never invented).  ``class`` is the protection class (I, II,
    III).  ``contact`` rates a switching contact; ``coil`` names the terminals of a coil and
    ``inductive`` marks an inductive load (both read by the contact check, point 6).
    ``safety`` says the device's safety job (``interlock``: the load must not run while it
    is open; ``limit``: it cuts the load above a limit), and ``through`` lists the terminal
    pairs a current passes inside the device (a pole, a contact, a fuse), so the checks can
    walk a path through it (E6).
    """

    id: Slug
    part: PartUri
    role: Literal["supply", "load", "control", "protection", "sensor", "earth", "passthrough"]
    rating: Rating | None = None
    terminals: list[str] = Field(default_factory=list)
    class_: Literal["I", "II", "III"] | None = Field(default=None, alias="class")
    instance: str | None = None
    contact: Contact | None = None
    coil: list[str] = Field(default_factory=list)
    inductive: bool = False
    safety: Literal["interlock", "limit"] | None = None
    through: list[list[str]] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("class_", mode="before")
    @classmethod
    def _class_words(cls, v: Any) -> Any:
        # `class: 2` and `class: ii` read as the roman numeral a rating plate prints
        roman = {1: "I", 2: "II", 3: "III", "1": "I", "2": "II", "3": "III"}
        if isinstance(v, bool):
            return v
        if v in roman:
            return roman[v]
        return v.upper() if isinstance(v, str) else v

    @field_validator("terminals")
    @classmethod
    def _terminals(cls, v: list[str]) -> list[str]:
        return _unique_terminals(v)

    @field_validator("through")
    @classmethod
    def _pairs(cls, v: list[list[str]]) -> list[list[str]]:
        for pair in v:
            if len(pair) != 2 or pair[0] == pair[1]:
                raise ValueError(
                    f"through {pair}: each entry is a pair of two different terminals, "
                    "e.g. [L1, T1]"
                )
        return v

    @model_validator(mode="after")
    def _named_terminals(self) -> Device:
        if not self.terminals:
            return self  # not sourced yet: validate_refs warns, nothing to check against
        for t in [*self.coil, *(t for pair in self.through for t in pair)]:
            if t not in self.terminals:
                raise ValueError(
                    f"terminal {t!r} is not one of the device's terminals "
                    f"({', '.join(self.terminals)}); add it to `terminals:` or fix the name"
                )
        return self

    @property
    def uri(self) -> str:
        """``device://<id>``."""
        return f"device://{self.id}"


# ---- circuits ----------------------------------------------------------------------------


class Connection(Model):
    """One conductor between two terminals (E3).

    ``from`` and ``to`` are connection ends (module docstring); ``conductor`` is an id of
    the calc kit's ``conductors.yaml`` or of the product's ``model/electrical/conductors/``;
    ``length`` the cut length; ``via`` the cable entry (``iface://``, kind ``cable-entry``)
    it crosses; ``colour`` the insulation colour when it is not the region's default.
    """

    from_: End = Field(alias="from")
    to: End
    conductor: str | None = None
    length: Length | None = None
    via: IfaceUri | None = None
    colour: str | None = None

    @model_validator(mode="after")
    def _two_ends(self) -> Connection:
        if self.from_ == self.to:
            raise ValueError(f"a connection joins two different terminals; both ends are {self.to}")
        return self

    def ends(self) -> tuple[EndRef, EndRef]:
        """Both ends, parsed."""
        return parse_end(self.from_), parse_end(self.to)


class EarthPath(Model):
    """A conductive part's path to earth through a joint (S-154 point 5).

    ``bonded_via`` lists the bolted or screwed joints (``iface://``) through which ``part``
    reaches an earthed part; a person verifies such a claim (E6).
    """

    part: PartUri
    bonded_via: list[IfaceUri] = Field(default_factory=list)
    notes: str | None = None


class Circuit(Model):
    """``model/electrical/circuits/<id>.yaml`` (E3): connections, protection, earth paths.

    ``purpose`` is power, control, sensing or earth; ``name`` says it in the owner's words;
    ``protection`` is ``part://``, ``device://`` or ``supply``; ``voltage`` and ``dc`` give
    the circuit's working voltage when it is not the supply's (a 12 V DC drive, a sensor
    loop), which the checks need to tell extra-low-voltage circuits from mains ones
    (S-154 point 4); ``earth`` lists the parts that reach earth through a joint.
    """

    id: Slug
    purpose: Literal["power", "control", "sensing", "earth"]
    name: str | None = None
    protection: CircuitProtection | None = None
    voltage: Volts | None = None
    dc: bool = False
    connections: list[Connection] = Field(default_factory=list)
    earth: list[EarthPath] = Field(default_factory=list)
    notes: str | None = None

    @property
    def uri(self) -> str:
        """``circuit://<id>``."""
        return f"circuit://{self.id}"


# ---- the product's own conductor rows ----------------------------------------------------


class ProductConductor(Model):
    """``model/electrical/conductors/<id>.yaml``: a conductor the calc kit's table lacks (E3).

    The same columns as ``calckit/data/conductors.yaml``; ``source`` is required (no
    invented numbers) and ``verify`` stays true until a person confirms the row.  A sensing
    cable may leave ``ampacity`` out: it carries no supply current.
    """

    id: Slug
    label: str
    csa: Quantity | None = None
    ampacity: Amps | None = None
    ambient: Quantity | None = None
    basis: str | None = None
    insulation: str | None = None
    max_temp: Quantity | None = None
    kind: Literal["panel", "cord", "high-temp", "sensing"] = "panel"
    region: str | None = None
    source: str
    verify: bool = True


# ---- reading the families ----------------------------------------------------------------


def supply(product: Any) -> Supply | None:
    """The product's supply, or ``None``."""
    return product.families.get("supply", {}).get("supply")  # type: ignore[no-any-return]


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
    if sup.region is not None and not wiring.conductors(sup.region):
        problems.add(
            file,
            "supply://supply",
            f"region {sup.region!r} has no conductor table on file, so no conductor can be "
            "checked against it",
            "name a region the calc kit rates (" + ", ".join(_regions()) + "), or add your "
            "own conductor rows under model/electrical/conductors/ with their source",
            severity="warn",
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
