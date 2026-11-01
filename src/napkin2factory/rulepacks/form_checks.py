"""Named checks behind ``form-v0.yaml``: taste, once chosen, becomes checkable (N8).

``n2f concept promote`` writes form requirements (``verify: {kind: rule, target:
rule://form-v0/<rule-id>}``); these checks produce the rule rows those requirements read.
Thresholds live in the product's resolved ``style.yaml`` (``corner_radius``,
``fastener_visibility``, ``layout.controls``), never in the pack: the YAML carries the
wording only. Same contract as :mod:`napkin2factory.rulepacks.checks`: each check takes
``(part, features, params, product)`` and returns violations; it raises
:class:`~napkin2factory.rulepacks.checks.RuleNotApplicable` when the rule does not concern
the part (no row) and :class:`~napkin2factory.rulepacks.checks.RuleSkip` when it concerns
the part but cannot decide (a ``skip`` row saying why).

What each check can and cannot see:

* ``form_corner_radius`` — custom parts with a styled role (body, opening, support,
  controls, trim; ``door`` and ``stand`` read as opening and support). It reads the bend
  radii in ``features.json`` and the part's declared
  ``corner_radius``/``fillet`` (a style default fills an unset one unless the build noted it
  did not fit). Edges a generator rounds without recording (custom geometry modules, frame
  tubes) are not seen: such a part is skipped with a message, never passed.
* ``form_fasteners_hidden_front`` — parts with role body or opening (or door). A hole
  counts as on the front when, placed in a top assembly (``instances.json``), its axis runs
  along Y and its centre lies in the front (−Y) half of that assembly's bounding box: the
  −Y wall of an enclosure, or a panel whose placement faces −Y. It cannot tell whether
  something in front hides the hole, and it reads holes in the body and door, not the
  screws themselves; a part not placed in any assembly is skipped (front and back cannot
  be told apart).
* ``form_controls_placement`` (a warning) — the part with role controls: its centroid,
  placed in a top assembly, against the side ``style.layout.controls`` names (left/right on
  X, front/back on Y, top/below on Z, relative to the assembly's bounding-box centre).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from napkin2factory.core.errors import N2FError
from napkin2factory.core.loader import Product
from napkin2factory.core.model import Part
from napkin2factory.core.model.style import STYLED_ROLES, StyleFile, role_for
from napkin2factory.core.units import UnitError, parse_quantity
from napkin2factory.rulepacks.checks import CheckFn, RuleNotApplicable, RuleSkip, Violation

#: Roles whose fastener holes must not show on the front (``hidden-front``).
#: ``role_for`` reads an alias as its role, so a part written ``role: door`` is an opening.
FASTENER_ROLES: frozenset[str] = frozenset({"body", "opening"})
#: Kit generators with a declared corner rounding, and the argument that carries it.
KIT_ROUND_ARGS: dict[str, str] = {
    "panel": "corner_radius",
    "plate": "corner_radius",
    "tube": "corner_radius",
    "block": "fillet",
}
#: A hole axis this close to ±Y faces front or back.
AXIS_TOLERANCE = 0.99
#: Side words in ``layout.controls`` and the axis/sign each one means.
SIDES: dict[str, tuple[int, int]] = {
    "left": (0, -1),
    "right": (0, 1),
    "front": (1, -1),
    "back": (1, 1),
    "below": (2, -1),
    "top": (2, 1),
}
_SIDE_ALIASES = {"rear": "back", "bottom": "below", "under": "below", "above": "top"}

Vec = tuple[float, float, float]


def _style(product: Product) -> StyleFile:
    from napkin2factory.core.style import load_style

    try:
        return load_style(product.paths.root)
    except N2FError as exc:
        raise RuleSkip(f"style.yaml does not load ({exc}); fix it to check form") from exc


def _mm(q: Any) -> float:
    return float(q.to("mm").magnitude)


def _fmt_mm(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".") + " mm"


def _built(feats: dict[str, Any]) -> None:
    if not any(k for k in feats if not k.startswith("_")):
        raise RuleSkip("not built yet — run `n2f build`")


def _arg_mm(product: Product, value: Any) -> float | None:
    """A kit argument in mm (a quantity, a bare number in mm, or ``param://…``)."""
    try:
        if isinstance(value, str) and value.strip().startswith("param://"):
            return _mm(product.parameter_value(value.strip().removeprefix("param://")))
        return _mm(parse_quantity(value, "mm"))
    except (N2FError, UnitError, KeyError, ValueError, AttributeError, TypeError):
        return None


def _declared_round(
    part: Part, product: Product, style: StyleFile, feats: dict[str, Any]
) -> tuple[str, float] | None:
    """The part's corner rounding (label, mm): declared, or the style default it took."""
    from napkin2factory.core.model.parts import KitGeometry

    geo = part.geometry
    if not isinstance(geo, KitGeometry) or geo.kit not in KIT_ROUND_ARGS:
        return None
    name = KIT_ROUND_ARGS[geo.kit]
    label = "corner radius" if name == "corner_radius" else "edge fillet"
    if name in geo.args:
        value = _arg_mm(product, geo.args[name])
        return None if value is None else (label, value)
    if geo.kit == "block" and "chamfer" in geo.args:
        return (f"{label} (chamfered instead)", 0.0)
    skipped = any(
        str(n).startswith(f"style {name} ") and "not applied" in str(n)
        for n in feats.get("notes", [])
    )
    return (label, 0.0) if skipped else (f"{label} (from style.yaml)", _mm(style.corner_radius))


def form_corner_radius(
    part: Part, feats: dict[str, Any], params: dict[str, Any], product: Product
) -> list[Violation]:
    """Bend radii and declared corner radii ≥ ``style.corner_radius`` on styled parts."""
    if part.kind != "custom" or not part.has_geometry or role_for(part) not in STYLED_ROLES:
        raise RuleNotApplicable
    style = _style(product)
    minimum = _mm(style.corner_radius)
    if minimum <= 0:
        raise RuleSkip("style.yaml sets no corner_radius (0 mm): no minimum radius chosen")
    _built(feats)
    radii: list[tuple[str, float]] = [
        (f"bend {b.get('label') or i + 1}", float(b["radius"]))
        for i, b in enumerate(feats.get("bends", []))
    ]
    declared = _declared_round(part, product, style, feats)
    if declared is not None:
        radii.append(declared)
    if not radii:
        raise RuleSkip(
            "no bends or corner radius recorded for this part (custom geometry or frame "
            "tubes): check its corners by eye"
        )
    return [
        {"label": label, "radius": _fmt_mm(r), "min": _fmt_mm(minimum)}
        for label, r in radii
        if r + 1e-6 < minimum
    ]


def _rotate(q: list[float], v: Vec) -> Vec:
    """Rotate ``v`` by the unit quaternion ``q`` (x, y, z, w)."""
    x, y, z, w = (float(c) for c in q)
    vx, vy, vz = v
    # t = 2 q × v ; v' = v + w t + q × t
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def _placements(
    product: Product, build_dir: Path, uri: str
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """(top assembly id, instance, assembly props) for every placement of ``uri``."""
    from napkin2factory.bom.rollups import top_assemblies

    out: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for aid in top_assemblies(product):
        folder = build_dir / "assemblies" / aid
        inst_path, props_path = folder / "instances.json", folder / "props.json"
        if not inst_path.is_file() or not props_path.is_file():
            continue
        props = json.loads(props_path.read_text(encoding="utf-8"))
        for inst in json.loads(inst_path.read_text(encoding="utf-8")):
            if inst.get("uri") == uri:
                out.append((aid, inst, props))
    return out


def _world(inst: dict[str, Any], p: Vec) -> Vec:
    r = _rotate(inst["rotation"], p)
    t = inst["translation"]
    return (r[0] + float(t[0]), r[1] + float(t[1]), r[2] + float(t[2]))


def _build_dir(feats: dict[str, Any], product: Product) -> Path:
    return Path(str(feats.get("_build_dir") or product.paths.build))


def form_fasteners_hidden_front(
    part: Part, feats: dict[str, Any], params: dict[str, Any], product: Product
) -> list[Violation]:
    """No fastener holes on the front (−Y) face of body and door parts (``hidden-front``)."""
    if not part.has_geometry or role_for(part) not in FASTENER_ROLES:
        raise RuleNotApplicable
    style = _style(product)
    if style.fastener_visibility != "hidden-front":
        raise RuleSkip(
            f"style.yaml has fastener_visibility {style.fastener_visibility}: "
            "fasteners may show on the front"
        )
    _built(feats)
    placements = _placements(product, _build_dir(feats, product), part.uri)
    if not placements:
        raise RuleSkip("not placed in a built assembly, so the front cannot be told from the back")
    out: list[Violation] = []
    seen: set[str] = set()
    for aid, inst, props in placements:
        lo, hi = props["bbox"]["min"], props["bbox"]["max"]
        mid_y = (float(lo[1]) + float(hi[1])) / 2
        for i, h in enumerate(feats.get("holes", [])):
            axis = _rotate(inst["rotation"], tuple(h.get("axis") or (0.0, 0.0, 1.0)))
            centre = _world(inst, tuple(h["center"]))
            if abs(axis[1]) < AXIS_TOLERANCE or centre[1] > mid_y + 1e-6:
                continue
            label = str(h.get("label") or f"hole {i + 1}")
            if label in seen:
                continue
            seen.add(label)
            out.append(
                {
                    "label": label,
                    "diameter": _fmt_mm(float(h["diameter"])),
                    "where": f"y = {centre[1]:.0f} mm, front half of {aid}",
                }
            )
    return out


def _sides(text: str) -> list[str]:
    words = re.split(r"[\s\-_/,]+", text.strip().lower())
    found: list[str] = []
    for w in words:
        side = _SIDE_ALIASES.get(w, w)
        if side in SIDES and side not in found:
            found.append(side)
    return found


def form_controls_placement(
    part: Part, feats: dict[str, Any], params: dict[str, Any], product: Product
) -> list[Violation]:
    """The controls part sits on the side ``style.layout.controls`` names."""
    if not part.has_geometry or role_for(part) != "controls":
        raise RuleNotApplicable
    style = _style(product)
    wanted = str(style.layout.get("controls", "")).strip()
    if not wanted:
        raise RuleSkip("style.yaml has no layout.controls (e.g. side-right) to compare with")
    sides = _sides(wanted)
    if not sides:
        raise RuleSkip(
            f"layout.controls {wanted!r} names no side (left, right, front, back, top, below)"
        )
    build_dir = _build_dir(feats, product)
    props_path = build_dir / "parts" / part.id / "props.json"
    placements = _placements(product, build_dir, part.uri)
    if not props_path.is_file() or not placements:
        raise RuleSkip("not placed in a built assembly yet — run `n2f build`")
    c = json.loads(props_path.read_text(encoding="utf-8")).get("centroid") or {}
    local: Vec = (float(c.get("x", 0.0)), float(c.get("y", 0.0)), float(c.get("z", 0.0)))
    out: list[Violation] = []
    for aid, inst, props in placements:
        lo, hi = props["bbox"]["min"], props["bbox"]["max"]
        centre = [(float(lo[k]) + float(hi[k])) / 2 for k in range(3)]
        world = _world(inst, local)
        for side in sides:
            axis, sign = SIDES[side]
            offset = world[axis] - centre[axis]
            if offset * sign <= 0:
                opposite = next(s for s, (a, g) in SIDES.items() if a == axis and g == -sign)
                out.append(
                    {
                        "side": wanted,
                        "where": f"{opposite} of the centre of {aid} "
                        f"({'xyz'[axis]} = {world[axis]:.0f} mm)",
                    }
                )
    return out


FORM_CHECKS: dict[str, CheckFn] = {
    "form_corner_radius": form_corner_radius,
    "form_fasteners_hidden_front": form_fasteners_hidden_front,
    "form_controls_placement": form_controls_placement,
}

__all__ = [
    "FORM_CHECKS",
    "form_controls_placement",
    "form_corner_radius",
    "form_fasteners_hidden_front",
]
