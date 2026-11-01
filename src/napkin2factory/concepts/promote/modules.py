"""Step 3b: the card's modules become the top assembly, stubs and size budgets (P10)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import yaml

from napkin2factory.concepts.promote.common import (
    _and,
    _q_text,
    _rel,
    _yaml_scalar,
)
from napkin2factory.core.errors import GateBlocked, N2FError
from napkin2factory.core.model.concepts import ConceptCard

#: Each budget's axis, the word for "at most so much along it" and the dimension's name.
BUDGET_AXES: tuple[tuple[str, str, str], ...] = (
    ("x", "wide", "width"),
    ("y", "deep", "depth"),
    ("z", "tall", "height"),
)
MODULE_HEADER = (
    "# Seeded from concept {cid} by `n2f concept promote`: the {words} module, still empty.\n"
    "# Give it its parts under `children:` (design it flat inside; split it further only for\n"
    "# a reason). The size it must keep to is three requirements taken from {cid}'s rough\n"
    "# shapes; changing one is a decision.\n"
)
TOP_HEADER = (
    "# Seeded from concept {cid} by `n2f concept promote`: the whole product, one\n"
    "# sub-assembly per module the concept sketched. Parts that belong to no module go\n"
    "# straight under `children:` here.\n"
)


@dataclass
class SeededAssembly:
    """One assembly file promotion wrote: the top assembly or a module stub (P10)."""

    id: str
    name: str
    file: str  # relative to the product folder
    top: bool = False
    build: str = "unit"
    driver: list[str] = field(default_factory=list)
    #: the three budgets (width, depth, height) as written, ``None`` without rough shapes
    budget: tuple[str, str, str] | None = None


@dataclass
class ModulePlan:
    """What promotion does with the card's modules (P10)."""

    names: list[str] = field(default_factory=list)
    #: owner words, one per module: ``door (built as one unit)``
    words: list[str] = field(default_factory=list)
    seeded: list[SeededAssembly] = field(default_factory=list)
    texts: dict[str, str] = field(default_factory=dict)  # file (relative) → YAML text
    budgets: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    #: the modules said in plain words when the product already has assemblies
    suggestion: str | None = None

    @property
    def top(self) -> str | None:
        """The seeded top assembly's id, if one was seeded."""
        return next((a.id for a in self.seeded if a.top), None)


#: A module budget under this along any axis is flagged at promotion (gate D): a rough
#: shape drawn as a plate, not a size any real module (a door with its insulation) keeps.
THIN_BUDGET_MM = 10.0


def _module_title(name: str) -> str:
    return name.replace("-", " ").capitalize()


def _round_up(mm: float) -> Any:
    """A length rounded *up* to 0.1 mm once, so the rough shapes themselves keep to it."""
    from napkin2factory.core.units import Quantity

    return Quantity(math.ceil(round(mm * 10, 6)) / 10, "mm")


