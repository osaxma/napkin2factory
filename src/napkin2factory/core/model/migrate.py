"""The schema version of a product folder and the migrations between versions (F7).

``n2f.yaml`` carries ``schema: <n>``: the version of the file format the product's files
are written in.  The policy is ``docs/schema-policy.md``: an additive optional field with a
default that reproduces the old behaviour does not bump it; a rename, a removal or a
changed meaning bumps :data:`CURRENT`, ships a :class:`Migration` registered here by
``(from, to)`` and a fixture product of the old version under ``tests/fixtures/schema/``.

* :func:`pending` lists the migrations a folder needs, in order (none for a current one).
* :func:`apply` runs them on the folder and writes the new ``schema:``; ``n2f init .`` calls
  it after a snapshot and prints :attr:`Upgrade.changes` in owner words.
* :func:`refuse_unreadable` is the loader's guard: a folder from a newer system stops with a
  plain message, a folder with migrations pending stops and names ``n2f init .``.

The registry is empty while only schema 1 has existed; the test suite registers a throwaway
``1 → 2`` migration to prove the path round-trips (``tests/unit/test_migrate.py``).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.core.errors import ModelError, N2FError, Problems

#: The schema this system reads and writes.  Bumped only with a registered migration (F7).
CURRENT = 1

#: The schema a folder without a ``schema:`` key is read as (every v0.1–v0.4 product had 1).
DEFAULT = 1

MANIFEST = "n2f.yaml"


class SchemaError(N2FError):
    """A product folder's schema cannot be read or brought up to date by this system."""


class NewerSchema(SchemaError):
    """The folder was written by a newer napkin2factory than the one installed."""


@dataclass(frozen=True)
class Migration:
    """One step from schema ``from_version`` to ``to_version``.

    Attributes:
        from_version: the schema it reads.
        to_version: the schema it writes (usually ``from_version + 1``).
        title: what changes, in the owner's words ("the space a product must fit is now
            called site width, depth and height").
        run: ``run(root)`` edits the files under the product folder ``root`` in place and
            returns one owner-word line per change it made ("n2f.yaml: renamed …").  It
            never touches ``schema:``; :func:`apply` writes that after the last step.
    """

    from_version: int
    to_version: int
    title: str
    run: Callable[[Path], list[str]]


