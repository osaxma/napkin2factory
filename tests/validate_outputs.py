"""Artifact assertions (GRAND_PLAN §8.1): derive the expected artifact set from the model
and open every output with a real parser.

Usage: ``python tests/validate_outputs.py <product-dir> [--stage geometry|all|concepts]`` or import
:func:`validate_outputs`.  Exit code 1 and one line per problem on failure.  The checks grow
by milestone: M2 geometry, M5 drawings/DXF/BOM/docs/report, M8 kiln-specific; v0.2 M6 the
napkin stage (``build/concepts/``) whenever the product has concept cards and they were built
(``--stage concepts`` checks only those, for a copy that was not built by the factory).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

STAGES = ("geometry", "all", "concepts")


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


def validate_concepts(root: Path, problems: list[str]) -> None:
    """Concept artifacts (N1, N6, N10): per built card and the board, when they exist.

    A card counts as built when ``build/concepts/<id>/`` exists, or, once the board was
    written, when the card carries a screening (the board shows it): such a card has
    ``massing.glb`` (parseable, one node per massing call), ``props.json``,
    ``screening.json`` (the same verdict as the card) and a non-blank ``renders/iso.png``.
    The board parses, is self-contained (no external script, link or asset), stays under
    20 MB, shows every card and states each red card's reasons.
    """
    import re

    import pygltflib
    from selectolax.lexbor import LexborHTMLParser

    from napkin2factory.core import concepts as cm

    if not list((root / "concepts").glob("C-*.yaml")):
        return
    out = root / "build" / "concepts"
    board = out / "board.html"
    cards = cm.load_concepts(root)
    for cid, card in cards.items():
        d = out / cid
        if not d.is_dir() and not (board.is_file() and card.screening is not None):
            continue
        for name in ("massing.glb", "props.json", "screening.json", "renders/iso.png"):
            if not (d / name).is_file():
                problems.append(f"concept {cid}: missing build/concepts/{cid}/{name}")
        if (d / "massing.glb").is_file():
            g = pygltflib.GLTF2().load(str(d / "massing.glb"))
            uris = {(n.extras or {}).get("n2f_uri") or n.name for n in g.nodes}
            for call in card.massing:
                if f"concept://{cid}/{call.as_}" not in uris:
                    problems.append(f"concept {cid}: GLB lacks the node for {call.as_}")
        if (d / "screening.json").is_file() and card.screening is not None:
            sj = json.loads((d / "screening.json").read_text())
            if sj.get("verdict") != card.screening.verdict:
                problems.append(
                    f"concept {cid}: screening.json says {sj.get('verdict')}, "
                    f"the card says {card.screening.verdict}"
                )
        iso = d / "renders" / "iso.png"
        if iso.is_file() and not _png_nonblank(iso):
            problems.append(f"concept {cid}: renders/iso.png is blank")
    if not board.is_file():
        return
    html = board.read_text(encoding="utf-8")
    size = board.stat().st_size
    if size > 20 * 1024 * 1024:
        problems.append(f"board: {size / 1e6:.1f} MB exceeds the 20 MB budget (N10)")
    tree = LexborHTMLParser(html)
    external = re.compile(r"\b(?:src|href)\s*=\s*['\"]?(?:https?:)?//", re.IGNORECASE)
    if tree.css("script[src]") or tree.css('link:not([href^="data:"])') or external.search(html):
        problems.append("board: has external script/link/asset references (N10)")
    shown = {a.attributes.get("data-id") for a in tree.css("article.concept")}
    for cid, card in cards.items():
        if cid not in shown:
            problems.append(f"board: {cid} is not on the board")
        if card.verdict == "red":
            node = tree.css_first(f"#card-{cid} .limits.bad")
            if node is None or "this direction has problems" not in node.text():
                problems.append(f"board: red card {cid} does not show its reasons")


def validate_outputs(root: Path, stage: str = "all") -> list[str]:
    """Return a list of problems (empty means every expected artifact exists and parses)."""
    from napkin2factory.core.loader import load_product

    root = Path(root).resolve()
    problems: list[str] = []
    if stage == "concepts":
        validate_concepts(root, problems)
        return problems
    product = load_product(root)
    validate_geometry(root, product, problems)
    if stage == "all":
        try:
            from tests.validate_outputs_full import validate_full
        except ImportError:  # grows at M5
            validate_full = None
        if validate_full is not None:
            validate_full(root, product, problems)
        validate_concepts(root, problems)
    return problems


def main(argv: list[str]) -> int:
    """CLI entry."""
    if not argv:
        print("usage: validate_outputs.py <product-dir> [--stage geometry|all|concepts]")
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
