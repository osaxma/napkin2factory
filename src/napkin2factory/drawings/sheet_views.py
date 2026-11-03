"""Drawing views, annotations and placement boxes; split from sheet.py (S-184)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from napkin2factory.drawings.svg import (
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
    Text,
    bbox_of,
    fmt_mm,
)
from napkin2factory.drawings.views import View2D

if TYPE_CHECKING:
    from napkin2factory.drawings.sheet import SheetInput

Vec3 = tuple[float, float, float]
Pt = tuple[float, float]


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
