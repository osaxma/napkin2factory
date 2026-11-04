"""Structural mechanics for joints, wood, fatigue and load cases (W1).

Pure-function, unit-checked (`pint`) structural pack covering:
- Wood screw and lag screw withdrawal per the NDS (National Design Specification
  for Wood Construction).
- Threaded insert pull-out capacity and safety factor against applied loads from
  cited catalogue rows.
- Joint moment capacity for welded tube corners and bolted corner groups.
- Frame racking (lateral sway) for unbraced portals with rigid or semi-rigid corners
  (Roark / slope-deflection frame mechanics).
- Wood creep deflection (elastic deflection multiplied by duration creep factor per
  USDA Wood Handbook / Eurocode 5 k_def).
- Across-grain wood dimensional movement across relative humidity changes using
  dimensional change coefficients from ``calckit/data/wood_movement.yaml``.
- Fatigue safety margin using endurance limit and Marin/Goodman criteria per Shigley;
  materials without an endurance limit require an explicit S-N value at the cycle count.
- Load cases and default factors of safety from ``calckit/data/load_cases.yaml``, with
  enforcement that safety factors may only be tightened, never loosened.

Every public function takes and returns pint quantities from the shared registry
(:mod:`napkin2factory.core.units`); internal calculations operate on float SI values.
"""

from __future__ import annotations

import inspect

from napkin2factory.calckit.joints.cases import CASES
from napkin2factory.calckit.joints.fatigue import factor_of_safety, fatigue_margin
from napkin2factory.calckit.joints.frames import PortalFrame, frame_racking, joint_moment_capacity
from napkin2factory.calckit.joints.inserts import THREADED_INSERT_ROWS
from napkin2factory.calckit.joints.withdrawal import (
    PulloutResult,
    insert_pullout,
    lag_screw_withdrawal,
    wood_screw_withdrawal,
)
from napkin2factory.calckit.joints.wood import wood_creep_deflection, wood_movement

__all__ = [
    "CASES",
    "PortalFrame",
    "PulloutResult",
    "THREADED_INSERT_ROWS",
    "factor_of_safety",
    "fatigue_margin",
    "frame_racking",
    "insert_pullout",
    "joint_moment_capacity",
    "lag_screw_withdrawal",
    "wood_creep_deflection",
    "wood_movement",
    "wood_screw_withdrawal",
]

# A re-exported function or class keeps this package as its __module__, not the
# submodule that defines it: the calc checker (core/checks/calcs.py) and the
# reference-case coverage test (calckit/_cases.py) find a pack by that name.
for _name in __all__:
    _obj = globals()[_name]
    if inspect.isfunction(_obj) or inspect.isclass(_obj):
        _obj.__module__ = __name__
del _name, _obj, inspect
