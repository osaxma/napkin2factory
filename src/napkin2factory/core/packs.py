"""Product-local packs (FOUNDATION F10, S-128): ``model/screens/`` and ``model/rulepacks/``.

A product may carry its own napkin-stage screens and its own rule-pack checks, loaded like
``model/calcs/``: imported fresh for each product root (cached by path and content hash,
never shared between two products) and hashed into what depends on them.

* ``model/screens/*.py`` — each module exposes ``SCREENS``, a sequence of
  :class:`~napkin2factory.core.domain.Screen` (the same contract as a domain's screens, with
  :func:`napkin2factory.concepts.screens.reads` declaring their fields and phase). Hashed into
  the concept build (:func:`screens_hash`).
* ``model/rulepacks/*.yaml`` with their checks in ``model/rulepacks/*.py`` — a module exposes
  ``CHECKS`` (part checks, ``fn(part, features, params, product) -> violations``) and may
  expose ``ASSEMBLY_CHECKS`` (``fn(assembly, params, product)``), the shapes the shipped packs
  use. Hashed into the ``checks`` rule's inputs (:func:`pack_inputs`).

A pack cannot register rule families, verify kinds, report sections or gate rows: those are
the system's (a domain's), never a product's. A module that fails to import is an error that
names the file.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from napkin2factory.core.domain import Screen
from napkin2factory.core.errors import N2FError
from napkin2factory.core.graph.hashing import sha256_file, sha256_text, sha256_tree

SCREENS_DIR = ("model", "screens")
RULEPACKS_DIR = ("model", "rulepacks")
_MODULE_CACHE: dict[str, tuple[str, Any]] = {}


def _folder(root: Path, parts: tuple[str, ...]) -> Path:
    return Path(root).joinpath(*parts)


def _modules(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*.py") if not p.name.startswith("_"))


def load_module(path: Path, kind: str) -> Any:
    """Import one pack module fresh for its product (cached while its content is unchanged)."""
    path = Path(path).resolve()
    name = f"n2f_{kind}_{sha256_text(str(path.parent))[7:19]}_{path.stem}"
    key = f"{path}:{sha256_file(path)}"
    cached = _MODULE_CACHE.get(name)
    if cached is not None and cached[0] == key:
        return cached[1]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise N2FError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        sys.modules.pop(name, None)
        raise N2FError(
            f"model/{path.parent.name}/{path.name} cannot be loaded: {type(exc).__name__}: {exc}"
        ) from exc
    _MODULE_CACHE[name] = (key, mod)
    return mod


def product_screens(root: Path) -> list[Screen]:
    """The screens of ``<root>/model/screens/*.py``, module by module in name order."""
    out: list[Screen] = []
    for path in _modules(_folder(root, SCREENS_DIR)):
        screens = getattr(load_module(path, "screens"), "SCREENS", None)
        if screens is None:
            raise N2FError(
                f"model/screens/{path.name} has no SCREENS: list its screens as "
                '`SCREENS = (Screen("name", run),)`'
            )
        for s in screens:
            if not isinstance(s, Screen):
                raise N2FError(f"model/screens/{path.name}: {s!r} is not a Screen(name, run)")
            out.append(s)
    return out


def screens_hash(root: Path) -> str | None:
    """The hash of ``model/screens/`` (``None`` when the product has no screens)."""
    folder = _folder(root, SCREENS_DIR)
    return sha256_tree(folder, (".py", ".yaml")) if _modules(folder) else None


CheckTable = dict[str, Callable[..., Any]]


def pack_checks(root: Path) -> tuple[CheckTable, CheckTable]:
    """``(part checks, assembly checks)`` of ``<root>/model/rulepacks/*.py``."""
    parts: CheckTable = {}
    assemblies: CheckTable = {}
    for path in _modules(_folder(root, RULEPACKS_DIR)):
        mod = load_module(path, "rulepacks")
        parts.update(getattr(mod, "CHECKS", {}) or {})
        assemblies.update(getattr(mod, "ASSEMBLY_CHECKS", {}) or {})
    return parts, assemblies


def pack_inputs(root: Path) -> dict[str, str]:
    """The ``checks`` rule's input for the product's rule packs; empty without any (F10).

    Empty, not a constant, when the folder is absent, so a product without packs keeps the
    keys it had before packs existed.
    """
    folder = _folder(root, RULEPACKS_DIR)
    if not folder.is_dir() or (not any(folder.glob("*.y*ml")) and not _modules(folder)):
        return {}
    return {"rulepacks": sha256_tree(folder, (".py", ".yaml", ".yml"))}


__all__ = [
    "load_module",
    "pack_checks",
    "pack_inputs",
    "product_screens",
    "screens_hash",
]
