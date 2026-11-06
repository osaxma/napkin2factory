"""``n2f concept fork-from-model`` and ``n2f concept compare`` (v0.8 R11).

The verbs land in M3a; this module is registered from ``cli/concept.py``, S-257: new verbs
go in their own module, not in the concept command file.
"""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    """Attach the ``fork-from-model`` and ``compare`` verbs to the concept group (no verbs yet)."""
    return None
