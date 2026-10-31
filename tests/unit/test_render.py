"""True plane section render (B-0017): clip at the plane, cap the cut faces."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from napkin2factory.geometry.render import (
    CUT_SHADE,
    HATCH_SHADE,
    Mesh,
    Scene,
    clip_below,
    project,
    rasterize,
    signed_volume,
)

COLOR = (0.8, 0.4, 0.2)
CUT = np.round(np.asarray(COLOR) * CUT_SHADE * 255).astype(int)
HATCH = np.round(np.asarray(COLOR) * HATCH_SHADE * 255).astype(int)
SIZE = (400, 300)

# outward-wound unit cube: 8 corners, 12 triangles
_CUBE_V = np.array(
    [[x, y, z] for z in (0.0, 1.0) for y in (0.0, 1.0) for x in (0.0, 1.0)], dtype=np.float64
)
_CUBE_T = np.array(
    [
        [0, 2, 1], [1, 2, 3],  # bottom (-Z)
        [4, 5, 6], [5, 7, 6],  # top (+Z)
        [0, 1, 4], [1, 5, 4],  # -Y
        [2, 6, 3], [3, 6, 7],  # +Y
        [0, 4, 2], [2, 4, 6],  # -X
        [1, 3, 5], [3, 7, 5],  # +X
    ],
    dtype=np.int64,
)  # fmt: skip


def box(
    lo: tuple[float, float, float], hi: tuple[float, float, float], inward: bool = False
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Axis-aligned box mesh; ``inward`` flips the winding (a cavity surface)."""
    v = np.asarray(lo) + _CUBE_V * (np.asarray(hi) - np.asarray(lo))
    t = _CUBE_T[:, ::-1].copy() if inward else _CUBE_T.copy()
    return v, t


