"""Wiring tables: conductors, earthing arrangements and conductor colours, typed.

A loader, not a calc pack: it computes nothing, so it has no reference cases (F17 covers
formulas). It reads three calc-kit tables through :func:`load_table`, so every row carries
its ``source`` and ``verify: true`` and ``make verify-list`` prints it (S-146):

* ``calckit/data/conductors.yaml`` — copper conductors by region: cross-section, the
  ampacity a wiring check fails on (with the table, column and ambient it assumes),
  insulation and its temperature limit. EU rows from IEC 60204-1 Table 6 (IEC 60364-5-52),
  US rows from NFPA 79 Table 12.5.1 / NEC 310.16, 402.5 and 400.5(A) [verify].
* ``calckit/data/earthing.yaml`` — the system earthing arrangements of IEC 60364-1 §312.2
  (TN-S, TN-C-S, TT, IT) and what a Class I product must provide in each [verify].
* ``calckit/data/wire_colours.yaml`` — conductor colours by region and role (IEC 60445,
  HD 308, IEC 60204-1; NEC 200.6, 250.119, NFPA 79) [verify].

An id, code or (region, role) the tables do not hold raises :class:`ValueError` naming the
known ones: unlike a screening lookup, a wiring model that names a conductor nobody has
on file is a typo in the model, and the message says what to write instead. A region with
no conductors returns an empty list, as :func:`napkin2factory.calckit.power.circuit_rows`
does; the caller warns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from napkin2factory.calckit._tables import load_table
from napkin2factory.core.units import Quantity

#: A pint quantity from the shared registry (pint is untyped for mypy).
Qty = Any


@dataclass(frozen=True)
class Conductor:
    """One copper conductor of ``conductors.yaml``.

    Attributes:
        id: the row's id (``cu-2p5-pvc``, ``awg14-mtw``), what a connection names.
        region: the region code whose tables rate it (``EU``, ``US``).
        label: a plain name for the owner and the schedule.
        csa: cross-sectional area (mm²).
        ampacity: the current it may carry continuously on :attr:`basis` (A).
        ambient: the ambient temperature the ampacity assumes (degC).
        basis: the installation method, column and conditions the ampacity assumes.
        insulation: the insulation and its class.
        max_temp: the insulation's conductor temperature limit (degC).
        kind: ``panel`` (inside an enclosure or machine), ``cord`` or ``high-temp``.
        awg: the American Wire Gauge size (US rows), else ``None``.
        source: the table the numbers come from.
        verify: the row still needs a person's confirmation.
    """

    id: str
    region: str
    label: str
    csa: Qty
    ampacity: Qty
    ambient: Qty
    basis: str
    insulation: str
    max_temp: Qty
    kind: str
    awg: int | None
    source: str
    verify: bool


@dataclass(frozen=True)
class Earthing:
    """One system earthing arrangement of ``earthing.yaml``.

    Attributes:
        code: the IEC letter code (``TN-S``, ``TN-C-S``, ``TT``, ``IT``).
        label: the code as printed for the owner.
        description: one line on how the arrangement is built.
        class_i: what a Class I product must provide on such a supply.
        source: the standard's clauses.
        verify: the row still needs a person's confirmation.
    """

    code: str
    label: str
    description: str
    class_i: str
    source: str
    verify: bool


@dataclass(frozen=True)
class WireColour:
    """One conductor colour of ``wire_colours.yaml``.

    Attributes:
        region: the region code (``EU``, ``US``).
        role: ``L``, ``L1``–``L3``, ``N``, ``PE``, ``control-ac``, ``control-dc`` or
            ``interlock-external``.
        colour: the colour name (``brown``, ``green-and-yellow``).
        label: what the role means, in plain words.
        source: the standard's clause.
        verify: the row still needs a person's confirmation.
    """

    region: str
    role: str
    colour: str
    label: str
    source: str
    verify: bool


def _conductor(row: dict[str, Any]) -> Conductor:
    awg = row.get("awg")
    return Conductor(
        id=str(row["id"]),
        region=str(row["region"]),
        label=str(row["label"]),
        csa=Quantity(float(row["csa"]), "mm**2"),
        ampacity=Quantity(float(row["ampacity"]), "A"),
        ambient=Quantity(float(row["ambient"]), "degC"),
        basis=str(row["basis"]),
        insulation=str(row["insulation"]),
        max_temp=Quantity(float(row["max_temp"]), "degC"),
        kind=str(row["kind"]),
        awg=None if awg is None else int(awg),
        source=str(row["source"]),
        verify=bool(row["verify"]),
    )


def all_conductors() -> list[Conductor]:
    """Every row of ``conductors.yaml``, in file order."""
    return [_conductor(r) for r in load_table("conductors")]


def conductor(conductor_id: str) -> Conductor:
    """The conductor whose id is ``conductor_id`` (exact match).

    Raises:
        ValueError: no row has that id; the message lists the ids on file.
    """
    rows = all_conductors()
    for c in rows:
        if c.id == conductor_id:
            return c
    raise ValueError(
        f"no conductor {conductor_id!r} on file; known conductors: {', '.join(c.id for c in rows)}"
    )


def conductors(region: str) -> list[Conductor]:
    """The conductors rated by ``region``'s tables (case-insensitive); may be empty."""
    code = region.strip().upper()
    return [c for c in all_conductors() if c.region.upper() == code]


def all_earthing() -> list[Earthing]:
    """Every row of ``earthing.yaml``, in file order."""
    return [
        Earthing(
            code=str(r["code"]),
            label=str(r["label"]),
            description=str(r["description"]),
            class_i=str(r["class_i"]),
            source=str(r["source"]),
            verify=bool(r["verify"]),
        )
        for r in load_table("earthing")
    ]


def earthing(code: str) -> Earthing:
    """The earthing arrangement ``code`` (``TN-S``, ``tn-c-s`` …; case-insensitive).

    Raises:
        ValueError: the code is not on file; the message lists the known codes.
    """
    rows = all_earthing()
    wanted = code.strip().upper()
    for e in rows:
        if e.code.upper() == wanted:
            return e
    raise ValueError(
        f"no earthing arrangement {code!r} on file; known arrangements: "
        f"{', '.join(e.code for e in rows)}"
    )


def all_colours() -> list[WireColour]:
    """Every row of ``wire_colours.yaml``, in file order."""
    return [
        WireColour(
            region=str(r["region"]),
            role=str(r["role"]),
            colour=str(r["colour"]),
            label=str(r["label"]),
            source=str(r["source"]),
            verify=bool(r["verify"]),
        )
        for r in load_table("wire_colours")
    ]


def colour(region: str, role: str) -> WireColour:
    """The conductor colour for ``role`` in ``region`` (region case-insensitive, role exact).

    Raises:
        ValueError: no row for that pair; the message lists the pairs on file.
    """
    rows = all_colours()
    code = region.strip().upper()
    for c in rows:
        if c.region.upper() == code and c.role == role:
            return c
    raise ValueError(
        f"no conductor colour for role {role!r} in region {region!r}; known: "
        f"{', '.join(f'{c.region} {c.role}' for c in rows)}"
    )
