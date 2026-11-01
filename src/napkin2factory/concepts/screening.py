"""Concept screening: labelled numbers, the ``concept-v0`` rules and a verdict (N5).

Screening is a third tier, distinct from verification. Every number it writes carries a
label at the data level:

* ``computed`` — measured from the massing silhouettes (bounding box, volume, mass from
  declared materials, footprint with the door swing);
* ``estimate`` — from the calc kit (:mod:`napkin2factory.calckit`) fed with the card's
  envelope numbers;
* ``given`` — the card's own inputs echoed back (``envelope.power``, ``site.circuit``):
  neither measured nor estimated (review gate A, C1). A verdict built on them (does the
  power fit the circuit?) is still an estimate.

Each value's ``source`` says where it comes from in the owner's words (a ``[verify]`` tag
reads "to be checked"); its ``ref`` names the calc-kit function or rule parameters for
engineers (``--json`` and the card only, never the board — review gate B, B2).

Missing inputs never become invented numbers: the estimate is omitted and a note says what
would unlock it. A red verdict is information — written to the card with its reasons,
never hidden.

Defaults screening states when the card is silent (all from the kiln's own parameters,
``examples/kiln/model/parameters.yaml``, and tagged [verify] in DECISIONS.md): room
25 degC; skin film coefficient 5 W/m²K (natural convection); skin emissivity 0.9 (powder
coat); hot face 1200 degC. Layer materials come from one row each in
``calckit/data/materials.yaml`` (the table the massing densities read too): a bare
``insulation: <thickness>`` is one ceramic-fiber-board layer (k 0.15 W/m·K, ρ 260 kg/m³,
c 1050 J/kg·K); named layers matching ``brick``/``K23`` take K23 firebrick values (k 0.25
W/m·K, ρ 480 kg/m³, c 1000 J/kg·K); ``shell``/``sheet`` layers grow the box but carry no
resistance and store no heat. A hinged door counts what its leaf reaches past the hinge at
the card's opening angle θ (``leaf × max(0, −cos θ)``); a card that gives no angle counts the
leaf swung fully back (the widest case) and a note says so.

A re-screen that finds exactly what the card already says keeps the card's ``at``
(:func:`keep_unchanged_at`), so rebuilding an unchanged card leaves its file alone (S-086).
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from napkin2factory.core.concepts import QUANTITY_KINDS, card_quantity, wrong_kind
from napkin2factory.core.model.concepts import ConceptCard, LabelledValue, Screening
from napkin2factory.core.units import Quantity, is_quantity

Qty = Any

T_AMBIENT = Quantity(25.0, "degC")
H_OUTER = Quantity(5.0, "W/(m**2*K)")
EMISSIVITY = Quantity(0.9, "")
MAX_TEMPERATURE = Quantity(1200.0, "degC")
THERMAL_SOURCE = "kiln parameters: room 25 degC, h 5 W/m²K, ε 0.9 [verify]"


@dataclass(frozen=True)
class LayerMaterial:
    """Default properties for a named insulation layer."""

    keywords: tuple[str, ...]
    conductivity: float | None  # W/(m·K); None = resistance neglected
    density: float | None  # kg/m³; None = stores nothing, no mass counted
    specific_heat: float | None  # J/(kg·K)
    process_class: str | None  # cost band; None = carried by the massing
    source: str


def _table_material(name: str) -> LayerMaterial:
    """One row of ``calckit/data/materials.yaml`` as a layer default (review gate A, C4)."""
    from napkin2factory.calckit._tables import load_table

    row = next(r for r in load_table("materials") if r["name"] == name)

    def num(key: str) -> float | None:
        return None if row.get(key) is None else float(row[key])

    k, rho, c = num("conductivity"), num("density"), num("specific_heat")
    return LayerMaterial(
        tuple(str(w) for w in row["keywords"]),
        k,
        rho,
        c,
        row.get("process_class"),
        f"{row['name']}: k {k:g}, ρ {rho:g}, c {c:g} (calckit/data/materials.yaml) [verify]",
    )


LAYER_MATERIALS: tuple[LayerMaterial, ...] = (
    _table_material("K-23 insulating firebrick"),
    _table_material("ceramic fiber board (Kaowool 1260)"),
    LayerMaterial(
        ("shell", "sheet", "skin", "steel", "casing", "case"),
        None,
        None,
        None,
        None,
        "sheet shell: grows the box, no resistance, no stored heat (the massing carries it)",
    ),
)
FIBER_BOARD = LAYER_MATERIALS[1]


@dataclass
class ScreenLayer:
    """One parsed insulation layer."""

    name: str
    thickness: Qty
    clearance: Qty | None
    conductivity: Qty | None
    density: Qty | None
    specific_heat: Qty | None
    process_class: str | None
    known: bool  # conductivity known (or deliberately neglected)


def _length(v: Any) -> Qty | None:
    if not is_quantity(v):
        return None
    try:
        v.to("mm")
    except Exception:  # pint DimensionalityError
        return None
    return v


def _default_for(text: str) -> LayerMaterial | None:
    low = text.lower()
    return next((m for m in LAYER_MATERIALS if any(k in low for k in m.keywords)), None)


def parse_layers(card: ConceptCard, notes: list[str]) -> list[ScreenLayer] | None:
    """``envelope.insulation`` as wall layers, hot face first; ``None`` (with a note) if absent."""
    ins = card.envelope.get("insulation")
    if ins is None:
        return None
    t = _length(ins)
    if t is not None:
        fb = FIBER_BOARD
        return [
            ScreenLayer(
                "fiber board",
                t,
                None,
                Quantity(fb.conductivity, "W/(m*K)"),
                Quantity(fb.density, "kg/m**3"),
                Quantity(fb.specific_heat, "J/(kg*K)"),
                fb.process_class,
                True,
            )
        ]
    if not isinstance(ins, list) or not all(isinstance(x, dict) for x in ins):
        notes.append(
            "the insulation cannot be read: give one thickness (like 170 mm), or a list of "
            "named layers, each with a thickness (and how well it conducts heat, unless it is "
            "brick or fiber)"
        )
        return None
    layers: list[ScreenLayer] = []
    for i, item in enumerate(ins):
        name = str(item.get("name") or f"layer {i + 1}")
        thickness = _length(item.get("thickness"))
        if thickness is None:
            notes.append(f"insulation layer {i + 1} ({name}) needs a thickness, like 64 mm")
            return None
        m = _default_for(f"{name} {item.get('material', '')}")
        k = item.get("conductivity")
        if is_quantity(k):
            known = True
        elif m is not None:
            k = None if m.conductivity is None else Quantity(m.conductivity, "W/(m*K)")
            known = True
        else:
            k, known = None, False
        rho = item.get("density")
        if not is_quantity(rho):
            rho = None if m is None or m.density is None else Quantity(m.density, "kg/m**3")
        cp = item.get("specific_heat")
        if not is_quantity(cp):
            cp = (
                None
                if m is None or m.specific_heat is None
                else Quantity(m.specific_heat, "J/(kg*K)")
            )
        layers.append(
            ScreenLayer(
                name,
                thickness,
                _length(item.get("clearance")),
                k,
                rho,
                cp,
                m.process_class if m is not None else None,
                known,
            )
        )
    return layers


# --- formatting ---------------------------------------------------------------------


def _sig(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}g}" if abs(x) < 10**digits else f"{x:.0f}"


def fmt(q: Qty, unit: str) -> str:
    """A screening value as text (``995 mm``, ``2.5 kW``, ``7.1 h``, ``1840 USD``)."""
    x = float(q.to(unit).magnitude)
    if unit == "mm":
        return f"{x:.0f} mm"
    if unit == "W":
        return f"{_sig(x / 1000)} kW" if abs(x) >= 1000 else f"{x:.0f} W"
    if unit == "degC":
        return f"{x:.0f} degC"
    if unit == "USD":
        return f"{x:.0f} USD"
    if unit == "hour":
        return f"{x:.2g} h" if x < 10 else f"{x:.0f} h"
    if unit == "MJ":
        return f"{_sig(x)} MJ"
    if unit == "A":
        return f"{x:.1f} A"
    if unit == "L":
        return f"{_sig(x)} L"
    if unit == "kg":
        return f"{_sig(x)} kg"
    return f"{_sig(x)} {unit}"


class _Collector:
    """Raw values for the rules plus their labelled, formatted twins for the card."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.raw: dict[str, Any] = {}
        self.out: dict[str, LabelledValue] = {}

    def add(self, name: str, raw: Any, text: str, source: str, ref: str | None = None) -> None:
        """Record one value: ``source`` in the owner's words, ``ref`` for engineers."""
        self.raw[name] = raw
        self.out[name] = LabelledValue(
            value=text,
            label=self.label,  # type: ignore[arg-type]
            source=source,
            ref=ref,
        )