def hollow_box(
    outer: float = 100.0, wall: float = 10.0
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Closed hollow box: outer surface wound outward, inner cavity wound inward."""
    vo, to = box((0, 0, 0), (outer, outer, outer))
    vi, ti = box((wall, wall, wall), (outer - wall, outer - wall, outer - wall), inward=True)
    return np.vstack([vo, vi]), np.vstack([to, ti + len(vo)])


def _px(img: NDArray[np.uint8], xy: NDArray[np.float64]) -> NDArray[np.int64]:
    x, y = int(xy[0]), int(xy[1])
    return img[y, x].astype(np.int64)


def _is_cut(rgb: NDArray[np.int64]) -> bool:
    """Cut fill or its hatch line."""
    return bool(np.abs(rgb - CUT).max() <= 1 or np.abs(rgb - HATCH).max() <= 1)


def test_clip_below_splits_exactly_at_the_plane() -> None:
    v, t = box((0, 0, 0), (1, 1, 1))
    cv, ct = clip_below(v, t, 0.5)
    used = cv[np.unique(ct)]
    assert used[:, 2].max() <= 0.5 + 1e-12
    assert np.isclose(used[:, 2].max(), 0.5)
    # winding preserved: the clipped open box still has its sides facing outward
    assert signed_volume(v, t) > 0


def test_cube_section_has_no_top_face_and_a_cut_cap() -> None:
    v, t = box((0, 0, 0), (1, 1, 1))
    scene = Scene([Mesh(v, t, COLOR, "cube")])
    full = rasterize(scene, "iso", SIZE)
    sec = rasterize(scene, "iso", SIZE, section_z=0.5)
    # the top face colour (sampled from the unsectioned iso) must vanish
    top_centre = project(scene, np.array([[0.5, 0.5, 1.0]]), "iso", SIZE)[0]
    top_rgb = _px(full, top_centre)
    assert not np.all(sec.reshape(-1, 3) == top_rgb, axis=1).any()
    # the image centre is the cube centre, which is on the cut plane inside the solid
    centre = sec[SIZE[1] // 2, SIZE[0] // 2].astype(np.int64)
    assert _is_cut(centre), centre
    assert scene.notes == []


def test_hollow_box_section_shows_four_straight_wall_bands() -> None:
    v, t = hollow_box()
    scene = Scene([Mesh(v, t, COLOR, "hollow")])
    img = rasterize(scene, "iso", SIZE, section_z=50.0)
    # band centre lines (mid-wall) on the plane, away from the corners: all cut shade
    walls = {
        "-x": [(5.0, y, 50.0) for y in np.linspace(12, 88, 40)],
        "+x": [(95.0, y, 50.0) for y in np.linspace(12, 88, 40)],
        "-y": [(x, 5.0, 50.0) for x in np.linspace(12, 88, 40)],
        "+y": [(x, 95.0, 50.0) for x in np.linspace(12, 88, 40)],
    }
    for name, pts in walls.items():
        px = project(scene, np.asarray(pts), "iso", SIZE)
        colours = {tuple(_px(img, p)) for p in px}
        assert all(_is_cut(np.asarray(c)) for c in colours), (name, colours)
        # no sliver signature: only the cut fill and its hatch along the whole band
        assert len(colours) <= 2, (name, colours)
    # straight edges: just outside the outer edge (on the far side, where the ray misses
    # the box) is background; just inside the inner edge is the cavity, not cut
    out = project(
        scene, np.asarray([(-1.5, y, 50.0) for y in np.linspace(12, 88, 20)]), "iso", SIZE
    )
    assert all(tuple(_px(img, p)) == (255, 255, 255) for p in out)
    cav = project(
        scene, np.asarray([(x, 11.5, 50.0) for x in np.linspace(15, 85, 20)]), "iso", SIZE
    )
    assert not any(_is_cut(_px(img, p)) for p in cav)
    # the cavity reads as a view down onto the floor (an up-facing, lit face), not a cap
    full = rasterize(scene, "iso", SIZE)
    up_face = _px(full, project(scene, np.array([[50.0, 50.0, 100.0]]), "iso", SIZE)[0])
    floor = _px(img, project(scene, np.array([[20.0, 80.0, 10.0]]), "iso", SIZE)[0])
    assert np.array_equal(floor, up_face), (floor, up_face)


def test_cut_band_width_matches_the_wall() -> None:
    """Scan along the -X wall's cross-wall direction: one run of cut pixels, wall-wide."""
    v, t = hollow_box()
    scene = Scene([Mesh(v, t, COLOR, "hollow")])
    img = rasterize(scene, "iso", SIZE, section_z=50.0)
    for y in (30.0, 50.0, 70.0):
        xs = np.linspace(-3.0, 20.0, 231)
        px = project(
            scene, np.stack([xs, np.full_like(xs, y), np.full_like(xs, 50.0)], 1), "iso", SIZE
        )
        cut = np.array([_is_cut(_px(img, p)) for p in px])
        runs = np.flatnonzero(np.diff(cut.astype(int)))
        assert len(runs) == 2, runs  # exactly one band
        start, stop = xs[runs[0] + 1], xs[runs[1]]
        assert abs(start - 0.0) < 0.6 and abs(stop - 10.0) < 0.6, (start, stop)


def test_mirrored_winding_still_caps() -> None:
    v, t = box((0, 0, 0), (1, 1, 1))
    scene = Scene([Mesh(v, t[:, ::-1].copy(), COLOR, "flipped")])
    sec = rasterize(scene, "iso", SIZE, section_z=0.5)
    assert _is_cut(sec[SIZE[1] // 2, SIZE[0] // 2].astype(np.int64))


def test_open_mesh_is_clipped_uncapped_and_noted() -> None:
    v = np.array([[-1.0, 0.0, -1.0], [1.0, 0.0, -1.0], [0.0, 0.0, 1.0]])
    scene = Scene([Mesh(v, np.array([[0, 1, 2]]), COLOR, "sheet")])
    rasterize(scene, "iso", SIZE, section_z=0.0)
    assert scene.notes and "sheet" in scene.notes[0]


def test_large_triangle_is_clipped_not_dropped_or_kept_whole() -> None:
    """Regression (B-0017): the old path kept a crossing triangle whole."""
    v = np.array([[-1.0, 0.0, -1.0], [1.0, 0.0, -1.0], [0.0, 0.0, 1.0]])
    scene = Scene([Mesh(v, np.array([[0, 1, 2]]), COLOR, "tri")])
    img = rasterize(scene, "front", SIZE, section_z=0.0)
    drawn = np.flatnonzero((img != 255).any(axis=2).any(axis=1))
    plane_row = project(scene, np.array([[0.0, 0.0, 0.0]]), "front", SIZE)[0][1]
    assert drawn.size, "the part below the plane must be drawn"
    assert drawn.min() >= plane_row - 1.0, (drawn.min(), plane_row)
    # and it reaches all the way down to the triangle's base
    base_row = project(scene, np.array([[0.0, 0.0, -1.0]]), "front", SIZE)[0][1]
    assert drawn.max() >= base_row - 1.0


def test_build123d_hollow_box_caps_its_walls() -> None:
    """The OCCT tessellation winds outward (reversed faces honoured), so caps work."""
    from build123d import Box, Pos

    from napkin2factory.geometry.exporters import tessellate

    shell = Pos(50, 50, 50) * Box(100, 100, 100) - Pos(50, 50, 60) * Box(80, 80, 100)
    v, t = tessellate(shell)
    scene = Scene([Mesh(v, t, COLOR, "b3d")])
    img = rasterize(scene, "iso", SIZE, section_z=50.0)
    assert scene.notes == []
    pts = [(5.0, y, 50.0) for y in np.linspace(15, 85, 15)] + [
        (x, 95.0, 50.0) for x in np.linspace(15, 85, 15)
    ]
    px = project(scene, np.asarray(pts), "iso", SIZE)
    assert all(_is_cut(_px(img, p)) for p in px)
