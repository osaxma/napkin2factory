"""style.yaml schema (decision N7): the product's look, seeded by ``n2f init``.

Colours and finishes are keyed by **part role**, a small closed vocabulary (``body``,
``door``, ``stand``, ``controls``, ``trim``, ``lining``, ``fastener``, ``default``).  Three
presets are plain data (:data:`PRESETS`); :meth:`StyleFile.resolved` fills whatever the file
leaves out from its preset.  The kit's aesthetic parameters read the shape cues
(``radius_scale``, ``corner_radius``, ``chamfer``, ``reveal``, ``overhang``,
``vent_pattern``) only for parts that opt in with an explicit styling role (see
:data:`STYLED_ROLES`); the screenshot rig and the report viewer read the palette.
"""

from __future__ import annotations

import re
from typing import Any, Literal, get_args

from pydantic import Field, field_validator, model_validator

from napkin2factory.core.model.base import Model, Quantity

StylePreset = Literal["industrial", "appliance", "lab"]
FastenerVisibility = Literal["visible", "hidden-front", "hidden"]
StyleRole = Literal["body", "door", "stand", "controls", "trim", "lining", "fastener", "default"]
FinishName = Literal["powder-coat", "brushed-steel", "painted", "ceramic", "anodized", "plastic"]
VentPattern = Literal["slots", "holes"]

#: Every role, in display order.
STYLE_ROLES: tuple[str, ...] = get_args(StyleRole)
#: Roles whose parts take style-sourced geometry defaults (the opt-in rule): a part with no
#: role, or role ``lining``/``fastener``/``default``, builds exactly as without a style.
STYLED_ROLES: frozenset[str] = frozenset({"body", "door", "stand", "controls", "trim"})

#: Finish name → physically based rendering factors for the viewer (glTF metallic-roughness).
#: These are rendering parameters chosen by eye for the screenshot rig, not engineering
#: numbers: nothing is computed or checked from them.
FINISHES: dict[str, dict[str, float]] = {
    "powder-coat": {"metallic": 0.1, "roughness": 0.6},
    "brushed-steel": {"metallic": 0.9, "roughness": 0.35},
    "painted": {"metallic": 0.0, "roughness": 0.5},
    "ceramic": {"metallic": 0.0, "roughness": 0.8},
    "anodized": {"metallic": 0.7, "roughness": 0.4},
    "plastic": {"metallic": 0.0, "roughness": 0.45},
}

#: The three presets as data.  ``industrial`` is the neutral one: its shape cues are all
#: no-ops, so a product without ``style.yaml`` builds the same geometry as before.
PRESETS: dict[str, dict[str, Any]] = {
    "industrial": {
        "palette": {
            "body": "#4b5157",
            "door": "#3f444a",
            "stand": "#2b2e32",
            "controls": "#e07a2e",
            "trim": "#8c9196",
            "lining": "#cfc6b6",
            "fastener": "#9ba1a7",
            "default": "#5b6167",
        },
        "finish": {
            "body": "powder-coat",
            "door": "powder-coat",
            "stand": "powder-coat",
            "controls": "plastic",
            "trim": "brushed-steel",
            "lining": "ceramic",
            "fastener": "brushed-steel",
            "default": "powder-coat",
        },
        "accent": "#e07a2e",
        "background": "#f4f4f2",
        "radius_scale": 1.0,
        "reveal": "2 mm",
        "fastener_visibility": "visible",
        "corner_radius": "0 mm",
        "chamfer": "0 mm",
        "overhang": "0 mm",
        "vent_pattern": "slots",
    },
    "appliance": {
        "palette": {
            "body": "#efede8",
            "door": "#e6e3dc",
            "stand": "#3a3e42",
            "controls": "#3a3e42",
            "trim": "#b9bdc1",
            "lining": "#d8d1c4",
            "fastener": "#b9bdc1",
            "default": "#d9d7d2",
        },
        "finish": {
            "body": "painted",
            "door": "painted",
            "stand": "powder-coat",
            "controls": "plastic",
            "trim": "brushed-steel",
            "lining": "ceramic",
            "fastener": "brushed-steel",
            "default": "painted",
        },
        "accent": None,
        "background": "#dcdee0",
        "radius_scale": 1.5,
        "reveal": "2 mm",
        "fastener_visibility": "hidden-front",
        "corner_radius": "0 mm",
        "chamfer": "0 mm",
        "overhang": "0 mm",
        "vent_pattern": "slots",
    },
    "lab": {
        "palette": {
            "body": "#d4d8dc",
            "door": "#c9ced3",
            "stand": "#8e959c",
            "controls": "#2f6db5",
            "trim": "#aab1b8",
            "lining": "#d8d1c4",
            "fastener": "#aab1b8",
            "default": "#c4c9ce",
        },
        "finish": {
            "body": "painted",
            "door": "painted",
            "stand": "painted",
            "controls": "plastic",
            "trim": "anodized",
            "lining": "ceramic",
            "fastener": "brushed-steel",
            "default": "painted",
        },
        "accent": "#2f6db5",
        "background": "#f4f4f2",
        "radius_scale": 1.0,
        "reveal": "2 mm",
        "fastener_visibility": "visible",
        "corner_radius": "0 mm",
        "chamfer": "0 mm",
        "overhang": "0 mm",
        "vent_pattern": "slots",
    },
}

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _check_hex(value: str, where: str) -> str:
    if not _HEX.match(value):
        raise ValueError(f"{where} {value!r} is not a colour like '#4b5157'")
    return value.lower()


