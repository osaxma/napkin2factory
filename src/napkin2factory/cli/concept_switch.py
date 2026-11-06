"""``n2f concept switch`` (v0.8 R10): move the chosen direction to another card.

The verb lands in M3a; this module is registered from ``cli/concept.py``, S-257: new verbs
go in their own module, not in the concept command file.
"""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    """Attach the ``switch`` verb to the concept command group (no verbs yet)."""
    return None
