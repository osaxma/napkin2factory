"""Envelope mass, cost bands, manual-handling class and stock-sheet fit.

* Mass is volume × the nominal density of :mod:`napkin2factory.geometry.materials`
  (handbook values, sourced per row there).
* Cost, lift class and stock sheets come from the data tables under ``calckit/data``
  (``cost_bands``, ``lift_classes``, ``stock_sheets``); every row carries a ``source``
  and ``verify: true`` and DECISIONS.md lists them as [verify]. A process class or
  material class the tables do not know returns an ``unknown`` result (callers warn,
  never fail).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from napkin2factory.calckit._tables import load_table
from napkin2factory.core.units import Quantity
from napkin2factory.geometry.materials import density_kg_m3

#: A pint quantity from the shared registry (pint is untyped for mypy).
Qty = Any


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
class CostEstimate:
    """A cost band for one process class.

    Attributes:
        low: lower bound (USD), ``None`` when the class is unknown.
        high: upper bound (USD), ``None`` when the class is unknown.
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
    count: int = 1,
) -> CostEstimate:
    """Cost band for ``count`` items of one process class at quantity 1 (USD).

    Reads ``calckit/data/cost_bands.yaml`` (rows ``{process_class, unit: per_kg |
    per_m2 | per_item, low_usd, high_usd, source, verify}``): ``per_kg`` multiplies by
    ``mass``, ``per_m2`` by ``area``, ``per_item`` by ``count`` alone. The bands are
    first derived from the kiln's own per-part estimates (DEC-012) [verify].

    Raises:
        ValueError: the row needs a mass or an area that was not given.
    """
    rows = [r for r in load_table("cost_bands") if r["process_class"] == process_class]
    if not rows:
        return CostEstimate(
            low=None,
            high=None,
            basis=f"unknown process class {process_class!r}: no cost band on file",
            source="",
            known=False,
        )
    row = rows[0]
    unit = str(row["unit"])
    lo, hi = float(row["low_usd"]), float(row["high_usd"])
    if unit == "per_kg":
        if mass is None:
            raise ValueError(f"cost band {process_class!r} is per kg; pass mass=")
        qty, what = float(mass.to("kg").magnitude), f"{mass.to('kg'):~.3gP}"
        rate = "USD/kg"
    elif unit == "per_m2":
        if area is None:
            raise ValueError(f"cost band {process_class!r} is per m²; pass area=")
        qty, what = float(area.to("m**2").magnitude), f"{area.to('m**2'):~.3gP}"
        rate = "USD/m²"
    elif unit == "per_item":
        qty, what, rate = 1.0, "1 item", "USD/item"
    else:
        raise ValueError(f"cost band {process_class!r} has unknown unit {unit!r}")
    return CostEstimate(
        low=Quantity(lo * qty * count, "USD"),
        high=Quantity(hi * qty * count, "USD"),
        basis=f"estimate: {lo:g}–{hi:g} {rate} × {what} × {count}",
        source=str(row["source"]),
        verify=bool(row["verify"]),
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


__all__ = [
    "CostEstimate",
    "LiftVerdict",
    "StockVerdict",
    "cost_estimate",
    "density",
    "lift_class",
    "mass",
    "stock_sheet_fits",
]