def module_boxes(card: ConceptCard) -> dict[str, tuple[float, float, float]]:
    """Each module's box (x, y, z extent in mm) over the massing lines that name it.

    The massing is composed again, in memory, from the card as it is now (no files, no
    pictures): the same measurement screening makes of the whole card.
    """
    from napkin2factory.concepts.massing import compose

    if not any(call.module for call in card.massing):
        return {}
    result = compose(card, write=False, render=False)
    boxes: dict[str, tuple[float, float, float]] = {}
    for name in card.module_names():
        pieces = [p for p in result.pieces if p.call.module == name]
        if not pieces:
            continue
        lo = [min(p.bbox_min[i] for p in pieces) for i in range(3)]
        hi = [max(p.bbox_max[i] for p in pieces) for i in range(3)]
        boxes[name] = (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
    return boxes


def _budget_rows(card: ConceptCard, name: str, size: tuple[Any, Any, Any]) -> list[dict[str, Any]]:
    words = name.replace("-", " ")
    rows = []
    for (axis, adjective, dimension), limit in zip(BUDGET_AXES, size, strict=True):
        rows.append(
            {
                "title": f"The {words} module fits the {dimension} the concept gave it",
                "statement": f"The {words} module is at most {_q_text(limit)} {adjective} "
                f"(computed from the rough shapes on {card.id}).",
                "category": "geometry",
                "verify": {
                    "kind": "geometry_prop",
                    "target": f"asm://{name}#props.bbox.{axis}",
                    "op": "<=",
                    "value": _q_text(limit),
                },
                "allocation": [f"asm://{name}"],
                "source": f"concept {card.id} massing",
                "rationale": f"Size budget from concept {card.id}: the rough shapes of the "
                f"{words} measure {_q_text(limit)} along {axis} (computed from the massing, "
                "rounded up to 0.1 mm). The module is designed within it; changing a budget "
                "is a decision.",
            }
        )
    return rows


def plan_modules(card: ConceptCard, product: Any, notes: list[str]) -> ModulePlan:
    """The card's modules: seeded structure and budgets, or a suggestion (P10).

    With no assembly in the product: the top assembly (``<product id>``) with one child per
    module, one empty stub per module (its ``build``/``driver`` from the card) and three size
    budgets per module that has rough shapes. With assemblies already there: nothing is
    written; the modules come back as a suggestion in plain words. A card without modules
    gives an empty plan (promotion as before, P14).

    Raises:
        GateBlocked: a module is named like the product itself, or its file already exists.
    """
    from napkin2factory.core.concepts import module_words
    from napkin2factory.core.model.assemblies import DRIVERS, Assembly

    plan = ModulePlan(names=card.module_names(), words=module_words(card))
    if not plan.names:
        return plan
    if product.assemblies:
        there = [n.replace("-", " ") for n in plan.names if n in product.assemblies]
        missing = [n.replace("-", " ") for n in plan.names if n not in product.assemblies]
        state = []
        if there:
            state.append(
                f"{_and(there)} "
                + ("is already a sub-assembly" if len(there) == 1 else "are already sub-assemblies")
            )
        if missing:
            verb = "is" if len(missing) == 1 else "are"
            state.append(
                f"{_and(missing)} {verb} not: split {'it' if len(missing) == 1 else 'one'} "
                "off only where its reason applies"
            )
        plan.suggestion = (
            f"{card.id} sketches these modules: {_and(plan.words)}. The product already has "
            f"its assemblies, so nothing was changed; {'; '.join(state)}."
        )
        return plan
    top_id = str(product.id)
    if top_id in plan.names:
        raise GateBlocked(
            f"{card.id} names a module {top_id!r}, the product's own name, which the whole "
            "product's assembly takes; rename the module on the card and promote again"
        )
    rel_dir = _rel(product.root, product.paths.assemblies)
    for aid in [top_id, *plan.names]:
        if (product.paths.assemblies / f"{aid}.yaml").exists():
            raise GateBlocked(
                f"{rel_dir}/{aid}.yaml already exists; promotion never overwrites a file — "
                "move it away or rename the module on the card, then promote again"
            )
    boxes = module_boxes(card)
    seeded: list[SeededAssembly] = []
    for name in plan.names:
        entry = card.module_entry(name)
        driver = [d for d in entry.driver if d in DRIVERS]
        dropped = [d for d in entry.driver if d not in DRIVERS]
        if dropped:
            notes.append(
                f"module {name}: {_and(dropped)} left out of its assembly file (not a reason "
                "the model knows; `n2f concept lint` lists the words)"
            )
        build = entry.build
        if build not in ("unit", "phantom"):
            notes.append(f"module {name}: build {build!r} read as unit (built as one unit)")
            build = "unit"
        box = boxes.get(name)
        budget: tuple[str, str, str] | None = None
        if box is None:
            notes.append(f"module {name}: no rough shape belongs to it, so it has no size budget")
        else:
            size = (_round_up(box[0]), _round_up(box[1]), _round_up(box[2]))
            plan.budgets += [("budget", row) for row in _budget_rows(card, name, size)]
            budget = (_q_text(size[0]), _q_text(size[1]), _q_text(size[2]))
            # gate D: a sketch's plate (a 3 mm door) would become a budget no real module
            # meets; say so before anyone designs to it
            thin = [
                f"{_q_text(q)} {adjective}"
                for (_, adjective, _), q, mm in zip(BUDGET_AXES, size, box, strict=True)
                if mm < THIN_BUDGET_MM
            ]
            if thin:
                notes.append(
                    f"module {name}: the sketch drew it as a thin plate ({_and(thin)}), so its "
                    "size budget says so too: set its real size on the card or in the budget "
                    "requirement before designing (changing a budget is a decision)"
                )
        seeded.append(
            SeededAssembly(
                id=name,
                name=_module_title(name),
                file=f"{rel_dir}/{name}.yaml",
                build=build,
                driver=driver,
                budget=budget,
            )
        )
    loose = [call.as_ for call in card.massing if call.module is None]
    if loose:
        one = len(loose) == 1
        notes.append(
            f"{_and(loose)} belong{'s' if one else ''} to no module: "
            f"{'its' if one else 'their'} parts go straight into the top assembly"
        )
    top = SeededAssembly(
        id=top_id,
        name=str(product.manifest.product.name),
        file=f"{rel_dir}/{top_id}.yaml",
        top=True,
    )
    plan.seeded = [top, *seeded]
    texts: dict[str, str] = {}
    lines = [f"id: {top_id}", f"name: {_yaml_scalar(top.name)}", "children:"]
    lines += [f"  - {{asm: asm://{a.id}}}" for a in seeded]
    texts[top.file] = TOP_HEADER.format(cid=card.id) + "\n".join(lines) + "\n"
    for a in seeded:
        lines = [f"id: {a.id}", f"name: {_yaml_scalar(a.name)}"]
        if a.build == "phantom":
            lines.append("build: phantom")
        if a.driver:
            lines.append(f"driver: [{', '.join(a.driver)}]")
        lines.append("children: []")
        header = MODULE_HEADER.format(cid=card.id, words=a.id.replace("-", " "))
        texts[a.file] = header + "\n".join(lines) + "\n"
    for file, text in texts.items():
        try:
            Assembly.model_validate(yaml.safe_load(text))
        except Exception as exc:
            raise N2FError(
                f"promotion could not write {file} cleanly ({exc}); nothing was written"
            ) from exc
    plan.texts = texts
    return plan
