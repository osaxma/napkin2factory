"""The calc kit: envelope-grade engineering calcs that work before a product model exists.

Three packs, each function pint-typed, cited and covered by a hand-checked test:

* :mod:`~napkin2factory.calckit.thermal_enclosure` — layered conduction (mean-area
  method), skin and guard temperatures, heat loss, stored heat, heat-up power and time.
* :mod:`~napkin2factory.calckit.power` — element current, resistance, wire length,
  surface load; circuit class per region.
* :mod:`~napkin2factory.calckit.mass_cost` — mass from volume, cost bands per process
  class, manual-handling class, stock-sheet fit.

Screening (``n2f concept build``) calls the kit with concept-card envelope numbers; a
product's own calcs import it where they overlap (a product's thermal and element
calcs), so both fidelities share one source. Tables live under
``calckit/data`` and are read with :func:`load_table`. See ``docs/calckit.md``.
"""

from __future__ import annotations

from napkin2factory.calckit import mass_cost, power, thermal_enclosure
from napkin2factory.calckit._tables import TableError, load_table, table_names

__all__ = ["TableError", "load_table", "mass_cost", "power", "table_names", "thermal_enclosure"]
