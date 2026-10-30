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
import math
from dataclasses import dataclass, field
from typing import Any

from napkin2factory.drawings.svg import (
    FONT,
    OUTWARD,
    SMALL,
    TEXT,
    AlignedDim,
    Box,
    Circle,
    Leader,
    Line,
    LinearDim,
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


# ---- dimension requests (scale independent, view coordinates) ---------------------


@dataclass
class _Req:
    kind: str  # h | v | aligned | radius | diameter
    a: Pt
    b: Pt
    text: str
    label: str
    value: float
    side: str | None = None  # fixed side for overall dims
    overall: bool = False


def _classify(a: Pt, b: Pt, value: float) -> str | None:
    du, dv = abs(b[0] - a[0]), abs(b[1] - a[1])
    tol = 1e-3
    if du < tol and dv < tol:
        return None
    if dv < tol:
        return "h"
    if du < tol:
        return "v"
    if abs(du - value) < 0.01:
        return "h"
    if abs(dv - value) < 0.01:
        return "v"
    return "aligned"


def _duplicate(r: _Req, existing: list[_Req]) -> bool:
    i = 0 if r.kind == "h" else 1
    lo, hi = sorted((r.a[i], r.b[i]))
    for e in existing:
        if e.kind != r.kind or abs(e.value - r.value) > 0.05:
            continue
        elo, ehi = sorted((e.a[i], e.b[i]))
        if abs(lo - elo) < 0.05 and abs(hi - ehi) < 0.05:
            return True
    return False


def _overall_reqs(view: View2D, lo: Vec3, hi: Vec3, size: Vec3) -> list[_Req]:
    p = view.project
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    sx, sy, sz = (fmt_mm(v) for v in size)
    if view.name == "front":
        return [
            _Req("h", p((x0, y0, z0)), p((x1, y0, z0)), sx, "overall-x", size[0], "bottom", True),
            _Req("v", p((x0, y0, z0)), p((x0, y0, z1)), sz, "overall-z", size[2], "left", True),
        ]
    if view.name == "top":
        return [
            _Req("h", p((x0, y1, z1)), p((x1, y1, z1)), sx, "overall-x", size[0], "top", True),
            _Req("v", p((x0, y0, z1)), p((x0, y1, z1)), sy, "overall-y", size[1], "left", True),
        ]
    if view.name == "right":
        return [
            _Req("h", p((x1, y0, z0)), p((x1, y1, z0)), sy, "overall-y", size[1], "bottom", True),
            _Req("v", p((x1, y1, z0)), p((x1, y1, z1)), sz, "overall-z", size[2], "right", True),
        ]
    return []


def _feature_reqs(
    dims: list[dict[str, Any]], view: str, project: Any, existing: list[_Req]
) -> tuple[list[_Req], list[str]]:
    """Requests for generator dims on ``view``; returns (requests, unplaced labels)."""
    out: list[_Req] = []
    unplaced: list[str] = []
    for d in dims:
        if d.get("view", "front") != view:
            continue
        label = str(d.get("label", ""))
        value = float(d["value"])
        a, b = project(tuple(d["p1"])), project(tuple(d["p2"]))
        kind = d.get("kind", "linear")
        if kind in ("radius", "diameter"):
            text = ("R" if kind == "radius" else "⌀") + fmt_mm(value)
            out.append(_Req(kind, a, b, text, label, value))
            continue
        k = _classify(a, b, value)
        if k is None:
            unplaced.append(f"{view}:{label}")
            continue
        if view == "iso":
            k = "aligned"
        r = _Req(k, a, b, fmt_mm(value), label, value)
        if k in ("h", "v") and _duplicate(r, existing + out):
            continue
        out.append(r)
    return out, unplaced


# ---- one view drawn in its local frame ---------------------------------------------


@dataclass
class _ViewDrawing:
    name: str
    w: float
    h: float
    geometry: list[Prim]
    annotations: list[Prim] = field(default_factory=list)
    tags: list[Prim] = field(default_factory=list)
    caption: list[Prim] = field(default_factory=list)
    n_dims: int = 0
    x: float = 0.0
    y: float = 0.0

    @property
    def ext(self) -> Box:
        """Local box of geometry plus annotations and caption."""
        b = Box(0.0, 0.0, self.w, self.h)
        more = bbox_of(self.annotations + self.caption + self.tags)
        return b if more is None else b.union(more)

    def margins(self) -> dict[str, float]:
        """How far annotations reach beyond the view box on each side."""
        e = self.ext
        return {"left": -e.x0, "top": -e.y0, "right": e.x1 - self.w, "bottom": e.y1 - self.h}

    @property
    def abs_ext(self) -> Box:
        """Placed extent on the sheet."""
        return self.ext.moved(self.x, self.y)


def _mapper(umin: float, vmax: float, s: float) -> Any:
    def to_local(p: Pt) -> Pt:
        return ((p[0] - umin) * s, (vmax - p[1]) * s)

    return to_local


def _annotate(vd: _ViewDrawing, reqs: list[_Req], to_local: Any, s: float) -> None:
    """Place linear dims on side bands (stacked) and leaders beyond them."""
    by_side: dict[str, list[LinearDim]] = {k: [] for k in OUTWARD}
    leaders: dict[str, list[Leader]] = {"top": [], "bottom": []}
    view_box = Box(0.0, 0.0, vd.w, vd.h)
    overall_flags: dict[int, bool] = {}  # id(LinearDim) → is an overall dim
    for r in reqs:
        a, b = to_local(r.a), to_local(r.b)
        if r.kind in ("h", "v"):
            if r.side:
                side = r.side
            elif r.kind == "h":
                side = "top" if (a[1] + b[1]) / 2 < vd.h / 2 else "bottom"
            else:
                side = "left" if (a[0] + b[0]) / 2 < vd.w / 2 else "right"
            ld = LinearDim(a, b, r.kind, side, r.text, r.label)
            overall_flags[id(ld)] = r.overall
            by_side[side].append(ld)
        elif r.kind == "aligned":
            vd.annotations += AlignedDim(a, b, r.text, view_box, r.label).prims()
            vd.n_dims += 1
        else:
            # radius: p1 = arc centre, p2 = point on the arc; diameter: p1 = hole centre
            center = a
            anchor = b if r.kind == "radius" and math.dist(a, b) > 1e-6 else a
            side = "top" if center[1] < vd.h / 2 else "bottom"
            outward = 1 if center[0] >= vd.w / 2 else -1
            if anchor == center:
                rr = (r.value / 2 if r.kind == "diameter" else r.value) * s
                k = math.sqrt(0.5)
                dy = -k if side == "top" else k
                anchor = (center[0] + outward * k * rr, center[1] + dy * rr)
            leaders[side].append(Leader(anchor, side, r.text, outward, r.label))
    reach: dict[str, float] = {}
    for side, items in by_side.items():
        items.sort(key=lambda d: (overall_flags[id(d)], d.span))
        edge = {"bottom": vd.h, "top": 0.0, "left": 0.0, "right": vd.w}[side]
        sign = 1.0 if side in ("bottom", "right") else -1.0
        offset = 0.0
        prev_outer = 0.0
        for i, d in enumerate(items):
            inner, outer = d.footprint()
            if i == 0:
                offset = max(8.0, inner + 4.0)
            else:
                offset = max(offset + 7.0, offset + prev_outer + inner + 2.5)
            vd.annotations += d.prims(edge + sign * offset)
            prev_outer = outer
            vd.n_dims += 1
        reach[side] = offset + prev_outer if items else 0.0
    for side, lds in leaders.items():
        lds.sort(key=lambda ld: (ld.anchor[0], ld.anchor[1]))
        edge = vd.h if side == "bottom" else 0.0
        sign = 1.0 if side == "bottom" else -1.0
        for i, lead in enumerate(lds):
            level = edge + sign * (reach[side] + 7.0 + 6.0 * i)
            vd.annotations += lead.prims(level)
            vd.n_dims += 1


def _caption(vd: _ViewDrawing, text: str) -> None:
    e = vd.ext
    vd.caption = [Text(vd.w / 2, e.y1 + 6.0, text, size=TEXT, bold=True, cls="caption")]


def _ortho_drawing(
    view: View2D, inp: SheetInput, s: float, tags: dict[str, list[tuple[Vec3, float, str]]]
) -> tuple[_ViewDrawing, list[str]]:
    to_local = _mapper(view.umin, view.vmax, s)
    geom: list[Prim] = [Path([[to_local(p) for p in pl] for pl in view.visible], "visible")]
    if view.hidden:
        geom.append(Path([[to_local(p) for p in pl] for pl in view.hidden], "hidden"))
    vd = _ViewDrawing(view.name, view.width * s, view.height * s, geom)
    reqs = _overall_reqs(view, inp.bbox_min, inp.bbox_max, inp.bbox_size)
    feats, unplaced = _feature_reqs(inp.dims, view.name, view.project, reqs)
    _annotate(vd, reqs + feats, to_local, s)
    for center, dia, tag in tags.get(view.name, []):
        cx, cy = to_local(view.project(center))
        r = dia / 2 * s
        arm = r + 1.5  # centre mark: thin chain lines through the hole, past its edge
        vd.geometry += [
            Line(cx - arm, cy, cx + arm, cy, cls="center"),
            Line(cx, cy - arm, cx, cy + arm, cls="center"),
        ]
        sx = 1 if cx < vd.w / 2 else -1
        anchor = "start" if sx > 0 else "end"
        ty = cy + r + 0.6 + 0.75 * SMALL if cy < vd.h / 2 else cy - r - 0.6
        vd.tags.append(Text(cx + sx * (r + 0.4), ty, tag, size=SMALL, anchor=anchor, cls="holetag"))
    return vd, unplaced


def _iso_drawing(view: View2D, inp: SheetInput, s: float) -> tuple[_ViewDrawing, list[str]]:
    to_local = _mapper(view.umin, view.vmax, s)
    geom: list[Prim] = [Path([[to_local(p) for p in pl] for pl in view.visible], "visible")]
    vd = _ViewDrawing("iso", view.width * s, view.height * s, geom)
    feats, unplaced = _feature_reqs(inp.dims, "iso", view.project, [])
    _annotate(vd, feats, to_local, s)
    _caption(vd, "ISOMETRIC VIEW")
    return vd, unplaced


def _flat_drawing(inp: SheetInput, s: float) -> tuple[_ViewDrawing, list[str]]:
    flat = inp.flat or {}
    outline = [tuple(p) for p in flat["outline"]]
    pts: list[Pt] = [(float(p[0]), float(p[1])) for p in outline]
    for c, d in flat.get("holes", []):
        pts += [(c[0] - d / 2, c[1] - d / 2), (c[0] + d / 2, c[1] + d / 2)]
    for cut in flat.get("cutouts", []):
        pts += [(float(p[0]), float(p[1])) for p in cut]
    umin, umax = min(p[0] for p in pts), max(p[0] for p in pts)
    vmin, vmax = min(p[1] for p in pts), max(p[1] for p in pts)
    to_local = _mapper(umin, vmax, s)
    geom: list[Prim] = [Path([[to_local(p) for p in pts[: len(outline)]]], "visible", closed=True)]
    if flat.get("cutouts"):
        geom.append(
            Path(
                [[to_local((p[0], p[1])) for p in cut] for cut in flat["cutouts"]],
                "visible",
                closed=True,
            )
        )
    for c, d in flat.get("holes", []):
        cx, cy = to_local((c[0], c[1]))
        geom.append(Circle(cx, cy, d / 2 * s))
    direction = {b.get("label"): b.get("direction", "up") for b in inp.bends}
    for p1, p2, angle, label in flat.get("bend_lines", []):
        a, b = to_local((p1[0], p1[1])), to_local((p2[0], p2[1]))
        geom.append(Line(a[0], a[1], b[0], b[1], cls="bend"))
        text = f"{label} {str(direction.get(label, 'up')).upper()} {float(angle):g}°"
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        vertical = abs(b[0] - a[0]) < abs(b[1] - a[1])
        geom.append(
            Text(
                mx - 1.0 if vertical else mx,
                my if vertical else my - 1.0,
                text,
                size=SMALL,
                angle=-90 if vertical else 0,
                cls="bendtext",
            )
        )
    vd = _ViewDrawing("flat", (umax - umin) * s, (vmax - vmin) * s, geom)
    xs = [p[0] for p in pts[: len(outline)]]
    ys = [p[1] for p in pts[: len(outline)]]
    bw, bh = max(xs) - min(xs), max(ys) - min(ys)
    reqs = [
        _Req(
            "h", (min(xs), min(ys)), (max(xs), min(ys)), fmt_mm(bw), "blank-x", bw, "bottom", True
        ),
        _Req("v", (min(xs), min(ys)), (min(xs), max(ys)), fmt_mm(bh), "blank-y", bh, "left", True),
    ]
    feats, unplaced = _feature_reqs(inp.dims, "flat", lambda p: (p[0], p[1]), reqs)
    _annotate(vd, reqs + feats, to_local, s)
    t = flat.get("thickness", inp.thickness)
    _caption(vd, f"FLAT PATTERN (developed blank, t = {fmt_mm(float(t))} mm)" if t else "FLAT")
    return vd, unplaced


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
    prims += _cell(x + 70, yy, 40, 12, "DATE", t.date)
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
