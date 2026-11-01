"""Concept screening: labelled numbers, the concept rules and a verdict (N5, F15).

Screening is a third tier, distinct from verification. Every number it writes carries a
label at the data level:

* ``computed`` — measured from the massing silhouettes (bounding box, volume, mass from
  declared materials, footprint with the door swing);
* ``estimate`` — from the calc kit (:mod:`napkin2factory.calckit`) fed with the card's
  envelope numbers;
* ``given`` — the card's own inputs echoed back: neither measured nor estimated (review
  gate A, C1). A verdict built on them is still an estimate.

Each value's ``source`` says where it comes from in the owner's words (a ``[verify]`` tag
reads "to be checked"); its ``ref`` names the calc-kit function or rule parameters for
engineers (``--json`` and the card only, never the board — review gate B, B2).

Missing inputs never become invented numbers: the estimate is omitted and a note says what
would unlock it. A red verdict is information — written to the card with its reasons,
never hidden.

The screens themselves live in :mod:`napkin2factory.concepts.screens` (the runner and the
system's generic screens) and in a product's own ``model/screens/`` (F8, F10); this module is
the entry point and the record: the screening written to ``build/`` and to the card.

A re-screen that finds exactly what the card already says keeps the card's ``at``
(:func:`keep_unchanged_at`), so rebuilding an unchanged card leaves its file alone (S-086).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from napkin2factory.concepts.screens import run_screens
from napkin2factory.core.model.concepts import ConceptCard, Screening


def screen(
    card: ConceptCard,
    massing: Any,
    root: Path | None = None,
    *,
    now: dt.datetime | None = None,
) -> Screening:
    """Screen one card against its massing: labelled numbers, rule rows, verdict.

    Args:
        card: the concept card.
        massing: the :class:`~napkin2factory.concepts.massing.MassingResult` (or ``None``).
        root: the product folder: its own screens (``model/screens/``, F10) run too.
        now: the timestamp to record (default: now, to the second).
    """
    return run_screens(card, massing, root, now=now)


def same_screening(a: Screening | None, b: Screening | None) -> bool:
    """Whether two screenings say the same thing, whenever each was taken (S-086).

    Everything but ``at`` is compared: the given, computed and estimated values with their
    sources, the rule rows, the verdict and the notes. Rule rows are compared by id, not by
    position: the system's rows come before a product's own (F10, S-128), and a card
    screened when those rules were the system's says the same thing in another order.
    """
    if a is None or b is None:
        return False

    def said(s: Screening) -> dict[str, Any]:
        data = s.model_dump(mode="json", exclude={"at"})
        data["rules"] = sorted(data.get("rules") or [], key=lambda r: str(r.get("id")))
        return data

    return said(a) == said(b)


def keep_unchanged_at(
    previous: Screening | None, screening: Screening, *, screens_changed: bool = False
) -> bool:
    """Carry the earlier ``at`` over when nothing else changed; ``True`` if it was kept.

    A re-build of an unchanged card then leaves the card file as it was, so the shipped
    cards do not drift under ``make``. ``screens_changed`` (the product's own screens are
    not the ones the last build ran, F10) invalidates the earlier screening: the card gets
    a fresh ``at`` even when the numbers come out the same.
    """
    if screens_changed:
        return False
    if previous is not None and previous.at is not None and same_screening(previous, screening):
        screening.at = previous.at
        return True
    return False


def recorded_screens_key(out_dir: Path) -> str | None:
    """The product screens' hash the last build of this card recorded (None: none or no build)."""
    path = out_dir / "screening.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        return None
    key = data.get("screens") if isinstance(data, dict) else None
    return str(key) if key else None


def write_screening_json(
    out_dir: Path, card: ConceptCard, screening: Screening, screens: str | None = None
) -> Path:
    """``build/concepts/<id>/screening.json`` (the same dict the card carries).

    ``screens`` is the hash of the product's own screens that ran (F10), recorded so the
    next build can tell when they changed.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "screening.json"
    data = {"id": card.id, "title": card.title, **screening.model_dump(mode="json")}
    if screens is not None:
        data["screens"] = screens
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return path


def write_screening_to_card(root: Path, card_id: str, screening: Screening) -> Path:
    """Replace the card's ``screening:`` in place; comments and key order elsewhere survive.

    Each labelled value and rule row is written as one flow-style line, so a re-screen is a
    readable diff.
    """
    from ruamel.yaml.comments import CommentedMap, CommentedSeq

    from napkin2factory.core import concepts as cm
    from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip

    path = cm.card_path(root, card_id)
    data = screening.model_dump(mode="json")
    block = CommentedMap()
    for key, value in data.items():
        if key in ("given", "computed", "estimates"):
            sub = CommentedMap()
            for name, lv in value.items():
                line = CommentedMap(lv)
                line.fa.set_flow_style()
                sub[name] = line
            block[key] = sub
        elif key == "rules":
            seq = CommentedSeq()
            for row in value:
                line = CommentedMap(row)
                line.fa.set_flow_style()
                seq.append(line)
            block[key] = seq
        else:
            block[key] = value
    doc = load_roundtrip(path)
    doc["screening"] = block
    dump_roundtrip(path, doc, explicit_null=True)
    return path


__all__ = [
    "keep_unchanged_at",
    "recorded_screens_key",
    "same_screening",
    "screen",
    "write_screening_json",
    "write_screening_to_card",
]
