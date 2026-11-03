"""The ``elec`` rule family and the files it ships (ELECTRICAL_STAGE E5; filled in M2).

One rule per circuit, after the parts (it reads the devices and the cable entries) and
before the manuals (``before=("doc",)``, S-143: a manual page that shows the wiring reads
this build's files).  Outputs under ``build/electrical/``: ``<circuit>/diagram.svg``,
``<circuit>/connections.json``, ``schedule.csv``, ``labels.csv``, ``cables.csv``,
``README.txt``; the diagrams, the tables and the README (the disclaimer and what each file
is, S-179) go in the release package (S-142).

The family's code is ``outputs/``, ``model/`` and ``interfaces/`` (S-153): an edit of the
owner's view (``owner/``) or the checks (``checks/``) reruns no ``elec:`` rule.
"""

from __future__ import annotations

from napkin2factory.core.domain import ReleaseFiles, RuleFamily
from napkin2factory.domains.electrical.outputs.consumables import (
    electrical_bom_lines as BOM_LINES,
)
from napkin2factory.domains.electrical.outputs.rules import elec_rules, elec_static_reads

RULE_FAMILIES = (
    RuleFamily(
        "elec",
        elec_rules,
        after=("part",),
        before=("doc",),
        produces="circuit://",
        # S-153: the folders whose files are this family's code (folders only: the core
        # hashes folders), so an edit of owner/ or checks/ reruns none of its rules
        code=("outputs", "model", "interfaces"),
        output_dir="electrical",
        static_reads=elec_static_reads,
    ),
)

RELEASE_FILES = (
    ReleaseFiles(
        "electrical",
        ("*/diagram.svg", "schedule.csv", "labels.csv", "cables.csv", "README.txt"),
        "wiring diagrams, cable schedule, terminal labels",
    ),
)

__all__ = [
    "BOM_LINES",
    "RELEASE_FILES",
    "RULE_FAMILIES",
]
