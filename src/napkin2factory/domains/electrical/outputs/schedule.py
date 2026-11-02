"""The cable schedule, the terminal labels and the cables to buy (E5, S-145). Stub until M2."""

from __future__ import annotations

from typing import Any


def schedule_rows(product: Any) -> list[dict[str, Any]]:
    """One row per conductor: id, from, to, cross-section, length, colour, via (stub: none)."""
    return []


def label_rows(product: Any) -> list[dict[str, Any]]:
    """One row per terminal label for the shop (stub: none)."""
    return []


def cable_rows(product: Any) -> list[dict[str, Any]]:
    """The cable to buy, per conductor id, with its total length (stub: none)."""
    return []
