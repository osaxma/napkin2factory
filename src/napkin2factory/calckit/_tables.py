"""Data tables shipped with the calc kit (``calckit/data/<name>.yaml``).

Every table is a list of rows; every row names where its numbers come from (``source``)
and whether a person still has to confirm them (``verify``). Nothing in these tables is
verified by the project yet: they are the owner's to confirm, and DECISIONS.md lists each
table as ``[verify]``. A lookup key a table does not know (a region, a process class, a
material class) is never an error: the pack functions return an ``unknown`` verdict and
the caller warns.
"""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path
from typing import Any

from napkin2factory.core.yamlio import read_yaml

DATA_DIR = Path(__file__).parent / "data"

#: Keys every row of every table must carry.
REQUIRED_ROW_KEYS = ("source", "verify")


class TableError(ValueError):
    """A calc-kit table is missing or malformed; the message says which file to fix."""


def table_names() -> list[str]:
    """Names of the shipped tables (file stems under ``calckit/data``)."""
    return sorted(p.stem for p in DATA_DIR.glob("*.yaml"))


@lru_cache(maxsize=None)
def _load(name: str) -> tuple[dict[str, Any], ...]:
    path = DATA_DIR / f"{name}.yaml"
    if not path.is_file():
        raise TableError(
            f"no calc-kit table {name!r}: expected {path}; shipped tables are "
            f"{', '.join(table_names()) or 'none'}"
        )
    data = read_yaml(path)
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise TableError(f"{path}: expected a non-empty 'rows:' list")
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise TableError(f"{path}: row {i} is not a mapping")
        for key in REQUIRED_ROW_KEYS:
            if key not in row:
                raise TableError(
                    f"{path}: row {i} has no {key!r} key; every row must say where its "
                    "numbers come from ('source') and whether they still need a person's "
                    "confirmation ('verify: true')"
                )
        if not isinstance(row["source"], str) or not row["source"].strip():
            raise TableError(f"{path}: row {i} has an empty 'source'")
        if not isinstance(row["verify"], bool):
            raise TableError(f"{path}: row {i} 'verify' must be true or false")
    return tuple(rows)


def load_table(name: str) -> list[dict[str, Any]]:
    """Rows of ``calckit/data/<name>.yaml``, validated, read once and cached.

    Each call returns a fresh copy, so callers may modify the rows.

    Raises:
        TableError: the table does not exist, or a row lacks ``source`` or ``verify``.
    """
    return copy.deepcopy(list(_load(name)))
