"""style.yaml schema (decision N7): the product's look, seeded by ``n2f init``.

Colours and finishes are keyed by **part role**, a table of neutral words
(``core/data/style_roles.yaml``: ``body``, ``opening``, ``support``, ``controls``, ``trim``,
``lining``, ``fastener``, ``default``; F6, F9) plus the roles domains register
(``Domain.style_roles``).  The earlier words ``door`` and ``stand`` are
read as aliases of ``opening`` and ``support`` for one version (F16).  Three
presets are plain data (:data:`PRESETS`); :meth:`StyleFile.resolved` fills whatever the file
leaves out from its preset.  The kit's aesthetic parameters read the shape cues
(``radius_scale``, ``corner_radius``, ``chamfer``, ``reveal``, ``overhang``,
``vent_pattern``) only for parts that opt in with an explicit styling role (see
:data:`STYLED_ROLES`); the screenshot rig and the report viewer read the palette.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from collections.abc import Set as AbstractSet
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from napkin2factory.core.model.base import Model, Quantity, table_check

StylePreset = Literal["industrial", "appliance", "lab"]
FastenerVisibility = Literal["visible", "hidden-front", "hidden"]


def _roles() -> dict[str, Any]:
    """The style-role registry: ``core/data/style_roles.yaml`` plus the domains' (F6)."""
    from napkin2factory.core.registry import registry

    return registry().style_roles()


class _RoleNames(Sequence[str]):
    """Every role, in display order (the table's, then the domains'), read live."""

    def __getitem__(self, i: Any) -> Any:
        return tuple(_roles())[i]

    def __len__(self) -> int:
        return len(_roles())

    def __iter__(self) -> Iterator[str]:
        return iter(tuple(_roles()))

    def __contains__(self, x: object) -> bool:
        return x in _roles()

    def __eq__(self, other: object) -> bool:
        return tuple(self) == (tuple(other) if isinstance(other, (tuple, list)) else other)

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return repr(tuple(self))


class _RoleMap(Mapping[str, str]):
    """A live mapping over the registered roles (``pick`` says which)."""

    def __init__(self, pick: Callable[[], dict[str, str]]) -> None:
        self._pick = pick

    def __getitem__(self, key: str) -> str:
        return self._pick()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._pick())

    def __len__(self) -> int:
        return len(self._pick())

    def __repr__(self) -> str:
        return repr(self._pick())


class _RoleSet(AbstractSet[str]):
    """The styled roles and their aliases, read live."""

    def __contains__(self, x: object) -> bool:
        return x in _styled()

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(_styled()))

    def __len__(self) -> int:
        return len(_styled())

    def __repr__(self) -> str:
        return repr(frozenset(_styled()))


def _aliases() -> dict[str, str]:
    return {a: r.id for r in _roles().values() for a in r.aliases}


def _styled() -> frozenset[str]:
    styled = {r.id for r in _roles().values() if r.styled}
    return frozenset(styled | {a for a, role in _aliases().items() if role in styled})


# These read the registry on each use (they are views, not copies), so a domain's roles,
# registered after this module is imported, are seen wherever they were imported (S-129).
#: Every role, in display order (the table's, then the domains').
STYLE_ROLES: Sequence[str] = _RoleNames()
#: An earlier role word → the role it is read as, for one version (F16, S-128).
ROLE_ALIASES: Mapping[str, str] = _RoleMap(_aliases)
#: Each role in the owner's words.
ROLE_WORDS: Mapping[str, str] = _RoleMap(lambda: {k: r.words for k, r in _roles().items()})


def canonical_role(name: str) -> str:
    """The role a word stands for: ``door`` → ``opening``; a role is itself."""
    return ROLE_ALIASES.get(name, name)


def _role_names() -> list[str]:
    return [*STYLE_ROLES, *ROLE_ALIASES]


#: A styling role: a word of the table or one of its aliases, kept as written (a part's
#: ``role: door`` reads, and hashes, as before); :func:`canonical_role` resolves it.
StyleRole = Annotated[str, table_check("style role", _role_names)]


