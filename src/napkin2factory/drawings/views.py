"""Hidden-line projection of a part into the drawing views (D11).

View convention (shared with :data:`napkin2factory.geometry.render.VIEWS`): every view is an
orthographic projection along the direction from the eye towards the part centre.

========  ================  ==========  =========================================
view      eye direction     up          page axes (u → right, v → up)
========  ================  ==========  =========================================
front     (0, −1, 0)        +Z          u = +X, v = +Z (looking along +Y)
top       (0, 0, +1)        +Y          u = +X, v = +Y (looking down −Z)
right     (+1, 0, 0)        +Z          u = +Y, v = +Z (looking along −X)
iso       (1, −1, 0.8)      +Z          axonometric, hidden lines omitted
========  ================  ==========  =========================================

Third-angle arrangement on the sheet: top above front, right to the right of front.
2D coordinates are model millimetres relative to the part's bounding-box centre.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from napkin2factory.geometry.render import VIEWS

Vec3 = tuple[float, float, float]
Pt = tuple[float, float]
Polyline = list[Pt]

ORTHO_VIEWS: tuple[str, ...] = ("front", "top", "right")
ALL_VIEWS: tuple[str, ...] = ("front", "top", "right", "iso")


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _unit(a: Vec3) -> Vec3:
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def view_basis(view: str) -> tuple[Vec3, Vec3, Vec3]:
    """Return ``(x_dir, y_dir, eye_dir)`` of a view, matching OCCT's ``gp_Ax2`` convention.

    Args:
        view: a key of :data:`napkin2factory.geometry.render.VIEWS`.

    Returns:
        Unit vectors: page-right, page-up and the direction towards the eye.
    """
    eye, up = VIEWS[view]
    n = _unit(eye)
    x = _unit(_cross(up, n))
    y = _cross(n, x)
    return x, y, n


@dataclass
class View2D:
    """One projected view: polylines in model mm about the part centre, plus extents."""

    name: str
    center: Vec3
    x_dir: Vec3
    y_dir: Vec3
    visible: list[Polyline] = field(default_factory=list)
    hidden: list[Polyline] = field(default_factory=list)
    umin: float = 0.0
    umax: float = 0.0
    vmin: float = 0.0
    vmax: float = 0.0

    def project(self, p: Vec3) -> Pt:
        """Project a model-space point into this view's (u, v)."""
        d = _sub(p, self.center)
        return (_dot(d, self.x_dir), _dot(d, self.y_dir))

    @property
    def width(self) -> float:
        """Extent along u, model mm."""
        return self.umax - self.umin

    @property
    def height(self) -> float:
        """Extent along v, model mm."""
        return self.vmax - self.vmin


def _edge_points(edge: Any, tol: float) -> Polyline:
    """Sample one projected edge as a polyline (lines exactly, curves by chord count)."""
    from build123d import GeomType

    if edge.geom_type == GeomType.LINE:
        a, b = edge.position_at(0.0), edge.position_at(1.0)
        return [(a.X, a.Y), (b.X, b.Y)]
    n = max(8, min(96, math.ceil(edge.length / tol)))
    pts = edge.positions([i / n for i in range(n + 1)])
    return [(p.X, p.Y) for p in pts]


def _rounded(polys: list[Polyline]) -> list[Polyline]:
    """Round to 1 µm and sort so the drawing does not depend on OCCT edge order."""
    out = [[(round(x, 3) + 0.0, round(y, 3) + 0.0) for x, y in p] for p in polys if len(p) > 1]
    return sorted(out)


def project_shape(shape: Any, view: str, center: Vec3, tol: float = 0.5) -> View2D:
    """Hidden-line-remove ``shape`` for ``view`` about ``center``.

    Args:
        shape: a build123d shape.
        view: ``front``, ``top``, ``right`` or ``iso``.
        center: the model point that maps to (0, 0) in the view (the bbox centre).
        tol: approximate chord length in model mm for sampling curved edges.

    Returns:
        The projected view; for ``iso`` hidden lines are dropped (pictorial view).
    """
    from build123d import Vector

    x_dir, y_dir, n = view_basis(view)
    c = Vector(*center)
    eye = c + Vector(*n) * 10_000.0
    _eye_dir, up = VIEWS[view]
    visible, hidden = shape.project_to_viewport(eye, viewport_up=up, look_at=c)
    v2 = View2D(name=view, center=center, x_dir=x_dir, y_dir=y_dir)
    v2.visible = _rounded([_edge_points(e, tol) for e in visible])
    v2.hidden = [] if view == "iso" else _rounded([_edge_points(e, tol) for e in hidden])
    pts = [p for poly in v2.visible + v2.hidden for p in poly]
    if not pts:
        raise ValueError(f"{view} view produced no edges")
    v2.umin = min(p[0] for p in pts)
    v2.umax = max(p[0] for p in pts)
    v2.vmin = min(p[1] for p in pts)
    v2.vmax = max(p[1] for p in pts)
    return v2


def ortho_extents(view: View2D, bbox_min: Vec3, bbox_max: Vec3) -> None:
    """Widen an orthographic view's extents to the projected bounding box (exact props)."""
    corners = [
        (x, y, z)
        for x in (bbox_min[0], bbox_max[0])
        for y in (bbox_min[1], bbox_max[1])
        for z in (bbox_min[2], bbox_max[2])
    ]
    uv = [view.project(c) for c in corners]
    view.umin = min(view.umin, *(p[0] for p in uv))
    view.umax = max(view.umax, *(p[0] for p in uv))
    view.vmin = min(view.vmin, *(p[1] for p in uv))
    view.vmax = max(view.vmax, *(p[1] for p in uv))


def hole_view(axis: Vec3) -> str | None:
    """The orthographic view in which a hole with ``axis`` appears as a circle."""
    ax = [abs(a) for a in axis]
    if max(ax) < 0.999:
        return None
    i = ax.index(max(ax))
    return ("right", "front", "top")[i]
