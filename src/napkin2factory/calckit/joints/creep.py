"""Timber creep: the k_def table lookup, a timber member's sag and a composite member's sag."""

from __future__ import annotations

from collections.abc import Sequence

from napkin2factory.calckit._tables import load_table
from napkin2factory.calckit.joints._units import Qty, _si

_DURATIONS = {
    "instantaneous": "instantaneous",
    "short-term": "instantaneous",
    "medium-term": "medium-term",
    "sustained": "sustained",
    "long-term": "sustained",
    "permanent": "sustained",
}
_MOISTURE = {
    "dry": "dry",
    "service-class-1": "dry",
    "indoor": "dry",
    "damp": "damp",
    "service-class-2": "damp",
    "wet": "wet",
    "service-class-3": "wet",
    "cycling": "wet",
}


def timber_k_def(load_duration: str = "sustained", moisture: str = "dry") -> float:
    """Creep factor ``k_def`` of solid timber from ``calckit/data/timber_creep.yaml``.

    EN 1995-1-1:2004 Table 3.2 and section 2.3.2.2 (service class by ``moisture``, load
    duration by ``load_duration``). Verify: every row of the table is still to be confirmed.

    Args:
        load_duration: ``"instantaneous"``/``"short-term"``, ``"medium-term"`` or
            ``"sustained"``/``"long-term"``/``"permanent"``.
        moisture: ``"dry"`` (service class 1), ``"damp"`` (class 2) or ``"wet"`` (class 3).

    Returns:
        The factor ``k_def`` (dimensionless float).

    Raises:
        ValueError: if the duration or the moisture is not one of the above.
    """
    duration = _DURATIONS.get(load_duration.strip().lower())
    if duration is None:
        raise ValueError(
            f"unknown load_duration {load_duration!r}; known durations: "
            f"'instantaneous', 'short-term', 'medium-term', 'sustained', 'long-term', 'permanent'"
        )
    wanted = _MOISTURE.get(moisture.strip().lower())
    if wanted is None:
        raise ValueError(
            f"unknown moisture {moisture!r}; known: 'dry', 'damp', 'wet' (service classes 1, 2, 3)"
        )
    for row in load_table("timber_creep"):
        if row["load_duration"] == duration and row["moisture"] in (wanted, "any"):
            return float(row["k_def"])
    raise ValueError(f"no k_def row in timber_creep.yaml for {duration!r} and {wanted!r}")


def wood_creep_deflection(
    elastic_deflection: Qty,
    load_duration: str = "sustained",
    moisture: str = "dry",
) -> Qty:
    """Total deflection of a member made wholly of timber, creep included.

    ``total = elastic * (1 + k_def)`` with ``k_def`` from :func:`timber_k_def`
    (EN 1995-1-1 Table 3.2). For a timber member working with steel, use
    :func:`composite_creep_deflection`: this overstates the creep of a mixed member.

    Args:
        elastic_deflection: instantaneous elastic deflection (length Qty).
        load_duration: see :func:`timber_k_def`.
        moisture: see :func:`timber_k_def`.

    Returns:
        Deflection including creep, in the unit of ``elastic_deflection``.
    """
    _si(elastic_deflection, "mm", "2.5 mm")
    return elastic_deflection * (1.0 + timber_k_def(load_duration, moisture))


def composite_creep_deflection(
    elastic_deflection: Qty,
    members: Sequence[tuple[Qty, bool]],
    load_duration: str = "sustained",
    moisture: str = "dry",
) -> Qty:
    """Long-term deflection of members bending together when only the timber creeps.

    EN 1995-1-1:2004 section 2.3.2.2: creep reduces the timber's stiffness to
    ``E / (1 + k_def)`` while steel keeps its own. For one load pattern the deflection is
    inversely proportional to the combined stiffness, so
    ``final = elastic * sum(EI) / sum(EI_final)`` with ``EI_final = EI / (1 + k_def)`` for a
    timber member and ``EI`` for any other. Use the same sustained load for the elastic
    deflection as for the final one.

    Args:
        elastic_deflection: instantaneous deflection of the whole member under the
            sustained load (length Qty).
        members: ``(EI, is_timber)`` for each part acting together, EI a bending stiffness
            quantity (e.g. ``12.3 GPa * 1.8e6 mm**4``), ``is_timber`` True for wood.
        load_duration: see :func:`timber_k_def`.
        moisture: see :func:`timber_k_def`.

    Returns:
        Long-term deflection, in the unit of ``elastic_deflection``.
    """
    _si(elastic_deflection, "mm", "0.66 mm")
    if not members:
        raise ValueError("members must list at least one (EI, is_timber) pair")
    k_def = timber_k_def(load_duration, moisture)
    total = 0.0
    final = 0.0
    for ei, is_timber in members:
        ei_nmm2 = _si(ei, "N*mm**2", "2.2e10 N*mm**2")
        if ei_nmm2 <= 0:
            raise ValueError("every member's EI must be positive")
        total += ei_nmm2
        final += ei_nmm2 / (1.0 + k_def) if is_timber else ei_nmm2
    return elastic_deflection * (total / final)
