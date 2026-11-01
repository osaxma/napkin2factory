"""PNG renders for agent eyes (decision D12).

The chosen OCP wheel (``cadquery-ocp-novtk``, see D2) bundles no VTK, so the render
path is a numpy z-buffer rasterizer over the OCCT tessellation: flat shading, one
colour per part, orthographic views plus an isometric view and an optional section.
These renders exist so an agent can check that it built the right thing; they are
not marketing images.

Section view (B-0017). ``rasterize(section_z=z)`` is a true plane section:

* **Clip.** Every triangle is clipped exactly against the plane ``Z = z`` in numpy
  (:func:`clip_below`): the part below the plane survives as one or two sub-triangles
  whose cut edge lies on the plane; nothing above the plane is drawn.
* **Cap.** The cut faces are filled in image space with the classic back-face capping
  rule. With the viewer above the plane (the iso eye looks down), a ray that meets the
  plane *inside* a closed solid next hits that solid from the inside, i.e. its nearest
  surface is a back face (outward normal pointing away from the viewer). Such pixels are
  painted in the **cut shade**: the part colour darkened 35 % (``CUT_SHADE`` = 0.65 ×
  colour, flat, unlit) with 1 px 45° hatch lines every 8 px at 0.35 × colour
  (``HATCH_SHADE``, ``HATCH_PITCH``). Flat 0.65 alone is indistinguishable from a lit
  face turned away from the light (lit faces span 0.35-1.0 × colour), so the hatch, the
  drafting convention for cut material, is what makes the cap read as a cut. A wall
  reads as a hatched band between its outer and inner surfaces and a cavity reads as a
  view down into the part.

Why this route and not the alternatives: chaining intersection segments into loops and
triangulating them with holes needs vertex welding and a polygon-with-holes
triangulator, both fragile on OCCT tessellations whose vertices are duplicated per face;
an OCCT half-space boolean per part is exact but needs the build123d shapes at render
time, costs a boolean plus a re-tessellation per placed instance, and can fail. Back-face
capping is exact at pixel resolution, needs only the outward winding OCCT already gives
(build123d's ``tessellate`` honours reversed faces), and costs one dot product per
triangle. Mesh winding is normalised per mesh from the signed volume (so a mirrored
placement still caps correctly); a mesh that is not closed (signed volume ~ 0) is drawn
clipped but uncapped, and the fact is appended to ``Scene.notes``. Caps are drawn only
when the view looks down onto the plane (the eye direction has a positive Z component);
otherwise the section is clipped and uncapped.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

Float = NDArray[np.float64]

#: Named view directions: (eye direction, up vector), in model coordinates (Z up).
VIEWS: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "front": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    "top": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    "right": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "iso": ((1.0, -1.0, 0.8), (0.0, 0.0, 1.0)),
}

#: Cut faces are drawn flat (unlit) in the part colour times this factor (35 % darker) ...
CUT_SHADE = 0.65
#: ... with 1 px 45° hatch lines every ``HATCH_PITCH`` px in the part colour times this.
HATCH_SHADE = 0.35
HATCH_PITCH = 8


@dataclass
class Mesh:
    """A triangle mesh with a flat colour, in model coordinates."""

    vertices: Float
    triangles: NDArray[np.int64]
    color: tuple[float, float, float]
    label: str = ""


@dataclass
class Scene:
    """A list of meshes to rasterize together.

    ``notes`` collects render-time remarks (e.g. a mesh that could not be capped in a
    section) for the caller to log; :func:`rasterize` appends to it. ``uncapped`` lists the
    labels of the meshes behind those notes, so a caller can name the part in its own words
    (B-0019).
    """

    meshes: list[Mesh] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    uncapped: list[str] = field(default_factory=list)

    def bounds(self) -> tuple[Float, Float]:
        """Return (min, max) corners over all meshes."""
        if not self.meshes:
            return np.zeros(3), np.ones(3)
        allv = np.vstack([m.vertices for m in self.meshes])
        return allv.min(axis=0), allv.max(axis=0)


def color_for(label: str) -> tuple[float, float, float]:
    """Stable, reasonably distinct colour for a part id (hash-derived hue)."""
    h = int(hashlib.sha256(label.encode()).hexdigest()[:8], 16)
    hue = (h % 360) / 360.0
    sat, val = 0.55, 0.85
    i = int(hue * 6)
    f = hue * 6 - i
    p, q, t = val * (1 - sat), val * (1 - f * sat), val * (1 - (1 - f) * sat)
    rgb = [(val, t, p), (q, val, p), (p, val, t), (p, q, val), (t, p, val), (val, p, q)][i % 6]
    return rgb


def _basis(eye: Iterable[float], up: Iterable[float]) -> tuple[Float, Float, Float]:
    e = np.asarray(list(eye), dtype=float)
    e /= np.linalg.norm(e)
    u = np.asarray(list(up), dtype=float)
    right = np.cross(u, e)
    if np.linalg.norm(right) < 1e-9:
        right = np.cross((1.0, 0.0, 0.0), e)
    right /= np.linalg.norm(right)
    true_up = np.cross(e, right)
    return right, true_up, e


def clip_below(
    vertices: Float, triangles: NDArray[np.int64], z: float
) -> tuple[Float, NDArray[np.int64]]:
    """Clip a triangle mesh to the half-space ``Z <= z``, keeping winding.

    Triangles wholly at or below the plane are kept unchanged, triangles wholly above
    are dropped, and triangles crossing the plane are split at the plane into the one
    or two sub-triangles below it. New vertices lie exactly on ``Z = z``.

    Returns:
        (vertices, triangles): the original vertices followed by the new plane vertices,
        and the clipped triangle list.
    """
    v = np.asarray(vertices, dtype=np.float64)
    t = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    if t.size == 0:
        return v, t
    above = v[:, 2] > z
    n_above = above[t].sum(axis=1)
    keep = t[n_above == 0]
    one = t[n_above == 1]
    two = t[n_above == 2]
    new_v: list[Float] = [v]
    new_t: list[NDArray[np.int64]] = [keep]
    offset = len(v)

    def cut(a: NDArray[np.int64], b: NDArray[np.int64]) -> Float:
        pa, pb = v[a], v[b]
        da, db = pa[:, 2] - z, pb[:, 2] - z
        s_ = (da / (da - db))[:, None]
        p = pa + s_ * (pb - pa)
        p[:, 2] = z
        return p

    if len(one):
        # A above; B, C below -> quad (P_AB, B, C, P_AC) as two triangles
        r = _roll_odd_first(one, above)
        a, b, c = r[:, 0], r[:, 1], r[:, 2]
        pab, pac = cut(a, b), cut(a, c)
        m = len(r)
        i_ab = offset + np.arange(m)
        i_ac = offset + m + np.arange(m)
        new_v += [pab, pac]
        offset += 2 * m
        new_t += [np.stack([i_ab, b, c], axis=1), np.stack([i_ab, c, i_ac], axis=1)]
    if len(two):
        # A below; B, C above -> triangle (A, P_AB, P_AC)
        r = _roll_odd_first(two, ~above)
        a, b, c = r[:, 0], r[:, 1], r[:, 2]
        pab, pac = cut(a, b), cut(a, c)
        m = len(r)
        i_ab = offset + np.arange(m)
        i_ac = offset + m + np.arange(m)
        new_v += [pab, pac]
        offset += 2 * m
        new_t.append(np.stack([a, i_ab, i_ac], axis=1))
    return np.vstack(new_v), np.vstack(new_t).astype(np.int64)


def _roll_odd_first(tris: NDArray[np.int64], flag: NDArray[np.bool_]) -> NDArray[np.int64]:
    """Rotate each row so the single vertex with ``flag`` set comes first."""
    k = np.argmax(flag[tris], axis=1)
    idx = (k[:, None] + np.arange(3)[None, :]) % 3
    return np.take_along_axis(tris, idx, axis=1)


def signed_volume(vertices: Float, triangles: NDArray[np.int64]) -> float:
    """Signed volume of a triangle mesh (positive when the winding faces outward)."""
    p = np.asarray(vertices, dtype=np.float64)[np.asarray(triangles, dtype=np.int64)]
    if p.size == 0:
        return 0.0
    return float(np.einsum("ij,ij->i", p[:, 0], np.cross(p[:, 1], p[:, 2])).sum() / 6.0)


@dataclass(frozen=True)
class _Framing:
    """Orthographic camera fitted to a scene: basis, centre, 2D midpoint and scale."""

    right: Float
    up: Float
    fwd: Float
    center: Float
    mid2d: Float
    scale: float
    size: tuple[int, int]

    def to_pixels(self, points: Float) -> Float:
        """Pixel (x, y) of model-space points (x right, y down)."""
        v = np.asarray(points, dtype=np.float64).reshape(-1, 3) - self.center
        px = (np.stack([v @ self.right, v @ self.up], axis=1) - self.mid2d) * self.scale
        w, h = self.size
        px[:, 0] += w / 2
        px[:, 1] = h / 2 - px[:, 1]
        return px


def _framing(scene: Scene, view: str, size: tuple[int, int]) -> _Framing:
    eye, up = VIEWS[view]
    right, true_up, fwd = _basis(eye, up)
    lo, hi = scene.bounds()
    center = (lo + hi) / 2
    # Project all vertices to find extents, then scale to fit with a margin; the section
    # view uses the unclipped extents so it frames exactly like the iso view.
    pts = (
        np.vstack([m.vertices - center for m in scene.meshes]) if scene.meshes else np.zeros((1, 3))
    )
    xy = np.stack([pts @ right, pts @ true_up], axis=1)
    span = max(float((xy.max(axis=0) - xy.min(axis=0)).max()), 1e-9)
    w, h = size
    scale = 0.86 * min(w, h) / span
    mid2d = (xy.max(axis=0) + xy.min(axis=0)) / 2
    return _Framing(right, true_up, fwd, center, mid2d, scale, size)


def project(
    scene: Scene, points: Float, view: str = "iso", size: tuple[int, int] = (800, 600)
) -> Float:
    """Pixel (x, y) where :func:`rasterize` draws the given model points (same framing)."""
    return _framing(scene, view, size).to_pixels(points)


def rasterize(
    scene: Scene,
    view: str = "iso",
    size: tuple[int, int] = (800, 600),
    section_z: float | None = None,
    background: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> NDArray[np.uint8]:
    """Rasterize a scene into an RGB uint8 image using an orthographic z-buffer.

    Args:
        scene: meshes to draw.
        view: a key of :data:`VIEWS`.
        size: (width, height) in pixels.
        section_z: if given, a true plane section at ``Z = section_z``: triangles are
            clipped at the plane, nothing above it is drawn, and the cut faces of closed
            meshes are capped in the cut shade (part colour × :data:`CUT_SHADE`) when the
            view looks down onto the plane. Framing is the same as the unsectioned view.
        background: RGB floats in 0..1.
    """
    w, h = size
    img = np.empty((h, w, 3), dtype=np.float64)
    img[:] = background
    if not scene.meshes:
        return (img * 255).astype(np.uint8)
    zbuf = np.full((h, w), -np.inf)
    fr = _framing(scene, view, size)
    fwd, center = fr.fwd, fr.center
    lo, hi = scene.bounds()
    cap = section_z is not None and float(fwd[2]) > 1e-9
    capbuf = np.zeros((h, w), dtype=bool) if cap else None
    # back faces lose ties against front faces at silhouettes
    bias = 1e-6 * float(np.linalg.norm(hi - lo))
    light = np.asarray([0.4, -0.6, 0.7])
    light /= np.linalg.norm(light)
    for m in scene.meshes:
        verts, tris = m.vertices, np.asarray(m.triangles, dtype=np.int64).reshape(-1, 3)
        capped = False
        if section_z is not None:
            if cap:
                vol = signed_volume(verts, tris)
                ext = np.ptp(verts, axis=0) if len(verts) else np.zeros(3)
                if abs(vol) > 1e-6 * float(np.prod(np.maximum(ext, 1e-9))):
                    capped = True
                    if vol < 0:
                        tris = tris[:, ::-1]
                else:
                    note = f"{m.label or 'mesh'}: not a closed solid; section drawn without caps"
                    if note not in scene.notes:
                        scene.notes.append(note)
                        scene.uncapped.append(m.label or "mesh")
            verts, tris = clip_below(verts, tris, section_z)
        if len(tris) == 0:
            continue
        v = verts - center
        px = fr.to_pixels(verts)
        depth = v @ fwd
        p = v[tris]
        nrm = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
        length = np.linalg.norm(nrm, axis=1)
        unit = nrm / np.where(length > 1e-12, length, 1.0)[:, None]
        unit[length <= 1e-12] = (0.0, 0.0, 1.0)
        shades = 0.35 + 0.65 * np.abs(unit @ light)
        back = (unit @ fwd < 0.0) if capped else np.zeros(len(tris), dtype=bool)
        base = np.asarray(m.color)
        cut_color = base * CUT_SHADE
        for tri, shade, is_back in zip(tris, shades, back, strict=True):
            a, b, c = px[tri[0]], px[tri[1]], px[tri[2]]
            da, db, dc = depth[tri[0]], depth[tri[1]], depth[tri[2]]
            if is_back:
                _fill_triangle(
                    img, zbuf, a, b, c, da - bias, db - bias, dc - bias, cut_color, capbuf, True
                )
            else:
                _fill_triangle(img, zbuf, a, b, c, da, db, dc, base * shade, capbuf, False)
    if capbuf is not None and capbuf.any():
        # 45° section hatching over the cut faces (drafting convention)
        yy, xx = np.mgrid[0:h, 0:w]
        lines = capbuf & ((xx + yy) % HATCH_PITCH == 0)
        img[lines] *= HATCH_SHADE / CUT_SHADE
    return np.clip(img * 255, 0, 255).astype(np.uint8)


def _fill_triangle(
    img: Float,
    zbuf: Float,
    a: Float,
    b: Float,
    c: Float,
    da: float,
    db: float,
    dc: float,
    color: Float,
    capbuf: NDArray[np.bool_] | None = None,
    is_cap: bool = False,
) -> None:
    h, w = zbuf.shape
    xmin = max(int(np.floor(min(a[0], b[0], c[0]))), 0)
    xmax = min(int(np.ceil(max(a[0], b[0], c[0]))), w - 1)
    ymin = max(int(np.floor(min(a[1], b[1], c[1]))), 0)
    ymax = min(int(np.ceil(max(a[1], b[1], c[1]))), h - 1)
    if xmin > xmax or ymin > ymax:
        return
    det = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
    if abs(det) < 1e-12:
        return
    xs, ys = np.meshgrid(np.arange(xmin, xmax + 1) + 0.5, np.arange(ymin, ymax + 1) + 0.5)
    l1 = ((b[0] - xs) * (c[1] - ys) - (c[0] - xs) * (b[1] - ys)) / det
    l2 = ((c[0] - xs) * (a[1] - ys) - (a[0] - xs) * (c[1] - ys)) / det
    l3 = 1.0 - l1 - l2
    inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
    if not inside.any():
        return
    z = l1 * da + l2 * db + l3 * dc
    region = zbuf[ymin : ymax + 1, xmin : xmax + 1]
    update = inside & (z > region)
    region[update] = z[update]
    img[ymin : ymax + 1, xmin : xmax + 1][update] = color
    if capbuf is not None:
        capbuf[ymin : ymax + 1, xmin : xmax + 1][update] = is_cap


def write_png(path: Path | str, image: NDArray[np.uint8]) -> Path:
    """Write an RGB uint8 array as PNG using only zlib (no imaging dependency)."""
    import struct
    import zlib

    h, w, _ = image.shape
    raw = b"".join(b"\x00" + image[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(png)
    return out


def image_variance(image: NDArray[np.uint8]) -> float:
    """Pixel variance, used by tests to assert a render is not blank."""
    return float(np.var(image.astype(np.float64)))
