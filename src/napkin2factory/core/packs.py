"""Product-local packs (FOUNDATION F10, S-128): ``model/screens/`` and ``model/rulepacks/``.

A product may carry its own napkin-stage screens and its own rule-pack checks, loaded like
``model/calcs/``: imported fresh for each product root (cached by path and content hash,
never shared between two products) and hashed into what depends on them.

* ``model/screens/*.py`` — each module exposes ``SCREENS``, a sequence of
  :class:`~napkin2factory.core.domain.Screen` (the same contract as a domain's screens, with
  :func:`napkin2factory.concepts.screens.reads` declaring their fields and phase). Hashed into
  the concept build (:func:`screens_hash`). A module may also expose ``WORDS``, the product's
  own words for what the system's generic rows name (:data:`WORD_KEYS`; :func:`product_words`).
* ``model/rulepacks/*.yaml`` with their checks in ``model/rulepacks/*.py`` — a module exposes
  ``CHECKS`` (part checks, ``fn(part, features, params, product) -> violations``) and may
  expose ``ASSEMBLY_CHECKS`` (``fn(assembly, params, product)``), the shapes the shipped packs
  use. Hashed into the ``checks`` rule's inputs (:func:`pack_inputs`).

A pack cannot register rule families, verify kinds, report sections or gate rows: those are
the system's (a domain's), never a product's. A module that fails to import, and a product
check that fails while running, is a plain error that names the file and the next step, never
a traceback (gate F, S-137); a product screen that fails while running likewise
(:mod:`napkin2factory.concepts.screens.runner`).
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
#: The words a screens module's ``WORDS`` may give, with what each names (S-137): the
#: system's generic rows say "the space" unless the product calls it something else (a
#: "recess"), so no product's noun is the system's.
WORD_KEYS: dict[str, str] = {"space": "the space the product must fit"}


def move_out(folder: str) -> str:
    """The next step after a pack file fails: fix it, or take it out of ``folder``."""
    return f"fix that file, or move it out of model/{folder}/ to go on without it"


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
            f" → {move_out(path.parent.name)}"
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


def product_words(root: Path | None) -> dict[str, str]:
    """The product's own words for the generic rows (``WORDS`` of its screens modules).

    Modules are read in name order; a later module's word wins. Empty without a root, a
    ``model/screens/`` folder or any ``WORDS``. An unknown key or a word that is not text is
    an error naming the file and the keys there are (:data:`WORD_KEYS`).
    """
    if root is None:
        return {}
    out: dict[str, str] = {}
    for path in _modules(_folder(root, SCREENS_DIR)):
        words = getattr(load_module(path, "screens"), "WORDS", None)
        if words is None:
            continue
        known = ", ".join(f"{k} ({v})" for k, v in WORD_KEYS.items())
        if not isinstance(words, dict):
            raise N2FError(
                f"model/screens/{path.name}: WORDS must be a mapping like "
                f'`WORDS = {{"space": "recess"}}`; the words there are: {known}'
            )
        for key, word in words.items():
            if key not in WORD_KEYS or not isinstance(word, str) or not word.strip():
                raise N2FError(
                    f"model/screens/{path.name}: WORDS has {key!r}: {word!r}; give text for "
                    f"one of: {known}"
                )
            out[key] = word.strip()
    return out


def screens_hash(root: Path) -> str | None:
    """The hash of ``model/screens/`` (``None`` when the product has no screens)."""
    folder = _folder(root, SCREENS_DIR)
    return sha256_tree(folder, (".py", ".yaml")) if _modules(folder) else None


CheckTable = dict[str, Callable[..., Any]]


def _plain_failures(fn: Callable[..., Any], file: str, name: str) -> Callable[..., Any]:
    """``fn``, raising a plain error naming the file and the check when it fails (gate F)."""
    from napkin2factory.rulepacks.checks import RuleNotApplicable, RuleSkip

    def run(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except (RuleNotApplicable, RuleSkip, N2FError):
            raise  # the checks' own signals, and errors already in plain words
        except Exception as exc:
            subject = getattr(args[0], "uri", None) if args else None
            on = f" on {subject}" if subject else ""
            raise N2FError(
                f"model/rulepacks/{file}: the check '{name}' failed while running{on} "
                f"({type(exc).__name__}: {exc}) → {move_out('rulepacks')}, then run "
                "`n2f check` again"
            ) from exc

    run.__wrapped__ = fn  # type: ignore[attr-defined]
    return run


def pack_checks(root: Path) -> tuple[CheckTable, CheckTable]:
    """``(part checks, assembly checks)`` of ``<root>/model/rulepacks/*.py``.

    Each is wrapped so that one failing while running is a plain error naming its file and
    check, not a traceback (gate F, S-137).
    """
    parts: CheckTable = {}
    assemblies: CheckTable = {}
    for path in _modules(_folder(root, RULEPACKS_DIR)):
        mod = load_module(path, "rulepacks")
        for table, attr in ((parts, "CHECKS"), (assemblies, "ASSEMBLY_CHECKS")):
            for name, fn in (getattr(mod, attr, {}) or {}).items():
                table[name] = _plain_failures(fn, path.name, str(name))
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
    "WORD_KEYS",
    "load_module",
    "move_out",
    "pack_checks",
    "pack_inputs",
    "product_screens",
    "product_words",
    "screens_hash",
]
