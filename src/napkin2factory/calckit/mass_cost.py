"""Envelope mass, cost bands, manual-handling class and stock-sheet fit.

* Mass is volume × the nominal density of :mod:`napkin2factory.geometry.materials`
  (handbook values, sourced from ``calckit/data/materials.yaml``).
* Cost, lift class and stock sheets come from the data tables under ``calckit/data``
  (``cost_bands``, ``lift_classes``, ``stock_sheets``); every row carries a ``source``
  and ``verify: true`` and DECISIONS.md lists them as [verify]. A process class or
  material class the tables do not know returns an ``unknown`` result (callers warn,
  never fail). A specified region with no rows in the table fails loudly (W3, W7); no
  region means the US rows (:data:`DEFAULT_REGION`) and callers say so (S-227).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from napkin2factory.calckit._cases import Case
from napkin2factory.calckit._tables import load_table
from napkin2factory.core.units import Quantity
from napkin2factory.geometry.materials import density_kg_m3

#: A pint quantity from the shared registry (pint is untyped for mypy).
Qty = Any

#: The bands read when a product declares no region; the cost line says so (S-227).
DEFAULT_REGION = "US"


def density(material: str) -> tuple[Qty, str]:
    """Nominal density of a material name and its source (kg/m³).

    Uses :func:`napkin2factory.geometry.materials.density_kg_m3`: first substring match
    in its table (stainless, mild steel, aluminium, K23, ceramic fiber, …); an unknown
    name falls back to mild steel and the source string says so.
    """
    rho, src = density_kg_m3(material)
    return Quantity(rho, "kg/m**3"), src


def mass(volume: Qty, material: str) -> Qty:
    """Mass of ``volume`` of ``material``, ``m = V · ρ`` (kg); see :func:`density`."""
    rho, _ = density(material)
    return (volume.to("m**3") * rho).to("kg")


@dataclass(frozen=True)
class CostBand:
    """A dated regional cost band for one process class (W3).

    Attributes:
        process_class: process class name (e.g. ``sheet-metal``, ``woodworking``).
        unit: rate basis: ``per_kg``, ``per_m``, ``per_m2``, or ``per_item``.
        low: lower bound rate per unit.
        high: upper bound rate per unit.
        currency: currency code (e.g. ``USD``).
        region: supply region (e.g. ``US``, ``EU``).
        as_of: date of rate as YYYY-MM.
        stale: True when the band is older than 24 months.
        source: provenance description.
        known: False when no band exists for the process class.
        verify: True when the band still needs human confirmation.
    """

    process_class: str
    unit: str = "per_kg"
    low: float | None = None
    high: float | None = None
    currency: str = "USD"
    region: str = "US"
    as_of: str = ""
    stale: bool = False
    source: str = ""
    known: bool = True
    verify: bool = True


def _is_stale(as_of: str, today: dt.date | None = None) -> bool:
    """Whether a YYYY-MM date is older than 24 months from today (W3)."""
    if not as_of:
        return False
    try:
        parts = as_of.strip().split("-")
        year, month = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return False
    now = today or dt.date.today()
    months_old = (now.year - year) * 12 + (now.month - month)
    return months_old > 24


def cost_band(
    process_class: str,
    region: str | None = None,
    today: dt.date | None = None,
) -> CostBand:
    """The dated regional cost band for ``process_class`` (W3).

    Reads ``calckit/data/cost_bands.yaml``.

    Args:
        process_class: the manufacturing process class to price.
        region: optional region code (e.g. ``"US"``, ``"EU"``). When ``None``, the
            :data:`DEFAULT_REGION` rows are read (the first rows on file were always the US
            ones); callers whose owner did not declare a region say so (S-227). When
            specified, fails loudly naming the table and its regions if the table holds no
            rows for that region.
        today: reference date for the 24-month staleness check (defaults to today).

    Returns:
        A :class:`CostBand` representing the matching band, marked ``stale`` if
        older than 24 months, or with ``known=False`` if the process class has no band.

    Raises:
        ValueError: ``region`` is given but no row in ``cost_bands.yaml`` has that region.
    """
    rows = load_table("cost_bands")
    all_regions = sorted({str(r["region"]) for r in rows if r.get("region")})
    reg_code = (region if region is not None else DEFAULT_REGION).strip().upper()
    if region is not None and reg_code not in {r.upper() for r in all_regions}:
        raise ValueError(
            f"table 'cost_bands' has no rows for region {region!r}; "
            f"regions on file: {', '.join(all_regions)}"
        )
    matching = [
        r
        for r in rows
        if r["process_class"] == process_class and str(r.get("region", "")).upper() == reg_code
    ]

    if not matching:
        return CostBand(
            process_class=process_class,
            low=None,
            high=None,
            region=reg_code,  # the region asked for, not the dataclass default (gate I, B2)
            source="",
            as_of="",
            stale=False,
            known=False,
        )

    row = matching[0]
    as_of = str(row.get("as_of", ""))
    stale = _is_stale(as_of, today=today)
    lo = float(row["low"]) if "low" in row else float(row["low_usd"])
    hi = float(row["high"]) if "high" in row else float(row["high_usd"])
    return CostBand(
        process_class=str(row["process_class"]),
        unit=str(row.get("unit", "per_kg")),
        low=lo,
        high=hi,
        currency=str(row.get("currency", "USD")),
        region=str(row.get("region", "US")),
        as_of=as_of,
        stale=stale,
        source=str(row.get("source", "")),
        known=True,
        verify=bool(row.get("verify", True)),
    )


def band_regions() -> list[str]:
    """The region codes ``cost_bands.yaml`` has rows for, sorted."""
    return sorted({str(r["region"]).upper() for r in load_table("cost_bands") if r.get("region")})


def bands_words(bands: Sequence[CostBand], *, declared: bool = True) -> str:
    """The region and date of the bands a cost was read from, in the owner's words (S-227).

    ``US cost bands, as of 2026-10 to 2026-11``; ``, stale`` is added only when a band is
    older than 24 months; ``declared=False`` (the product named no region) adds
    ``, no region declared`` so a US default is never silent. No bands: an empty string.
    """
    if not bands:
        return ""
    regions = sorted({b.region for b in bands if b.region})
    dates = sorted({b.as_of for b in bands if b.as_of})
    text = "/".join(regions or [DEFAULT_REGION]) + " cost bands"
    if dates:
        text += f", as of {dates[0]}" + (f" to {dates[-1]}" if len(dates) > 1 else "")
    if any(b.stale for b in bands):
        text += ", stale"
    if not declared:
        text += ", no region declared"
    return text


@dataclass(frozen=True)
class CostEstimate:
    """A cost band for one process class.

    Attributes:
        low: lower bound (currency), ``None`` when the class is unknown.
        high: upper bound (currency), ``None`` when the class is unknown.
        basis: how the band was computed, in words.
        source: the table row's source.
        known: ``False`` when the process class is not in ``cost_bands.yaml``.
        verify: the table row still needs a person's confirmation.
    """

    low: Qty | None
    high: Qty | None
    basis: str
    source: str
    known: bool = True
    verify: bool = True


def cost_estimate(
    process_class: str,
    mass: Qty | None = None,
    area: Qty | None = None,
    length: Qty | None = None,
    count: int = 1,
    region: str | None = None,
    today: dt.date | None = None,
) -> CostEstimate:
    """Cost band for ``count`` items of one process class at quantity 1 (W3).

    Reads ``calckit/data/cost_bands.yaml`` via :func:`cost_band`:
    ``per_kg`` multiplies by ``mass``, ``per_m2`` by ``area``, ``per_m`` by ``length``,
    ``per_item`` by ``count`` alone.

    Raises:
        ValueError: the row needs a mass, area, or length that was not given, or
            the region has no rows in the table.
    """
    band = cost_band(process_class, region=region, today=today)
    if not band.known or band.low is None or band.high is None:
        return CostEstimate(
            low=None,
            high=None,
            basis=f"unknown process class {process_class!r}: no cost band on file",
            source="",
            known=False,
        )

    unit = band.unit
    lo, hi = band.low, band.high
    currency = band.currency
    if unit == "per_kg":
        if mass is None:
            raise ValueError(f"cost band {process_class!r} is per kg; pass mass=")
        qty, what = float(mass.to("kg").magnitude), f"{mass.to('kg'):~.3gP}"
        rate = f"{currency}/kg"
    elif unit == "per_m2":
        if area is None:
            raise ValueError(f"cost band {process_class!r} is per m²; pass area=")
        qty, what = float(area.to("m**2").magnitude), f"{area.to('m**2'):~.3gP}"
        rate = f"{currency}/m²"
    elif unit == "per_m":
        if length is None:
            raise ValueError(f"cost band {process_class!r} is per m; pass length=")
        qty, what = float(length.to("m").magnitude), f"{length.to('m'):~.3gP}"
        rate = f"{currency}/m"
    elif unit == "per_item":
        qty, what, rate = 1.0, "1 item", f"{currency}/item"
    else:
        raise ValueError(f"cost band {process_class!r} has unknown unit {unit!r}")

    return CostEstimate(
        low=Quantity(lo * qty * count, currency),
        high=Quantity(hi * qty * count, currency),
        basis=f"estimate: {lo:g}–{hi:g} {rate} × {what} × {count}",
        source=band.source,
        known=True,
        verify=band.verify,
    )


@dataclass(frozen=True)
class LiftVerdict:
    """Manual-handling class of a mass.

    Attributes:
        label: ``one-person``, ``two-person`` or ``equipment`` (per the table).
        mass: the mass asked about (kg).
        max_mass: the class's upper bound (kg), ``None`` for the open-ended class.
        source: the table row's source.
        verify: the table row still needs a person's confirmation.
    """

    label: str
    mass: Qty
    max_mass: Qty | None
    source: str
    verify: bool = True


def lift_class(mass: Qty) -> LiftVerdict:
    """The lightest handling class whose limit covers ``mass``.

    Reads ``calckit/data/lift_classes.yaml``: UK HSE manual-handling guideline weights
    (INDG143 / L23: 25 kg one person close to the body at waist height, two-thirds of
    the sum for a team of two) — a screening filter, not a safe limit [verify].
    """
    kg = float(mass.to("kg").magnitude)
    rows = load_table("lift_classes")
    for row in rows:
        limit = row.get("max_kg")
        if limit is None or kg <= float(limit):
            return LiftVerdict(
                label=str(row["label"]),
                mass=mass.to("kg"),
                max_mass=None if limit is None else Quantity(float(limit), "kg"),
                source=str(row["source"]),
                verify=bool(row["verify"]),
            )
    last = rows[-1]
    return LiftVerdict(
        label=str(last["label"]),
        mass=mass.to("kg"),
        max_mass=Quantity(float(last["max_kg"]), "kg"),
        source=str(last["source"]),
        verify=bool(last["verify"]),
    )


@dataclass(frozen=True)
class StockVerdict:
    """Whether a flat blank fits a stock sheet.

    Attributes:
        fits: some stock sheet holds the blank (either way round).
        sheet: the smallest sheet (by area) that holds it, or ``None``.
        fitting: labels of every sheet that holds it, smallest first.
        known: ``False`` when the material class is not in ``stock_sheets.yaml``.
        source: the chosen row's source (empty when nothing fits or unknown).
        message: one plain sentence for the owner.
        verify: the table rows still need a person's confirmation.
    """

    fits: bool
    sheet: str | None
    fitting: list[str] = field(default_factory=list)
    known: bool = True
    source: str = ""
    message: str = ""
    verify: bool = True


def stock_sheet_fits(
    blank: tuple[Qty, Qty],
    material_class: str = "mild-steel",
    margin: Qty | None = None,
) -> StockVerdict:
    """Does a developed (flat) blank fit a common stock sheet of ``material_class``?

    Reads ``calckit/data/stock_sheets.yaml`` (common stockist formats, e.g. 1000 × 2000,
    1220 × 2440, 1250 × 2500, 1500 × 3000 mm for mild steel) [verify]. The blank fits a
    sheet when it does either way round, after adding ``margin`` (default none) to each
    side of the blank.

    Args:
        blank: the flat blank's two dimensions.
        material_class: ``mild-steel``, ``stainless-steel`` or ``aluminium``.
        margin: optional edge margin added on every side of the blank.
    """
    extra = 0.0 if margin is None else 2 * float(margin.to("mm").magnitude)
    a, b = (float(x.to("mm").magnitude) + extra for x in blank)
    small, large = min(a, b), max(a, b)
    rows = [r for r in load_table("stock_sheets") if r["material_class"] == material_class]
    if not rows:
        return StockVerdict(
            fits=False,
            sheet=None,
            known=False,
            message=f"no stock sheet sizes on file for {material_class!r}",
        )
    ok = [
        r
        for r in rows
        if small <= min(float(r["width_mm"]), float(r["length_mm"]))
        and large <= max(float(r["width_mm"]), float(r["length_mm"]))
    ]
    ok.sort(key=lambda r: float(r["width_mm"]) * float(r["length_mm"]))
    if not ok:
        biggest = max(rows, key=lambda r: float(r["width_mm"]) * float(r["length_mm"]))
        return StockVerdict(
            fits=False,
            sheet=None,
            message=(
                f"blank {large:g} × {small:g} mm does not fit any {material_class} stock "
                f"sheet on file (largest {biggest['label']})"
            ),
        )
    return StockVerdict(
        fits=True,
        sheet=str(ok[0]["label"]),
        fitting=[str(r["label"]) for r in ok],
        source=str(ok[0]["source"]),
        message=f"blank {large:g} × {small:g} mm fits a {ok[0]['label']} sheet",
        verify=all(bool(r["verify"]) for r in ok),
    )


# --- reference cases (F17) -------------------------------------------------------------

#: Every public function's reference cases; ``external`` ones come from a published source.
CASES: list[Case] = [
    Case(
        "density",
        Quantity(7850, "kg/m**3"),
        "EN 1993-1-1 (Eurocode 3: design of steel structures, general rules), clause 3.2.6, "
        "design values of material coefficients for structural steel: density 7850 kg/m3",
        args=("mild steel",),
        pick="0",
        rel=1e-12,
        external=True,
        verify=True,
    ),
    Case(
        "mass",
        Quantity(4.8, "kg"),
        "hand computation: 10 L of insulating firebrick at 480 kg/m3 (calckit/data/"
        "materials.yaml) = 0.010 x 480 = 4.8 kg",
        args=(Quantity(10, "L"), "K23 insulating firebrick"),
        rel=1e-12,
    ),
    Case(
        "cost_band",
        8.0,
        "calckit/data/cost_bands.yaml, sheet-metal in US: 8.0-67.6 USD/kg",
        args=("sheet-metal",),
        kwargs={"region": "US"},
        pick="low",
        rel=1e-12,
    ),
    Case(
        "band_regions",
        ["EU", "US"],
        "hand count of the region column in calckit/data/cost_bands.yaml: EU and US rows",
    ),
    Case(
        "bands_words",
        "EU cost bands, as of 2026-11, stale, no region declared",
        "hand computation: one EU band dated 2026-11 and marked stale, read with no region "
        "declared, in the words of the cost line",
        args=([CostBand("sheet-metal", region="EU", as_of="2026-11", stale=True)],),
        kwargs={"declared": False},
    ),
    Case(
        "cost_estimate",
        Quantity(752, "USD"),
        "calckit/data/cost_bands.yaml, cut-block 18.8-40.1 USD/kg: 18.8 x 40 kg = 752 USD "
        "(the low end of the band)",
        args=("cut-block",),
        kwargs={"mass": Quantity(40, "kg")},
        pick="low",
        rel=1e-12,
    ),
    Case(
        "lift_class",
        "two-person",
        "calckit/data/lift_classes.yaml (UK HSE INDG143 guideline weights): 30 kg is over "
        "25 kg for one person and within 33 kg for two",
        args=(Quantity(30, "kg"),),
        pick="label",
    ),
    Case(
        "stock_sheet_fits",
        "1220 x 2440 mm (4 x 8 ft)",
        "calckit/data/stock_sheets.yaml, mild steel: a 1770 x 1100 mm blank is too wide for "
        "1000 x 2000 (1100 > 1000) and fits 1220 x 2440 (1100 <= 1220, 1770 <= 2440)",
        args=((Quantity(1770, "mm"), Quantity(1100, "mm")),),
        pick="sheet",
    ),
]


__all__ = [
    "CASES",
    "CostBand",
    "CostEstimate",
    "DEFAULT_REGION",
    "LiftVerdict",
    "StockVerdict",
    "band_regions",
    "bands_words",
    "cost_band",
    "cost_estimate",
    "density",
    "lift_class",
    "mass",
    "stock_sheet_fits",
]
