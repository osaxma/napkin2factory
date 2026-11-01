"""What a product's own screens add to a promotion (F10, B-0086, S-131).

A screens module in the product's ``model/screens/`` (the same module that exposes
``SCREENS``) may also expose:

* ``PROMOTE_REQUIREMENTS`` — ``fn(card, seeded, top, notes) -> [(about, fields), ...]``:
  requirements its fields imply, in the shape :func:`~.site.site_requirements` returns
  (``title``, ``statement``, ``category``, ``verify``, ``rationale``; ``allocation`` defaults
  to the top assembly). ``seeded`` is the list of :class:`~.common.SeededParam` (``name``,
  ``source`` such as ``envelope.power``); notes it appends are said to the owner. They are
  written after the space the product must fit and before its weight.
* ``PROMOTE_RATIONALE`` — screening value keys the decision quotes, after the size and mass.

So a value only one product's screens produce (a heated box's supply circuit) is seeded by
that product, never named by the system. Modules load as ``core.packs`` loads the screens.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napkin2factory.core.model.concepts import ConceptCard


def pack_modules(root: Path | None) -> list[Any]:
    """The product's screens modules, in name order (none without ``model/screens/``)."""
    from napkin2factory.core.packs import load_module

    folder = Path(root) / "model" / "screens" if root is not None else None
    if folder is None or not folder.is_dir():
        return []
    return [
        load_module(p, "screens") for p in sorted(folder.glob("*.py")) if not p.name.startswith("_")
    ]


def pack_requirements(
    root: Path | None, card: ConceptCard, seeded: list[Any], top: str | None, notes: list[str]
) -> list[tuple[str, dict[str, Any]]]:
    """Every ``PROMOTE_REQUIREMENTS`` row of the product's screens, module by module."""
    out: list[tuple[str, dict[str, Any]]] = []
    for mod in pack_modules(root):
        seed = getattr(mod, "PROMOTE_REQUIREMENTS", None)
        if seed is not None:
            out += list(seed(card, seeded, top, notes))
    return out


def pack_rationale_keys(root: Path | None) -> tuple[str, ...]:
    """Every ``PROMOTE_RATIONALE`` key of the product's screens, without repeats."""
    keys: list[str] = []
    for mod in pack_modules(root):
        keys += [k for k in getattr(mod, "PROMOTE_RATIONALE", ()) if k not in keys]
    return tuple(keys)
