"""Concept screens (F8, F10, F15): the contract, the system's generic screens, the runner.

A product's own screens (``model/screens/*.py``) use the same contract as the generic ones:

```python
from napkin2factory.concepts.screens import CardField, reads
from napkin2factory.core.domain import Screen

POWER = CardField("envelope", "power", "W", "a power", "2.5 kW", "the power")

@reads(POWER, phase="estimate")
def supply(card, massing, values):
    ...
    return []  # concept rule rows

SCREENS = (Screen("supply", supply),)
WORDS = {"space": "recess"}  # optional: the product's word for the space it must fit
```
"""

from napkin2factory.concepts.screens.base import (
    DEFAULT_PHASE,
    PHASES,
    SPACE_WORDS,
    TO_CHECK,
    CardField,
    Collector,
    ScreenValues,
    and_,
    fields_of,
    fmt,
    owner_names,
    phase_of,
    reads,
    sig,
    the,
)
from napkin2factory.concepts.screens.generic import GENERIC_SCREENS
from napkin2factory.concepts.screens.runner import (
    card_fields,
    declared_fields,
    generic_fields,
    installed_screens,
    run_screens,
    screens_key,
    wrong_kind_notes,
)

__all__ = [
    "DEFAULT_PHASE",
    "GENERIC_SCREENS",
    "PHASES",
    "SPACE_WORDS",
    "TO_CHECK",
    "CardField",
    "Collector",
    "ScreenValues",
    "and_",
    "card_fields",
    "declared_fields",
    "fields_of",
    "fmt",
    "generic_fields",
    "installed_screens",
    "owner_names",
    "phase_of",
    "reads",
    "run_screens",
    "screens_key",
    "sig",
    "the",
    "wrong_kind_notes",
]
