"""PNG renders for agent eyes (decision D12).

The chosen OCP wheel (``cadquery-ocp-novtk``, see D2) bundles no VTK, so the render
path is a numpy z-buffer rasterizer over the OCCT tessellation: flat shading, one
colour per part, orthographic views plus an isometric view and an optional section.
These renders exist so an agent can check that it built the right thing; they are
not marketing images.
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


@dataclass
class Mesh:
    """A triangle mesh with a flat colour, in model coordinates."""

    vertices: Float
    triangles: NDArray[np.int64]
    color: tuple[float, float, float]
    label: str = ""


@dataclass
class Scene:
    """A list of meshes to rasterize together."""

    meshes: list[Mesh] = field(default_factory=list)

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
        section_z: if given, triangles with all vertices above this Z are dropped,
            producing a crude section view looking down into the part.
        background: RGB floats in 0..1.
    """
    w, h = size
    eye, up = VIEWS[view]
    right, true_up, fwd = _basis(eye, up)
    lo, hi = scene.bounds()
    center = (lo + hi) / 2
    img = np.empty((h, w, 3), dtype=np.float64)
    img[:] = background
    zbuf = np.full((h, w), -np.inf)
    # Project all vertices once to find extents, then scale to fit with a margin.
    projected: list[tuple[Float, Float, NDArray[np.int64], tuple[float, float, float]]] = []
    all2d: list[Float] = []
    for m in scene.meshes:
        v = m.vertices - center
        tris = m.triangles
        if section_z is not None:
            keep = ~(m.vertices[tris][:, :, 2] > section_z).all(axis=1)
            tris = tris[keep]
        xy = np.stack([v @ right, v @ true_up], axis=1)
        depth = v @ fwd
        projected.append((xy, depth, tris, m.color))
        all2d.append(xy)
    if not all2d:
        return (img * 255).astype(np.uint8)
    pts = np.vstack(all2d)
    span = max(float((pts.max(axis=0) - pts.min(axis=0)).max()), 1e-9)
    scale = 0.86 * min(w, h) / span
    mid2d = (pts.max(axis=0) + pts.min(axis=0)) / 2
    light = np.asarray([0.4, -0.6, 0.7])
    light /= np.linalg.norm(light)
    for xy, depth, tris, color in projected:
        px = (xy - mid2d) * scale
        px[:, 0] += w / 2
        px[:, 1] = h / 2 - px[:, 1]
        base = np.asarray(color)
        for tri in tris:
            a, b, c = px[tri[0]], px[tri[1]], px[tri[2]]
            da, db, dc = depth[tri[0]], depth[tri[1]], depth[tri[2]]
            # Flat shading from the model-space normal.
            n = _normal(xy, depth, tri, right, true_up, fwd)
            shade = 0.35 + 0.65 * max(0.0, float(abs(n @ light)))
            _fill_triangle(img, zbuf, a, b, c, da, db, dc, base * shade)
    return np.clip(img * 255, 0, 255).astype(np.uint8)


def _normal(
    xy: Float, depth: Float, tri: NDArray[np.int64], right: Float, up: Float, fwd: Float
) -> Float:
    p = [xy[i][0] * right + xy[i][1] * up + depth[i] * fwd for i in tri]
    n = np.cross(p[1] - p[0], p[2] - p[0])
    norm = np.linalg.norm(n)
    return n / norm if norm > 1e-12 else np.asarray([0.0, 0.0, 1.0])


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
