"""Part-level exporters: STEP, GLB (D13), props JSON, features JSON, renders (D12)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from napkin2factory.geometry.features import PartResult, to_json
from napkin2factory.geometry.glb import GlbInstance, GlbMesh, write_glb
from napkin2factory.geometry.materials import density_kg_m3
from napkin2factory.geometry.render import Mesh, Scene, color_for, rasterize, write_png

#: Fixed deflection for the reproducibility hash (D14) and the embedded GLBs.
TESS_TOLERANCE = 0.1
TESS_ANGULAR = 0.3
#: Render-time remarks (``Scene.notes``) land in this file next to the PNGs (B-0019).
RENDER_NOTES = "notes.json"


def tessellate(
    shape: Any, tolerance: float = TESS_TOLERANCE
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Triangulate a build123d shape into (vertices[n,3], triangles[m,3])."""
    verts, tris = shape.tessellate(tolerance, TESS_ANGULAR)
    v = np.asarray([(p.X, p.Y, p.Z) for p in verts], dtype=np.float64).reshape(-1, 3)
    t = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
    return v, t


def tessellation_hash(vertices: NDArray[np.float64], triangles: NDArray[np.int64]) -> str:
    """sha256 over the rounded tessellation (geometric reproducibility key, D14)."""
    h = hashlib.sha256()
    h.update(np.round(vertices, 3).astype(np.float64).tobytes())
    h.update(triangles.astype(np.int64).tobytes())
    return "sha256:" + h.hexdigest()


def compute_props(
    shape: Any,
    material: Any = None,
    declared_mass: Any = None,
    tess: tuple[NDArray[np.float64], NDArray[np.int64]] | None = None,
) -> dict[str, Any]:
    """Geometric properties: bbox, volume, area, mass, centroid, counts, tessellation hash."""
    bb = shape.bounding_box()
    volume_mm3 = float(shape.volume)
    rho, rho_src = density_kg_m3(material)
    mass_kg = volume_mm3 * 1e-9 * rho
    mass_src = f"volume × density ({rho:g} kg/m³: {rho_src})"
    if declared_mass is not None:
        mass_kg = float(declared_mass.to("kg").magnitude)
        mass_src = "declared on the part"
    c = shape.center()
    v, t = tess if tess is not None else tessellate(shape)
    return {
        "bbox": {
            "x": round(bb.size.X, 4),
            "y": round(bb.size.Y, 4),
            "z": round(bb.size.Z, 4),
            "min": [round(bb.min.X, 4), round(bb.min.Y, 4), round(bb.min.Z, 4)],
            "max": [round(bb.max.X, 4), round(bb.max.Y, 4), round(bb.max.Z, 4)],
        },
        "volume": round(volume_mm3, 3),
        "area": round(float(shape.area), 3),
        "mass": round(mass_kg, 6),
        "mass_source": mass_src,
        "density": rho,
        "centroid": {"x": round(c.X, 4), "y": round(c.Y, 4), "z": round(c.Z, 4)},
        "face_count": len(shape.faces()),
        "edge_count": len(shape.edges()),
        "solid_count": len(shape.solids()),
        "tess_hash": tessellation_hash(v, t),
        "units": {"length": "mm", "volume": "mm**3", "area": "mm**2", "mass": "kg"},
    }


def export_step(shape: Any, path: Path) -> Path:
    """Write STEP."""
    from build123d import export_step as _export_step

    path.parent.mkdir(parents=True, exist_ok=True)
    _export_step(shape, str(path))
    return path


def export_part_glb(
    uri: str, vertices: NDArray[np.float64], triangles: NDArray[np.int64], path: Path
) -> Path:
    """Write a single-part GLB: one mesh, one material, one instance node, all named ``uri``."""
    mesh = GlbMesh(
        uri=uri,
        vertices=vertices.astype(np.float32),
        triangles=triangles.astype(np.uint32),
        color=color_for(uri),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(write_glb([mesh], [GlbInstance(f"{uri}#1", uri)]))
    return path


def write_json(path: Path, data: Any) -> Path:
    """Write pretty JSON with stable key order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_json(data), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def render_views(
    scene: Scene,
    out_dir: Path,
    size: tuple[int, int] = (800, 600),
    section_z: float | None = None,
) -> dict[str, Path]:
    """Front, top, right, iso and (optionally) a section render (D12).

    What the rasterizer had to remark (``scene.notes``, e.g. an open mesh drawn clipped but
    not capped in the section) is written to ``notes.json`` beside the PNGs, only when there
    is something to say (B-0019); :func:`read_render_notes` reads it back. The returned map
    holds the images only.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for view in ("front", "top", "right", "iso"):
        paths[view] = write_png(out_dir / f"{view}.png", rasterize(scene, view, size))
    if section_z is not None:
        paths["section"] = write_png(
            out_dir / "section.png", rasterize(scene, "iso", size, section_z=section_z)
        )
    notes_path = out_dir / RENDER_NOTES
    if scene.notes:
        write_json(notes_path, {"notes": list(scene.notes), "uncapped": list(scene.uncapped)})
    elif notes_path.exists():
        notes_path.unlink()
    return paths


def read_render_notes(renders_dir: Path) -> dict[str, list[str]]:
    """``notes.json`` of a renders folder: ``{"notes": [...], "uncapped": [...]}``, or empty."""
    path = renders_dir / RENDER_NOTES
    if not path.is_file():
        return {"notes": [], "uncapped": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "notes": [str(n) for n in data.get("notes", [])],
        "uncapped": [str(u) for u in data.get("uncapped", [])],
    }


def scene_for_part(uri: str, vertices: NDArray[np.float64], triangles: NDArray[np.int64]) -> Scene:
    """A one-mesh scene coloured by the part's stable colour."""
    return Scene([Mesh(vertices, triangles, color_for(uri), uri)])


def export_part(
    uri: str,
    result: PartResult,
    out_dir: Path,
    material: Any = None,
    declared_mass: Any = None,
    render: bool = True,
) -> dict[str, Any]:
    """Write every part artifact into ``out_dir`` and return the props."""
    out_dir.mkdir(parents=True, exist_ok=True)
    v, t = tessellate(result.shape)
    props = compute_props(result.shape, material, declared_mass, (v, t))
    props.update({k: v_ for k, v_ in result.props.items() if k not in props})
    props["uri"] = uri
    export_step(result.shape, out_dir / "model.step")
    export_part_glb(uri, v, t, out_dir / "model.glb")
    np.savez_compressed(out_dir / "mesh.npz", vertices=v, triangles=t)
    write_json(out_dir / "props.json", props)
    feats = to_json(result.features)
    feats["dims"] = to_json(result.dims)
    feats["cut_list"] = to_json(result.cut_list)
    feats["notes"] = list(result.notes)
    write_json(out_dir / "features.json", feats)
    if result.flat_pattern is not None:
        write_json(out_dir / "flat_pattern.json", result.flat_pattern)
    if render:
        mid_z = (props["bbox"]["min"][2] + props["bbox"]["max"][2]) / 2
        render_views(scene_for_part(uri, v, t), out_dir / "renders", section_z=mid_z)
    return props
