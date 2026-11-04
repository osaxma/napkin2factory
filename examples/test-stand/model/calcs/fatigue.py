"""Fatigue of the frame beams and the column-end bolts at the design cycle count (SPEC 4.3)."""

from __future__ import annotations

from _stand import FRAME_MATERIAL, _beam_peak_stress

from napkin2factory.calckit import joints
from napkin2factory.core.units import Quantity


def beam_fatigue_factor(P):  # noqa: N803
    """Modified Goodman factor of the beams for a load of 0 to F to 0 (R = 0).

    The stress amplitude and the mean stress are each half the peak stress (Shigley chapter 6,
    via ``joints.fatigue_margin``). The aluminium has no endurance limit, so its strength at
    5e8 cycles is used at the design cycle count, which is conservative.
    """
    half = _beam_peak_stress(P).stress / 2
    return Quantity(
        joints.fatigue_margin(
            half,
            half,
            FRAME_MATERIAL,
            P["test-cycles"],
            ultimate_strength=P["beam-sut"],
            sn_strength=P["beam-sf"],
        ),
        "",
    )


def bolt_fatigue_factor(P):  # noqa: N803
    """Goodman factor of a preloaded column-end bolt.

    Shigley section 8-11 [verify the equation number]; a hand check, since
    ``joints.fatigue_margin`` has no preload term.

    Preload 0.75 of the proof strength (Eq. 8-31 [verify]); the joint constant is taken as 1,
    so the bolt sees all the external load (conservative): sigma_a = (P_ext / A_t) / 2 and
    n_f = S_e (S_ut - sigma_i) / [sigma_a (S_ut + S_e)].
    """
    external = (P["rated-load"] / 2) / P["bolts-per-joint"]  # 0 -> this per bolt
    sigma_a = (external / P["bolt-area"] / 2).to("MPa")
    sigma_i = 0.75 * P["bolt-sp"]
    factor = P["bolt-se"] * (P["bolt-sut"] - sigma_i) / (sigma_a * (P["bolt-sut"] + P["bolt-se"]))
    return Quantity(float(factor.to("").magnitude), "")
