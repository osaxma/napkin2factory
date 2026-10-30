"""Artifact assertions (GRAND_PLAN §8.1): derive the expected artifact set from the model
and open every output with a real parser.

Usage: ``python tests/validate_outputs.py <product-dir> [--stage geometry|all]`` or import
:func:`validate_outputs`.  Exit code 1 and one line per problem on failure.  The checks grow
by milestone: M2 geometry, M5 drawings/DXF/BOM/docs/report, M8 kiln-specific.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

STAGES = ("geometry", "all")


def _png_nonblank(path: Path) -> bool:
    from PIL import Image

    img = np.asarray(Image.open(path).convert("L"), dtype=np.float64)
    # Enough pixels differ from the background: a 1 mm sheet seen edge-on is a thin line, not
    # a blank (the old variance test rejected the kiln's controller lid).
    background = img[0, 0]
    return int((np.abs(img - background) > 8).sum()) >= 200


def validate_geometry(root: Path, product, problems: list[str]) -> None:  # type: ignore[no-untyped-def]
    """Every part with geometry and every assembly has parseable STEP/GLB/props/features/renders."""
    import pygltflib
    from build123d import import_step

    build = root / "build"
    for part in product.parts.values():
        d = build / "parts" / part.id
        if not part.has_geometry:
            if d.exists():
                problems.append(f"{part.uri}: has no geometry but build/parts/{part.id} exists")
            continue
        for name in ("model.step", "model.glb", "props.json", "features.json"):
            if not (d / name).is_file():
                problems.append(f"{part.uri}: missing {name}")
        if not (d / "props.json").is_file():
            continue
        props = json.loads((d / "props.json").read_text())
        for key in (
            "bbox",
            "volume",
            "area",
            "mass",
            "centroid",
            "face_count",
            "tess_hash",
            "reads",
        ):
            if key not in props:
                problems.append(f"{part.uri}: props.json lacks {key}")
        if props.get("volume", 0) <= 0:
            problems.append(f"{part.uri}: non-positive volume")
        if (d / "model.step").is_file():
            shape = import_step(str(d / "model.step"))
            if abs(shape.volume - props["volume"]) > 0.005 * props["volume"] + 1e-6:
                problems.append(
                    f"{part.uri}: STEP re-import volume {shape.volume:.1f} "
                    f"!= props {props['volume']:.1f}"
                )
        if (d / "model.glb").is_file():
            g = pygltflib.GLTF2().load(str(d / "model.glb"))
            if [m.name for m in g.meshes] != [part.uri]:
                problems.append(f"{part.uri}: GLB mesh names {[m.name for m in g.meshes]}")
            if [m.name for m in g.materials] != [part.uri]:
                problems.append(f"{part.uri}: GLB material names {[m.name for m in g.materials]}")
            if not any((n.extras or {}).get("n2f_uri") == part.uri for n in g.nodes):
                problems.append(f"{part.uri}: GLB nodes lack n2f_uri extras")
        feats = (
            json.loads((d / "features.json").read_text()) if (d / "features.json").is_file() else {}
        )
        if part.process == "sheet-metal":
            if not feats.get("bends"):
                problems.append(f"{part.uri}: sheet-metal part declares no bends")
            if not (d / "flat_pattern.json").is_file():
                problems.append(f"{part.uri}: sheet-metal part has no flat_pattern.json")
        renders = d / "renders"
        for view in ("front", "top", "right", "iso", "section"):
            p = renders / f"{view}.png"
            if not p.is_file():
                problems.append(f"{part.uri}: missing render {view}.png")
            elif not _png_nonblank(p):
                problems.append(f"{part.uri}: render {view}.png is blank")
    for asm in product.assemblies.values():
        d = build / "assemblies" / asm.id
        for name in ("model.glb", "props.json", "instances.json"):
            if not (d / name).is_file():
                problems.append(f"{asm.uri}: missing {name}")
        if not (d / "props.json").is_file():
            continue
        props = json.loads((d / "props.json").read_text())
        declared = props.get("declared_counts", {})
        actual = props.get("instance_counts", {})
        if declared != actual:
            problems.append(f"{asm.uri}: instance counts {actual} != declared {declared} (D18)")
        g = pygltflib.GLTF2().load(str(d / "model.glb"))
        mesh_names = [m.name for m in g.meshes]
        if len(mesh_names) != len(set(mesh_names)):
            problems.append(f"{asm.uri}: GLB has duplicate meshes (instancing broken, D13)")
        if set(mesh_names) != set(actual):
            problems.append(f"{asm.uri}: GLB meshes {sorted(mesh_names)} != parts {sorted(actual)}")
        inst_nodes = [n for n in g.nodes if (n.extras or {}).get("n2f_kind") == "instance"]
        if len(inst_nodes) != props.get("instances"):
            problems.append(
                f"{asm.uri}: GLB instance nodes {len(inst_nodes)} != {props.get('instances')}"
            )
        for view in ("front", "top", "right", "iso", "section"):
            p = d / "renders" / f"{view}.png"
            if not p.is_file():
                problems.append(f"{asm.uri}: missing render {view}.png")
            elif not _png_nonblank(p):
                problems.append(f"{asm.uri}: render {view}.png is blank")


def validate_outputs(root: Path, stage: str = "all") -> list[str]:
    """Return a list of problems (empty means every expected artifact exists and parses)."""
    from napkin2factory.core.loader import load_product

    root = Path(root).resolve()
    product = load_product(root)
    problems: list[str] = []
    validate_geometry(root, product, problems)
    if stage == "all":
        try:
            from tests.validate_outputs_full import validate_full
        except ImportError:  # grows at M5
            validate_full = None
        if validate_full is not None:
            validate_full(root, product, problems)
    return problems


def main(argv: list[str]) -> int:
    """CLI entry."""
    if not argv:
        print("usage: validate_outputs.py <product-dir> [--stage geometry|all]")
        return 2
    stage = "all"
    if "--stage" in argv:
        stage = argv[argv.index("--stage") + 1]
    problems = validate_outputs(Path(argv[0]), stage)
    for p in problems:
        print("✗", p)
    if not problems:
        print(f"✓ artifacts complete and parseable for {argv[0]} (stage {stage})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main(sys.argv[1:]))