def _finishes() -> dict[str, dict[str, float]]:
    from napkin2factory.core.registry import registry

    return registry().finishes()


#: A finish: ``core/data/finishes.yaml`` plus the domains' (F6).
FinishName = Annotated[str, table_check("finish", _finishes)]
VentPattern = Literal["slots", "holes"]

#: Roles whose parts take style-sourced geometry defaults (the opt-in rule): a part with no
#: role, or role ``lining``/``fastener``/``default``, builds exactly as without a style.
#: The aliases are members too, so a part written ``role: door`` builds as it did.
STYLED_ROLES: AbstractSet[str] = _RoleSet()


def __getattr__(name: str) -> Any:
    """``FINISHES`` is the finishes table (F6), read on each access.

    Finish → glTF metallic-roughness factors, chosen by eye for the screenshot rig, not
    engineering numbers (``core/data/finishes.yaml``).
    """
    if name == "FINISHES":
        return _finishes()
    raise AttributeError(name)


#: The three presets as data.  ``industrial`` is the neutral one: its shape cues are all
#: no-ops, so a product without ``style.yaml`` builds the same geometry as before.
PRESETS: dict[str, dict[str, Any]] = {
    "industrial": {
        "palette": {
            "body": "#4b5157",
            "opening": "#3f444a",
            "support": "#2b2e32",
            "controls": "#e07a2e",
            "trim": "#8c9196",
            "lining": "#cfc6b6",
            "fastener": "#9ba1a7",
            "default": "#5b6167",
        },
        "finish": {
            "body": "powder-coat",
            "opening": "powder-coat",
            "support": "powder-coat",
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
            "opening": "#e6e3dc",
            "support": "#3a3e42",
            "controls": "#3a3e42",
            "trim": "#b9bdc1",
            "lining": "#d8d1c4",
            "fastener": "#b9bdc1",
            "default": "#d9d7d2",
        },
        "finish": {
            "body": "painted",
            "opening": "painted",
            "support": "powder-coat",
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
            "opening": "#c9ced3",
            "support": "#8e959c",
            "controls": "#2f6db5",
            "trim": "#aab1b8",
            "lining": "#d8d1c4",
            "fastener": "#aab1b8",
            "default": "#c4c9ce",
        },
        "finish": {
            "body": "painted",
            "opening": "painted",
            "support": "painted",
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
    #: Where things go, in words (``{controls: side-right, door: hinged-left}``), as chosen
    #: with the promoted concept; the ``form-v0`` controls-placement rule reads it (N8).
    layout: dict[str, str] = Field(default_factory=dict)

    @field_validator("palette")
    @classmethod
    def _palette_hex(cls, v: dict[str, str]) -> dict[str, str]:
        return {
            canonical_role(role): _check_hex(colour, f"palette.{role}")
            for role, colour in v.items()
        }

    @field_validator("finish")
    @classmethod
    def _finish_roles(cls, v: dict[str, str]) -> dict[str, str]:
        return {canonical_role(role): finish for role, finish in v.items()}

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
        return {"color": r.colour(role), **_finishes()[finish]}


def role_for(obj: Any) -> str:
    """The styling role of a :class:`Part` or :class:`MassingCall`.

    The explicit ``role`` when set; else its ``as`` name (a massing call) or id (a part)
    when that is a role word (``body``, ``opening``…) or an alias of one; else ``default``.
    Always the table's word: an alias (``door``) reads as its role (``opening``).
    """
    role = getattr(obj, "role", None)
    if role:
        return canonical_role(str(role))
    name = getattr(obj, "as_", None) or getattr(obj, "id", None)
    if name in STYLE_ROLES or name in ROLE_ALIASES:
        return canonical_role(str(name))
    return "default"


__all__ = [
    "PRESETS",
    "ROLE_ALIASES",
    "ROLE_WORDS",
    "STYLED_ROLES",
    "STYLE_ROLES",
    "FastenerVisibility",
    "FinishName",
    "StyleFile",
    "StylePreset",
    "StyleRole",
    "VentPattern",
    "canonical_role",
    "role_for",
]
