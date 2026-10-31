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
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from napkin2factory.core.errors import N2FError
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
