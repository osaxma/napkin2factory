"""Which files are the design direction and which stay with the product (v0.8 §3, R10).

A direction switch puts the *direction* files back from a parked state and leaves the
*product* files (cards, requirements, decisions, change records…) as they are. The two lists
are the rule; a tracked folder neither names stops the switch (S-264), because guessing
which side a new kind of file belongs to would lose or duplicate an owner's work.
"""

from __future__ import annotations

from collections.abc import Iterable

#: Fixed direction files and folders (the domain families' folders are added by
#: :func:`direction_paths`). Folders have no trailing slash: the store takes them as prefixes.
_DIRECTION_FIXED: tuple[str, ...] = (
    "model/parameters.yaml",
    "model/parts",
    "model/geometry",
    "model/assemblies",
    "model/interfaces",
    "model/calcs",
    "model/docs",
    "model/tests",
    "model/signoffs",
    "style.yaml",
)

#: What the product keeps across a switch: its record, its rules, its history, its setup.
PRODUCT_PATHS: tuple[str, ...] = (
    "concepts",
    "model/requirements.yaml",
    "model/intake.md",
    "model/decisions.yaml",
    "model/screens",
    "model/rulepacks",
    "model/manufacturers",
    "changes",
    "CHANGELOG.md",
    "reports",
    "n2f.yaml",
    "operator.yaml",
    "AGENTS.md",
    "roles",
    "SPEC.md",
    "SPEC.oracle.yaml",
    ".github",
    ".gitignore",
)


def direction_paths() -> list[str]:
    """The direction paths: the fixed list plus every registered domain family's folder."""
    from napkin2factory.core.registry import registry

    extra = [f.folder.strip("/") for f in registry().model_families()]
    return list(dict.fromkeys([*_DIRECTION_FIXED, *extra]))


def _covered(path: str, prefixes: Iterable[str]) -> bool:
    return any(path == p or path.startswith(p + "/") for p in prefixes)


def unnamed_entries(tracked: Iterable[str], direction: Iterable[str] | None = None) -> list[str]:
    """Tracked top-level folders and entries directly under ``model/`` that neither list names.

    A tracked top-level *file* neither list names (an example's ``demo.sh``) stays with the
    product and is not reported. A domain family folder nested under a folder the registry
    names only in part (``model/electrical/supplies``) makes the whole entry named.
    """
    dpaths = list(direction) if direction is not None else direction_paths()
    named = [*dpaths, *PRODUCT_PATHS]
    # an entry under model/ that holds a named family folder is named as a whole
    parents = {"/".join(p.split("/")[:2]) for p in dpaths if p.count("/") >= 2}
    found: set[str] = set()
    for path in tracked:
        if _covered(path, named) or _covered(path, parents):
            continue
        parts = path.split("/")
        if len(parts) == 1:
            continue  # a top-level file stays with the product
        found.add("/".join(parts[:2]) if parts[0] == "model" else parts[0])
    return sorted(found)
