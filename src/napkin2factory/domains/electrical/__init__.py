"""The electrical domain (ELECTRICAL_STAGE.md, v0.6): the product's wiring, as data.

Registered through the domain contract (``docs/domains.md``) and nothing else: the core
knows the contract, never this package.  The owner's word for it is "wiring".  This file
only composes ``DOMAIN`` from its parts, laid out so separate tasks never share a file:

* ``model/`` — the four model families (supply, devices, circuits, the product's conductor
  rows) and their cross-reference check;
* ``interfaces/`` — the ``cable-entry`` interface kind (the joint between the two domains);
* ``outputs/`` — the ``elec`` rule family and the files the release package takes;
* ``checks/`` — the ``circuit`` verify kind and the ``electrical`` check stage;
* ``owner/`` — gate rows, the report section, doc helpers, vocabulary, screens, context.
"""

from __future__ import annotations

from pathlib import Path

from napkin2factory.core.domain import Domain, ModelFamily
from napkin2factory.domains.electrical.checks import CHECK_STAGES, VERIFY_KINDS
from napkin2factory.domains.electrical.interfaces import INTERFACE_KINDS
from napkin2factory.domains.electrical.model import (
    CIRCUIT_FOLDER,
    CONDUCTOR_FOLDER,
    DEVICE_FOLDER,
    SUPPLY_FOLDER,
    Circuit,
    Device,
    ProductConductor,
    Supply,
    validate_refs,
)
from napkin2factory.domains.electrical.outputs import (
    BOM_LINES,
    RELEASE_FILES,
    RULE_FAMILIES,
)
from napkin2factory.domains.electrical.owner import (
    CONTEXT,
    DOC_HELPERS,
    GATE_ROWS,
    REPORT_SECTIONS,
    SCREENS,
    VOCABULARY,
)

ROOT = Path(__file__).resolve().parent

#: The model families (S-153): one ``validate_refs`` for the whole wiring model, on the
#: supply family, so each reference is checked once with every family loaded.
FAMILIES = (
    ModelFamily("supply", schema=Supply, folder=SUPPLY_FOLDER, validate_refs=validate_refs),
    ModelFamily("device", schema=Device, folder=DEVICE_FOLDER),
    ModelFamily("circuit", schema=Circuit, folder=CIRCUIT_FOLDER),
    ModelFamily("conductor", schema=ProductConductor, folder=CONDUCTOR_FOLDER),
)

DOMAIN = Domain(
    name="electrical",
    title="Wiring: supply, devices, circuits, cable entries",
    root=ROOT,
    families=FAMILIES,
    rule_families=RULE_FAMILIES,
    verify_kinds=VERIFY_KINDS,
    check_stages=CHECK_STAGES,
    gate_rows=GATE_ROWS,
    report_sections=REPORT_SECTIONS,
    doc_helpers=DOC_HELPERS,
    vocabulary=VOCABULARY,
    interface_kinds=INTERFACE_KINDS,
    categories=("electrical",),
    screens=SCREENS,
    context=CONTEXT,
    release_files=RELEASE_FILES,
    bom_lines=BOM_LINES,
    disclaimer=(
        "Its wiring has not been reviewed by a licensed electrician: a licensed electrician "
        "wires the product to local code."
    ),
)
