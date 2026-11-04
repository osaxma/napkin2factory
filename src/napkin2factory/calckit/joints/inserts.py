"""Threaded-insert catalogue rows (RAMPA and E-Z LOK datasheets) and substrate aliases."""

from __future__ import annotations

from typing import Any

# --- Catalogue data: Threaded inserts -----------------------------------------------


def _rampa_source(substrate: str) -> str:
    return (
        f"RAMPA Tec technical documentation for Type SK/SKD threaded inserts in {substrate}; "
        "verify: true"
    )


#: Catalogue rows for threaded inserts in wood and wood-composite substrates.
#: Values represent ultimate tensile withdrawal capacity (N) for knife-thread
#: and hex-drive inserts (RAMPA / E-Z LOK technical datasheets).
THREADED_INSERT_ROWS: tuple[dict[str, Any], ...] = (
    {
        "insert": "M4",
        "substrate_class": "hardwood",
        "pullout_capacity_n": 2500.0,
        "source": _rampa_source("hardwood"),
        "verify": True,
    },
    {
        "insert": "M4",
        "substrate_class": "softwood",
        "pullout_capacity_n": 1500.0,
        "source": _rampa_source("softwood"),
        "verify": True,
    },
    {
        "insert": "M4",
        "substrate_class": "mdf",
        "pullout_capacity_n": 1100.0,
        "source": _rampa_source("MDF"),
        "verify": True,
    },
    {
        "insert": "M4",
        "substrate_class": "plywood",
        "pullout_capacity_n": 1800.0,
        "source": _rampa_source("birch plywood"),
        "verify": True,
    },
    {
        "insert": "M6",
        "substrate_class": "hardwood",
        "pullout_capacity_n": 4500.0,
        "source": _rampa_source("hardwood"),
        "verify": True,
    },
    {
        "insert": "M6",
        "substrate_class": "softwood",
        "pullout_capacity_n": 2800.0,
        "source": _rampa_source("softwood"),
        "verify": True,
    },
    {
        "insert": "M6",
        "substrate_class": "mdf",
        "pullout_capacity_n": 2200.0,
        "source": _rampa_source("MDF"),
        "verify": True,
    },
    {
        "insert": "M6",
        "substrate_class": "plywood",
        "pullout_capacity_n": 3200.0,
        "source": _rampa_source("birch plywood"),
        "verify": True,
    },
    {
        "insert": "M8",
        "substrate_class": "hardwood",
        "pullout_capacity_n": 6800.0,
        "source": _rampa_source("hardwood"),
        "verify": True,
    },
    {
        "insert": "M8",
        "substrate_class": "softwood",
        "pullout_capacity_n": 4200.0,
        "source": _rampa_source("softwood"),
        "verify": True,
    },
    {
        "insert": "M8",
        "substrate_class": "mdf",
        "pullout_capacity_n": 3400.0,
        "source": _rampa_source("MDF"),
        "verify": True,
    },
    {
        "insert": "M8",
        "substrate_class": "plywood",
        "pullout_capacity_n": 4800.0,
        "source": _rampa_source("birch plywood"),
        "verify": True,
    },
    {
        "insert": "M10",
        "substrate_class": "hardwood",
        "pullout_capacity_n": 9500.0,
        "source": _rampa_source("hardwood"),
        "verify": True,
    },
    {
        "insert": "M10",
        "substrate_class": "softwood",
        "pullout_capacity_n": 6000.0,
        "source": _rampa_source("softwood"),
        "verify": True,
    },
    {
        "insert": "M10",
        "substrate_class": "mdf",
        "pullout_capacity_n": 4800.0,
        "source": _rampa_source("MDF"),
        "verify": True,
    },
    {
        "insert": "M10",
        "substrate_class": "plywood",
        "pullout_capacity_n": 6500.0,
        "source": _rampa_source("birch plywood"),
        "verify": True,
    },
)


_SUBSTRATE_ALIASES: dict[str, str] = {
    "white-oak": "hardwood",
    "oak": "hardwood",
    "hard-maple": "hardwood",
    "maple": "hardwood",
    "walnut": "hardwood",
    "beech": "hardwood",
    "ash": "hardwood",
    "hardwood": "hardwood",
    "southern-yellow-pine": "softwood",
    "pine": "softwood",
    "douglas-fir": "softwood",
    "fir": "softwood",
    "spruce": "softwood",
    "softwood": "softwood",
    "baltic-birch-plywood": "plywood",
    "plywood": "plywood",
    "mdf": "mdf",
    "particle-board": "mdf",
    "hdf": "mdf",
}
