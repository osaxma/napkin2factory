"""Helpers a manual page calls for the wiring (F5; M4 fills the tables).

``{{ circuit("power").name }}`` records ``circuit://power#name``; ``cable_schedule()`` and
``terminal_labels()`` return the rows of ``build/electrical/schedule.csv`` and
``labels.csv`` (stub: none yet).
"""

from __future__ import annotations

from typing import Any

from napkin2factory.core.domain import HelperContext
from napkin2factory.domains.electrical.model import circuits


def circuit_helper(h: HelperContext) -> Any:
    """``circuit("<id>")``: the circuit, every field read recorded (D5)."""

    def circuit(cid: str) -> Any:
        cid = cid.replace("circuit://", "")
        if cid not in circuits(h.product):
            raise h.error(
                f"circuit('{cid}') does not exist; circuits: "
                + (", ".join(sorted(circuits(h.product))) or "none")
            )
        return h.proxy(circuits(h.product)[cid], f"circuit://{cid}")

    return circuit


def cable_schedule_helper(h: HelperContext) -> Any:
    """``cable_schedule()``: one row per conductor (stub: none)."""

    def cable_schedule() -> list[dict[str, Any]]:
        return []

    return cable_schedule


def terminal_labels_helper(h: HelperContext) -> Any:
    """``terminal_labels()``: one row per terminal label (stub: none)."""

    def terminal_labels() -> list[dict[str, Any]]:
        return []

    return terminal_labels


DOC_HELPERS = {
    "circuit": circuit_helper,
    "cable_schedule": cable_schedule_helper,
    "terminal_labels": terminal_labels_helper,
}
