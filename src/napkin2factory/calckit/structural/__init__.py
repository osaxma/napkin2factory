r"""Envelope-grade structural mechanics: member sections, beams, buckling, and shear.

Pure functions taking and returning pint quantities from the shared registry
(:mod:`napkin2factory.core.units`), backed by handbook reference cases (Roark, Shigley,
AISC). Used by the generic ``structural`` napkin screen
(:mod:`napkin2factory.concepts.screens.structural`) and product-level sizing calcs (W1).

Method and physics (one source for screening and product calcs; W1):

* **Cross-section geometry.** Geometric properties of solid rectangles, hollow rectangular
  tubing, and circular tubing (Roark Table 1): area moment of inertia :math:`I`, section
  modulus :math:`Z = I / c`, and cross-sectional area :math:`A`.
* **Beam deflection.**
  - Simply supported: center point load :math:`\delta = \frac{F L^3}{48 E I}`
    (Roark Table 8.1 Case 1d) and uniform distributed load :math:`\delta = \frac{5 w L^4}{384 E I}`
    (Roark Table 8.1 Case 1e).
  - Cantilever with column rotation: tip deflection under end point load combined with the
    rotation of a vertical support column under moment :math:`M = F L_a`:
    :math:`\delta = \frac{F L_a^3}{3 E I_a} + \frac{F L_a^2 H}{E I_c}`
    (Roark Table 8.1 Cases 1a & 3a; Track A §3.1).
* **Bending stress and yield margin.** Flexure formula :math:`\sigma_b = \frac{M}{Z}` and
  yield safety factor :math:`FS_y = \frac{\sigma_y}{\sigma_b}` (Roark §8.1; Shigley §1-10).
* **Column stability (Euler buckling).** Critical elastic buckling load
  :math:`P_{cr} = \frac{\pi^2 E I_{\min}}{(K L)^2}` with effective length factor :math:`K`
  per end condition (AISC Table C-A-7.1; Shigley Table 4-2). A slenderness check verifies
  that :math:`\lambda = \frac{K L}{r} \ge \lambda_c = \sqrt{\frac{2 \pi^2 E}{\sigma_y}}`;
  slenderness below :math:`\lambda_c` falls in the inelastic range and is refused, naming
  Johnson's parabolic formula as not covered (Shigley §4-11).
* **Tip-over safety factor.** Ratio of gravity restoring moment to overturning moment
  :math:`FS = \frac{m g x_{\text{cg}}}{F_{\text{edge}} x_{\text{overhang}}}` (Track A §3.1).
* **Fastener group shear.** Direct shear stress per fastener :math:`\tau = \frac{V}{n A_s}`
  and safety factor against allowable shear strength
  :math:`FS = \frac{\tau_{\text{allow}}}{\tau}` (Shigley §8-5).

Every public function takes and returns pint quantities from the shared registry
(:mod:`napkin2factory.core.units`); floats are used only inside, in SI units.
Results suitable for concept screens carry the formula and published source.
"""

from __future__ import annotations

import inspect

from napkin2factory.calckit.structural._units import STANDARD_GRAVITY
from napkin2factory.calckit.structural.beams import (
    BendingStressResult,
    DeflectionResult,
    beam_bending_stress,
    beam_deflection_cantilever,
    beam_deflection_simply_supported,
    cantilever_deflection,
    simply_supported_deflection,
    yield_safety_factor,
)
from napkin2factory.calckit.structural.cases import CASES
from napkin2factory.calckit.structural.columns import (
    K_FACTORS,
    K_FACTORS_THEORETICAL,
    BucklingResult,
    ShearResult,
    TipOverResult,
    check_euler_slenderness,
    euler_buckling,
    euler_buckling_load,
    fastener_group_shear,
    tip_over_safety_factor,
)
from napkin2factory.calckit.structural.sections import (
    RectSection,
    RectTubeSection,
    RoundTubeSection,
    rect_section,
    rect_section_inertia,
    rect_tube_section,
    round_tube_section,
    tube_section_inertia,
)

__all__ = [
    "CASES",
    "K_FACTORS",
    "K_FACTORS_THEORETICAL",
    "STANDARD_GRAVITY",
    "BendingStressResult",
    "BucklingResult",
    "DeflectionResult",
    "RectSection",
    "RectTubeSection",
    "RoundTubeSection",
    "ShearResult",
    "TipOverResult",
    "beam_bending_stress",
    "beam_deflection_cantilever",
    "beam_deflection_simply_supported",
    "cantilever_deflection",
    "check_euler_slenderness",
    "euler_buckling",
    "euler_buckling_load",
    "fastener_group_shear",
    "rect_section",
    "rect_section_inertia",
    "rect_tube_section",
    "round_tube_section",
    "simply_supported_deflection",
    "tip_over_safety_factor",
    "tube_section_inertia",
    "yield_safety_factor",
]

# A re-exported function or class keeps this package as its __module__, not the
# submodule that defines it: the calc checker (core/checks/calcs.py) and the
# reference-case coverage test (calckit/_cases.py) find a pack by that name.
for _name in __all__:
    _obj = globals()[_name]
    if inspect.isfunction(_obj) or inspect.isclass(_obj):
        _obj.__module__ = __name__
del _name, _obj, inspect
