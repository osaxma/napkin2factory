"""SVG primitives, dimension lines and leaders for drawings, in sheet millimetres.

Every primitive knows its bounding box (text boxes are estimated from the font size) so the
sheet layout can reserve room for annotations before anything is placed.  Coordinates are
y-down (SVG); serialisation rounds to 0.01 mm so output is byte-stable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from xml.sax.saxutils import escape, quoteattr

Pt = tuple[float, float]

#: ISO 3098-ish sizes, mm.
TEXT = 3.5
SMALL = 2.5
ARROW = 2.5  # arrowhead length
ARROW_W = 0.9  # arrowhead full width
CHAR_W = 0.6  # average glyph advance as a fraction of the font size (sans, digits)
FONT = "DejaVu Sans, Arial, Helvetica, sans-serif"

#: Line styles: (stroke-width, dasharray or None).
STYLES: dict[str, tuple[float, str | None]] = {
    "visible": (0.5, None),
    "hidden": (0.25, "2 1"),
    "bend": (0.25, "5 1.5 1 1.5"),
    "center": (0.18, "4 1 1 1"),
    "dim": (0.18, None),
    "thin": (0.25, None),
    "frame": (0.7, None),
    "table": (0.25, None),
}


def f(v: float) -> str:
    """Format a coordinate: 2 decimals, trailing zeros stripped, no negative zero."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def fmt_mm(v: float) -> str:
    """Dimension value text: millimetres with one decimal."""
    return f"{v:.1f}"


def text_width(text: str, size: float) -> float:
    """Estimated advance width of ``text`` at ``size``."""
    return len(text) * size * CHAR_W


def fit_size(text: str, width: float, size: float, minimum: float = 1.6) -> float:
    """Largest font size ≤ ``size`` (≥ ``minimum``) at which ``text`` fits in ``width``."""
    if not text:
        return size
    return max(minimum, min(size, width / (len(text) * CHAR_W)))


