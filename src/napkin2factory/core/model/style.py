"""style.yaml schema (decision N7): the product's look, seeded by ``n2f init``.

Minimal in M1; ``n2f concept promote`` fills it and the kit's aesthetic parameters read it
from M3 on.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from napkin2factory.core.model.base import Model, Quantity

StylePreset = Literal["industrial", "appliance", "lab"]
FastenerVisibility = Literal["visible", "hidden-front", "hidden"]


class StyleFile(Model):
    """``style.yaml``: preset, colours and finishes by part role, and shape cues."""

    preset: StylePreset = "industrial"
    palette: dict[str, str] = Field(default_factory=dict)
    finish: dict[str, str] = Field(default_factory=dict)
    radius_scale: float = Field(default=1.0, gt=0)
    reveal: Quantity = "2 mm"
    fastener_visibility: FastenerVisibility = "visible"
