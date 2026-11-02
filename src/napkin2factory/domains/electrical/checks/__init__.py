"""The wiring checks (ELECTRICAL_STAGE E6, E11; M3).

The ``electrical`` check stage (after the interface checks) reads the wiring once
(``calcs.py``), walks its nets (``nets.py``) and writes a row per rule of
``electrical-v0.yaml`` (``stage.py``): the load against the supply, conductors against
the table, earth paths, protection, interlocks and limits, cable-entry voltages, contact
ratings, and the supply-headroom choice.  The ``circuit`` verify kind (``verify.py``)
compares a circuit's figure (``circuit://<id>#load_current`` …) with a requirement's
value.  Rows are of kind ``electrical``: the Verify gate's "Wiring checks" row counts them.
"""

from __future__ import annotations

from napkin2factory.core.domain import CheckStage, VerifyKind
from napkin2factory.domains.electrical.checks.stage import electrical_check_reads, electrical_checks
from napkin2factory.domains.electrical.checks.verify import check_circuit_verify, evaluate_circuit

VERIFY_KINDS = (
    VerifyKind(
        "circuit",
        evaluate_circuit,
        target_schemes=("circuit",),
        compares=True,
        title="a circuit's figure (load current, supply margin, conductor margin, earth paths)",
        check=check_circuit_verify,
    ),
)

CHECK_STAGES = (
    CheckStage(
        "electrical",
        electrical_checks,
        after=("interface",),
        reads=electrical_check_reads,
    ),
)
