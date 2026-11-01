"""Step 2: the card's ``envelope`` numbers seed ``model/parameters.yaml`` (N8)."""

from __future__ import annotations

import re
from typing import Any

import yaml

from napkin2factory.concepts.promote.common import (
    _SLUG_RE,
    SeededParam,
    _and,
    _num,
    _q_text,
    _same,
    _slug,
    _split,
)
from napkin2factory.concepts.promote.swing import door_seeds, seed_words
from napkin2factory.core import concepts as cm
from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.units import is_quantity

#: ``owner`` of every seeded parameter.
SEED_OWNER = "napkin"


#: Suffixes of a three-value envelope entry.
AXIS_SUFFIXES: tuple[str, str, str] = ("width", "depth", "height")


def seed_plan(
    card: ConceptCard, notes: list[str], renamed: dict[str, str] | None = None
) -> list[tuple[str, Any, str]]:
    """``(parameter name, quantity, envelope source)`` for every envelope number.

    ``renamed``: envelope keys that seed under another name (:func:`cm.param_names`, as the
    product's screens declare them).
    """
    plan: list[tuple[str, Any, str]] = []
    for key, value in card.envelope.items():
        base = (renamed or {}).get(key, _slug(key))
        if not _SLUG_RE.match(base):
            notes.append(f"envelope.{key}: not usable as a parameter name; not seeded")
            continue
        if is_quantity(value):
            plan.append((base, value, f"envelope.{key}"))
        elif isinstance(value, list) and value and all(is_quantity(v) for v in value):
            names = (
                [f"{base}-{s}" for s in AXIS_SUFFIXES]
                if len(value) == 3
                else [f"{base}-{i + 1}" for i in range(len(value))]
            )
            for i, (name, v) in enumerate(zip(names, value, strict=True)):
                plan.append((name, v, f"envelope.{key}[{i}]"))
        elif isinstance(value, list) and all(isinstance(v, dict) for v in value):
            skipped: set[str] = set()
            for i, layer in enumerate(value):
                name = _slug(str(layer.get("name") or f"{base}-{i + 1}"))
                for prop in ("thickness", "clearance"):
                    q = layer.get(prop)
                    if is_quantity(q):
                        plan.append((f"{name}-{prop}", q, f"envelope.{key}[{i}].{prop}"))
                skipped |= {k for k in layer if k not in ("name", "thickness", "clearance")}
            if skipped:
                verb = "stays" if len(skipped) == 1 else "stay"
                notes.append(
                    f"envelope.{key}: layer {_and(sorted(skipped))} {verb} on the card "
                    "(screening values), not seeded as parameters"
                )
        else:
            notes.append(f"envelope.{key}: not a quantity or a list of them; not seeded")
    return plan


_PARAM_LINE = r"^(\s*{slug}\s*:\s*\{{.*?)(value\s*:\s*)([-+0-9.eE]+)(.*)$"


def _edit_param_value(text: str, slug: str, value: str) -> str | None:
    """Change ``value:`` on the parameter's own flow line (``_edit_param_line``'s pattern)."""
    pat = re.compile(_PARAM_LINE.format(slug=re.escape(slug)))
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = pat.match(line)
        if m:
            lines[i] = f"{m.group(1)}{m.group(2)}{value}{m.group(4)}"
            return "".join(lines)
    return None


def plan_parameters(
    card: ConceptCard, product: Any, text: str, override: bool, notes: list[str]
) -> tuple[list[SeededParam], str, list[str]]:
    """Seeded parameters, the new ``parameters.yaml`` text, and refusals (collisions)."""
    from napkin2factory.concepts.screens import SPACE_WORDS
    from napkin2factory.core.packs import product_words

    space = product_words(product.paths.root).get("space", SPACE_WORDS)
    seeded: list[SeededParam] = []
    conflicts: list[str] = []
    new_lines: list[str] = []
    plan: list[tuple[str, Any, str, str | None]] = [
        (name, q, source, None)
        for name, q, source in seed_plan(card, notes, cm.param_names(product.paths.root))
    ]
    planned_names = {item[0] for item in plan}
    plan += [item for item in door_seeds(card) if item[0] not in planned_names]
    for name, q, source, expr in plan:
        value_text = _q_text(q)
        if name in product.parameters:
            declared = product.parameters[name]
            try:
                current = product.parameter_value(name)
            except Exception as exc:  # an expression that does not evaluate
                conflicts.append(f"{name} cannot be read in the model ({exc})")
                continue
            if _same(current, q):
                seeded.append(SeededParam(name, value_text, "declared", source=source))
                continue
            was = _q_text(current)
            if not override:
                conflicts.append(f"{name} is {was} in the model but {value_text} on {card.id}")
                continue
            if declared.expr is not None or expr is not None:
                conflicts.append(
                    f"{name} is computed by an expression ({declared.expr}), so it cannot be "
                    "overwritten; change the card or the expression by hand"
                )
                continue
            unit = declared.unit or None
            converted = q.to(unit) if unit else q
            edited = _edit_param_value(text, name, _num(float(converted.magnitude)))
            if edited is None:
                conflicts.append(
                    f"{name} is not written as one line ({{value: …, unit: …}}), so it "
                    "cannot be overwritten safely; change it by hand"
                )
                continue
            text = edited
            seeded.append(SeededParam(name, value_text, "overwritten", was=was, source=source))
            continue
        mag, unit = _split(q)
        fields: dict[str, Any] = {"expr": expr} if expr is not None else {"value": mag}
        entry = {
            name: {
                **fields,
                "unit": unit,
                "description": f"from concept {card.id}" + seed_words(name, space),
                "owner": SEED_OWNER,
            }
        }
        line = yaml.safe_dump(
            entry, sort_keys=False, default_flow_style=None, allow_unicode=True, width=10**6
        )
        new_lines.append(line)
        seeded.append(SeededParam(name, value_text, "new", source=source))
    if new_lines:
        m = re.search(r"^(\s+)[a-z0-9][a-z0-9-]*\s*:", text, re.MULTILINE)
        indent = m.group(1) if m else "  "
        text = re.sub(r"^parameters:\s*\{\}\s*$", "parameters:", text, count=1, flags=re.M)
        if not text.endswith("\n"):
            text += "\n"
        text += f"{indent}# --- from concept {card.id} (n2f concept promote) ---\n"
        text += "".join(f"{indent}{ln}" for ln in new_lines)
    return seeded, text, conflicts
