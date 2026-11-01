"""Step 5: the card's ``style`` and ``layout`` go into ``style.yaml``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from napkin2factory.core.errors import N2FError
from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.model.style import PRESETS, StyleFile
from napkin2factory.core.units import format_quantity, is_quantity

STYLE_HEADER = (
    "# style.yaml: how the product looks (preset, colours and finishes by part role, shape cues).\n"
    "# Filled from the chosen concept by `n2f concept promote`; you may also edit it by hand.\n"
)


def _plain(value: Any) -> Any:
    return format_quantity(value) if is_quantity(value) else value


def plan_style(card: ConceptCard, root: Path, notes: list[str]) -> tuple[str, StyleFile, bool]:
    """The new ``style.yaml`` text, the resolved style it gives, and whether it is new.

    The card's ``style`` keys override the file's (``palette``/``finish`` per role) and its
    ``layout`` is recorded. When the card names a different preset, the file's values that
    still equal the old preset's take the new preset's (so the product looks like the
    pictures on the board); hand-edited values are kept and noted.
    """
    from ruamel.yaml.comments import CommentedMap

    from napkin2factory.core.style import style_path
    from napkin2factory.core.yamlio import dumps_roundtrip, load_roundtrip

    path = style_path(root)
    created = not path.is_file()
    fields = set(StyleFile.model_fields)
    card_style = {k: v for k, v in card.style.items() if k in fields}
    unknown = sorted(k for k in card.style if k not in fields)
    if unknown:
        notes.append(f"card style keys not used: {', '.join(unknown)}")
    if created:
        preset = str(card_style.get("preset", "industrial"))
        if preset not in PRESETS:
            raise N2FError(f"{card.id}: style preset {preset!r} is not one of {', '.join(PRESETS)}")
        doc: Any = CommentedMap(
            StyleFile.model_validate({"preset": preset}).resolved().model_dump(mode="json")
        )
        doc.pop("layout", None)
    else:
        doc = load_roundtrip(path)
        if not isinstance(doc, dict):
            raise N2FError("style.yaml is not a mapping; fix it (or delete it) and promote again")
        old = str(doc.get("preset", "industrial"))
        new = str(card_style.get("preset", old))
        if new != old and new in PRESETS and old in PRESETS:
            kept: list[str] = []
            for key in list(doc):
                if key in ("preset", "layout") or key not in PRESETS[old]:
                    continue
                if key in ("palette", "finish") and isinstance(doc[key], dict):
                    for role in list(doc[key]):
                        if str(doc[key][role]).lower() == str(PRESETS[old][key].get(role)).lower():
                            doc[key][role] = PRESETS[new][key].get(role)
                        else:
                            kept.append(f"{key}.{role}")
                elif str(_plain(doc[key])) == str(PRESETS[old][key]):
                    doc[key] = PRESETS[new][key]
                else:
                    kept.append(key)
            if kept:
                notes.append(
                    f"style.yaml moved from the {old} to the {new} preset; kept your own "
                    f"{', '.join(kept)}"
                )
    for key, value in card_style.items():
        if key in ("palette", "finish") and isinstance(value, dict):
            sub = doc.get(key)
            if not isinstance(sub, dict):
                sub = CommentedMap()
                doc[key] = sub
            for role, v in value.items():
                sub[role] = v
        else:
            doc[key] = _plain(value)
    if card.layout:
        flow = CommentedMap(card.layout)
        flow.fa.set_flow_style()
        doc["layout"] = flow
    text = dumps_roundtrip(doc, explicit_null=True)
    if created:
        text = STYLE_HEADER + f"# Seeded from concept {card.id}.\n" + text
    try:
        style = StyleFile.model_validate(yaml.safe_load(text) or {}).resolved()
    except Exception as exc:
        raise N2FError(
            f"{card.id}: its style does not fit style.yaml ({exc}); fix the card's `style:` "
            "and promote again"
        ) from exc
    return text, style, created
