"""The kiln's own napkin-stage screens: a heated, insulated box on a mains supply (F8, F10).

Moved verbatim from the system's screening (``concepts/screening.py`` and
``rulepacks/concept_checks.py`` before v0.5, S-128): the system keeps only the screens any
product's card can use (fits the space, mass, cost, lift, stock sheets, walls), and these,
which only a heated box needs, live with the product that needs them. Any product may copy
this file into its own ``model/screens/``.

* **thermal** — heat loss, outer skin, stored heat, heat-up time or the power a planned
  heat-up needs, from the card's ``chamber``, ``insulation`` layers, ``power``,
  ``heat_up_time`` and ``max_temperature`` (``calckit.thermal_enclosure``). It shares the
  inner size and the wall with the system's walls-fit-envelope rule, the insulation's mass
  with the total mass, and each layer with the cost band.
* **supply** — the current on the site's ``circuit`` (or the usual circuits of ``region``)
  and rule ``circuit-available``.
* **controls-vs-hot-face**, **skin-vs-touch**, **chamber-volume** — rules
  ``controls-not-adjacent-hot-face``, ``skin-vs-touch-limit`` (``site.touch_limit``) and
  ``chamber-volume-vs-target`` (``envelope.target_volume``), all advisories.

Defaults screening states when the card is silent (all from the kiln's own parameters,
``model/parameters.yaml``, and tagged [verify] in DECISIONS.md): room 25 degC; skin film
coefficient 5 W/m²K (natural convection); skin emissivity 0.9 (powder coat); hot face
1200 degC. Layer materials come from one row each in ``calckit/data/materials.yaml`` (the
table the massing densities read too): a bare ``insulation: <thickness>`` is one
ceramic-fiber-board layer (k 0.15 W/m·K, ρ 260 kg/m³, c 1050 J/kg·K); named layers matching
``brick``/``K23`` take K23 firebrick values (k 0.25 W/m·K, ρ 480 kg/m³, c 1000 J/kg·K);
``shell``/``sheet`` layers grow the box but carry no resistance and store no heat.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from napkin2factory.calckit import power as pw
from napkin2factory.concepts.screens import (
    TO_CHECK,
    CardField,
    ScreenValues,
    and_,
    fmt,
    reads,
)
from napkin2factory.core.domain import Screen
from napkin2factory.core.model.concepts import ConceptCard, RuleRow
from napkin2factory.core.units import Quantity, is_quantity
from napkin2factory.rulepacks.concept_checks import (
    ConceptFacts,
    Outcome,
    parse_circuit,
    rule_rows,
)

Qty = Any

T_AMBIENT = Quantity(25.0, "degC")
H_OUTER = Quantity(5.0, "W/(m**2*K)")
EMISSIVITY = Quantity(0.9, "")
MAX_TEMPERATURE = Quantity(1200.0, "degC")
THERMAL_SOURCE = "kiln parameters: room 25 degC, h 5 W/m²K, ε 0.9 [verify]"

# --- the card fields these screens read (F8) -----------------------------------------------

CHAMBER = CardField(
    "envelope", "chamber", None, "three lengths", "[200 mm, 200 mm, 200 mm]", "the chamber size"
)
INSULATION = CardField(
    "envelope", "insulation", None, "a thickness or named layers", "170 mm", "the insulation"
)
#: the power seeds the kiln's parameter element-power at promotion (the kiln's own name)
POWER = CardField("envelope", "power", "W", "a power", "2.5 kW", "the power", param="element-power")
HEAT_UP_TIME = CardField(
    "envelope", "heat_up_time", "hour", "a time", "4 h", "the planned heat-up time"
)
MAX_TEMP = CardField(
    "envelope", "max_temperature", "degC", "a temperature", "1200 degC", "the top temperature"
)
SITE_MAX_TEMP = CardField(
    "site", "max_temperature", "degC", "a temperature", "1200 degC", "the top temperature"
)
TARGET_VOLUME = CardField("envelope", "target_volume", "L", "a volume", "8 L", "the volume to hold")
CIRCUIT = CardField("site", "circuit", None, "words", "230V-16A", "the circuit it plugs into")
REGION = CardField("site", "region", None, "words", "EU", "where it will be used")
TOUCH_LIMIT = CardField(
    "site", "touch_limit", "degC", "a temperature", "60 degC", "the touch limit"
)
CONTROLS = CardField("layout", "controls", None, "words", "side-right", "where the controls go")
LOAD = CardField("layout", "load", None, "words", "front", "where it is loaded from")


# --- wall layers ---------------------------------------------------------------------------


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
    ins = INSULATION.raw(card)
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
    for field in (MAX_TEMP, SITE_MAX_TEMP):
        t: Any = field.raw(card)
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


def _src(layer: ScreenLayer) -> str:
    m = _default_for(layer.name)
    return m.source.split(":")[0] if m is not None else f"{layer.name} as given"


# --- the thermal screen ----------------------------------------------------------------------


@reads(CHAMBER, INSULATION, POWER, HEAT_UP_TIME, MAX_TEMP, SITE_MAX_TEMP, phase="estimate")
def thermal(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """Heat loss, skin temperature, stored heat and heat-up from the chamber and its walls."""
    from napkin2factory.calckit import thermal_enclosure as te

    est, extra, notes = values.estimate, values.shared, values.notes
    chamber: Any = CHAMBER.raw(card)
    chamber_ok = (
        isinstance(chamber, list)
        and len(chamber) == 3
        and all(_length(c) is not None for c in chamber)
    )
    layers = parse_layers(card, notes)
    if chamber is None and INSULATION.raw(card) is None:
        notes.append(
            "no chamber size and no insulation on the card: heat loss, heat-up and insulation "
            "mass are not estimated"
        )
        return []
    if not chamber_ok:
        if chamber is not None:
            notes.append("the chamber size needs three lengths: width, depth and height")
        elif layers is not None:
            notes.append(
                "add the chamber size (width, depth, height) to estimate heat loss, heat-up and "
                "insulation mass"
            )
        return []
    if layers is None:
        notes.append(
            "add the insulation (one thickness, or named layers) to estimate heat loss, heat-up "
            "and insulation mass"
        )
        return []
    # the inner size and the wall per side, for the system's walls-fit-envelope rule
    extra["inner_size"] = chamber
    wall = sum(
        ((layer.clearance or Quantity(0, "mm")) + layer.thickness for layer in layers),
        Quantity(0, "mm"),
    )
    extra["wall"] = wall.to("mm")
    # this product's words for them, said by the system's rule (S-133)
    extra["inner_words"] = "chamber"
    extra["wall_words"] = "insulation"
    # insulation mass (layers with a density)
    volumes = _layer_volumes(chamber, layers)
    ins_mass = 0.0
    for layer, vol in zip(layers, volumes, strict=True):
        if layer.density is not None:
            ins_mass += vol * float(layer.density.to("kg/m**3").magnitude)
    # each layer with a density and a way it is made is priced with the rough shapes
    values.cost_items += [
        (
            f"{layer.name} layer",
            str(layer.process_class),
            vol * float(layer.density.to("kg/m**3").magnitude),
        )
        for layer, vol in zip(layers, volumes, strict=True)
        if layer.density is not None and layer.process_class
    ]
    if ins_mass > 0:
        est.add(
            "insulation_mass",
            Quantity(ins_mass, "kg"),
            fmt(Quantity(ins_mass, "kg"), "kg"),
            f"from the wall layers' sizes and their materials; {TO_CHECK}",
            "layer volumes × density (" + "; ".join(sorted({_src(lay) for lay in layers})) + ")",
        )
        values.mass_items.append((Quantity(ins_mass, "kg"), "the insulation", "insulation_mass"))
    unknown = [layer.name for layer in layers if not layer.known]
    if unknown:
        noun = "layer conducts" if len(unknown) == 1 else "layers conduct"
        notes.append(
            f"say how well the {and_(unknown)} insulation {noun} heat (a conductivity, "
            "like 0.15 W/(m*K)) to estimate heat loss and heat-up"
        )
        return []
    kit_layers = [
        te.Layer(layer.thickness, layer.conductivity, layer.name, clearance=layer.clearance)
        for layer in layers
    ]
    if not any(layer.conductivity is not None for layer in layers):
        notes.append(
            "no insulation layer says how well it conducts heat: give one a conductivity "
            "(like 0.15 W/(m*K)) to estimate heat loss"
        )
        return []
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
            f"the {and_(light)} insulation {noun} no density (how heavy it is), so the heat "
            "the walls store and the heat-up time are not estimated"
        )
    power = POWER.quantity(card)
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
    target = HEAT_UP_TIME.quantity(card)
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
    return []


# --- the supply screen -------------------------------------------------------------------------


def _power_text(power: Qty) -> str:
    w = float(power.to("W").magnitude)
    return f"{w / 1000:.3g} kW" if w >= 1000 else f"{w:.0f} W"


def _article(label: str | None) -> str:
    return "an" if (label or "x")[0] in "8aeiouAEIOU" or (label or "").startswith("11") else "a"


def circuit_available(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """The element current, with headroom, fits the site's circuit.

    An explicit ``site.circuit`` (``240V-13A``) is checked directly; otherwise the region
    table picks the smallest class (``calckit.power.circuit_for_power``). An unknown region
    is a warning, never a failure.
    """
    power = facts.shared.get("power")
    if power is None:
        return Outcome(
            "skip",
            message="no power to check: give the card a power, or a heat-up time with the "
            "chamber and insulation",
        )
    headroom = float(params.get("headroom", pw.CIRCUIT_HEADROOM_MIN))
    circuit = CIRCUIT.raw(facts.card)
    region = REGION.raw(facts.card)
    parsed = parse_circuit(circuit) if isinstance(circuit, str) else None
    # the current is an estimate; the card's own power and circuit are given (gate A, C1)
    relies = ["estimate"]
    if parsed is not None or facts.shared.get("power_label") == "card":
        relies.append("given")
    values: dict[str, Any] = {
        "power": _power_text(power),
        "margin": f"{(headroom - 1) * 100:.0f} %",
        "region": region,
    }
    if parsed is not None:
        volts, amps = parsed
        current = pw.element_current(power, volts)
        needed = headroom * float(current.to("A").magnitude)
        values.update(
            current=f"{float(current.to('A').magnitude):.1f} A at {volts.magnitude:g} V",
            needed=f"{needed:.1f} A",
            circuit=f"the {circuit} circuit on site",
        )
        if needed <= float(amps.to("A").magnitude) + 1e-9:
            values["circuit"] = f"fits the {circuit} circuit on site"
            return Outcome("pass", values, [], relies)
        return Outcome("violated", values, [values], relies)
    if not isinstance(region, str) or not region.strip():
        return Outcome(
            "skip", message="no supply on the card (a circuit like 240V-13A, or a region)"
        )
    verdict = pw.circuit_for_power(region, power, headroom=headroom)
    if verdict.status == "unknown_region":
        return Outcome("warn", values, [], relies)
    amps_now = float(verdict.current.to("A").magnitude)
    values.update(current=f"{amps_now:.1f} A", needed=f"{headroom * amps_now:.1f} A")
    if verdict.status == "ok":
        values["circuit"] = f"needs {_article(verdict.label)} {verdict.label}"
        return Outcome("pass", values, [], relies)
    values["circuit"] = f"any circuit on file for {region}"
    return Outcome("violated", values, [values], relies)


@reads(POWER, CIRCUIT, REGION, phase="estimate")
def supply(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """The element current on the site's circuit, or the usual circuit of its region."""
    card_power = POWER.quantity(card)
    if card_power is not None:
        values.given.add("power", card_power, fmt(card_power, "W"), "on the card", "envelope.power")
    _supply_values(card, values)
    return _rows("circuit-available", card, massing, values)


