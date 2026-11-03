"""Compose one A3 drawing sheet: views, dimensions, hole table and title block (D11).

The layout is solved per candidate scale, largest first: each view is drawn in its own
local frame together with its annotations (dimensions, leaders, captions), so the space
the annotations need is known before placement.  The orthographic block (top above
front, right beside front — third-angle) is anchored top-left; the iso view, the flat
pattern and the hole table are packed into the remaining space; the title block sits in
the bottom-right corner.  The first scale at which everything fits wins and is recorded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from napkin2factory.drawings.sheet_views import (
    _annotate,
    _caption,
    _classify,
    _duplicate,
    _feature_reqs,
    _flat_drawing,
    _iso_drawing,
    _mapper,
    _ortho_drawing,
    _overall_reqs,
    _Req,
    _ViewDrawing,
)
from napkin2factory.drawings.svg import (
    FONT,
    TEXT,
    Box,
    Circle,
    Line,
    Path,
    Prim,
    Rect,
    Text,
    bbox_of,
    f,
    fit_size,
    fmt_mm,
    group,
)
from napkin2factory.drawings.views import ORTHO_VIEWS, View2D, hole_view

PAGE_W, PAGE_H = 420.0, 297.0
SHEET = "A3 420×297"
FRAME = 10.0
X0, Y0, X1, Y1 = FRAME + 5, FRAME + 5, PAGE_W - FRAME - 5, PAGE_H - FRAME - 5
GAP = 8.0
TB_W, TB_H = 180.0, 52.0
TB_BOX = Box(PAGE_W - FRAME - TB_W, PAGE_H - FRAME - TB_H, PAGE_W - FRAME, PAGE_H - FRAME)

#: Candidate scales, largest first: (label, sheet mm per model mm).
SCALES: list[tuple[str, float]] = [
    ("5:1", 5.0),
    ("2:1", 2.0),
    ("1:1", 1.0),
    ("1:1.5", 1 / 1.5),
    ("1:2", 0.5),
    ("1:2.5", 0.4),
    ("1:3", 1 / 3),
    ("1:4", 0.25),
    ("1:5", 0.2),
    ("1:7.5", 1 / 7.5),
    ("1:10", 0.1),
    ("1:15", 1 / 15),
    ("1:20", 0.05),
    ("1:25", 0.04),
    ("1:50", 0.02),
    ("1:100", 0.01),
]

Vec3 = tuple[float, float, float]
Pt = tuple[float, float]


@dataclass
class TitleFields:
    """What the title block shows."""

    uri: str
    name: str
    rev: str
    material: str
    process: str
    finish: str
    tolerance: str
    version: str
    date: str


@dataclass
class SheetInput:
    """Everything the composer needs, already loaded."""

    title: TitleFields
    views: dict[str, View2D]
    bbox_min: Vec3
    bbox_max: Vec3
    bbox_size: Vec3
    dims: list[dict[str, Any]]
    holes: list[dict[str, Any]]
    flat: dict[str, Any] | None = None
    bends: list[dict[str, Any]] = field(default_factory=list)
    thickness: float | None = None


@dataclass
class SheetResult:
    """The SVG text, the text hashed for the output hash, and a summary for tests."""

    svg: str
    hash_text: str
    meta: dict[str, Any]


#: The snapshot date when the product has no saved snapshot yet (the build runner's value).
UNSAVED = "unsnapshotted"


def date_words(date: str) -> str:
    """A title block's date in owner words: "not yet saved" for an unsaved product (gate D)."""
    return "not yet saved" if date == UNSAVED else date


# ---- hole table and title block ------------------------------------------------------


