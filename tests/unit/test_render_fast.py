"""Tests for vectorised chunk-based rasterizer against reference per-triangle fill."""

from __future__ import annotations

import time

import numpy as np
import pytest
from numpy.typing import NDArray

from napkin2factory.geometry import render
from napkin2factory.geometry.render import (
    CUT_SHADE,
    HATCH_PITCH,
    HATCH_SHADE,
    VIEWS,
    Float,
    Mesh,
    Scene,
    _framing,
    clip_below,
    rasterize,
    signed_volume,
)


# Reference implementation copied from the pre-M7 per-triangle rasterizer.
def _fill_triangle_reference(
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
    """Old per-triangle fill used as bit-exact oracle for testing."""
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


def _rasterize_reference(
    scene: Scene,
    view: str = "iso",
    size: tuple[int, int] = (800, 600),
    section_z: float | None = None,
    background: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> NDArray[np.uint8]:
    """Reference rasterizer calling _fill_triangle_reference."""
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
                _fill_triangle_reference(
                    img, zbuf, a, b, c, da - bias, db - bias, dc - bias, cut_color, capbuf, True
                )
            else:
                _fill_triangle_reference(
                    img, zbuf, a, b, c, da, db, dc, base * shade, capbuf, False
                )
    if capbuf is not None and capbuf.any():
        yy, xx = np.mgrid[0:h, 0:w]
        lines = capbuf & ((xx + yy) % HATCH_PITCH == 0)
        img[lines] *= HATCH_SHADE / CUT_SHADE
    return np.clip(img * 255, 0, 255).astype(np.uint8)


def _unit_box() -> tuple[Float, NDArray[np.int64]]:
    verts = np.array(
        [[x, y, z] for z in (0.0, 1.0) for y in (0.0, 1.0) for x in (0.0, 1.0)],
        dtype=np.float64,
    )
    tris = np.array(
        [
            [0, 2, 1],
            [1, 2, 3],
            [4, 5, 6],
            [5, 7, 6],
            [0, 1, 4],
            [1, 5, 4],
            [2, 6, 3],
            [3, 6, 7],
            [0, 4, 2],
            [2, 4, 6],
            [1, 3, 5],
            [3, 7, 5],
        ],
        dtype=np.int64,
    )
    return verts, tris


def _sphere_mesh(n_lat: int = 16, n_lon: int = 16) -> tuple[Float, NDArray[np.int64]]:
    verts_list = []
    for i in range(n_lat + 1):
        theta = np.pi * i / n_lat
        for j in range(n_lon):
            phi = 2 * np.pi * j / n_lon
            verts_list.append(
                [np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)]
            )
    verts = np.array(verts_list, dtype=np.float64)
    tris_list = []
    for i in range(n_lat):
        for j in range(n_lon):
            p1 = i * n_lon + j
            p2 = p1 + 1 if (j + 1) < n_lon else i * n_lon
            p3 = (i + 1) * n_lon + j
            p4 = p3 + 1 if (j + 1) < n_lon else (i + 1) * n_lon
            tris_list.append([p1, p3, p2])
            tris_list.append([p2, p3, p4])
    return verts, np.array(tris_list, dtype=np.int64)


def _create_icosphere(subdivisions: int = 5) -> tuple[Float, NDArray[np.int64]]:
    phi = (1.0 + np.sqrt(5.0)) / 2.0
    verts_init = [
        [-1, phi, 0],
        [1, phi, 0],
        [-1, -phi, 0],
        [1, -phi, 0],
        [0, -1, phi],
        [0, 1, phi],
        [0, -1, -phi],
        [0, 1, -phi],
        [phi, 0, -1],
        [phi, 0, 1],
        [-phi, 0, -1],
        [-phi, 0, 1],
    ]
    verts_norm = [v / np.linalg.norm(v) for v in verts_init]
    faces = [
        [0, 11, 5],
        [0, 5, 1],
        [0, 1, 7],
        [0, 7, 10],
        [0, 10, 11],
        [1, 5, 9],
        [5, 11, 4],
        [11, 10, 2],
        [10, 7, 6],
        [7, 1, 8],
        [3, 9, 4],
        [3, 4, 2],
        [3, 2, 6],
        [3, 6, 8],
        [3, 8, 9],
        [4, 9, 5],
        [2, 4, 11],
        [6, 2, 10],
        [8, 6, 7],
        [9, 8, 1],
    ]
    verts = np.array(verts_norm, dtype=np.float64)
    triangles = np.array(faces, dtype=np.int64)

    for _ in range(subdivisions):
        midpoints: dict[tuple[int, int], int] = {}
        new_faces = []
        new_verts = list(verts)

        def get_mid(p1: int, p2: int) -> int:
            key = (min(p1, p2), max(p1, p2))
            if key in midpoints:
                return midpoints[key]
            v = (verts[p1] + verts[p2]) / 2.0
            v /= np.linalg.norm(v)
            idx = len(new_verts)
            new_verts.append(v)
            midpoints[key] = idx
            return idx

        for tri in triangles:
            m01 = get_mid(int(tri[0]), int(tri[1]))
            m12 = get_mid(int(tri[1]), int(tri[2]))
            m20 = get_mid(int(tri[2]), int(tri[0]))
            new_faces.extend(
                [
                    [tri[0], m01, m20],
                    [tri[1], m12, m01],
                    [tri[2], m20, m12],
                    [m01, m12, m20],
                ]
            )
        verts = np.array(new_verts, dtype=np.float64)
        triangles = np.array(new_faces, dtype=np.int64)
    return verts, triangles


def test_unit_box_identical() -> None:
    v, t = _unit_box()
    sc_ref = Scene([Mesh(v, t, (0.8, 0.4, 0.2), "box")])
    sc_new = Scene([Mesh(v, t, (0.8, 0.4, 0.2), "box")])
    img_ref = _rasterize_reference(sc_ref, "iso", (400, 300))
    img_new = rasterize(sc_new, "iso", (400, 300))
    assert np.array_equal(img_ref, img_new)


def test_sphere_mesh_identical() -> None:
    v, t = _sphere_mesh(20, 20)
    sc_ref = Scene([Mesh(v, t, (0.2, 0.6, 0.8), "sphere")])
    sc_new = Scene([Mesh(v, t, (0.2, 0.6, 0.8), "sphere")])
    img_ref = _rasterize_reference(sc_ref, "iso", (400, 300))
    img_new = rasterize(sc_new, "iso", (400, 300))
    assert np.array_equal(img_ref, img_new)


def test_box_section_z_identical() -> None:
    v, t = _unit_box()
    sc_ref = Scene([Mesh(v, t, (0.8, 0.4, 0.2), "box")])
    sc_new = Scene([Mesh(v, t, (0.8, 0.4, 0.2), "box")])
    img_ref = _rasterize_reference(sc_ref, "iso", (400, 300), section_z=0.5)
    img_new = rasterize(sc_new, "iso", (400, 300), section_z=0.5)
    assert np.array_equal(img_ref, img_new)


def test_overlapping_coplanar_meshes_identical() -> None:
    v1 = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=np.float64)
    t1 = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    v2 = np.array([[0.2, 0.2, 0], [0.8, 0.2, 0], [0.8, 0.8, 0], [0.2, 0.8, 0]], dtype=np.float64)
    t2 = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    sc_ref = Scene([Mesh(v1, t1, (1.0, 0.0, 0.0), "m1"), Mesh(v2, t2, (0.0, 1.0, 0.0), "m2")])
    sc_new = Scene([Mesh(v1, t1, (1.0, 0.0, 0.0), "m1"), Mesh(v2, t2, (0.0, 1.0, 0.0), "m2")])
    img_ref = _rasterize_reference(sc_ref, "top", (400, 300))
    img_new = rasterize(sc_new, "top", (400, 300))
    assert np.array_equal(img_ref, img_new)