#: The owner's words for a ``[verify]`` tag at the end of a "where it comes from" sentence.
TO_CHECK = "to be checked"


def _and(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def _the(items: list[str]) -> str:
    """``the body and the door``; three or more: ``the guard, hinge and door``."""
    return "the " + (" and the ".join(items) if len(items) < 3 else _and(items))


def owner_names(names: list[str]) -> list[str]:
    """Call names as words, pieces sharing a prefix grouped: ``guard (5 pieces)``, ``hinge``."""
    words = [n.replace("_", " ").replace("-", " ").strip() for n in names]
    heads = [w.split(" ")[0] for w in words]
    out: list[str] = []
    for w, head in zip(words, heads, strict=True):
        n = heads.count(head)
        item = f"{head} ({n} pieces)" if n > 1 and " " in w else w
        if item not in out:
            out.append(item)
    return out


# --- the screen ---------------------------------------------------------------------


def _box_volume(dims: list[float]) -> float:
    return dims[0] * dims[1] * dims[2]


def _layer_volumes(chamber: list[Qty], layers: list[ScreenLayer]) -> list[float]:
    """Solid volume of each layer (m³): its box less the box inside it (clearance empty)."""
    dims = [float(c.to("m").magnitude) for c in chamber]
    out = []
    for layer in layers:
        c = 0.0 if layer.clearance is None else float(layer.clearance.to("m").magnitude)
        inside = [x + 2 * c for x in dims]
        dims = [x + 2 * (c + float(layer.thickness.to("m").magnitude)) for x in dims]
        out.append(_box_volume(dims) - _box_volume(inside))
    return out


def _temperature(card: ConceptCard, notes: list[str]) -> Qty:
    for section in (card.envelope, card.site):
        t: Any = section.get("max_temperature")
        if is_quantity(t):
            try:
                t.to("degC")
                return t
            except Exception:  # pint DimensionalityError
                break
    notes.append(
        "the card gives no top temperature: the estimates assume 1200 degC inside the chamber"
    )
    return MAX_TEMPERATURE


#: What each card number is, in the owner's words, for a note about one of the wrong kind.
KIND_WORDS: dict[str, str] = {
    "power": "the power",
    "heat_up_time": "the planned heat-up time",
    "max_temperature": "the top temperature",
    "door_swing": "how far the door opens",
    "door_width": "the door width",
    "target_volume": "the volume to hold",
    "alcove_width": "the alcove width",
    "alcove_depth": "the alcove depth",
    "alcove_height": "the alcove height",
    "mass_limit": "the weight limit",
    "touch_limit": "the touch limit",
    "ambient_max": "the hottest room temperature",
}


def _thermal(card: ConceptCard, est: _Collector, extra: dict[str, Any], notes: list[str]) -> None:
    from napkin2factory.calckit import thermal_enclosure as te

    chamber: Any = card.envelope.get("chamber")
    chamber_ok = (
        isinstance(chamber, list)
        and len(chamber) == 3
        and all(_length(c) is not None for c in chamber)
    )
    layers = parse_layers(card, notes)
    if chamber is None and card.envelope.get("insulation") is None:
        notes.append(
            "no chamber size and no insulation on the card: heat loss, heat-up and insulation "
            "mass are not estimated"
        )
        return
    if not chamber_ok:
        if chamber is not None:
            notes.append("the chamber size needs three lengths: width, depth and height")
        elif layers is not None:
            notes.append(
                "add the chamber size (width, depth, height) to estimate heat loss, heat-up and "
                "insulation mass"
            )
        return
    if layers is None:
        notes.append(
            "add the insulation (one thickness, or named layers) to estimate heat loss, heat-up "
            "and insulation mass"
        )
        return
    extra["chamber"] = chamber
    wall = sum(
        ((layer.clearance or Quantity(0, "mm")) + layer.thickness for layer in layers),
        Quantity(0, "mm"),
    )
    extra["wall"] = wall.to("mm")
    # insulation mass (layers with a density)
    volumes = _layer_volumes(chamber, layers)
    ins_mass = 0.0
    for layer, vol in zip(layers, volumes, strict=True):
        if layer.density is not None:
            ins_mass += vol * float(layer.density.to("kg/m**3").magnitude)
    extra["insulation_layers"] = [
        (layer, vol * float(layer.density.to("kg/m**3").magnitude))
        for layer, vol in zip(layers, volumes, strict=True)
        if layer.density is not None
    ]
    if ins_mass > 0:
        est.add(
            "insulation_mass",
            Quantity(ins_mass, "kg"),
            fmt(Quantity(ins_mass, "kg"), "kg"),
            f"from the wall layers' sizes and their materials; {TO_CHECK}",
            "layer volumes × density (" + "; ".join(sorted({_src(lay) for lay in layers})) + ")",
        )
    unknown = [layer.name for layer in layers if not layer.known]
    if unknown:
        noun = "layer conducts" if len(unknown) == 1 else "layers conduct"
        notes.append(
            f"say how well the {_and(unknown)} insulation {noun} heat (a conductivity, "
            "like 0.15 W/(m*K)) to estimate heat loss and heat-up"
        )
        return
    kit_layers = [
        te.Layer(layer.thickness, layer.conductivity, layer.name, clearance=layer.clearance)
        for layer in layers
    ]
    if not any(layer.conductivity is not None for layer in layers):
        notes.append(
            "no insulation layer says how well it conducts heat: give one a conductivity "
            "(like 0.15 W/(m*K)) to estimate heat loss"
        )
        return
    t_hot = _temperature(card, notes)
    res = te.steady_loss(chamber, kit_layers, t_hot, T_AMBIENT, H_OUTER, EMISSIVITY)
    room = f"{float(T_AMBIENT.magnitude):g} °C"
    est.add(
        "heat_loss",
        res.loss,
        fmt(res.loss, "W"),
        f"from the wall layers at the hot-face temperature in a {room} room; {TO_CHECK}",
        f"thermal_enclosure.steady_loss ({THERMAL_SOURCE})",
    )
    est.add(
        "skin_temperature",
        res.outer_skin_temperature,
        fmt(res.outer_skin_temperature, "degC"),
        f"from the heat loss through the outer face; {TO_CHECK}",
        f"thermal_enclosure.steady_loss ({THERMAL_SOURCE})",
    )
    stored = None
    if all(layer.density is not None or layer.conductivity is None for layer in layers):
        stored = te.stored_heat(
            chamber,
            kit_layers,
            [layer.density for layer in layers],
            [layer.specific_heat for layer in layers],
            t_hot,
            T_AMBIENT,
            res.interface_temperatures,
        )
        est.add(
            "stored_heat",
            stored,
            fmt(stored, "MJ"),
            "the heat the walls hold at temperature, from their materials",
            "thermal_enclosure.stored_heat",
        )
    else:
        light = [
            layer.name
            for layer in layers
            if layer.density is None and layer.conductivity is not None
        ]
        noun = "layer has" if len(light) == 1 else "layers have"
        notes.append(
            f"the {_and(light)} insulation {noun} no density (how heavy it is), so the heat "
            "the walls store and the heat-up time are not estimated"
        )
    power = card_quantity(card, "envelope", "power")
    if power is not None:
        extra["power"] = power
        extra["power_label"] = "card"
    if stored is not None and power is not None:
        try:
            t = te.heat_up_time(stored, res.loss, power)
            est.add(
                "heat_up_time",
                t,
                fmt(t, "hour"),
                "from the walls' stored heat and the element power",
                "thermal_enclosure.heat_up_time",
            )
        except ValueError:
            notes.append(
                f"{fmt(power, 'W')} does not exceed the {fmt(res.loss, 'W')} steady loss: "
                "the chamber would never reach temperature"
            )
    target = card_quantity(card, "envelope", "heat_up_time")
    if stored is not None and target is not None:
        p = te.heat_up_power(stored, res.loss, target)
        est.add(
            "required_power",
            p,
            fmt(p, "W"),
            "from the walls' stored heat and heat loss over the planned heat-up time",
            "thermal_enclosure.heat_up_power",
        )
        if "power" not in extra:
            extra["power"] = p
            extra["power_label"] = "estimate"


def _door_words(door: str, basis: str, term: float, angle: float | None) -> str:
    """Where the width with the door open comes from, in the owner's words."""
    if door not in ("hinged-left", "hinged-right"):
        return f"the body only: a {door.replace('-', ' ')} door swings nothing beside it"
    leaf = "the door (its width on the card)" if "on the card" in basis else "the door leaf"
    if angle is not None:
        if term <= 0:
            return f"the body only: {leaf} opens to {angle:g}°, so it stays in front of the body"
        return f"the body plus what {leaf}, opened to {angle:g}°, reaches past the hinge"
    if term <= 0:
        return (
            "the body only: the card gives no door shape or door width, so the open door "
            "is not counted"
        )
    return f"the body plus {leaf} swung fully back beside the hinge"


def _src(layer: ScreenLayer) -> str:
    m = _default_for(layer.name)
    return m.source.split(":")[0] if m is not None else f"{layer.name} as given"


def _supply(
    card: ConceptCard,
    est: _Collector,
    given: _Collector,
    extra: dict[str, Any],
    notes: list[str],
) -> None:
    from napkin2factory.calckit import power as pw
    from napkin2factory.rulepacks.concept_checks import parse_circuit

    power = extra.get("power")
    if power is None:
        power = card_quantity(card, "envelope", "power")
        if power is not None:
            extra["power"], extra["power_label"] = power, "card"
        elif card.envelope.get("power") is not None:
            return  # a power of the wrong kind: screen() already says so
        else:
            notes.append(
                "no power on the card: give the element power (or a planned heat-up time with "
                "the chamber size and the insulation) to check the supply"
            )
            return
    circuit = card.site.get("circuit")
    region = card.site.get("region")
    parsed = parse_circuit(circuit) if isinstance(circuit, str) else None
    if parsed is not None:
        volts, _amps = parsed
        current = pw.element_current(power, volts)
        est.add(
            "current",
            current,
            fmt(current, "A"),
            "from the power and the circuit's voltage",
            f"power.element_current at {volts.magnitude:g} V",
        )
        given.add(
            "circuit_class",
            f"the {circuit} circuit",
            f"the {circuit} circuit",
            "on the card",
            "site.circuit",
        )
        return
    if isinstance(circuit, str) and circuit.strip():
        notes.append(
            f"the circuit {circuit.strip()!r} is not written like 240V-13A, so the usual "
            "circuits of the region are used instead"
        )
    if not isinstance(region, str) or not region.strip():
        notes.append(
            "say which circuit it plugs into (like 230V-16A) or where it will be used (SA, EU, "
            "UK, US or AU) to check the supply"
        )
        return
    verdict = pw.circuit_for_power(region, power)
    if verdict.status == "unknown_region":
        notes.append(f"no list of the usual circuits in {region} yet: confirm the supply by hand")
        return
    est.add(
        "current",
        verdict.current,
        fmt(verdict.current, "A"),
        f"from the power and the usual {region} supply voltage",
        "power.circuit_for_power",
    )
    if verdict.status == "ok":
        label = str(verdict.label)
        est.add(
            "circuit_class",
            label,
            label,
            f"the smallest {region} circuit on file that carries it; {TO_CHECK}",
            f"power.circuit_for_power ({region} table) [verify]",
        )
    else:
        notes.append(
            f"none of the usual {region} circuits on file carries {fmt(verdict.current, 'A')}"
        )


def _cost(massing: Any, est: _Collector, extra: dict[str, Any], notes: list[str]) -> None:
    from napkin2factory.calckit import mass_cost

    low = high = 0.0
    counted: list[str] = []
    priced: list[str] = []
    unpriced: list[str] = []
    no_material: list[str] = []
    no_band: list[str] = []
    items: list[tuple[str, str, float | None]] = []
    if massing is not None:
        items += [(p.name, p.process_class, p.mass) for p in massing.pieces]
    items += [
        (f"{layer.name} layer", str(layer.process_class), kg)
        for layer, kg in extra.get("insulation_layers", [])
        if layer.process_class
    ]
    for name, pclass, kg in items:
        try:
            c = mass_cost.cost_estimate(pclass, mass=None if kg is None else Quantity(kg, "kg"))
        except ValueError:
            no_material.append(name)
            unpriced.append(name)
            continue
        if not c.known or c.low is None or c.high is None:
            no_band.append(name)
            unpriced.append(name)
            continue
        low += float(c.low.to("USD").magnitude)
        high += float(c.high.to("USD").magnitude)
        counted.append(f"{name}: {pclass}")
        priced.append(name)
    if no_material:
        notes.append(
            f"the cost leaves out {_the(owner_names(no_material))}: no material, so no mass "
            "to price"
        )
    if no_band:
        notes.append(
            f"the cost leaves out {_the(owner_names(no_band))}: no price range on file for "
            "how it is made"
        )
    if not counted:
        return
    ref = "mass_cost.cost_estimate (" + "; ".join(counted) + ") [verify]"
    words = f"rough cost of the {_and(owner_names(priced))} from cost bands per process"
    if unpriced:
        left = owner_names(unpriced)
        verb = "is" if len(left) == 1 else "are"
        names = " and the ".join(left) if len(left) < 3 else _and(left)
        words += f"; the {names} {verb} not counted"
    words += f"; {TO_CHECK}"
    est.add("cost_low", Quantity(low, "USD"), fmt(Quantity(low, "USD"), "USD"), words, ref)
    est.add("cost_high", Quantity(high, "USD"), fmt(Quantity(high, "USD"), "USD"), words, ref)


def screen(
    card: ConceptCard,
    massing: Any,
    root: Path | None = None,
    *,
    now: dt.datetime | None = None,
) -> Screening:
    """Screen one card against its massing: labelled numbers, rule rows, verdict.

    Args:
        card: the concept card.
        massing: the :class:`~napkin2factory.concepts.massing.MassingResult` (or ``None``).
        root: the product folder (unused today; the signature matches the build step).
        now: the timestamp to record (default: now, to the second).
    """
    from napkin2factory.calckit import mass_cost
    from napkin2factory.rulepacks.concept_checks import (
        HINGED,
        door_leaf,
        door_swing_angle,
        door_swing_term,
        rule_params,
        run_concept_rules,
    )

    notes: list[str] = []
    comp = _Collector("computed")
    est = _Collector("estimate")
    given = _Collector("given")
    extra: dict[str, Any] = {}
    if massing is not None and massing.pieces:
        w, d, h = massing.size
        for name, value, axis in (("width", w, "x"), ("depth", d, "y"), ("height", h, "z")):
            comp.add(
                name,
                Quantity(value, "mm"),
                fmt(Quantity(value, "mm"), "mm"),
                "measured across the rough shapes",
                f"massing bounding box ({axis})",
            )
        vol = Quantity(massing.volume, "mm**3")
        comp.add(
            "volume",
            vol,
            fmt(vol, "L"),
            "the space the rough shapes fill",
            "sum of the massing silhouettes",
        )
        if massing.mass is not None:
            m = Quantity(massing.mass, "kg")
            comp.add(
                "mass",
                m,
                fmt(m, "kg"),
                "from the rough shapes and their materials",
                "silhouette volume × density per call; frames and tubes by member section "
                "× cut length (geometry/materials.py)",
            )
        else:
            shapes = owner_names(list(massing.without_material))
            verb = "has" if len(shapes) == 1 else "have"
            notes.append(
                f"{_the(shapes)} {verb} no material yet, so the rough shapes have no mass: "
                "give them a material to weigh them"
            )
        door = str(card.layout.get("door", "") or "").strip().lower()
        if door and door != "none":  # no door on the card: no door row (review gate B, C11)
            factor = float(rule_params("fits-site-width").get("door_swing_factor", 1.0))
            term, basis = door_swing_term(card, massing, factor)
            angle = door_swing_angle(card)
            foot = Quantity(w + term, "mm")
            comp.add(
                "footprint_with_door_swing",
                foot,
                fmt(foot, "mm"),
                _door_words(door, basis, term, angle),
                f"width + open door ({basis})",
            )
            leaf = door_leaf(card, massing) if door in HINGED else None
            if leaf is not None:
                # the leaf to 0.1 mm (the precision of the massing), so promotion bounds the
                # alcove with the raw numbers, not the difference of two rounded ones (S-085)
                comp.add(
                    "door_leaf",
                    Quantity(leaf[0], "mm"),
                    f"{leaf[0]:.1f} mm",
                    "the width of the door that swings open",
                    "massing call `door`, x-extent"
                    if "on the card" not in leaf[1]
                    else "envelope.door_width",
                )
            if door in HINGED and angle is None and term > 0:
                notes.append(
                    "the card does not say how far the door opens, so the open door is "
                    "counted swung fully back against the wall (the widest case); give its "
                    "opening angle (like 110 degree) to count only what it really needs"
                )
    for section, key in QUANTITY_KINDS:  # a number of the wrong kind is left out, said once
        wrong = wrong_kind(section, key, getattr(card, section).get(key))
        if wrong is not None:
            shown, kind, example = wrong
            notes.append(
                f"{KIND_WORDS.get(key, 'a number')} on the card ({shown}) is not {kind}, so "
                f"screening leaves it out: give it like {example}"
            )
    _thermal(card, est, extra, notes)
    card_power = card_quantity(card, "envelope", "power")
    if card_power is not None:
        given.add("power", card_power, fmt(card_power, "W"), "on the card", "envelope.power")
    _supply(card, est, given, extra, notes)
    if "mass" in comp.raw and "insulation_mass" in est.raw:
        total = (comp.raw["mass"] + est.raw["insulation_mass"]).to("kg")
        est.add(
            "total_mass",
            total,
            fmt(total, "kg"),
            "the rough shapes plus the insulation",
            "massing mass + insulation_mass",
        )
    _cost(massing, est, extra, notes)
    lift_mass = est.raw.get("total_mass", comp.raw.get("mass"))
    if lift_mass is not None:
        verdict = mass_cost.lift_class(lift_mass)
        est.add(
            "lift_class",
            verdict.label,
            verdict.label,
            f"from the mass and the lifting limits; {TO_CHECK}",
            "mass_cost.lift_class (HSE guideline weights) [verify]",
        )
    rules = run_concept_rules(card, comp.raw, est.raw, massing, extra)
    rules += _registered_screens(card, massing, comp, est, given, notes)  # F8, F10
    red = any(r.status == "fail" for r in rules)
    stamp = (now or dt.datetime.now()).replace(microsecond=0)
    return Screening(
        given=given.out,
        computed=comp.out,
        estimates=est.out,
        rules=rules,
        verdict="red" if red else "green",
        at=stamp,
        notes=notes,
    )


class ScreenValues:
    """What a registered screen adds to (F8): ``computed``, ``estimate``, ``given``, ``notes``."""

    def __init__(
        self, computed: _Collector, estimate: _Collector, given: _Collector, notes: list[str]
    ) -> None:
        self.computed, self.estimate, self.given, self.notes = computed, estimate, given, notes


def _registered_screens(
    card: ConceptCard,
    massing: Any,
    comp: _Collector,
    est: _Collector,
    given: _Collector,
    notes: list[str],
) -> list[Any]:
    """Run the screens domains register, after the built-in ones; their rule rows."""
    from napkin2factory.core.registry import registry

    values = ScreenValues(comp, est, given, notes)
    rows: list[Any] = []
    for s in registry().screens():
        rows += s.run(card, massing, values)
    return rows


def same_screening(a: Screening | None, b: Screening | None) -> bool:
    """Whether two screenings say the same thing, whenever each was taken (S-086).

    Everything but ``at`` is compared: the given, computed and estimated values with their
    sources, the rule rows, the verdict and the notes.
    """
    if a is None or b is None:
        return False
    return a.model_dump(mode="json", exclude={"at"}) == b.model_dump(mode="json", exclude={"at"})


def keep_unchanged_at(previous: Screening | None, screening: Screening) -> bool:
    """Carry the earlier ``at`` over when nothing else changed; ``True`` if it was kept.

    A re-build of an unchanged card then leaves the card file as it was, so the shipped
    cards do not drift under ``make``.
    """
    if previous is not None and previous.at is not None and same_screening(previous, screening):
        screening.at = previous.at
        return True
    return False


def write_screening_json(out_dir: Path, card: ConceptCard, screening: Screening) -> Path:
    """``build/concepts/<id>/screening.json`` (the same dict the card carries)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "screening.json"
    data = {"id": card.id, "title": card.title, **screening.model_dump(mode="json")}
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return path


def write_screening_to_card(root: Path, card_id: str, screening: Screening) -> Path:
    """Replace the card's ``screening:`` in place; comments and key order elsewhere survive.

    Each labelled value and rule row is written as one flow-style line, so a re-screen is a
    readable diff.
    """
    from ruamel.yaml.comments import CommentedMap, CommentedSeq

    from napkin2factory.core import concepts as cm
    from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip

    path = cm.card_path(root, card_id)
    data = screening.model_dump(mode="json")
    block = CommentedMap()
    for key, value in data.items():
        if key in ("given", "computed", "estimates"):
            sub = CommentedMap()
            for name, lv in value.items():
                line = CommentedMap(lv)
                line.fa.set_flow_style()
                sub[name] = line
            block[key] = sub
        elif key == "rules":
            seq = CommentedSeq()
            for row in value:
                line = CommentedMap(row)
                line.fa.set_flow_style()
                seq.append(line)
            block[key] = seq
        else:
            block[key] = value
    doc = load_roundtrip(path)
    doc["screening"] = block
    dump_roundtrip(path, doc, explicit_null=True)
    return path


__all__ = [
    "LAYER_MATERIALS",
    "keep_unchanged_at",
    "parse_layers",
    "same_screening",
    "screen",
    "write_screening_json",
    "write_screening_to_card",
]