def hole_rows(inp: SheetInput) -> list[dict[str, Any]]:
    """Holes grouped by diameter with tags A1, A2…, coordinates from the view's lower-left."""
    lo = inp.bbox_min
    groups: dict[float, list[dict[str, Any]]] = {}
    for h in inp.holes:
        groups.setdefault(round(float(h["diameter"]), 3), []).append(h)
    rows: list[dict[str, Any]] = []
    for gi, dia in enumerate(sorted(groups)):
        letter = chr(ord("A") + gi % 26) + ("" if gi < 26 else str(gi // 26))
        members = []
        for h in groups[dia]:
            c = tuple(float(v) for v in h["center"])
            ax = h.get("axis") or (0.0, 0.0, 1.0)
            view = hole_view((float(ax[0]), float(ax[1]), float(ax[2])))
            if view == "top":
                xy: tuple[float, float] | None = (c[0] - lo[0], c[1] - lo[1])
            elif view == "front":
                xy = (c[0] - lo[0], c[2] - lo[2])
            elif view == "right":
                xy = (c[1] - lo[1], c[2] - lo[2])
            else:
                xy = None
            members.append((view or "", xy, c))
        members.sort(key=lambda m: (m[0], m[1] or (0.0, 0.0)))
        for i, (view, xy, c) in enumerate(members):
            rows.append(
                {
                    "tag": f"{letter}{i + 1}",
                    "diameter": dia,
                    "x": xy[0] if xy else None,
                    "y": xy[1] if xy else None,
                    "view": view,
                    "qty": len(members) if i == 0 else None,
                    "center": c,
                }
            )
    return rows


HT_COLS: list[tuple[str, float]] = [
    ("TAG", 12.0),
    ("⌀", 16.0),
    ("X", 18.0),
    ("Y", 18.0),
    ("VIEW", 16.0),
    ("QTY", 12.0),
]
HT_ROW = 5.0


def _hole_table(rows: list[dict[str, Any]]) -> list[Prim]:
    w = sum(c[1] for c in HT_COLS)
    prims: list[Prim] = [
        Text(w / 2, 4.2, "HOLE TABLE", size=TEXT, bold=True, cls="caption"),
        Text(w / 2, 8.4, "X / Y from the lower-left corner of the view", size=2.0, cls="note"),
    ]
    top = 10.0
    n = len(rows) + 1
    prims.append(Rect(0, top, w, n * HT_ROW))
    x = 0.0
    for _, cw in HT_COLS[:-1]:
        x += cw
        prims.append(Line(x, top, x, top + n * HT_ROW, cls="table"))
    for i in range(1, n):
        prims.append(Line(0, top + i * HT_ROW, w, top + i * HT_ROW, cls="table"))
    x = 0.0
    for name, cw in HT_COLS:
        prims.append(Text(x + cw / 2, top + 3.6, name, size=2.5, bold=True, cls="tablehead"))
        x += cw
    for ri, r in enumerate(rows):
        y = top + (ri + 1) * HT_ROW + 3.6
        cells = [
            r["tag"],
            "⌀" + fmt_mm(r["diameter"]),
            fmt_mm(r["x"]) if r["x"] is not None else "—",
            fmt_mm(r["y"]) if r["y"] is not None else "—",
            r["view"] or "—",
            str(r["qty"]) if r["qty"] else "",
        ]
        x = 0.0
        for (_, cw), val in zip(HT_COLS, cells, strict=True):
            prims.append(Text(x + cw / 2, y, val, size=fit_size(val, cw - 1.5, 2.5), cls="cell"))
            x += cw
    return prims


def _cell(x: float, y: float, w: float, h: float, label: str, value: str) -> list[Prim]:
    size = fit_size(value, w - 2.4, 3.2)
    return [
        Rect(x, y, w, h),
        Text(x + 1.2, y + 2.6, label, size=1.8, anchor="start", cls="tblabel"),
        Text(x + 1.2, y + h - 2.0, value, size=size, anchor="start", cls="tbvalue"),
    ]


def _third_angle_symbol(x: float, y: float, w: float, h: float) -> list[Prim]:
    """ISO 5456-2 third-angle symbol: truncated cone with its small end towards the circles."""
    cy = y + h / 2 + 0.8
    tx = x + w * 0.18
    big, small, length = 3.0, 1.6, 8.0
    cone = [(tx, cy - big), (tx + length, cy - small), (tx + length, cy + small), (tx, cy + big)]
    cx = x + w * 0.72
    return [
        Rect(x, y, w, h),
        Text(x + 1.2, y + 2.6, "PROJECTION", size=1.8, anchor="start", cls="tblabel"),
        Path([cone], "thin", closed=True),
        Circle(cx, cy, big, cls="thin"),
        Circle(cx, cy, small, cls="thin"),
        Line(tx - 1.5, cy, tx + length + 1.5, cy, cls="dim"),
        Line(cx - big - 1.5, cy, cx + big + 1.5, cy, cls="dim"),
        Line(cx, cy - big - 1.5, cx, cy + big + 1.5, cls="dim"),
    ]


def title_block(t: TitleFields, scale: str) -> list[Prim]:
    """Title block primitives in absolute sheet coordinates (bottom-right corner)."""
    x, y = TB_BOX.x0, TB_BOX.y0
    prims: list[Prim] = [Rect(x, y, TB_W, TB_H, cls="frame")]
    # row 1: name + URI | REV
    prims += [
        Rect(x, y, 140, 14),
        Text(x + 1.2, y + 2.6, "TITLE", size=1.8, anchor="start", cls="tblabel"),
        Text(
            x + 1.2,
            y + 8.0,
            t.name,
            size=fit_size(t.name, 137, 5.0),
            anchor="start",
            bold=True,
            cls="tbtitle",
        ),
        Text(x + 1.2, y + 12.4, t.uri, size=fit_size(t.uri, 137, 3.0), anchor="start", cls="uri"),
        Rect(x + 140, y, 40, 14),
        Text(x + 141.2, y + 2.6, "REV", size=1.8, anchor="start", cls="tblabel"),
        Text(x + 160, y + 11.5, t.rev, size=7.0, bold=True, cls="rev"),
    ]
    yy = y + 14
    prims += _cell(x, yy, 180, 9, "MATERIAL", t.material)
    yy += 9
    prims += _cell(x, yy, 55, 9, "PROCESS", t.process)
    prims += _cell(x + 55, yy, 75, 9, "FINISH", t.finish)
    prims += _cell(x + 130, yy, 50, 9, "GENERAL TOLERANCE", t.tolerance)
    yy += 9
    prims += _cell(x, yy, 30, 12, "SCALE", scale)
    prims += _cell(x + 30, yy, 40, 12, "SHEET", SHEET)
    prims += _cell(x + 70, yy, 40, 12, "DATE", date_words(t.date))
    prims += _cell(x + 110, yy, 30, 12, "UNITS", "mm")
    prims += _third_angle_symbol(x + 140, yy, 40, 12)
    yy += 12
    note = (
        f"Generated by napkin2factory {t.version}. Dimensions in mm; untoleranced "
        f"dimensions per {t.tolerance}. Do not scale the drawing. Produced with an AI system; "
        "not reviewed by a licensed engineer."
    )
    prims += [
        Rect(x, yy, 180, TB_H - (yy - y)),
        Text(x + 1.2, yy + 5.0, note, size=fit_size(note, 177, 2.2), anchor="start", cls="note"),
    ]
    return prims


# ---- layout ---------------------------------------------------------------------------


def _inside(b: Box) -> bool:
    return b.x0 >= X0 - 1e-6 and b.y0 >= Y0 - 1e-6 and b.x1 <= X1 + 1e-6 and b.y1 <= Y1 + 1e-6


def _pack(w: float, h: float, placed: list[Box], prefer: str) -> tuple[float, float] | None:
    """Find a free top-left corner for a ``w × h`` box among candidate positions."""
    xs = {X0, X1 - w} | {b.x1 + GAP for b in placed} | {b.x0 - GAP - w for b in placed}
    ys = {Y0, Y1 - h} | {b.y1 + GAP for b in placed} | {b.y0 - GAP - h for b in placed}
    best: tuple[tuple[float, float], tuple[float, float]] | None = None
    for x in xs:
        for y in ys:
            box = Box(x, y, x + w, y + h)
            if not _inside(box) or any(box.overlaps(p, GAP - 1e-6) for p in placed):
                continue
            key = {
                "top-right": (round(y, 3), -round(x, 3)),
                "top-left": (round(y, 3), round(x, 3)),
                "bottom-right": (-round(y + h, 3), -round(x + w, 3)),
            }[prefer]
            if best is None or key < best[0]:
                best = (key, (x, y))
    return None if best is None else best[1]


def _place(vd: _ViewDrawing, ext_xy: tuple[float, float]) -> None:
    """Move a drawing so its extent's top-left corner lands at ``ext_xy``."""
    e = vd.ext
    vd.x, vd.y = ext_xy[0] - e.x0, ext_xy[1] - e.y0


@dataclass
class _Layout:
    scale: tuple[str, float]
    drawings: dict[str, _ViewDrawing]
    table_xy: tuple[float, float] | None
    unplaced: list[str]


def _try_scale(
    inp: SheetInput, scale: tuple[str, float], rows: list[dict[str, Any]], table: list[Prim]
) -> _Layout | None:
    s = scale[1]
    tags: dict[str, list[tuple[Vec3, float, str]]] = {}
    for r in rows:
        if r["view"]:
            tags.setdefault(r["view"], []).append((r["center"], r["diameter"], r["tag"]))
    drawings: dict[str, _ViewDrawing] = {}
    unplaced: list[str] = []
    for name in ORTHO_VIEWS:
        drawings[name], u = _ortho_drawing(inp.views[name], inp, s, tags)
        unplaced += u
    drawings["iso"], u = _iso_drawing(inp.views["iso"], inp, s)
    unplaced += u
    if inp.flat:
        drawings["flat"], u = _flat_drawing(inp, s)
        unplaced += u
    front, top, right = drawings["front"], drawings["top"], drawings["right"]
    mf, mt, mr = front.margins(), top.margins(), right.margins()
    front.x = X0 + max(mf["left"], mt["left"])
    top.x = front.x
    top.y = Y0 + mt["top"]
    # The right view's top band and the top view's right band can collide at the corner
    # between them; resolve it either by pushing the front/right row down or the right
    # view further right, whichever gives the smaller block.
    options: list[tuple[float, float, float]] = []
    for push_down in (True, False):
        fy = top.y + top.h + mt["bottom"] + GAP + mf["top"]
        rx = front.x + front.w + mf["right"] + GAP + mr["left"]
        top_ext = top.abs_ext
        corner = Box(rx - mr["left"], fy - mr["top"], rx + right.w + mr["right"], fy)
        if corner.overlaps(top_ext, GAP):
            if push_down:
                fy = top_ext.y1 + GAP + mr["top"]
            else:
                rx = top_ext.x1 + GAP + mr["left"]
        area = (rx + right.w + mr["right"]) * (fy + max(front.h + mf["bottom"], right.h))
        options.append((area, fy, rx))
    _, front.y, right.x = min(options)
    right.y = front.y
    placed = [TB_BOX]
    for vd in (front, top, right):
        if not _inside(vd.abs_ext) or vd.abs_ext.overlaps(TB_BOX, GAP):
            return None
        placed.append(vd.abs_ext)
    for name, prefer in (("iso", "top-right"), ("flat", "top-left")):
        if name not in drawings:
            continue
        e = drawings[name].ext
        xy = _pack(e.w, e.h, placed, prefer)
        if xy is None:
            return None
        _place(drawings[name], xy)
        placed.append(drawings[name].abs_ext)
    table_xy = None
    if table:
        tb = bbox_of(table)
        assert tb is not None
        xy = _pack(tb.w, tb.h, placed, "bottom-right")
        if xy is None:
            return None
        table_xy = (xy[0] - tb.x0, xy[1] - tb.y0)
    return _Layout(scale, drawings, table_xy, unplaced)


STYLE = (
    f"text{{font-family:{FONT};fill:#000}}"
    ".hidden{stroke-dasharray:2 1}.bend{stroke-dasharray:5 1.5 1 1.5}"
    ".center{stroke-dasharray:4 1 1 1}"
)


def compose(inp: SheetInput) -> SheetResult:
    """Lay out and serialise the sheet.

    Raises:
        RuntimeError: if the part does not fit the sheet even at the smallest scale.
    """
    rows = hole_rows(inp)
    table = _hole_table(rows) if rows else []
    layout = None
    for scale in SCALES:
        layout = _try_scale(inp, scale, rows, table)
        if layout is not None:
            break
    if layout is None:
        raise RuntimeError(
            f"{inp.title.uri}: the views do not fit an A3 sheet even at {SCALES[-1][0]}"
        )
    label = layout.scale[0]
    parts: list[str] = []
    order = ["top", "front", "right", "iso", "flat"]
    dims: list[str] = []
    tags: list[str] = []
    n_dims = 0
    for name in order:
        vd = layout.drawings.get(name)
        if vd is None:
            continue
        bbox = f"{f(vd.x)} {f(vd.y)} {f(vd.w)} {f(vd.h)}"
        parts.append(group(f"view-{name}", vd.geometry + vd.caption, vd.x, vd.y, data_bbox=bbox))
        dims += [p.svg(vd.x, vd.y) for p in vd.annotations]
        tags += [p.svg(vd.x, vd.y) for p in vd.tags]
        n_dims += vd.n_dims
    parts.append(f'<g id="dims">{"".join(dims)}</g>')
    if tags:
        parts.append(f'<g id="hole-tags">{"".join(tags)}</g>')
    if layout.table_xy is not None:
        parts.append(group("hole-table", table, *layout.table_xy))
    frame = Rect(FRAME, FRAME, PAGE_W - 2 * FRAME, PAGE_H - 2 * FRAME, cls="frame")
    head = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{f(PAGE_W)}mm" height="{f(PAGE_H)}mm" viewBox="0 0 {f(PAGE_W)} {f(PAGE_H)}" '
        f'data-scale="{label}" data-part="{inp.title.uri}">'
        f"<style>{STYLE}</style>"
        f'<rect id="sheet" x="0" y="0" width="{f(PAGE_W)}" height="{f(PAGE_H)}" fill="#fff"/>'
        + group("frame", [frame])
    )
    body = "".join(parts)
    tb = group("titleblock", title_block(inp.title, label))
    svg = head + body + tb + "</svg>\n"
    stable_title = {k: v for k, v in vars(inp.title).items() if k != "date"}
    hash_text = head + body + json.dumps(stable_title, sort_keys=True) + "</svg>\n"
    meta = {
        "scale": label,
        "scale_factor": round(layout.scale[1], 6),
        "sheet": SHEET,
        "views": [n for n in order if n in layout.drawings],
        "dims": n_dims,
        "holes": len(rows),
        "has_flat": "flat" in layout.drawings,
        "unplaced_dims": layout.unplaced,
    }
    return SheetResult(svg=svg, hash_text=hash_text, meta=meta)


__all__ = [
    "FRAME",
    "GAP",
    "HT_COLS",
    "HT_ROW",
    "PAGE_H",
    "PAGE_W",
    "Pt",
    "SCALES",
    "SHEET",
    "STYLE",
    "SheetInput",
    "SheetResult",
    "TB_BOX",
    "TB_H",
    "TB_W",
    "TitleFields",
    "UNSAVED",
    "Vec3",
    "X0",
    "X1",
    "Y0",
    "Y1",
    "_Layout",
    "_Req",
    "_ViewDrawing",
    "_annotate",
    "_caption",
    "_cell",
    "_classify",
    "_duplicate",
    "_feature_reqs",
    "_flat_drawing",
    "_hole_table",
    "_inside",
    "_iso_drawing",
    "_mapper",
    "_ortho_drawing",
    "_overall_reqs",
    "_pack",
    "_place",
    "_third_angle_symbol",
    "_try_scale",
    "compose",
    "date_words",
    "hole_rows",
    "title_block",
]
