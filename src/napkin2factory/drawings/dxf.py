"""Flat-pattern DXF for the laser/punch shop (D11), written with ezdxf.

Layers: ``OUTLINE`` (closed polyline), ``HOLES`` (circles), ``CUTOUTS`` (closed
polylines), ``BEND`` (bend lines, linetype ``DASHED``), ``BEND-TEXT`` (direction and angle
per bend) and ``NOTES`` (part URI, thickness, bend convention).  Units are millimetres
(``$INSUNITS = 4``).  Coordinates are the flat pattern's own frame, unchanged.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

LAYERS: dict[str, int] = {
    "OUTLINE": 7,
    "HOLES": 1,
    "CUTOUTS": 3,
    "BEND": 5,
    "BEND-TEXT": 5,
    "NOTES": 8,
}

BEND_CONVENTION = (
    "BEND LINES: UP = flange bends towards the viewer of this flat view, "
    "DOWN = away from the viewer; angle is the bend angle"
)


def write_flat_dxf(
    path: Path,
    flat: dict[str, Any],
    uri: str,
    bends: list[dict[str, Any]],
    thickness: float | None,
) -> None:
    """Write the flat pattern to ``path`` (the caller handles atomic replacement).

    Args:
        path: destination file.
        flat: ``flat_pattern.json`` content (outline, holes, cutouts, bend_lines).
        uri: the part URI written into the NOTES layer.
        bends: ``features.json`` bends, used for each bend line's up/down direction.
        thickness: sheet thickness in mm, if known.
    """
    from ezdxf.filemanagement import new as new_dxf

    doc = new_dxf("R2010")
    doc.header["$INSUNITS"] = 4  # millimetres
    doc.header["$MEASUREMENT"] = 1  # metric
    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[0.75, 0.5, -0.25], description="Dashed __ __ __")
    for name, color in LAYERS.items():
        layer = doc.layers.add(name, color=color)
        if name == "BEND":
            layer.dxf.linetype = "DASHED"
    msp = doc.modelspace()
    outline = [(float(x), float(y)) for x, y in flat["outline"]]
    msp.add_lwpolyline(outline, close=True, dxfattribs={"layer": "OUTLINE"})
    for c, d in flat.get("holes", []):
        msp.add_circle((float(c[0]), float(c[1])), float(d) / 2, dxfattribs={"layer": "HOLES"})
    for cut in flat.get("cutouts", []):
        pts = [(float(x), float(y)) for x, y in cut]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "CUTOUTS"})
    direction = {b.get("label"): str(b.get("direction", "up")).upper() for b in bends}
    span = max(max(p[0] for p in outline) - min(p[0] for p in outline), 1.0)
    text_h = max(2.0, round(span / 120, 1))
    for p1, p2, angle, label in flat.get("bend_lines", []):
        a, b = (float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1]))
        msp.add_line(a, b, dxfattribs={"layer": "BEND", "linetype": "DASHED"})
        rot = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        if rot > 90:
            rot -= 180
        elif rot <= -90:
            rot += 180
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        text = f"{label} {direction.get(label, 'UP')} {float(angle):g}"
        msp.add_text(
            text + "%%d",
            height=text_h,
            rotation=rot,
            dxfattribs={"layer": "BEND-TEXT", "insert": mid},
        )
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    notes = [uri]
    if thickness:
        notes.append(f"THICKNESS {thickness:g} mm")
    notes.append(BEND_CONVENTION)
    for i, line in enumerate(notes):
        msp.add_text(
            line,
            height=text_h,
            dxfattribs={
                "layer": "NOTES",
                "insert": (min(xs), min(ys) - (i + 2) * text_h * 1.8),
            },
        )
    doc.saveas(path)
