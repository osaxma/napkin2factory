"""Wiring model schemas and value types; split from model/__init__.py (S-184)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
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
    ``dedicated: true`` says the supply circuit serves this product alone: nothing else may
    be plugged into it (the electrician confirms).  The supply-headroom check then passes
    a load above its cited share of the rating; it is how the model says that pick was made
    (S-171).
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
    dedicated: bool = False
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
