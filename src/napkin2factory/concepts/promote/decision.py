"""Steps 6 and 7: the decision's words and the cards' new status."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from napkin2factory.concepts.promote.packs import pack_rationale_keys
from napkin2factory.core import concepts as cm
from napkin2factory.core.model.concepts import ConceptCard

#: Screening values quoted in the decision's rationale, in this order: the size and mass,
#: then the keys the product's own screens add (``PROMOTE_RATIONALE``, B-0086), then the
#: cost and the lift (:data:`RATIONALE_SPLIT` keys come first).
RATIONALE_KEYS: tuple[str, ...] = (
    "width",
    "depth",
    "height",
    "footprint_with_door_swing",
    "mass",
    "total_mass",
    "cost_low",
    "cost_high",
    "lift_class",
)
#: How many of :data:`RATIONALE_KEYS` come before the product's own keys.
RATIONALE_SPLIT = 6


def _card_text(root: Path, card_id: str, status: str, decision: dict[str, Any]) -> str:
    """The card file with ``status`` and ``decision`` set (comments and order kept)."""
    from ruamel.yaml.comments import CommentedMap

    from napkin2factory.core.yamlio import dumps_roundtrip, load_roundtrip, read_yaml

    path = cm.card_path(root, card_id)
    ConceptCard.model_validate({**read_yaml(path), "status": status, "decision": decision})
    doc = load_roundtrip(path)
    doc["status"] = status
    flow = CommentedMap(decision)
    flow.fa.set_flow_style()
    doc["decision"] = flow
    return dumps_roundtrip(doc, explicit_null=True)


def verdict_words(card: ConceptCard) -> str:
    """The card's verdict as the decision says it.

    A card screening could not fully check is "no problems found, but not fully checked",
    never "green" (B1, S-226, S-233).
    """
    from napkin2factory.concepts.board import not_checked_line

    if card.verdict == "green" and card.screening is not None:
        if not_checked_line(card.screening.rules, card):
            return "no problems found, but not fully checked"
    return str(card.verdict)


#: What marks a clause as a formula or a source: an operator, a verify flag, a table or edition.
_CALC = re.compile(r"\[verify\]|[\^*=·σ]|\bed\.,|calckit")


def plain_reason(message: str) -> str:
    """A screening message without its calculation text (B-0230).

    The rows say the finding first and may add ``— formula; source`` after a dash, and a factor
    check adds ``(limit ÷ sag is 0.175, 1 needed, static case)``. A decision names an idea
    by what went wrong, never by the other idea's formulas.
    """
    first, *rest = message.split(" — ")
    # a dash also sets off plain explanation ("it needs 1245 mm — 995 mm for the body plus …"),
    # which stays; only a clause that reads as a formula or a source goes
    head = " — ".join([first, *(r for r in rest if not _CALC.search(r))])
    head = re.sub(r"\s*\([^()]*\bneeded\b[^()]*\)", "", head)
    return head.strip()


def _one_line(card: ConceptCard, root: Path | None = None) -> str:
    from napkin2factory.concepts.build import summary_line

    if card.screening is None or card.verdict is None:
        return "not built"
    if card.verdict == "red":
        return "red: " + "; ".join(plain_reason(r.message) for r in card.screening.failing)
    return verdict_words(card) + ": " + summary_line(card, card.screening, root)


def _labelled(card: ConceptCard, root: Path | None = None) -> list[str]:
    sc = card.screening
    assert sc is not None
    values = sc.values
    own = pack_rationale_keys(root)
    keys = (*RATIONALE_KEYS[:RATIONALE_SPLIT], *own, *RATIONALE_KEYS[RATIONALE_SPLIT:])
    out = []
    for key in dict.fromkeys(keys):
        lv = values.get(key)
        if lv is not None:
            out.append(f"{key.replace('_', ' ')} {lv.value} ({lv.label})")
    return out
