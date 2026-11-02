"""The wiring's gate rows (E7): "Wiring" under Design, "Wiring checks" under Verify.

Both exist only when the product has wiring content or its scope says the wiring is done
here (F4, F11); the core leaves them out while the scope is ``later``.  A load or control
device no connection reaches blocks the Design gate ("the Fan is not wired yet").
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napkin2factory.core.domain import GateRow, GateRowState
from napkin2factory.domains.electrical.model import (
    circuits,
    devices,
    has_content,
    wired_devices,
)

#: The roles a device must be wired in to leave Design (E7).
MUST_BE_WIRED = ("load", "control")
#: Owner words for the check rows' statuses (the Verify row).
CHECK_WORDS = {
    "pass": "OK",
    "fail": "needs attention",
    "warn": "for an electrician to confirm",
    "needs-human": "for a person to confirm",
}


def _scope_state(product: Any) -> str | None:
    entry = product.manifest.scope.get("electrical")
    return entry.state if entry is not None else None


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _device_words(product: Any, dev: Any) -> str:
    part = product.parts.get(dev.part.id)
    name = getattr(part, "name", None) or dev.part.id
    return f"the {name} ({dev.instance})" if dev.instance else f"the {name}"


def design_row(product: Any, build_dir: Path) -> GateRowState | None:
    """Under Design: how many devices and circuits, and every device nobody wired (E7)."""
    state = _scope_state(product)
    if not has_content(product):
        if state != "in":
            return None
        return GateRowState(
            "nothing wired yet",
            blockers=[
                "the wiring is marked done here, but there is no supply or device yet — add "
                "them under model/electrical/, or set the wiring's scope to later"
            ],
        )
    devs = devices(product)
    wired = wired_devices(product)
    unwired = [d for _, d in sorted(devs.items()) if d.role in MUST_BE_WIRED and d.id not in wired]
    counts = f"{_plural(len(devs), 'device')}, {_plural(len(circuits(product)), 'circuit')}"
    if not unwired:
        return GateRowState(f"{counts}: all wired" if devs else counts)
    return GateRowState(
        f"{counts}: {len(unwired)} not wired yet",
        blockers=[
            f"{_device_words(product, d)} is not wired yet — connect it in a circuit under "
            "model/electrical/circuits/"
            for d in unwired
        ],
    )


def verify_row(product: Any, build_dir: Path) -> GateRowState | None:
    """Under Verify: the wiring check rows, counted (none until the checks ran)."""
    if not has_content(product):
        return None
    # imported here: the core's check engine imports the loader, which imports this domain
    from napkin2factory.core.checks.stage import check_rows_state

    return check_rows_state(build_dir, "electrical", CHECK_WORDS)


GATE_ROWS = (
    GateRow(gate="design", title="Wiring", row=design_row),
    GateRow(gate="verify", title="Wiring checks", row=verify_row),
)
