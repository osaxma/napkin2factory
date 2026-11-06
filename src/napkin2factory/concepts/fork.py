"""``n2f concept fork-from-model``: the built design becomes a card (v0.8 R11).

The chosen direction was promoted into the model and built there.  Forking turns that
built design into a new napkin card: its envelope numbers come from the model's current
parameter values, its size, mass and cost are measured from the build and labelled
``computed`` with the source "from the built design (checkpoint #n)", and its ``built``
block records the saved state those figures were measured on.  The card is a starting
point for exploring a change; ``n2f concept build`` refuses to build it, because its
figures are the built design's, not a rough-shape massing's.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.concepts.promote.parameters import seed_plan
from napkin2factory.core import checkpoints as cps
from napkin2factory.core import concepts as cm
from napkin2factory.core.errors import GateBlocked, N2FError
from napkin2factory.core.model.concepts import (
    BuiltDesign,
    ConceptCard,
    LabelledValue,
    RuleRow,
    Screening,
)
from napkin2factory.core.tree import AssemblyTree
from napkin2factory.core.units import Quantity, format_quantity, is_quantity
from napkin2factory.core.vcs import Vcs
from napkin2factory.core.yamlio import read_yaml

#: The plain-words refusal when the build no longer matches the model.
STALE_WORDS = "the built design is out of date with the model — run `n2f build`, then fork it"
#: The computed figures' source, with the checkpoint number filled in.
SOURCE_FMT = "from the built design (checkpoint #{number})"
#: A parameter whose envelope entry keeps the card's value because the model lacks it.
KEPT_VALUE_WORDS = "kept the card's value — its parameters are not all in the model"


@dataclass
class ForkResult:
    """What ``fork_from_model`` wrote: the card, where it came from and the saved state."""

    card_id: str
    title: str
    based_on: str | None
    checkpoint: cps.Checkpoint | None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON form: the card id, its origin and the checkpoint (id and number)."""
        cp = self.checkpoint
        return {
            "id": self.card_id,
            "title": self.title,
            "based_on": self.based_on,
            "checkpoint": {"id": cp.id, "number": cp.number} if cp is not None else None,
            "notes": self.notes,
        }


def _mm(value: float) -> str:
    """A length in mm, formatted as the board shows one (``1600 mm``)."""
    return format_quantity(Quantity(round(float(value), 1), "mm"))


def _top_assembly(product: Any) -> tuple[str | None, str | None]:
    """The built design's top assembly and a note when there is more than one."""
    tops = AssemblyTree(product.assemblies).tops()
    note = (
        f"more than one top assembly ({', '.join(tops)}): measured {tops[0]}"
        if len(tops) > 1
        else None
    )
    return (tops[0] if tops else None), note


