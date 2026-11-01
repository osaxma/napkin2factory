"""Layered box enclosures: conduction, skin and guard temperatures, stored heat, heat-up.

Envelope-grade steady-state thermal calcs for a hot box (a chamber wrapped in layers),
generalised from a product's verified thermal calcs so that a concept card can be screened
before a product model exists.

Method (one source for both fidelities; a product's own calcs import these functions):

* **Mean-area conduction.** Each layer of a thick-walled box conducts over the geometric
  mean of its inner and outer box areas, ``R = t / (k · √(A_in · A_out))``, the usual
  correction for furnace walls about as thick as the chamber is wide (Incropera & DeWitt,
  *Fundamentals of Heat and Mass Transfer*, ch. 3, one-dimensional conduction and shape
  factors; furnace-wall practice) [verify]. A box of sides (w, d, h) has
  ``A = 2(w·d + w·h + d·h)``; a layer of thickness ``t`` behind a fit clearance ``c``
  grows every side by ``2(c + t)``. The clearance is lumped into the geometry, not into
  the resistance: the layer's inner area is the previous layer's outer face.
* **Boundary.** The outer skin loses heat by convection ``h·A·ΔT`` and grey-body
  radiation ``ε·σ·A·(T⁴ − T_amb⁴)`` (Incropera & DeWitt ch. 1 and 13). σ = 5.670374419e-8
  W/m²K⁴ (CODATA 2018; exact since the 2019 SI redefinition).
* **Guard (radiation shield).** A ventilated guard around the skin receives radiation
  from the skin (two grey surfaces, the skin inside the guard:
  ``σ·A_s·(T_s⁴ − T_g⁴) / (1/ε_s + (A_s/A_g)·(1/ε_g − 1))``, Incropera & DeWitt ch. 13)
  and loses it to the room by convection and radiation; the skin also loses heat by
  convection to the gap air, which the ventilation carries away.

Values a heated box typically uses and callers will usually pass (all [verify], cited where they
are used): natural-convection film coefficient h ≈ 5–10 W/m²K on a vertical sheet a few
tens of K above the air (simplified correlation h ≈ 1.42 (ΔT/L)^0.25 W/m²K for air);
emissivity 0.9 for powder coat (0.85–0.95 typical); K-23 insulating firebrick
k ≈ 0.25 W/m·K at mean wall temperature (Morgan Thermal Ceramics datasheet range
0.20–0.30 over 400–1000 °C); Kaowool 1260 board k ≈ 0.15 W/m·K at a ~400 °C mean
(datasheet range 0.12–0.18 over 400–700 °C), ρ ≈ 260 kg/m³ (Morgan Thermal Ceramics
datasheet). Those rows live in ``calckit/data/materials.yaml``; this module holds no
material constants itself.

Every public function takes and returns pint quantities from the shared registry
(:mod:`napkin2factory.core.units`); floats are used only inside, in SI units.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from napkin2factory.calckit._cases import Case
from napkin2factory.core.units import Quantity, UnitError

#: A pint quantity from the shared registry (pint is untyped for mypy).
Qty = Any

#: Stefan–Boltzmann constant, W/(m²·K⁴) (CODATA 2018; exact in the 2019 SI).
SIGMA = 5.670374419e-8


@dataclass(frozen=True)
class Layer:
    """One wall layer of a box enclosure.

    Attributes:
        thickness: layer thickness (length).
        conductivity: thermal conductivity (W/(m·K)), or ``None`` for a layer whose
            conduction resistance is neglected (a thin metal skin, or an air gap handled
            by the boundary model); it still grows the box.
        name: a label for messages and results.
        clearance: fit clearance on the layer's inner side (length, default none); it
            grows the box but carries no resistance and no mass.
    """

    thickness: Qty
    conductivity: Qty | None
    name: str
    clearance: Qty | None = None


@dataclass(frozen=True)
class ThermalResult:
    """Steady state of a layered box.

    Attributes:
        loss: heat flow through the walls (W).
        outer_skin_temperature: temperature of the outermost layer's outer face (degC).
        interface_temperatures: outer-face temperature of each layer, hot side first
            (degC); layers after the last conducting layer sit at the skin temperature.
        wall_resistance: total conduction resistance (K/W).
        guard_temperature: temperature of a ventilated guard (degC), when one is modelled.
    """

    loss: Qty
    outer_skin_temperature: Qty
    interface_temperatures: list[Qty] = field(default_factory=list)
    wall_resistance: Qty | None = None
    guard_temperature: Qty | None = None


# --- unit boundary ------------------------------------------------------------------


def _si(q: Qty, unit: str, example: str) -> float:
    """``q`` in ``unit`` as a float; a bare number is refused with a unit error."""
    if not hasattr(q, "to"):
        raise UnitError(
            f"thermal_enclosure expects a quantity like {example!r}, got the bare number {q!r}"
        )
    return float(q.to(unit).magnitude)


def _m(q: Qty) -> float:
    return _si(q, "m", "64 mm")


def _kelvin(q: Qty) -> float:
    return _si(q, "kelvin", "1200 degC")


def _wmk(q: Qty) -> float:
    return _si(q, "W/(m*K)", "0.15 W/(m*K)")


def _h(q: Qty) -> float:
    return _si(q, "W/(m**2*K)", "5 W/(m**2*K)")


def _dimless(x: Qty) -> float:
    # an emissivity too: Quantity(0.9, "") — the same rule as every other input (gate A, C10)
    return _si(x, "dimensionless", "Quantity(0.9, '')")


def _degc(t_k: float) -> Qty:
    return Quantity(t_k, "kelvin").to("degC")


# --- geometry -----------------------------------------------------------------------


def _box_area(w: float, d: float, h: float) -> float:
    return 2.0 * (w * d + w * h + d * h)


def _clearance_m(layer: Layer) -> float:
    return 0.0 if layer.clearance is None else _m(layer.clearance)


def _areas_m2(inner: Sequence[Qty], layers: Sequence[Layer]) -> list[float]:
    if len(inner) != 3:
        raise ValueError(f"inner must be (width, depth, height); got {len(inner)} values")
    dims = [_m(x) for x in inner]
    out = [_box_area(*dims)]
    for layer in layers:
        grow = 2 * (_clearance_m(layer) + _m(layer.thickness))
        dims = [x + grow for x in dims]
        out.append(_box_area(*dims))
    return out


def _resistances(inner: Sequence[Qty], layers: Sequence[Layer]) -> list[float | None]:
    areas = _areas_m2(inner, layers)
    out: list[float | None] = []
    for i, layer in enumerate(layers):
        if layer.conductivity is None:
            out.append(None)
            continue
        k = _wmk(layer.conductivity)
        out.append(_m(layer.thickness) / (k * math.sqrt(areas[i] * areas[i + 1])))
    return out


def _total(resistances: Sequence[float | None]) -> float:
    total = 0.0
    for r in resistances:
        if r is not None:
            total += r
    if total <= 0.0:
        raise ValueError("no conducting layer: give at least one layer a conductivity")
    return total


def box_areas(inner: Sequence[Qty], layers: Sequence[Layer]) -> list[Qty]:
    """Inner box area and the outer area of each layer, hot side first (m²).

    Method: ``A = 2(w·d + w·h + d·h)``; each layer grows every side by
    ``2·(clearance + thickness)`` (see the module docstring).

    Args:
        inner: chamber (width, depth, height).
        layers: wall layers from the hot face outwards.

    Returns:
        ``len(layers) + 1`` areas: the chamber, then each layer's outer face.
    """
    return [Quantity(a, "m**2") for a in _areas_m2(inner, layers)]


def layer_resistances(inner: Sequence[Qty], layers: Sequence[Layer]) -> list[Qty]:
    """Conduction resistance of each layer by the mean-area method (K/W).

    ``R = t / (k · √(A_in · A_out))`` with ``A_in`` the previous layer's outer face and
    ``A_out`` this layer's outer face (Incropera & DeWitt ch. 3) [verify]. A
    layer with ``conductivity=None`` contributes 0 K/W.
    """
    return [Quantity(0.0 if r is None else r, "K/W") for r in _resistances(inner, layers)]


def wall_resistance(inner: Sequence[Qty], layers: Sequence[Layer]) -> Qty:
    """Total wall resistance: the sum of ``t / (k · A_mean)`` over the layers (K/W).

    Raises:
        ValueError: no layer has a conductivity.
    """
    return Quantity(_total(_resistances(inner, layers)), "K/W")


# --- solvers ------------------------------------------------------------------------


def bisect_root(f: Callable[[float], float], lo: float, hi: float, tol: float = 1e-9) -> float:
    """Root of a monotone function on ``[lo, hi]`` by bisection (default to 1e-9).

    Plain floats (kelvin in this module); 200 halvings at most. The caller brackets the
    root; if ``f`` has the same sign at both ends the nearer end is returned.
    """
    f_lo = f(lo)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        f_mid = f(mid)
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def _interfaces(
    t_hot: float, q: float, resistances: Sequence[float | None], t_skin: float
) -> list[Qty]:
    last = max((i for i, r in enumerate(resistances) if r is not None), default=-1)
    out: list[Qty] = []
    t = t_hot
    for i, r in enumerate(resistances):
        if i >= last:
            out.append(_degc(t_skin))
            continue
        if r is not None:
            t = t - q * r
        out.append(_degc(t))
    return out


def steady_loss(
    inner: Sequence[Qty],
    layers: Sequence[Layer],
    t_hot: Qty,
    t_ambient: Qty,
    h_outer: Qty,
    emissivity_outer: Qty,
) -> ThermalResult:
    """Steady heat loss of a layered box whose outer skin faces the room directly.

    The skin temperature ``T_s`` is solved by bisection on ``[T_amb, T_hot]`` so that
    conduction through the walls equals convection plus radiation from the skin:

        (T_hot − T_s) / ΣR = A_s · [h · (T_s − T_amb) + ε · σ · (T_s⁴ − T_amb⁴)]

    with ``A_s`` the outermost box area and ``ΣR`` the mean-area wall resistance
    (Incropera & DeWitt ch. 1, 3, 13; σ CODATA 2018). Steady state only; uniform skin
    temperature (edges and corners run hotter); no thermal bridges.

    Args:
        inner: chamber (width, depth, height).
        layers: wall layers from the hot face outwards.
        t_hot: hot-face (chamber) temperature.
        t_ambient: room temperature.
        h_outer: convection film coefficient on the skin (W/(m²·K)) [verify, 5–10 for
            natural convection].
        emissivity_outer: skin emissivity (dimensionless) [verify, 0.9 powder coat].
    """
    th, ta = _kelvin(t_hot), _kelvin(t_ambient)
    h, eps = _h(h_outer), _dimless(emissivity_outer)
    a_s = _areas_m2(inner, layers)[-1]
    rs = _resistances(inner, layers)
    r_total = _total(rs)

    def residual(t_s: float) -> float:
        out = a_s * (h * (t_s - ta) + SIGMA * eps * (t_s**4 - ta**4))
        return (th - t_s) / r_total - out

    t_s = bisect_root(residual, ta, th)
    q = (th - t_s) / r_total
    return ThermalResult(
        loss=Quantity(q, "W"),
        outer_skin_temperature=_degc(t_s),
        interface_temperatures=_interfaces(th, q, rs, t_s),
        wall_resistance=Quantity(r_total, "K/W"),
    )


def _guard_k(
    t_hot_face: float,
    a_in: float,
    a_out: float,
    e_in: float,
    e_out: float,
    h_outer: float,
    t_amb: float,
    h_gap: float | None = None,
    t_gap: float | None = None,
) -> float:
    denom = 1.0 / e_in + (a_in / a_out) * (1.0 / e_out - 1.0)

    def balance(t_g: float) -> float:
        gain = SIGMA * a_in * (t_hot_face**4 - t_g**4) / denom
        if h_gap is not None and t_gap is not None:
            gain = gain + a_out * h_gap * (t_gap - t_g)
        loss = a_out * (h_outer * (t_g - t_amb) + SIGMA * e_out * (t_g**4 - t_amb**4))
        return gain - loss

    hi = t_hot_face if t_gap is None or h_gap is None else max(t_hot_face, t_gap)
    return bisect_root(balance, t_amb, hi)


def guard_temperature(
    hot_face_temperature: Qty,
    a_hot: Qty,
    a_guard: Qty,
    emissivity_hot: Qty,
    emissivity_guard: Qty,
    *,
    h_outer: Qty,
    t_ambient: Qty,
    h_gap_air: Qty | None = None,
    t_gap_air: Qty | None = None,
) -> Qty:
    """Temperature of a ventilated guard in front of a hot surface (degC).

    Two-node radiation balance, solved by bisection on ``[T_amb, T_hot]``: the guard
    gains ``σ·A_h·(T_h⁴ − T_g⁴) / (1/ε_h + (A_h/A_g)·(1/ε_g − 1))`` (two grey surfaces,
    the hot surface inside the guard; Incropera & DeWitt ch. 13) and loses
    ``A_g·[h·(T_g − T_amb) + ε_g·σ·(T_g⁴ − T_amb⁴)]`` to the room. Without the two
    gap-air arguments it neglects convection between the guard's inner face and the gap
    air. ``h_gap_air`` and ``t_gap_air``, when both given, add that exchange over ``A_g``
    (gain ``A_g·h_gap·(T_gap − T_g)``), an extension.

    Args:
        hot_face_temperature: temperature of the surface behind the guard.
        a_hot: area of that surface.
        a_guard: guard area.
        emissivity_hot: emissivity of the hot surface [verify, 0.9 powder coat].
        emissivity_guard: emissivity of the guard [verify, 0.9 powder coat].
        h_outer: film coefficient on the guard's outer face [verify, 5–10 W/m²K].
        t_ambient: room temperature.
        h_gap_air: optional film coefficient on the guard's inner face.
        t_gap_air: optional gap air temperature.
    """
    t_g = _guard_k(
        _kelvin(hot_face_temperature),
        _si(a_hot, "m**2", "0.5 m**2"),
        _si(a_guard, "m**2", "0.5 m**2"),
        _dimless(emissivity_hot),
        _dimless(emissivity_guard),
        _h(h_outer),
        _kelvin(t_ambient),
        None if h_gap_air is None else _h(h_gap_air),
        None if t_gap_air is None else _kelvin(t_gap_air),
    )
    return _degc(t_g)


def guarded_loss(
    inner: Sequence[Qty],
    layers: Sequence[Layer],
    guard_gap: Qty,
    t_hot: Qty,
    t_ambient: Qty,
    t_gap_air: Qty,
    h_convection: Qty,
    emissivity_skin: Qty,
    emissivity_guard: Qty,
) -> ThermalResult:
    """Steady loss of a layered box inside a ventilated guard (a heated body).

    The skin temperature ``T_s`` is solved by bisection on ``[max(T_amb, T_gap), T_hot]``
    so that conduction equals convection to the gap air plus radiation to the guard,
    where the guard temperature for each trial ``T_s`` comes from
    :func:`guard_temperature`:

        (T_hot − T_s)/ΣR = A_s·h·(T_s − T_gap) + Q_rad
        Q_rad = σ·A_s·(T_s⁴ − T_g⁴) / (1/ε_s + (A_s/A_g)·(1/ε_g − 1))

    ``A_s`` is the outermost layer's outer area; the guard area ``A_g`` grows every side
    of that box by ``2·guard_gap``. The gap air temperature is an assumption the caller
    supplies (50 °C is a typical first assumption, to be measured) [verify]; one film coefficient is
    used for the skin and the guard's outer face [verify, 5 W/m²K natural convection].
    Steady state only; the conduction of standoffs and fasteners between skin and guard
    is not modelled.
    """
    th, ta, tgap = _kelvin(t_hot), _kelvin(t_ambient), _kelvin(t_gap_air)
    h_c = _h(h_convection)
    e_s, e_g = _dimless(emissivity_skin), _dimless(emissivity_guard)
    gap_layer = Layer(guard_gap, None, "guard gap")
    areas = _areas_m2(inner, [*layers, gap_layer])
    a_s, a_g = areas[-2], areas[-1]
    rs = _resistances(inner, layers)
    r_total = _total(rs)

    def residual(t_s: float) -> float:
        t_g = _guard_k(t_s, a_s, a_g, e_s, e_g, h_c, ta)
        q_rad = SIGMA * a_s * (t_s**4 - t_g**4) / (1.0 / e_s + (a_s / a_g) * (1.0 / e_g - 1.0))
        return (th - t_s) / r_total - a_s * h_c * (t_s - tgap) - q_rad

    t_s = bisect_root(residual, max(ta, tgap), th)
    t_g = _guard_k(t_s, a_s, a_g, e_s, e_g, h_c, ta)
    q = (th - t_s) / r_total
    return ThermalResult(
        loss=Quantity(q, "W"),
        outer_skin_temperature=_degc(t_s),
        interface_temperatures=_interfaces(th, q, rs, t_s),
        wall_resistance=Quantity(r_total, "K/W"),
        guard_temperature=_degc(t_g),
    )


# --- stored heat and heat-up ---------------------------------------------------------


def _box_volume(dims: Sequence[float]) -> float:
    return dims[0] * dims[1] * dims[2]


def stored_heat(
    inner: Sequence[Qty],
    layers: Sequence[Layer],
    densities: Sequence[Qty | None],
    specific_heats: Sequence[Qty | None],
    t_hot: Qty,
    t_ambient: Qty,
    interface_temperatures: Sequence[Qty],
) -> Qty:
    """Heat stored in the wall layers from ambient to steady state (J).

    Each layer's solid volume (its box less the box inside it, the clearance being empty)
    is raised to the mean of its two face temperatures: the first layer between ``t_hot``
    and its outer face, every later layer between the previous layer's outer face and
    its own (``E = Σ ρ·c·V·(T_mean − T_amb)``). A layer whose density
    or specific heat is ``None`` stores nothing (an air gap). The material values are the
    caller's, from datasheets [verify].

    Args:
        inner: chamber (width, depth, height).
        layers: wall layers from the hot face outwards.
        densities: one per layer (kg/m³) or ``None``.
        specific_heats: one per layer (J/(kg·K)) or ``None``.
        t_hot: hot-face temperature.
        t_ambient: starting (room) temperature.
        interface_temperatures: outer-face temperature of each layer, as
            :attr:`ThermalResult.interface_temperatures` gives them.
    """
    n = len(layers)
    if not (len(densities) == len(specific_heats) == len(interface_temperatures) == n):
        raise ValueError(
            "densities, specific_heats and interface_temperatures need one entry per layer"
        )
    th, ta = _kelvin(t_hot), _kelvin(t_ambient)
    faces = [th, *(_kelvin(t) for t in interface_temperatures)]
    dims = [_m(x) for x in inner]
    energy = 0.0
    for i, layer in enumerate(layers):
        c = _clearance_m(layer)
        inside = [x + 2 * c for x in dims]
        dims = [x + 2 * (c + _m(layer.thickness)) for x in dims]
        rho, cp = densities[i], specific_heats[i]
        if rho is None or cp is None:
            continue
        rc = float((rho * cp).to("J/(m**3*K)").magnitude)
        volume = _box_volume(dims) - _box_volume(inside)
        energy += rc * volume * ((faces[i] + faces[i + 1]) / 2 - ta)
    return Quantity(energy, "J")


def heat_up_power(stored: Qty, loss: Qty, heat_up_time: Qty) -> Qty:
    """Power needed to reach temperature in ``heat_up_time``: ``P = Q_loss + E / t`` (W).

    Conservative envelope: the full steady loss is charged over the whole heat-up (the
    real loss grows from zero).
    """
    return (loss + stored / heat_up_time).to("W")


def heat_up_time(stored: Qty, loss: Qty, power: Qty) -> Qty:
    """Time to store ``stored`` with ``power`` while losing ``loss``: ``t = E / (P − Q)`` (h).

    The inverse of :func:`heat_up_power`, with the same conservative assumption.

    Raises:
        ValueError: ``power`` does not exceed ``loss`` (the box never reaches temperature).
    """
    surplus = (power - loss).to("W")
    if surplus.magnitude <= 0:
        raise ValueError(
            f"power {power.to('W'):~P} does not exceed the steady loss {loss.to('W'):~P}; "
            "the enclosure never reaches temperature"
        )
    return (stored / surplus).to("hour")


# --- reference cases (F17) -------------------------------------------------------------

_CUBE = (Quantity(1, "m"), Quantity(1, "m"), Quantity(1, "m"))
_SLAB = Layer(Quantity(0.1, "m"), Quantity(1, "W/(m*K)"), "slab")
_HAND = "hand computation: "

#: The worked example's plane wall, reproduced on a box so large (1 km a side) that the mean
#: areas equal the face area to 0.03 % — the plane-wall limit of the mean-area method.
_KM = (Quantity(1000, "m"), Quantity(1000, "m"), Quantity(1000, "m"))

#: Every public function's reference cases; ``external`` ones come from a published source.
CASES: list[Case] = [
    Case(
        "steady_loss",
        Quantity(50, "degC"),
        "Incropera, DeWitt, Bergman & Lavine, Fundamentals of Heat and Mass Transfer, 6th ed. "
        "(Wiley, 2007), Example 3.1, the composite oven window: L_A = 2 L_B, k_A = 0.15 and "
        "k_B = 0.08 W/(m K), oven at 400 degC with h_i + h_r = 50 W/(m2 K), room at 25 degC "
        "with h_o = 25 W/(m2 K); the minimum thickness L = 0.0627 m (L_A = 0.0418 m) holds the "
        "outer surface at 50 degC",
        args=(
            _KM,
            [
                Layer(Quantity(1, "mm"), Quantity(0.05, "W/(m*K)"), "inside film, 1/50 m2K/W"),
                Layer(Quantity(41.8, "mm"), Quantity(0.15, "W/(m*K)"), "plastic A"),
                Layer(Quantity(20.9, "mm"), Quantity(0.08, "W/(m*K)"), "plastic B"),
            ],
            Quantity(400, "degC"),
            Quantity(25, "degC"),
            Quantity(25, "W/(m**2*K)"),
            Quantity(0, ""),
        ),
        pick="outer_skin_temperature",
        abs=0.1,
        external=True,
        verify=True,
        note="the inside film (convection plus radiation, 50 W/(m2 K)) is a 1 mm layer of "
        "k = 0.05 W/(m K), the same 0.02 m2K/W; the outside is convection only (emissivity 0)",
    ),
    Case(
        "steady_loss",
        Quantity(1000 * 72 * 86.4 / 158.4, "W"),
        _HAND + "1 m cube, one 0.1 m layer of k = 1 W/(m K), no radiation: R_wall = "
        "0.1/(1 x sqrt(6 x 8.64)) = 1/72 K/W, R_film = 1/(10 x 8.64) = 1/86.4 K/W; "
        "q = 1000 K / (1/72 + 1/86.4) = 39 272.7 W",
        args=(
            _CUBE,
            [_SLAB],
            Quantity(1025, "degC"),
            Quantity(25, "degC"),
            Quantity(10, "W/(m**2*K)"),
            Quantity(0, ""),
        ),
        pick="loss",
        rel=1e-8,
    ),
    Case(
        "box_areas",
        Quantity(13.5, "m**2"),
        _HAND + "1 m cube + a 0.1 m layer = 1.2 m cube; + 0.05 m clearance and 0.1 m layer "
        "= 1.5 m cube: 6 x 1.5^2 = 13.5 m2",
        args=(
            _CUBE,
            [
                Layer(Quantity(100, "mm"), Quantity(1, "W/(m*K)"), "a"),
                Layer(Quantity(0.1, "m"), None, "b", Quantity(50, "mm")),
            ],
        ),
        pick="2",
        rel=1e-12,
    ),
    Case(
        "layer_resistances",
        Quantity(0.1 / 7.8, "K/W"),
        _HAND + "a 0.1 m layer (k = 1) behind 0.05 m clearance on a 1 m cube: A_in = 6, "
        "A_out = 6 x 1.3^2 = 10.14 m2, A_mean = sqrt(60.84) = 7.8 m2, R = 0.1/7.8 K/W",
        args=(_CUBE, [Layer(Quantity(0.1, "m"), Quantity(1, "W/(m*K)"), "s", Quantity(0.05, "m"))]),
        pick="0",
        rel=1e-12,
    ),
    Case(
        "wall_resistance",
        Quantity(0.1 / 7.2, "K/W"),
        _HAND + "a 0.1 m layer (k = 1) on a 1 m cube: A_mean = sqrt(6 x 8.64) = 7.2 m2, "
        "R = 0.1/7.2 = 0.013889 K/W",
        args=(_CUBE, [_SLAB]),
        rel=1e-12,
    ),
    Case(
        "bisect_root",
        2**0.5,
        _HAND + "the root of x^2 - 2 on [0, 2] is sqrt(2)",
        args=(lambda x: x * x - 2, 0.0, 2.0),
        kwargs={"tol": 1e-12},
        rel=1e-10,
    ),
    Case(
        "guard_temperature",
        Quantity(((400**4 + 300**4) / 2) ** 0.25, "K"),
        _HAND + "a black radiation shield between equal black areas at 400 K and a 300 K "
        "room, no convection: T_g^4 = (400^4 + 300^4)/2, T_g = 360.288 K",
        args=(
            Quantity(400, "K"),
            Quantity(1, "m**2"),
            Quantity(1, "m**2"),
            Quantity(1.0, ""),
            Quantity(1.0, ""),
        ),
        kwargs={"h_outer": Quantity(0, "W/(m**2*K)"), "t_ambient": Quantity(300, "K")},
        rel=1e-9,
    ),
    Case(
        "guarded_loss",
        Quantity(975 * 72 * 86.4 / 158.4, "W"),
        _HAND + "the steady_loss slab with a guard and no radiation: the skin loses to 50 degC "
        "gap air only, q = 975 K / (1/72 + 1/86.4) = 38 290.9 W",
        args=(
            _CUBE,
            [_SLAB, Layer(Quantity(0, "m"), None, "skin")],
            Quantity(25, "mm"),
            Quantity(1025, "degC"),
            Quantity(25, "degC"),
            Quantity(50, "degC"),
            Quantity(10, "W/(m**2*K)"),
            Quantity(1e-12, ""),
            Quantity(1e-12, ""),
        ),
        pick="loss",
        rel=1e-8,
    ),
    Case(
        "stored_heat",
        Quantity(3.5e9, "J"),
        _HAND + "a 0.5 m layer around a 1 m cube: V = 2^3 - 1 = 7 m3, rho c = 1 MJ/(m3 K), "
        "faces at +1000 K and +0 K, mean rise 500 K: E = 7 x 1e6 x 500 = 3.5 GJ",
        args=(
            _CUBE,
            [Layer(Quantity(0.5, "m"), Quantity(1, "W/(m*K)"), "block")],
            [Quantity(1000, "kg/m**3")],
            [Quantity(1000, "J/(kg*K)")],
            Quantity(1025, "degC"),
            Quantity(25, "degC"),
            [Quantity(25, "degC")],
        ),
        rel=1e-12,
    ),
    Case(
        "heat_up_power",
        Quantity(3000, "W"),
        _HAND + "1 kW loss + 36 MJ over 5 h (18 000 s) = 1000 + 2000 W",
        args=(Quantity(36, "MJ"), Quantity(1, "kW"), Quantity(5, "hour")),
        rel=1e-12,
    ),
    Case(
        "heat_up_time",
        Quantity(5, "hour"),
        _HAND + "36 MJ stored with 3 kW in and 1 kW lost: 36 MJ / 2 kW = 18 000 s = 5 h",
        args=(Quantity(36, "MJ"), Quantity(1, "kW"), Quantity(3, "kW")),
        rel=1e-12,
    ),
]


__all__ = [
    "CASES",
    "SIGMA",
    "Layer",
    "ThermalResult",
    "bisect_root",
    "box_areas",
    "guard_temperature",
    "guarded_loss",
    "heat_up_power",
    "heat_up_time",
    "layer_resistances",
    "steady_loss",
    "stored_heat",
    "wall_resistance",
]
