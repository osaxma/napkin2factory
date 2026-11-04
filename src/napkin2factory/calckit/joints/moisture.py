"""Equilibrium moisture content of wood from relative humidity and temperature (S-207)."""

from __future__ import annotations

from napkin2factory.calckit.joints._units import Qty, _si
from napkin2factory.core.units import Quantity

#: Room temperature the humidity calcs assume when none is given: 21 degC (about 70 degF,
#: the column of USDA Wood Handbook Table 4-2 that indoor furniture is read from).
DEFAULT_TEMPERATURE = Quantity(21.0, "degC")


def _rh_fraction(rh: float | Qty) -> float:
    """Relative humidity as a 0..1 fraction; a plain number above 1 is read as percent."""
    value = float(rh.to("dimensionless").magnitude) if hasattr(rh, "to") else float(rh)
    return value / 100.0 if value > 1.0 else value


def equilibrium_moisture_content(
    relative_humidity: float | Qty,
    temperature: Qty = DEFAULT_TEMPERATURE,
) -> float:
    r"""Equilibrium moisture content of wood (percent of oven-dry mass).

    Hailwood-Horrobin sorption equation, USDA Forest Products Laboratory Wood Handbook
    (FPL-GTR-190, 2010, ch. 4, Eq. 4-5; same chapter in FPL-GTR-282):

    :math:`M = \frac{1800}{W}\left[\frac{K h}{1 - K h}
    + \frac{K_1 K h + 2 K_1 K_2 K^2 h^2}{1 + K_1 K h + K_1 K_2 K^2 h^2}\right]`

    with :math:`h` the relative humidity (0 to 1) and, for :math:`T` in degC,
    :math:`W = 349 + 1.29T + 0.0135T^2`, :math:`K = 0.805 + 0.000736T - 2.73\times10^{-6}T^2`,
    :math:`K_1 = 6.27 - 0.00938T - 0.000303T^2`, :math:`K_2 = 1.91 + 0.0407T - 0.000293T^2`.
    Valid for roughly 0 to 90 % RH; the Handbook's Table 4-2 is this equation rounded.

    Args:
        relative_humidity: 0..1 fraction, or a percent above 1 (``30`` means 30 %), or a
            dimensionless quantity.
        temperature: air temperature as a temperature quantity (default 21 degC, about
            70 degF).

    Returns:
        Moisture content in percent (a float, e.g. ``9.24``).
    """
    t = _si(temperature, "degC", "21 degC")
    h = _rh_fraction(relative_humidity)
    if not 0.0 <= h < 1.0:
        raise ValueError(
            f"relative humidity must be between 0 and 100 %, got {relative_humidity!r}"
        )
    w = 349.0 + 1.29 * t + 0.0135 * t**2
    k = 0.805 + 0.000736 * t - 2.73e-6 * t**2
    k1 = 6.27 - 0.00938 * t - 0.000303 * t**2
    k2 = 1.91 + 0.0407 * t - 0.000293 * t**2
    kh = k * h
    return float(
        1800.0
        / w
        * (kh / (1.0 - kh) + (k1 * kh + 2.0 * k1 * k2 * kh**2) / (1.0 + k1 * kh + k1 * k2 * kh**2))
    )