def test_degenerate_triangle_identical() -> None:
    v = np.array([[0, 0, 0], [1, 1, 0], [2, 2, 0], [0, 1, 0]], dtype=np.float64)
    t = np.array([[0, 1, 2], [0, 1, 3]], dtype=np.int64)
    sc_ref = Scene([Mesh(v, t, (0.5, 0.5, 0.5), "degen")])
    sc_new = Scene([Mesh(v, t, (0.5, 0.5, 0.5), "degen")])
    img_ref = _rasterize_reference(sc_ref, "top", (400, 300))
    img_new = rasterize(sc_new, "top", (400, 300))
    assert np.array_equal(img_ref, img_new)


def test_triangle_partly_outside_identical() -> None:
    v = np.array([[-5, -5, 0], [15, -5, 0], [5, 15, 0]], dtype=np.float64)
    t = np.array([[0, 1, 2]], dtype=np.int64)
    sc_ref = Scene([Mesh(v, t, (0.4, 0.8, 0.2), "part")])
    sc_new = Scene([Mesh(v, t, (0.4, 0.8, 0.2), "part")])
    img_ref = _rasterize_reference(sc_ref, "top", (100, 100))
    img_new = rasterize(sc_new, "top", (100, 100))
    assert np.array_equal(img_ref, img_new)