@dataclass
class Box:
    """Axis-aligned box ``[x0, x1] × [y0, y1]`` (y down)."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def w(self) -> float:
        """Width."""
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        """Height."""
        return self.y1 - self.y0

    def union(self, o: Box) -> Box:
        """Smallest box containing both."""
        return Box(min(self.x0, o.x0), min(self.y0, o.y0), max(self.x1, o.x1), max(self.y1, o.y1))

    def moved(self, dx: float, dy: float) -> Box:
        """Translated copy."""
        return Box(self.x0 + dx, self.y0 + dy, self.x1 + dx, self.y1 + dy)

    def overlaps(self, o: Box, gap: float = 0.0) -> bool:
        """True if the boxes (each grown by ``gap``/2) intersect."""
        g = gap / 2
        return not (
            self.x1 + g <= o.x0 - g
            or o.x1 + g <= self.x0 - g
            or self.y1 + g <= o.y0 - g
            or o.y1 + g <= self.y0 - g
        )


def _box_of(pts: list[Pt]) -> Box:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return Box(min(xs), min(ys), max(xs), max(ys))


def _style_attrs(cls: str) -> str:
    width, dash = STYLES.get(cls, STYLES["thin"])
    s = f'class="{cls}" fill="none" stroke="#000" stroke-width="{f(width)}"'
    if dash:
        s += f' stroke-dasharray="{dash}"'
    return s


@dataclass
class Prim:
    """Base primitive."""

    def bbox(self) -> Box:
        """Bounding box in local sheet mm."""
        raise NotImplementedError

    def svg(self, dx: float = 0.0, dy: float = 0.0) -> str:
        """SVG markup translated by ``(dx, dy)``."""
        raise NotImplementedError


@dataclass
class Path(Prim):
    """One ``<path>`` made of several polylines."""

    polylines: list[list[Pt]]
    cls: str = "visible"
    closed: bool = False

    def bbox(self) -> Box:
        """Bounding box of all vertices."""
        return _box_of([p for pl in self.polylines for p in pl])

    def svg(self, dx: float = 0.0, dy: float = 0.0) -> str:
        """``<path d="M.. L..">``."""
        d: list[str] = []
        for pl in self.polylines:
            if len(pl) < 2:
                continue
            seg = "M" + " L".join(f"{f(x + dx)} {f(y + dy)}" for x, y in pl)
            d.append(seg + (" Z" if self.closed else ""))
        return f'<path {_style_attrs(self.cls)} d="{" ".join(d)}"/>'


@dataclass
class Line(Prim):
    """A straight segment."""

    x1: float
    y1: float
    x2: float
    y2: float
    cls: str = "dim"

    def bbox(self) -> Box:
        """Bounding box."""
        return _box_of([(self.x1, self.y1), (self.x2, self.y2)])

    def svg(self, dx: float = 0.0, dy: float = 0.0) -> str:
        """``<line>``."""
        return (
            f'<line {_style_attrs(self.cls)} x1="{f(self.x1 + dx)}" y1="{f(self.y1 + dy)}" '
            f'x2="{f(self.x2 + dx)}" y2="{f(self.y2 + dy)}"/>'
        )


@dataclass
class Circle(Prim):
    """A circle."""

    cx: float
    cy: float
    r: float
    cls: str = "visible"

    def bbox(self) -> Box:
        """Bounding box."""
        return Box(self.cx - self.r, self.cy - self.r, self.cx + self.r, self.cy + self.r)

    def svg(self, dx: float = 0.0, dy: float = 0.0) -> str:
        """``<circle>``."""
        return (
            f'<circle {_style_attrs(self.cls)} cx="{f(self.cx + dx)}" cy="{f(self.cy + dy)}" '
            f'r="{f(self.r)}"/>'
        )


@dataclass
class Rect(Prim):
    """An outlined rectangle."""

    x: float
    y: float
    w: float
    h: float
    cls: str = "table"

    def bbox(self) -> Box:
        """Bounding box."""
        return Box(self.x, self.y, self.x + self.w, self.y + self.h)

    def svg(self, dx: float = 0.0, dy: float = 0.0) -> str:
        """``<rect>``."""
        return (
            f'<rect {_style_attrs(self.cls)} x="{f(self.x + dx)}" y="{f(self.y + dy)}" '
            f'width="{f(self.w)}" height="{f(self.h)}"/>'
        )


@dataclass
class Arrow(Prim):
    """A filled arrowhead with its tip at ``tip`` pointing along ``direction``."""

    tip: Pt
    direction: Pt

    def _pts(self) -> list[Pt]:
        dx, dy = self.direction
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        bx, by = self.tip[0] - ux * ARROW, self.tip[1] - uy * ARROW
        hw = ARROW_W / 2
        return [self.tip, (bx - uy * hw, by + ux * hw), (bx + uy * hw, by - ux * hw)]

    def bbox(self) -> Box:
        """Bounding box."""
        return _box_of(self._pts())

    def svg(self, dx: float = 0.0, dy: float = 0.0) -> str:
        """``<path>`` triangle."""
        p = self._pts()
        d = "M" + " L".join(f"{f(x + dx)} {f(y + dy)}" for x, y in p) + " Z"
        return f'<path class="arrow" fill="#000" stroke="none" d="{d}"/>'


@dataclass
class Text(Prim):
    """Text with an anchor; ``angle`` is −90 for text reading bottom-to-top."""

    x: float
    y: float
    text: str
    size: float = TEXT
    anchor: str = "middle"  # start | middle | end
    angle: float = 0.0
    bold: bool = False
    cls: str = "dimtext"
    attrs: dict[str, str] = field(default_factory=dict)

    def bbox(self) -> Box:
        """Estimated glyph box (ascent 0.75, descent 0.2 of the size)."""
        w = text_width(self.text, self.size)
        a = {"start": 0.0, "middle": -w / 2, "end": -w}[self.anchor]
        local = [(a, -0.75 * self.size), (a + w, 0.2 * self.size)]
        if self.angle == 0:
            return Box(
                self.x + local[0][0],
                self.y + local[0][1],
                self.x + local[1][0],
                self.y + local[1][1],
            )
        t = math.radians(self.angle)
        ct, st = math.cos(t), math.sin(t)
        corners = [(u, v) for u in (local[0][0], local[1][0]) for v in (local[0][1], local[1][1])]
        pts = [(self.x + u * ct - v * st, self.y + u * st + v * ct) for u, v in corners]
        return _box_of(pts)

    def svg(self, dx: float = 0.0, dy: float = 0.0) -> str:
        """``<text>``."""
        x, y = self.x + dx, self.y + dy
        rot = f' transform="rotate({f(self.angle)} {f(x)} {f(y)})"' if self.angle else ""
        weight = ' font-weight="bold"' if self.bold else ""
        extra = "".join(f" {k}={quoteattr(v)}" for k, v in sorted(self.attrs.items()))
        return (
            f'<text class="{self.cls}" x="{f(x)}" y="{f(y)}" font-size="{f(self.size)}" '
            f'text-anchor="{self.anchor}"{weight}{rot}{extra}>{escape(self.text)}</text>'
        )


def bbox_of(prims: list[Prim]) -> Box | None:
    """Union of primitive boxes (``None`` when empty)."""
    out: Box | None = None
    for p in prims:
        b = p.bbox()
        out = b if out is None else out.union(b)
    return out


def group(gid: str, prims: list[Prim], dx: float = 0.0, dy: float = 0.0, **attrs: str) -> str:
    """Serialise primitives into ``<g id=...>`` translated by ``(dx, dy)``."""
    extra = "".join(f" {k.replace('_', '-')}={quoteattr(v)}" for k, v in attrs.items())
    body = "".join(p.svg(dx, dy) for p in prims)
    return f'<g id="{gid}"{extra}>{body}</g>'


# ---- dimensions ------------------------------------------------------------------

#: Outward unit vector for each side of a view box (y down).
OUTWARD: dict[str, Pt] = {"bottom": (0, 1), "top": (0, -1), "left": (-1, 0), "right": (1, 0)}


@dataclass
class LinearDim:
    """A horizontal or vertical dimension between two sheet points, placed on a side band."""

    a: Pt
    b: Pt
    orient: str  # h | v
    side: str  # bottom | top | left | right
    text: str
    label: str = ""

    @property
    def span(self) -> float:
        """Measured length on the sheet."""
        i = 0 if self.orient == "h" else 1
        return abs(self.b[i] - self.a[i])

    @property
    def short(self) -> bool:
        """True when the text and arrows do not fit between the extension lines."""
        return self.span < text_width(self.text, TEXT) + 2 * ARROW + 2

    def footprint(self) -> tuple[float, float]:
        """(inner, outer) extent across the band relative to the dimension line."""
        overshoot = 1.5
        glyph = 1.0 + 0.75 * TEXT  # baseline gap + ascent
        if self.orient == "v" and self.short:
            return 0.0, 1.5 + text_width(self.text, TEXT)
        # text sits on the −y side (h) or −x side (v, rotated) of the line
        text_towards_view = self.side in ("bottom", "right")
        if text_towards_view:
            return glyph, overshoot
        return 0.0, max(glyph, overshoot)

    def prims(self, line: float) -> list[Prim]:
        """Extension lines, dimension line, arrows and text with the line at ``line``.

        Args:
            line: the y (h) or x (v) coordinate of the dimension line.
        """
        out: list[Prim] = []
        ox, oy = OUTWARD[self.side]
        gap, over = 1.0, 1.5
        if self.orient == "h":
            xa, xb = sorted((self.a[0], self.b[0]))
            for x, y in ((self.a[0], self.a[1]), (self.b[0], self.b[1])):
                out.append(Line(x, y + oy * gap, x, line + oy * over))
            if self.short:
                out.append(Line(xa - ARROW - 2, line, xb + ARROW + 2, line))
                out += [Arrow((xa, line), (1, 0)), Arrow((xb, line), (-1, 0))]
                out.append(
                    Text(xb + ARROW + 3, line - 1.0, self.text, anchor="start", attrs=self._data())
                )
            else:
                out.append(Line(xa, line, xb, line))
                out += [Arrow((xa, line), (-1, 0)), Arrow((xb, line), (1, 0))]
                out.append(Text((xa + xb) / 2, line - 1.0, self.text, attrs=self._data()))
        else:
            ya, yb = sorted((self.a[1], self.b[1]))
            for x, y in ((self.a[0], self.a[1]), (self.b[0], self.b[1])):
                out.append(Line(x + ox * gap, y, line + ox * over, y))
            mid = (ya + yb) / 2
            if self.short:
                out.append(Line(line, ya - ARROW - 2, line, yb + ARROW + 2))
                out += [Arrow((line, ya), (0, 1)), Arrow((line, yb), (0, -1))]
                if self.side == "left":
                    out.append(
                        Text(line - 1.5, mid + 1.2, self.text, anchor="end", attrs=self._data())
                    )
                else:
                    out.append(
                        Text(line + 1.5, mid + 1.2, self.text, anchor="start", attrs=self._data())
                    )
            else:
                out.append(Line(line, ya, line, yb))
                out += [Arrow((line, ya), (0, -1)), Arrow((line, yb), (0, 1))]
                out.append(Text(line - 1.0, mid, self.text, angle=-90, attrs=self._data()))
        return out

    def _data(self) -> dict[str, str]:
        return {"data-dim": self.label} if self.label else {}


@dataclass
class AlignedDim:
    """A dimension parallel to a sloped segment, offset clear of the view box."""

    a: Pt
    b: Pt
    text: str
    view: Box
    label: str = ""

    def prims(self) -> list[Prim]:
        """Extension lines, dimension line, arrows and text, clear of ``view``."""
        (ax, ay), (bx, by) = self.a, self.b
        dx, dy = bx - ax, by - ay
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        nx, ny = -uy, ux
        cx, cy = (self.view.x0 + self.view.x1) / 2, (self.view.y0 + self.view.y1) / 2
        if (ax + bx) / 2 * nx + (ay + by) / 2 * ny < cx * nx + cy * ny:
            nx, ny = -nx, -ny
        corners = [
            (x, y) for x in (self.view.x0, self.view.x1) for y in (self.view.y0, self.view.y1)
        ]
        clear = max(0.0, *((x - ax) * nx + (y - ay) * ny for x, y in corners))
        off = clear + 8.0
        pa = (ax + nx * off, ay + ny * off)
        pb = (bx + nx * off, by + ny * off)
        out: list[Prim] = [
            Line(ax + nx, ay + ny, pa[0] + nx * 1.5, pa[1] + ny * 1.5),
            Line(bx + nx, by + ny, pb[0] + nx * 1.5, pb[1] + ny * 1.5),
            Line(pa[0], pa[1], pb[0], pb[1]),
            Arrow(pa, (-ux, -uy)),
            Arrow(pb, (ux, uy)),
        ]
        ang = math.degrees(math.atan2(uy, ux))
        if ang > 90:
            ang -= 180
        elif ang <= -90:
            ang += 180
        mx, my = (pa[0] + pb[0]) / 2 + nx * 1.0, (pa[1] + pb[1]) / 2 + ny * 1.0
        attrs = {"data-dim": self.label} if self.label else {}
        out.append(Text(mx, my, self.text, angle=round(ang, 3), attrs=attrs))
        return out


@dataclass
class Leader:
    """A radius/diameter callout: arrow on the feature, sloped leader, shoulder and text."""

    anchor: Pt
    side: str  # top | bottom
    text: str
    outward: int  # +1 → shoulder points right, −1 → left
    label: str = ""

    def prims(self, level: float) -> list[Prim]:
        """Leader whose shoulder sits at y = ``level``."""
        ax, ay = self.anchor
        run = min(abs(level - ay) * 0.5, 12.0) * self.outward
        ex, ey = ax + run, level
        sx = ex + 4.0 * self.outward
        attrs = {"data-dim": self.label} if self.label else {}
        anchor = "start" if self.outward > 0 else "end"
        return [
            Arrow((ax, ay), (ax - ex, ay - ey)),
            Line(ax, ay, ex, ey),
            Line(ex, ey, sx, ey),
            Text(sx + self.outward, ey + 1.25, self.text, anchor=anchor, attrs=attrs),
        ]
