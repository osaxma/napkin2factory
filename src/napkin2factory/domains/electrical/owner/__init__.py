"""The owner's view of the wiring (ELECTRICAL_STAGE E7, E8; filled in M4, the Design row in M1).

Gate rows (Design: "Wiring", whose blockers are the devices nobody wired, E7; Verify:
"Wiring checks", the check stage's rows), the report's "Wiring" section, the manual pages'
helpers (``circuit``, ``cable_schedule``, ``terminal_labels``), the owner's words, the
napkin screens (the supply screen moves here in M4, E8) and the module context.
"""

from __future__ import annotations

from napkin2factory.domains.electrical.owner.context import CONTEXT
from napkin2factory.domains.electrical.owner.docs_helpers import DOC_HELPERS
from napkin2factory.domains.electrical.owner.gates import GATE_ROWS
from napkin2factory.domains.electrical.owner.inspector import electrical_inspector
from napkin2factory.domains.electrical.owner.report import REPORT_SECTIONS
from napkin2factory.domains.electrical.owner.screens import SCREENS
from napkin2factory.domains.electrical.owner.vocabulary import VOCABULARY

__all__ = [
    "CONTEXT",
    "DOC_HELPERS",
    "GATE_ROWS",
    "REPORT_SECTIONS",
    "SCREENS",
    "VOCABULARY",
    "electrical_inspector",
]