@pytest.mark.parametrize("view", list(VIEWS.keys()))
def test_all_views_identical(view: str) -> None:
    v, t = _unit_box()
    sc_ref = Scene([Mesh(v, t, (0.8, 0.4, 0.2), "box")])
    sc_new = Scene([Mesh(v, t, (0.8, 0.4, 0.2), "box")])
    img_ref = _rasterize_reference(sc_ref, view, (400, 300))
    img_new = rasterize(sc_new, view, (400, 300))
    assert np.array_equal(img_ref, img_new)


def test_large_mesh_chunks_split_identical(monkeypatch: pytest.MonkeyPatch) -> None:
    v, t = _sphere_mesh(20, 20)
    sc_ref = Scene([Mesh(v, t, (0.3, 0.6, 0.9), "sph")])
    sc_new = Scene([Mesh(v, t, (0.3, 0.6, 0.9), "sph")])
    # Lower chunk cap so it splits into many chunks
    monkeypatch.setattr(render, "CHUNK_CAP", 500)
    img_new = rasterize(sc_new, "iso", (400, 300))
    img_ref = _rasterize_reference(sc_ref, "iso", (400, 300))
    assert np.array_equal(img_ref, img_new)


def test_interleaved_large_and_tiny_triangles_with_ties() -> None:
    """A scene with a huge triangle and many tiny ones, interleaved with ties, stays identical."""
    # Create a scene where tiny triangles (area < 256) and a huge triangle (area >> 256)
    # share the exact same depth z=1.0, interleaved before and after the huge triangle.
    verts = []
    tris = []

    # 10 tiny triangles preceding the huge triangle in original order (win ties)
    for i in range(10):
        x = 10.0 + i * 5.0
        y = 10.0 + (i % 3) * 5.0
        idx = len(verts)
        verts.extend([[x, y, 1.0], [x + 2.0, y, 1.0], [x, y + 2.0, 1.0]])
        tris.append([idx, idx + 1, idx + 2])

    # 1 huge triangle overlapping the tiny triangles
    idx = len(verts)
    verts.extend([[0.0, 0.0, 1.0], [100.0, 0.0, 1.0], [50.0, 100.0, 1.0]])
    tris.append([idx, idx + 1, idx + 2])

    # 10 tiny triangles succeeding the huge triangle in original order (lose ties)
    for i in range(10):
        x = 20.0 + i * 5.0
        y = 20.0 + (i % 3) * 5.0
        idx = len(verts)
        verts.extend([[x, y, 1.0], [x + 2.0, y, 1.0], [x, y + 2.0, 1.0]])
        tris.append([idx, idx + 1, idx + 2])

    verts_arr = np.array(verts, dtype=np.float64)
    tris_arr = np.array(tris, dtype=np.int64)

    sc_ref = Scene([Mesh(verts_arr, tris_arr, (0.7, 0.3, 0.5), "interleaved")])
    sc_new = Scene([Mesh(verts_arr, tris_arr, (0.7, 0.3, 0.5), "interleaved")])

    img_ref = _rasterize_reference(sc_ref, "top", (400, 300))
    img_new = rasterize(sc_new, "top", (400, 300))
    assert np.array_equal(img_ref, img_new)


def test_speedup_on_20k_triangles() -> None:
    v, t = _create_icosphere(5)  # 20,480 triangles
    sc_ref = Scene([Mesh(v, t, (0.2, 0.7, 0.9), "sphere")])
    sc_new = Scene([Mesh(v, t, (0.2, 0.7, 0.9), "sphere")])

    t0 = time.perf_counter()
    img_ref = _rasterize_reference(sc_ref, "iso", (800, 600))
    t1 = time.perf_counter()
    ref_time = t1 - t0

    t0 = time.perf_counter()
    img_new = rasterize(sc_new, "iso", (800, 600))
    t1 = time.perf_counter()
    new_time = t1 - t0

    assert np.array_equal(img_ref, img_new)
    speedup = ref_time / new_time
    # Target at least 4x faster
    assert speedup >= 3.5, (
        f"Speedup was only {speedup:.2f}x (ref {ref_time:.3f}s, new {new_time:.3f}s)"
    )
