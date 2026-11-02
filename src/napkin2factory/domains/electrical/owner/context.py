"""What ``n2f context asm://<id>`` adds for the wiring (F1; M4 fills it).

The circuits whose devices sit in the module, their connections, and the cable entries that
are its ports (stub: nothing yet).
"""

from __future__ import annotations

from typing import Any

from napkin2factory.core.domain import ContextContribution


def wiring_context(product: Any, aid: str, members: list[str]) -> list[str]:
    """Markdown lines for the module ``aid`` (stub: none)."""
    return []


CONTEXT = (ContextContribution("electrical", "Wiring in this module", wiring_context),)