def _supply_values(card: ConceptCard, values: ScreenValues) -> None:
    est, given, extra, notes = values.estimate, values.given, values.shared, values.notes
    power = extra.get("power")
    if power is None:
        power = POWER.quantity(card)
        if power is not None:
            extra["power"], extra["power_label"] = power, "card"
        elif POWER.raw(card) is not None:
            return  # a power of the wrong kind: the runner already says so
        else:
            notes.append(
                "no power on the card: give the element power (or a planned heat-up time with "
                "the chamber size and the insulation) to check the supply"
            )
            return
    circuit = CIRCUIT.raw(card)
    region = REGION.raw(card)
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


# --- the advisories --------------------------------------------------------------------------


def _face(text: str, default: str = "") -> str:
    words = set(re.split(r"[\s\-_/]+", text.strip().lower()))
    for face in (
        "top",
        "above",
        "below",
        "under",
        "bottom",
        "front",
        "back",
        "rear",
        "left",
        "right",
    ):
        if face in words:
            return {"above": "top", "under": "below", "bottom": "below", "rear": "back"}.get(
                face, face
            )
    return default


def controls_not_adjacent_hot_face(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """Controls not on the top, nor on the door's face beside or above it.

    The door's face is ``layout.load`` (default front) for a hinged or front door, the top
    for a lid. Controls below the door are fine.
    """
    controls = str(facts.card.layout.get("controls", "")).strip()
    door = str(facts.card.layout.get("door", "")).strip()
    if not controls or not door:
        return Outcome("skip", message="no controls and door placement on the card to compare")
    door_face = (
        "top"
        if _face(door) == "top" or "lid" in door.lower()
        else _face(str(facts.card.layout.get("load", "")), "front")
    )
    where = _face(controls)
    values = {"controls": controls, "door": door, "where": ""}
    if where == "top":
        values["where"] = "above"
    elif where == door_face and where != "below":
        values["where"] = "beside"
    if values["where"]:
        return Outcome("violated", values, [values], [])
    return Outcome("pass", values, [], [])


def _temperature_text(q: Qty) -> str:
    return f"{float(q.to('degC').magnitude):.0f} degC"


def touch_limit_default(contact: str) -> tuple[Qty, str] | None:
    """The burn threshold for one contact time from ``calckit/data/touch_limits.yaml``."""
    from napkin2factory.calckit import load_table

    row = next((r for r in load_table("touch_limits") if r["contact"] == contact), None)
    if row is None:
        return None
    return Quantity(float(row["limit_degC"]), "degC"), str(row["words"])


def skin_vs_touch_limit(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """The outer skin estimate stays under a touch limit (advisory).

    The limit is the card's ``site.touch_limit`` (given); without one, the burn threshold
    for the rule's ``contact`` time from ``calckit/data/touch_limits.yaml`` (ISO 13732-1,
    to be checked).
    """
    skin = facts.estimates.get("skin_temperature")
    if skin is None:
        return Outcome(
            "skip",
            message="no outer skin estimate (it needs the chamber size and the insulation)",
        )
    relies = ["estimate"]
    limit: Any = TOUCH_LIMIT.raw(facts.card)
    try:
        limit_c = float(limit.to("degC").magnitude) if is_quantity(limit) else None
    except Exception:  # pint DimensionalityError: not a temperature
        limit_c = None
    if limit_c is not None:
        where = "on the card"
        relies.append("given")
    else:
        found = touch_limit_default(str(params.get("contact", "1 min")))
        if found is None:
            return Outcome(
                "skip", message="no touch limit on the card and none on file for this contact time"
            )
        limit, where = found
        limit_c = float(limit.to("degC").magnitude)
    values = {
        "skin": _temperature_text(skin),
        "limit": f"{limit_c:.0f} degC",
        "where": where,
    }
    ok = float(skin.to("degC").magnitude) <= limit_c + 1e-9
    return Outcome("pass" if ok else "violated", values, [] if ok else [values], relies)


def chamber_volume_vs_target(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """The chamber holds at least the card's ``envelope.target_volume`` (advisory)."""
    target: Any = TARGET_VOLUME.raw(facts.card)
    try:
        target_l = float(target.to("L").magnitude) if is_quantity(target) else None
    except Exception:  # pint DimensionalityError: not a volume
        target_l = None
    if target_l is None:
        return Outcome("skip", message="no target volume on the card")
    chamber = facts.shared.get("inner_size")
    if chamber is None:
        return Outcome(
            "skip", message="no chamber size on the card to compare with the target volume"
        )
    vol = chamber[0] * chamber[1] * chamber[2]
    vol_l = float(vol.to("L").magnitude)
    values = {
        "volume": f"{vol_l:.3g} L",
        "target": f"{target_l:.3g} L",
        "size": " × ".join(f"{float(c.to('mm').magnitude):.0f}" for c in chamber) + " mm",
    }
    ok = vol_l >= target_l - 1e-9
    return Outcome("pass" if ok else "violated", values, [] if ok else [values], ["given"])


# --- the rules, worded like a pack (S-022) ------------------------------------------------------

CHECKS = {
    "circuit_available": circuit_available,
    "controls_not_adjacent_hot_face": controls_not_adjacent_hot_face,
    "skin_vs_touch_limit": skin_vs_touch_limit,
    "chamber_volume_vs_target": chamber_volume_vs_target,
}
RULES: dict[str, dict[str, Any]] = {
    "circuit-available": {
        "id": "circuit-available",
        "title": "The supply on site carries it",
        "severity": "fail",
        "check": "circuit_available",
        # rating ≥ headroom × current: the calc kit's margin, the one promotion writes into
        # the supply requirement too (REQ-006; NEC 210.20 uses 1.25) [verify]
        "params": {"headroom": pw.CIRCUIT_HEADROOM_MIN},
        "message": "{power} draws {current}; with {margin} headroom it needs {needed}, more "
        "than {circuit}",
        "pass_message": "{power} draws {current}: {circuit}",
        "warn_message": "no circuit table for region {region} — confirm the supply",
    },
    "controls-not-adjacent-hot-face": {
        "id": "controls-not-adjacent-hot-face",
        "title": "Controls away from the hot air path",
        "severity": "warn",
        "check": "controls_not_adjacent_hot_face",
        "params": {},
        "message": "controls {where} the door sit in the hot air path — consider the side or below",
        "pass_message": "controls ({controls}) are away from the door ({door})",
    },
    "skin-vs-touch-limit": {
        "id": "skin-vs-touch-limit",
        "title": "The outside is safe to touch",
        "severity": "warn",
        "check": "skin_vs_touch_limit",
        # the card's site.touch_limit; without one, the burn threshold for this contact time
        # from calckit/data/touch_limits.yaml (ISO 13732-1) [verify]
        "params": {"contact": "1 min"},
        "message": "the outside skin is about {skin} (estimate), above the {limit} touch limit "
        "({where}) — more insulation or a guard would bring it down",
        "pass_message": "the outside skin is about {skin} (estimate), under the {limit} touch "
        "limit ({where})",
    },
    "chamber-volume-vs-target": {
        "id": "chamber-volume-vs-target",
        "title": "The chamber holds the target volume",
        "severity": "warn",
        "check": "chamber_volume_vs_target",
        "params": {},
        "message": "the {size} chamber holds {volume}, less than the {target} the card aims for",
        "pass_message": "the {size} chamber holds {volume}, at least the {target} the card aims "
        "for",
    },
}


def _rows(rule_id: str, card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    facts = ConceptFacts(card, values.computed.raw, values.estimate.raw, massing, values.shared)
    return rule_rows([RULES[rule_id]], CHECKS, facts, "model/screens/heated_enclosure.py")


@reads(CONTROLS, LOAD)
def controls_vs_hot_face(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """Rule ``controls-not-adjacent-hot-face``."""
    return _rows("controls-not-adjacent-hot-face", card, massing, values)


@reads(TOUCH_LIMIT)
def skin_vs_touch(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """Rule ``skin-vs-touch-limit``."""
    return _rows("skin-vs-touch-limit", card, massing, values)


@reads(TARGET_VOLUME)
def chamber_volume(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """Rule ``chamber-volume-vs-target``."""
    return _rows("chamber-volume-vs-target", card, massing, values)


SCREENS = (
    Screen("thermal", thermal, title="Heat loss, skin and heat-up"),
    Screen("supply", supply, title="The supply carries it"),
    Screen("controls-vs-hot-face", controls_vs_hot_face, title="Controls away from the heat"),
    Screen("skin-vs-touch", skin_vs_touch, title="Safe to touch"),
    Screen("chamber-volume", chamber_volume, title="Chamber volume"),
)


# --- what promotion seeds from these fields (B-0086) ----------------------------------------
# Promotion reads these two names from a product's screens (``concepts/promote/packs.py``):
# the supply requirement and the screening values the decision quotes, which only a heated
# box has.

#: Screening values the promotion decision quotes, after the size and mass.
PROMOTE_RATIONALE = ("heat_up_time", "power", "required_power", "current", "circuit_class")


def promote_requirements(
    card: ConceptCard, seeded: list[Any], top: str | None, notes: list[str]
) -> list[tuple[str, dict[str, Any]]]:
    """The supply requirement: the element power the site's circuit carries (gate A, B1).

    ``power ≤ V·I / headroom`` on the parameter ``envelope.power`` seeded, with the headroom
    of rule ``circuit-available``, the number screening used, so a green circuit row cannot
    become a failing requirement on the same inputs.
    """
    from napkin2factory.core.units import format_quantity

    circuit = CIRCUIT.raw(card)
    power = next((p for p in seeded if p.source == f"envelope.{POWER.key}"), None)
    if circuit is None:
        if REGION.raw(card) is not None and power is not None:
            notes.append(
                f"site.region {REGION.raw(card)} but no site.circuit: no supply requirement "
                "written — add site.circuit (e.g. 230V-16A) once the socket is known"
            )
        return []
    parsed = parse_circuit(circuit) if isinstance(circuit, str) else None
    if parsed is None:
        notes.append(
            f"site.circuit {circuit!r} is not like 240V-13A: no supply requirement written"
        )
        return []
    if power is None:
        notes.append(
            "no power on the card (envelope.power): no supply requirement written — "
            "add one once the element power is known"
        )
        return []
    volts, amps = parsed
    headroom = float(RULES["circuit-available"]["params"]["headroom"])
    raw = float((volts * amps).to("W").magnitude) / headroom
    # rounded *up* to 0.1 W so a card exactly at the screening limit still passes
    limit = Quantity(math.ceil(round(raw * 10, 6)) / 10, "W")
    q = format_quantity
    return [
        (
            "supply",
            {
                "title": "Runs on the site circuit",
                "statement": f"The element power is at most {q(limit)}, so the "
                f"{circuit} site circuit keeps a {headroom:g} headroom.",
                "category": "performance",
                "verify": {
                    "kind": "param_bound",
                    "target": f"param://{power.name}",
                    "op": "<=",
                    "value": q(limit),
                },
                "allocation": [f"param://{power.name}"] + ([f"asm://{top}"] if top else []),
                "rationale": f"{q(volts)} × {q(amps)} / {headroom:g}: the "
                f"same {headroom:g} headroom screening used (rule circuit-available); "
                "the NEC 210.20 continuous-load factor 1.25 is stricter [verify].",
            },
        )
    ]


PROMOTE_REQUIREMENTS = promote_requirements


# --- what the build summary says from these fields (B-0097) ---------------------------------
# The concept build's one-line summary reads this name from a product's screens
# (``concepts/build.py::pack_summary_phrases``): the supply and the heat-up, which only a
# heated box has, after the size and mass and before the cost.


def _supply_phrase(screening: Any) -> str | None:
    """``2.5 kW (on the card) on the 240V-13A circuit — fits with a fifth to spare (estimate)``.

    The card's own power and circuit are given; only the fit is an estimate (gate A, C1).
    """
    from napkin2factory.concepts.build import screening_text, spare_words

    def v(section: str, name: str) -> str | None:
        return screening_text(screening, section, name)

    given_power = v("given", "power")
    if given_power:
        power = f"{given_power} (on the card)"
    elif v("estimates", "required_power"):
        power = f"{v('estimates', 'required_power')} (estimate)"
    else:
        return None
    on_card = v("given", "circuit_class")
    if on_card:
        row = screening.rule("circuit-available")
        spare = spare_words(float(RULES["circuit-available"]["params"]["headroom"]))
        if row is not None and row.status == "pass":
            fit = f"fits with {spare} to spare (estimate)"
        elif row is not None and row.status == "fail":
            fit = f"does not fit with {spare} to spare (estimate)"
        else:
            fit = "fit not checked"
        return f"{power} on {on_card} — {fit}"
    table = v("estimates", "circuit_class")
    if table:
        return f"{power} on a {table} (estimate)"
    return f"{power}, supply not checked"


def summary_phrases(card: ConceptCard, screening: Any) -> list[str]:
    """The supply, then the heat-up (or the power a planned heat-up needs), each labelled."""
    from napkin2factory.concepts.build import screening_text

    out: list[str] = []
    supply = _supply_phrase(screening)
    if supply:
        out.append(supply)
    heat = screening_text(screening, "estimates", "heat_up_time")
    required = screening_text(screening, "estimates", "required_power")
    if heat:
        out.append(f"{heat} to temperature (estimate)")
    elif required and is_quantity(card.envelope.get(HEAT_UP_TIME.key)):
        out.append(f"{required} for the planned heat-up (estimate)")
    return out


SUMMARY_PHRASES = summary_phrases
