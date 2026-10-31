"""The kit of parts (decision D4): tested parametric generators agents compose.

Every generator lives in its own module and exposes::

    ARGS: type[KitArgs]                    # pydantic schema of its arguments
    def generate(args: KitArgs, ctx: KitContext) -> PartResult
    def massing(args: KitArgs, ctx: KitContext) -> PartResult   # silhouette only (N3)

``args`` arrive already resolved: ``param://`` references are read through ``P`` (so the
dependency is recorded), ``"15 mm"`` strings are pint quantities, ``iface://`` references
are :class:`Interface` models read through ``I``.  Generators convert at their boundary
with :func:`mm`.  They never touch YAML and never read parameters by name themselves.

Massing fidelity (N3) is a mode of the same generators: with ``ctx.fidelity ==
"massing"`` :func:`run` calls ``massing`` instead of ``generate``.  It runs the same
argument validation (an impossible composition still fails for real) and then builds the
silhouette from primitive solids, never touching bend, hole, fillet or flat-pattern code.

Aesthetic parameters (N7): ``ctx.style`` carries the product's resolved ``style.yaml`` and
``ctx.role`` the part's explicit role.  :attr:`KitContext.styled` hands a generator the
style only at full fidelity and only for the roles in ``STYLED_ROLES`` (body, door, stand,
controls, trim); every other part builds exactly as without a style.  A style default fills
only arguments the part left unset, and one that does not fit the part is skipped with a
note instead of failing the build.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from napkin2factory.core.errors import N2FError
from napkin2factory.core.model.style import STYLED_ROLES, StyleFile
from napkin2factory.core.units import mm
from napkin2factory.geometry.features import PartResult

GENERATORS: tuple[str, ...] = (
    "plate",
    "block",
    "tube",
    "panel",
    "hole_pattern",
    "bracket_l",
    "enclosure",
    "frame",
)


class KitArgs(BaseModel):
    """Base for generator argument schemas: unknown keys are errors."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)


@dataclass
class KitContext:
    """What a generator may know beyond its arguments."""

    part_id: str
    material_name: str = ""
    interfaces: dict[str, Any] = field(default_factory=dict)  # iface id → Interface (already read)
    kit: Any = None  # the kit namespace, so composite generators can call siblings
    fidelity: Literal["full", "massing"] = "full"  # massing → silhouettes only (N3)
    style: StyleFile | None = None  # the product's resolved style.yaml (N7)
    role: str | None = None  # the part's explicit styling role

    @property
    def styled(self) -> StyleFile | None:
        """The style when this part opts in to style geometry defaults, else ``None``.

        Opt-in rule (N7): full fidelity, a style present, and an explicit role among
        body, door, stand, controls and trim.
        """
        if self.fidelity != "full" or self.style is None or self.role not in STYLED_ROLES:
            return None
        return self.style

    @property
    def uri(self) -> str:
        """``part://<id>``."""
        return f"part://{self.part_id}"


Generator = Callable[[Any, KitContext], PartResult]


class KitError(N2FError, ValueError):
    """A generator was called with bad arguments or cannot build the requested shape."""


def get_module(name: str) -> Any:
    """Import ``napkin2factory.geometry.kit.<name>`` or raise :class:`KitError`."""
    if name not in GENERATORS:
        raise KitError(f"unknown kit generator {name!r}; available: {', '.join(GENERATORS)}")
    return importlib.import_module(f"napkin2factory.geometry.kit.{name}")


def run(name: str, args: dict[str, Any], ctx: KitContext) -> PartResult:
    """Validate ``args`` against the generator's schema and run it.

    Calls the generator's ``massing`` when ``ctx.fidelity == "massing"``, else ``generate``.
    """
    mod = get_module(name)
    try:
        parsed = mod.ARGS.model_validate(args)
    except Exception as exc:
        raise KitError(f"kit {name} for {ctx.uri}: bad arguments: {exc}") from exc
    builder = mod.massing if ctx.fidelity == "massing" else mod.generate
    result: PartResult = builder(parsed, ctx)
    return result


class Kit:
    """Namespace handed to geometry modules as ``kit``: ``kit.plate(width=..., ...)``.

    Calls follow ``ctx.fidelity``, so a custom module run under a massing context gets
    silhouettes from every generator it composes.
    """

    def __init__(self, ctx: KitContext) -> None:
        self._ctx = ctx
        ctx.kit = self

    def __getattr__(self, name: str) -> Callable[..., PartResult]:
        if name.startswith("_") or name not in GENERATORS:
            raise AttributeError(name)

        def call(**kwargs: Any) -> PartResult:
            return run(name, kwargs, self._ctx)

        return call


__all__ = ["GENERATORS", "Kit", "KitArgs", "KitContext", "KitError", "get_module", "mm", "run"]