class StyleFile(Model):
    """``style.yaml``: preset, colours and finishes by part role, and shape cues.

    Fields the file leaves out take their preset's value through :meth:`resolved`.
    """

    preset: StylePreset = "industrial"
    palette: dict[StyleRole, str] = Field(default_factory=dict)
    finish: dict[StyleRole, FinishName] = Field(default_factory=dict)
    accent: str | None = None
    background: str = "#f4f4f2"
    radius_scale: float = Field(default=1.0, gt=0)
    reveal: Quantity = "2 mm"
    fastener_visibility: FastenerVisibility = "visible"
    corner_radius: Quantity = "0 mm"
    chamfer: Quantity = "0 mm"
    overhang: Quantity = "0 mm"
    vent_pattern: VentPattern = "slots"

    @field_validator("palette")
    @classmethod
    def _palette_hex(cls, v: dict[str, str]) -> dict[str, str]:
        return {role: _check_hex(colour, f"palette.{role}") for role, colour in v.items()}

    @field_validator("accent")
    @classmethod
    def _accent_hex(cls, v: str | None) -> str | None:
        return None if v is None else _check_hex(v, "accent")

    @field_validator("background")
    @classmethod
    def _background_hex(cls, v: str) -> str:
        return _check_hex(v, "background")

    @model_validator(mode="after")
    def _shape_cues(self) -> StyleFile:
        for name in ("reveal", "corner_radius", "chamfer", "overhang"):
            q = getattr(self, name)
            if not q.check("[length]"):
                raise ValueError(f"{name} must be a length like '2 mm', got {q}")
            if q.magnitude < 0:
                raise ValueError(f"{name} must not be negative, got {q}")
        if self.corner_radius.magnitude > 0 and self.chamfer.magnitude > 0:
            raise ValueError("a style sets corner_radius or chamfer, not both")
        return self

    def resolved(self) -> StyleFile:
        """A fully populated copy: preset values wherever the file is silent.

        ``palette`` and ``finish`` merge per role (the file's roles win); every other field
        takes the file's value only when the file set it.
        """
        base = PRESETS[self.preset]
        data: dict[str, Any] = {k: v for k, v in base.items() if k not in ("palette", "finish")}
        mine = self.model_dump(mode="json")
        for name in self.model_fields_set - {"palette", "finish"}:
            data[name] = mine[name]
        data["preset"] = self.preset
        data["palette"] = {**base["palette"], **self.palette}
        data["finish"] = {**base["finish"], **self.finish}
        return StyleFile.model_validate(data)

    def colour(self, role: str) -> str:
        """Palette colour for ``role`` (the ``default`` role's when the role has none)."""
        palette: dict[str, str] = {str(k): v for k, v in self.resolved().palette.items()}
        return palette.get(role) or palette.get("default") or "#808080"

    def material(self, role: str) -> dict[str, Any]:
        """Viewer material for ``role``: ``{color, metallic, roughness}`` (resolved style)."""
        r = self.resolved()
        finishes: dict[str, str] = {str(k): str(v) for k, v in r.finish.items()}
        finish = finishes.get(role) or finishes.get("default") or "painted"
        return {"color": r.colour(role), **FINISHES[finish]}


def role_for(obj: Any) -> str:
    """The styling role of a :class:`Part` or :class:`MassingCall`.

    The explicit ``role`` when set; else its ``as`` name (a massing call) or id (a part)
    when that is a role word (``body``, ``door``…); else ``default``.
    """
    role = getattr(obj, "role", None)
    if role:
        return str(role)
    name = getattr(obj, "as_", None) or getattr(obj, "id", None)
    return str(name) if name in STYLE_ROLES else "default"


__all__ = [
    "FINISHES",
    "PRESETS",
    "STYLED_ROLES",
    "STYLE_ROLES",
    "FastenerVisibility",
    "FinishName",
    "StyleFile",
    "StylePreset",
    "StyleRole",
    "VentPattern",
    "role_for",
]
