"""``n2f concept promote``: the chosen concept becomes model content (NAPKIN_STAGE N8).

Promotion is the bridge from the napkin stage to the factory and the arbitration event
between directions. In this order, **all or nothing** (every edit is computed in memory and
validated before the first byte is written; a refusal writes nothing):

1. **Gates** — the card was built (it has a screening); green, or red with ``--override``
   and ``--reason``; no other card is promoted. Refusals raise
   :class:`~napkin2factory.core.errors.GateBlocked` (exit 3).
2. **Parameters** — ``envelope`` numbers seed ``model/parameters.yaml`` (``owner:
   napkin``): a quantity becomes one parameter, a 3-list ``<key>-width/-depth/-height``,
   another list ``<key>-1..n``, a list of named layers ``<layer>-thickness`` (and
   ``-clearance``); a field a screen declares with another parameter name seeds that name.
   A parameter already declared with
   the same value is left alone ("already declared"); a different value refuses the whole
   promotion unless ``--override`` (then it is overwritten and listed in the decision).
3. **Site constraints → requirements** — the alcove (width with the open door's term,
   depth, height), what the product's own screens seed (a supply circuit, ``packs``) and a
   mass limit become ordinary ``req://`` rows allocated to the top assembly, so a product
   too wide for its space is caught on paper.
   3b. **Modules** (P10) — when the product has no assembly yet and the card names modules
   (``modules:``, ``module:`` on massing lines): the top assembly ``<product id>``, one empty
   stub per module and three size budgets per module (``asm://<m>#props.bbox.x|y|z``, from
   the module's rough shapes, labelled computed); the site and form requirements then go to
   that top assembly. When assemblies exist, the modules are only suggested (printed and
   recorded in the decision). A card without modules promotes as before (P14).
4. **Form requirements** — style and layout choices become requirements verified by the
   ``form-v0`` rule pack (``verify: {kind: rule, target: rule://form-v0/<rule>}``).
5. **style.yaml** — the card's ``style`` keys (and its ``layout``) override the product's.
6. **The decision** — one ``DEC-`` entry with every sibling attached as a rejected
   alternative.
7. **Cards** — the chosen card becomes ``promoted``; exploring siblings ``rejected``.
8. **Snapshot** — ``Promote C-00x: <title>`` (napkin verbs otherwise never snapshot, S-062).

Model files are edited as text where that keeps the owner's formatting (new parameters,
requirements and decisions are appended in the files' own style; an overwritten parameter
is a one-line change); ``style.yaml`` and the cards go through ruamel round-trip, so
comments and key order survive.

One module per seeder (F15, S-131): ``parameters`` (step 2), ``door`` and ``site`` (step 3),
``modules`` (3b), ``form`` (4), ``style`` (5), ``decision`` (6 and 7); ``packs`` reads what a
product's own screens seed (B-0086); ``verb`` runs them in
order and writes once; ``result`` says what happened. Every public name is importable from
here, as it was when promotion was one file.
"""

from napkin2factory.concepts.promote.common import NewRequirement, SeededParam
from napkin2factory.concepts.promote.decision import RATIONALE_KEYS
from napkin2factory.concepts.promote.door import (
    DOOR_LEAF_PARAM,
    DOOR_ROOM_PARAM,
    DOOR_ROW_TITLE,
    DoorSwing,
    door_seeds,
    door_swing,
    door_swing_term,
)
from napkin2factory.concepts.promote.form import FORM_PACK, form_requirements
from napkin2factory.concepts.promote.modules import (
    BUDGET_AXES,
    MODULE_HEADER,
    THIN_BUDGET_MM,
    TOP_HEADER,
    ModulePlan,
    SeededAssembly,
    module_boxes,
    plan_modules,
)
from napkin2factory.concepts.promote.parameters import (
    AXIS_SUFFIXES,
    SEED_OWNER,
    plan_parameters,
    seed_plan,
)
from napkin2factory.concepts.promote.result import PromotionResult
from napkin2factory.concepts.promote.site import site_requirements
from napkin2factory.concepts.promote.style import STYLE_HEADER, plan_style
from napkin2factory.concepts.promote.verb import promote

__all__ = [
    "AXIS_SUFFIXES",
    "BUDGET_AXES",
    "DOOR_LEAF_PARAM",
    "DOOR_ROOM_PARAM",
    "DOOR_ROW_TITLE",
    "FORM_PACK",
    "MODULE_HEADER",
    "RATIONALE_KEYS",
    "SEED_OWNER",
    "STYLE_HEADER",
    "THIN_BUDGET_MM",
    "TOP_HEADER",
    "DoorSwing",
    "ModulePlan",
    "NewRequirement",
    "PromotionResult",
    "SeededAssembly",
    "SeededParam",
    "door_seeds",
    "door_swing",
    "door_swing_term",
    "form_requirements",
    "module_boxes",
    "plan_modules",
    "plan_parameters",
    "plan_style",
    "promote",
    "seed_plan",
    "site_requirements",
]