@dataclass
class Upgrade:
    """What :func:`apply` did: the versions and the owner-word lines of each step."""

    from_version: int
    to_version: int
    steps: list[Migration] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON form (``n2f init --json``)."""
        return {
            "from": self.from_version,
            "to": self.to_version,
            "steps": [m.title for m in self.steps],
            "changes": self.changes,
        }


_REGISTRY: dict[tuple[int, int], Migration] = {}


def register(migration: Migration) -> None:
    """Add a migration to the registry (one per ``(from, to)``).

    Raises:
        ValueError: a migration for the same ``(from, to)`` is registered already, or the
            step does not go forwards.
    """
    key = (migration.from_version, migration.to_version)
    if migration.to_version <= migration.from_version:
        raise ValueError(f"a migration goes forwards; got {key[0]} → {key[1]}")
    if key in _REGISTRY:
        raise ValueError(f"a migration {key[0]} → {key[1]} is registered already")
    _REGISTRY[key] = migration


def unregister(from_version: int, to_version: int) -> None:
    """Remove a migration (tests)."""
    _REGISTRY.pop((from_version, to_version), None)


def registered() -> list[Migration]:
    """Every registered migration, by ``(from, to)``."""
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


@contextmanager
def registered_migration(migration: Migration) -> Iterator[Migration]:
    """Register ``migration`` for a block of code (tests); removed afterwards."""
    register(migration)
    try:
        yield migration
    finally:
        unregister(migration.from_version, migration.to_version)


def _root(product_or_root: Any) -> Path:
    paths = getattr(product_or_root, "paths", None)
    return Path(paths.root) if paths is not None else Path(product_or_root)


def schema_of(product_or_root: Any) -> int:
    """The ``schema:`` a product folder declares (:data:`DEFAULT` when the key is absent).

    Reads ``n2f.yaml`` as plain YAML, before any model validation, so a folder whose files
    this system cannot validate yet still says which version it is.  A value that is not a
    whole number is left to the manifest's own validation (returns :data:`DEFAULT`).
    """
    from napkin2factory.core.yamlio import read_yaml

    path = _root(product_or_root) / MANIFEST
    try:
        data = read_yaml(path)
    except Exception:  # unreadable YAML is the loader's message to give, not ours
        return DEFAULT
    value = data.get("schema", DEFAULT) if isinstance(data, dict) else DEFAULT
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT
    return value


def newer_message(found: int) -> str:
    """The plain sentence for a folder written by a newer system."""
    from napkin2factory import __version__

    return (
        f"this product's files were saved by a newer napkin2factory (file format {found}); "
        f"the installed version {__version__} reads format {CURRENT} and older. Update "
        "napkin2factory, then try again; nothing was changed"
    )


def pending(product_or_root: Any) -> list[Migration]:
    """The migrations that bring a folder up to :data:`CURRENT`, in order (empty if current).

    Args:
        product_or_root: a loaded product or the path of a product folder.

    Raises:
        NewerSchema: the folder declares a schema above :data:`CURRENT`.
        SchemaError: no chain of registered migrations leads from its schema to
            :data:`CURRENT`.
    """
    found = schema_of(product_or_root)
    if found > CURRENT:
        raise NewerSchema(newer_message(found))
    chain: list[Migration] = []
    version = found
    while version < CURRENT:
        steps = [m for (a, _), m in sorted(_REGISTRY.items()) if a == version]
        steps = [m for m in steps if m.to_version <= CURRENT]
        if not steps:
            raise SchemaError(
                f"this product's files are in file format {found} and no update from format "
                f"{version} is installed; the installed napkin2factory reads format {CURRENT}"
            )
        step = max(steps, key=lambda m: m.to_version)  # the longest registered stride
        chain.append(step)
        version = step.to_version
    return chain


_SCHEMA_LINE = re.compile(r"^schema:[^\n#]*", re.MULTILINE)


def _write_schema(root: Path, version: int) -> None:
    """Rewrite only the ``schema:`` line (or add it first), so nothing else in the file moves."""
    path = root / MANIFEST
    text = path.read_text(encoding="utf-8")
    if _SCHEMA_LINE.search(text):
        text = _SCHEMA_LINE.sub(f"schema: {version}", text, count=1)
    else:
        text = f"schema: {version}\n{text}"
    path.write_text(text, encoding="utf-8")


def apply(product_or_root: Any) -> Upgrade:
    """Run the pending migrations on the folder and write the new ``schema:``.

    The caller saves a snapshot first (``n2f init .`` does), so the owner can go back.
    Returns an :class:`Upgrade` whose ``changes`` are the steps' owner-word lines; an
    up-to-date folder returns an empty upgrade and is not touched.

    Raises:
        NewerSchema: as :func:`pending`.
        SchemaError: as :func:`pending`.
    """
    root = _root(product_or_root)
    found = schema_of(root)
    steps = pending(root)
    upgrade = Upgrade(from_version=found, to_version=found)
    for step in steps:
        upgrade.changes += step.run(root)
        upgrade.steps.append(step)
        upgrade.to_version = step.to_version
        _write_schema(root, step.to_version)  # each step leaves a consistent folder
    return upgrade


def refuse_unreadable(manifest: Path, problems: Problems) -> None:
    """Stop loading a folder this system cannot read as it is (the loader's one call, F7).

    A newer schema stops with :func:`newer_message`; an older one with migrations pending
    stops and names ``n2f init .``.  A current folder returns without a word.

    Raises:
        ModelError: one problem on ``n2f.yaml`` saying what to do.
    """
    root = manifest.parent
    found = schema_of(root)
    if found == CURRENT:
        return
    if found > CURRENT:
        problems.add(
            manifest,
            "n2f.yaml",
            newer_message(found),
            "update napkin2factory (the agent guide's install step), then run the command again",
            rule="schema",
        )
        raise ModelError(problems, "product saved by a newer napkin2factory")
    problems.add(
        manifest,
        "n2f.yaml",
        f"this product's files are in an older file format ({found}; the installed "
        f"napkin2factory reads {CURRENT})",
        "run `n2f init .` in the product folder: it saves a snapshot, then brings the files "
        "up to date and says what changed",
        rule="schema",
    )
    raise ModelError(problems, "product files need updating")


__all__ = [
    "CURRENT",
    "DEFAULT",
    "Migration",
    "NewerSchema",
    "SchemaError",
    "Upgrade",
    "apply",
    "newer_message",
    "pending",
    "refuse_unreadable",
    "register",
    "registered",
    "registered_migration",
    "schema_of",
    "unregister",
]
