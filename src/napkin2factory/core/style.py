"""Load a product's ``style.yaml`` (decision N7).

``load_style(root)`` returns the *resolved* style (preset values filled in); a product
without the file gets the ``industrial`` defaults, whose shape cues are all no-ops, so v0.1
products build exactly as before.  ``merge_card_style`` lays a concept card's ``style:``
sketch over the product's style for that card's pictures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napkin2factory.core.errors import N2FError
from napkin2factory.core.model.style import StyleFile

STYLE_FILE = "style.yaml"
#: The build-graph read key for the geometry-relevant part of ``style.yaml``.
STYLE_GEOMETRY_KEY = "style:geometry"
#: The build-graph read key for the look (palette and finishes) the report viewer paints.
STYLE_LOOK_KEY = "style:look"
#: The build-graph read key for the form cues the ``form-v0`` rule pack checks against.
STYLE_FORM_KEY = "style:form"

#: The style fields the ``form-v0`` rule pack reads (thresholds live in style, N8).
FORM_FIELDS: tuple[str, ...] = ("corner_radius", "fastener_visibility", "layout")

#: The style fields that change geometry (palette and finish only change pictures).
GEOMETRY_FIELDS: tuple[str, ...] = (
    "radius_scale",
    "corner_radius",
    "chamfer",
    "reveal",
    "overhang",
    "vent_pattern",
)


def style_path(root: Path) -> Path:
    """``<product>/style.yaml``."""
    return Path(root) / STYLE_FILE


def load_style(root: Path) -> StyleFile:
    """The product's resolved style; ``industrial`` defaults when there is no file.

    Raises:
        N2FError: the file exists but is not valid YAML or does not match the schema.
    """
    import yaml
    from pydantic import ValidationError

    path = style_path(root)
    if not path.is_file():
        return StyleFile().resolved()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise N2FError(f"style.yaml is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise N2FError("style.yaml must be a mapping (preset: industrial, palette: {...}, ...)")
    try:
        return StyleFile.model_validate(data).resolved()
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "style.yaml"
        raise N2FError(f"style.yaml: {where}: {first['msg']}") from exc


def geometry_fingerprint(style: StyleFile) -> dict[str, Any]:
    """The geometry-relevant part of a resolved style, JSON-ready (a build-graph read)."""
    data = style.model_dump(mode="json")
    return {k: data[k] for k in GEOMETRY_FIELDS}


def form_fingerprint(root: Path) -> dict[str, Any]:
    """The form cues of the product's resolved style (a build-graph read of the checks)."""
    data = load_style(root).model_dump(mode="json")
    return {k: data[k] for k in FORM_FIELDS}


def look_fingerprint(root: Path) -> dict[str, Any] | None:
    """Palette and finishes of the product's ``style.yaml``; ``None`` without the file."""
    if not style_path(root).is_file():
        return None
    data = load_style(root).model_dump(mode="json")
    return {"palette": data["palette"], "finish": data["finish"]}


def merge_card_style(product: StyleFile, card_style: dict[str, Any]) -> tuple[StyleFile, list[str]]:
    """A concept card's ``style:`` laid over the product's style; returns (style, notes).

    A card that names a different ``preset`` starts from that preset (the product's own
    colours belong to its own preset); otherwise the card's keys override the product's.
    ``palette``/``finish`` merge per role.  Keys the schema does not know are skipped with a
    note — a card sketch never stops a picture.
    """
    from pydantic import ValidationError

    if not card_style:
        return product, []
    fields = set(StyleFile.model_fields)
    unknown = sorted(k for k in card_style if k not in fields)
    known = {k: v for k, v in card_style.items() if k in fields}
    notes = [f"card style keys not used: {', '.join(unknown)}"] if unknown else []
    if known.get("preset", product.preset) != product.preset:
        data: dict[str, Any] = dict(known)
    else:
        data = product.model_dump(mode="json")
        for key, value in known.items():
            if key in ("palette", "finish") and isinstance(value, dict):
                data[key] = {**data.get(key, {}), **value}
            else:
                data[key] = value
    try:
        return StyleFile.model_validate(data).resolved(), notes
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        return product, [*notes, f"card style not used ({where}: {first['msg']})"]


__all__ = [
    "FORM_FIELDS",
    "GEOMETRY_FIELDS",
    "STYLE_FILE",
    "STYLE_FORM_KEY",
    "STYLE_GEOMETRY_KEY",
    "STYLE_LOOK_KEY",
    "form_fingerprint",
    "geometry_fingerprint",
    "load_style",
    "look_fingerprint",
    "merge_card_style",
    "style_path",
]