def _bbox(root: Path, product: Any, aid: str) -> dict[str, float]:
    """The top assembly's bounding box (``{x, y, z}`` in mm) from its build props."""
    path = product.paths.build / "assemblies" / aid / "props.json"
    if not path.is_file():
        raise N2FError(
            f"the built design has no measurements for {aid} — run `n2f build`, then fork it"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise N2FError(
            f"the built design has no measurements for {aid} — run `n2f build`, then fork it"
        ) from exc
    bbox = data.get("bbox") if isinstance(data, dict) else None
    if not isinstance(bbox, dict) or not all(k in bbox for k in "xyz"):
        raise N2FError(
            f"the built design has no bounding box for {aid} — run `n2f build`, then fork it"
        )
    return {k: float(bbox[k]) for k in "xyz"}


def _failed_requirement_rows(path: Path) -> list[RuleRow]:
    """One ``fail`` rule row per requirement the last ``n2f check`` failed."""
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows: list[RuleRow] = []
    for row in data.get("results", []) if isinstance(data, dict) else []:
        if not isinstance(row, dict) or row.get("status") != "fail":
            continue
        rid = str(row.get("id") or "")
        if not rid.startswith("req://"):
            continue
        rows.append(
            RuleRow(
                id=rid.removeprefix("req://"),
                title=str(row.get("title") or ""),
                severity="fail",
                status="fail",
                message=str(row.get("persona_message") or row.get("message") or ""),
                relies_on=[],
            )
        )
    return rows


def _envelope_key(source: str) -> str:
    """The envelope key a seed-plan ``source`` (``envelope.chamber[0].thickness``) names."""
    return source.removeprefix("envelope.").split("[", 1)[0].split(".", 1)[0]


def _layer_of(source: str) -> tuple[int, str] | None:
    """``(layer index, property)`` of a layer seed (``envelope.chamber[0].thickness``)."""
    m = re.match(r"envelope\.[^\[]+\[(\d+)\]\.(\w+)$", source)
    return (int(m.group(1)), m.group(2)) if m else None


def _rebuild(value: Any, entries: list[tuple[str, Any, str]], product: Any) -> Any:
    """The envelope value re-read from the model's current parameter values."""
    if is_quantity(value):
        return product.parameter_value(entries[0][0])
    if isinstance(value, list) and value and all(is_quantity(v) for v in value):
        return [product.parameter_value(name) for name, _, _ in entries]
    if isinstance(value, list) and all(isinstance(v, dict) for v in value):
        by_name = {name: _layer_of(source) for name, _, source in entries}
        out: list[dict[str, Any]] = []
        for i, layer in enumerate(value):
            rebuilt = dict(layer)  # keep the name and any props a screen does not seed
            for name, where in by_name.items():
                if where is not None and where[0] == i:
                    rebuilt[where[1]] = product.parameter_value(name)
            out.append(rebuilt)
        return out
    return value


def _envelope_from_model(
    chosen: ConceptCard | None, product: Any, renamed: dict[str, str]
) -> tuple[dict[str, Any], list[str]]:
    """The card's envelope: its keys, each with the model's current parameter values.

    An entry whose parameters are not all in the model keeps the card's value and says
    so in a note (R11). ``seed_plan`` names each entry's parameters.
    """
    if chosen is None:
        return {}, []
    plan = seed_plan(chosen, [], renamed)
    by_key: dict[str, list[tuple[str, Any, str]]] = {}
    for name, qty, source in plan:
        by_key.setdefault(_envelope_key(source), []).append((name, qty, source))
    out: dict[str, Any] = {}
    notes: list[str] = []
    for key, value in chosen.envelope.items():
        entries = by_key.get(key, [])
        if not entries:  # seed_plan names no parameter for it (a word, or a bad name)
            out[key] = value
            continue
        if not all(name in product.parameters for name, _, _ in entries):
            notes.append(f"envelope.{key}: {KEPT_VALUE_WORDS}")
            out[key] = value
            continue
        out[key] = _rebuild(value, entries, product)
    return out, notes


#: The rule kinds that are not renders: a change to any of them means the model moved on
#: (the renders are ``drawing``, ``report``, ``site``, ``asmsheet`` and ``doc``).
_NON_RENDER_KINDS = ("validate", "part", "asm", "bom", "checks")


def _stale(product: Any) -> bool:
    """True when the built design no longer matches the model (R11).

    ``render`` is a declared input of the part and assembly rules, so the plan differs by
    that flag: a build made with the default ``render=True`` looks stale under
    ``render=False`` even when nothing else changed.  A render-flag difference alone is not
    a model change, so the build is stale only when a non-render rule would run under both
    settings — the same reasoning ``current_vitals`` records for the parts list (S-251).
    """
    from napkin2factory.core.graph.runner import explain_build

    for render in (True, False):
        try:
            plan = explain_build(product, "all", render=render)
        except Exception:  # an unloadable model has no trustworthy figures
            return True
        if not any(run and rid.split(":", 1)[0] in _NON_RENDER_KINDS for rid, run, _ in plan):
            return False
    return True


def fork_from_model(root: Path | str, title: str | None = None) -> ForkResult:
    """Write the next card (``exploring``) from the built design.

    The card copies ``layout``, ``site``, ``style``, ``modules`` and ``massing`` from
    the chosen (promoted) card; its ``envelope`` keeps the chosen card's keys but takes
    the model's current parameter values; its screening numbers are ``computed`` from
    the build; its ``built`` block records the saved state they were measured on.

    Refuses (``GateBlocked``) when the build is out of date with the model, and when
    the folder has no saved state to record the figures against.
    """
    from napkin2factory.core.loader import load_product
    from napkin2factory.core.vitals import current_vitals

    root = Path(root)
    product = load_product(root)
    # 1. refuse a stale build: the figures would be measured on something that no
    #    longer matches the model (R11).
    if _stale(product):
        raise GateBlocked(STALE_WORDS)
    vcs = Vcs(root)
    if not (vcs.is_tracked() and vcs.is_repo_root()):
        raise GateBlocked(
            "this folder has no saved state to record the built design's figures against — "
            "track it first (`n2f init .`), then fork it"
        )
    cards = cm.load_concepts(root)
    chosen = next((c for c in cards.values() if cm.recorded_promotion(c, root)), None)
    # 2. gather the figures and the card's content, all read-only.
    vitals = current_vitals(product)
    top, top_note = _top_assembly(product)
    if top is None:
        raise N2FError("the built design has no top assembly — run `n2f build`, then fork it")
    bbox = _bbox(root, product, top)
    fail_rows = _failed_requirement_rows(product.paths.build / "checks" / "checks.json")
    renamed = cm.param_names(root)
    envelope, envelope_notes = _envelope_from_model(chosen, product, renamed)
    # 3. save unsaved edits as their own step, then read the saved state the figures
    #    were measured on (the newest checkpoint now, R4).
    from napkin2factory.ecr.checkpointing import save_edits_first

    save_edits_first(root)
    newest = cps.read(vcs, limit=1)
    if not newest:
        raise GateBlocked(
            "this folder has no saved state to record the built design's figures against — "
            "track it first (`n2f init .`), then fork it"
        )
    base_cp = newest[0]
    source = SOURCE_FMT.format(number=base_cp.number)
    title_text = (title or "").strip() or f"Built design at #{base_cp.number}"
    stamp = dt.datetime.now().replace(microsecond=0)
    computed: dict[str, LabelledValue] = {
        "width": LabelledValue(value=_mm(bbox["x"]), label="computed", source=source),
        "depth": LabelledValue(value=_mm(bbox["y"]), label="computed", source=source),
        "height": LabelledValue(value=_mm(bbox["z"]), label="computed", source=source),
    }
    if vitals.mass is not None:
        computed["mass"] = LabelledValue(value=vitals.mass, label="computed", source=source)
    if vitals.cost is not None:
        computed["cost"] = LabelledValue(value=vitals.cost, label="computed", source=source)
    screening = Screening(
        computed=computed,
        rules=fail_rows,
        verdict="red" if fail_rows else "green",
        at=stamp,
    )
    built = BuiltDesign(
        event="forked",
        checkpoint=base_cp.id,
        number=base_cp.number,
        mass=vitals.mass,
        cost=vitals.cost,
        at=stamp,
    )
    note_lines = [
        (
            f"Forked from the built design at checkpoint #{base_cp.number}, "
            f"based on {chosen.id} ({chosen.title})."
        )
        if chosen is not None
        else f"Forked from the built design at checkpoint #{base_cp.number}."
    ]
    note_lines.append(
        "The envelope numbers are the model's current parameter values; the computed "
        "figures are measured from the built design."
    )
    if top_note is not None:
        note_lines.append(top_note)
    note_lines += envelope_notes
    # 4. write the card.
    cid = cm.next_concept_id(root)
    if chosen is not None:
        raw = read_yaml(cm.card_path(root, chosen.id))
        layout = raw.get("layout", {})
        site = raw.get("site", {})
        style = raw.get("style", {})
        modules = raw.get("modules", {})
        massing = raw.get("massing", [])
    else:
        layout, site, style, modules, massing = {}, {}, {}, {}, []
    card = ConceptCard.model_validate(
        {
            "id": cid,
            "title": title_text,
            "status": "exploring",
            "based_on": chosen.id if chosen is not None else None,
            "refs": [],
            "layout": layout,
            "envelope": envelope,
            "site": site,
            "style": style,
            "modules": modules,
            "massing": massing,
            "notes": "\n".join(note_lines),
            "screening": screening,
            "decision": None,
            "built": built,
        }
    )
    cm.write_card(root, card)
    # 5. checkpoint the fork (R4).
    from napkin2factory.ecr.checkpointing import checkpoint

    cp = checkpoint(root, f"Forked {cid} from the built design")
    result_notes: list[str] = []
    if top_note is not None:
        result_notes.append(top_note)
    return ForkResult(
        card_id=cid,
        title=title_text,
        based_on=card.based_on,
        checkpoint=cp,
        notes=result_notes,
    )


__all__ = ["ForkResult", "fork_from_model"]
