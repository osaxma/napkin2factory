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

An id, code, (region, role) or region the tables do not hold raises :class:`ValueError` naming the
table and the known ones (W7): unlike a screening lookup, a wiring model that names a conductor,
earthing arrangement or region nobody has on file is an error, and the message says what to write.
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
        region: the region code whose standards define it (``EU``, ``UK``, ``US``).
        code: the arrangement code (``TN-S``, ``TN-C-S``, ``TT``, ``IT``, ``solidly-grounded``).
        label: the code as printed for the owner.
        description: one line on how the arrangement is built.
        class_i: what a Class I product must provide on such a supply.
        source: the standard's clauses.
        verify: the row still needs a person's confirmation.
    """

    region: str
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
    """The conductors rated by ``region``'s tables (case-insensitive).

    Raises:
        ValueError: table has no rows for ``region``; names the table and its known regions (W7).
    """
    rows = all_conductors()
    code = region.strip().upper()
    matched = [c for c in rows if c.region.upper() == code]
    if not matched:
        known = sorted({c.region for c in rows})
        msg = (
            f"table 'conductors' has no rows for region {region!r}; "
            f"known regions: {', '.join(known)}"
        )
        raise ValueError(msg)
    return matched


def all_earthing(region: str | None = None) -> list[Earthing]:
    """Every row of ``earthing.yaml``, in file order, optionally filtered by ``region`` (W7).

    Raises:
        ValueError: when ``region`` is given and ``earthing.yaml`` holds no rows for it.
    """
    rows = [
        Earthing(
            region=str(r["region"]),
            code=str(r["code"]),
            label=str(r["label"]),
            description=str(r["description"]),
            class_i=str(r["class_i"]),
            source=str(r["source"]),
            verify=bool(r["verify"]),
        )
        for r in load_table("earthing")
    ]
    if region is None:
        return rows
    code = region.strip().upper()
    matched = [e for e in rows if e.region.upper() == code]
    if not matched:
        known = sorted({e.region for e in rows})
        raise ValueError(
            f"table 'earthing' has no rows for region {region!r}; known regions: {', '.join(known)}"
        )
    return matched


def earthing(code: str, region: str | None = None) -> Earthing:
    """The earthing arrangement ``code``, optionally within ``region`` (case-insensitive, W7).

    A product with no region specified keeps today's behaviour by searching across all
    known earthing arrangements (W11).

    Raises:
        ValueError: the region is unknown to ``earthing.yaml``, or the code is not on file.
    """
    rows = all_earthing(region)
    wanted = code.strip().upper()
    for e in rows:
        if e.code.upper() == wanted:
            return e
    if region is not None:
        known_codes = sorted({e.code for e in rows})
        raise ValueError(
            f"no earthing arrangement {code!r} on file for region {region!r}; known arrangements: "
            f"{', '.join(known_codes)}"
        )
    all_codes = sorted({e.code for e in rows})
    raise ValueError(
        f"no earthing arrangement {code!r} on file; known arrangements: {', '.join(all_codes)}"
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
    """The conductor colour for ``role`` in ``region`` (region case-insensitive, role exact, W7).

    Raises:
        ValueError: no rows for that region, or no colour for that role in the region.
    """
    rows = all_colours()
    code = region.strip().upper()
    region_rows = [c for c in rows if c.region.upper() == code]
    if not region_rows:
        known = sorted({c.region for c in rows})
        msg = (
            f"table 'wire_colours' has no rows for region {region!r}; "
            f"known regions: {', '.join(known)}"
        )
        raise ValueError(msg)
    for c in region_rows:
        if c.role == role:
            return c
    raise ValueError(
        f"no conductor colour for role {role!r} in region {region!r}; known for this region: "
        f"{', '.join(c.role for c in region_rows)}"
    )


def known_regions() -> list[str]:
    """All region codes known across the wiring and circuit tables, sorted (W7)."""
    regions: set[str] = set()
    regions.update(c.region for c in all_conductors())
    regions.update(c.region for c in all_colours())
    regions.update(e.region for e in all_earthing())
    try:
        from napkin2factory.calckit._tables import load_table

        for row in load_table("circuits"):
            if "region" in row:
                regions.add(str(row["region"]))
    except Exception:
        pass
    return sorted(regions)
