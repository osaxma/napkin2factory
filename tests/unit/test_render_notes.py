"""B-0019: render-time remarks (``Scene.notes``) reach the build output instead of being dropped."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from typer.testing import CliRunner

from napkin2factory.cli.app import app
from napkin2factory.core.loader import load_product
from napkin2factory.geometry.exporters import (
    RENDER_NOTES,
    export_part,
    read_render_notes,
    render_views,
)
from napkin2factory.geometry.features import Features, PartResult
from napkin2factory.geometry.render import Mesh, Scene

SIZE = (80, 60)


def _open_sheet() -> PartResult:
    """A lone upright face: a mesh with no inside, so a section cannot cap it."""
    from build123d import Face, Plane

    return PartResult(shape=Plane.XZ * Face.make_rect(40, 60), features=Features(process="none"))


def _cube() -> tuple[np.ndarray, np.ndarray]:
    v = np.array([[x, y, z] for z in (0.0, 1.0) for y in (0.0, 1.0) for x in (0.0, 1.0)])
    t = np.array(
        [
            [0, 2, 1], [1, 2, 3], [4, 5, 6], [5, 7, 6], [0, 1, 4], [1, 5, 4],
            [2, 6, 3], [3, 6, 7], [0, 4, 2], [2, 4, 6], [1, 3, 5], [3, 7, 5],
        ]
    )  # fmt: skip
    return v, t


def test_open_mesh_in_a_section_writes_notes_next_to_the_renders(tmp_path: Path) -> None:
    props = export_part("part://sheet", _open_sheet(), tmp_path / "sheet")
    renders = tmp_path / "sheet" / "renders"
    assert (renders / "section.png").is_file()
    notes = read_render_notes(renders)
    assert notes["uncapped"] == ["part://sheet"]
    assert notes["notes"] and "not a closed solid" in notes["notes"][0]
    assert json.loads((renders / RENDER_NOTES).read_text())["uncapped"] == ["part://sheet"]
    assert "render_notes" not in props  # props (and the part's output hash) stay as they were


def test_closed_mesh_leaves_no_notes_and_clears_stale_ones(tmp_path: Path) -> None:
    v, t = _cube()
    stale = tmp_path / RENDER_NOTES
    stale.write_text('{"notes": ["old"], "uncapped": ["x"]}')
    render_views(Scene([Mesh(v, t, (0.5, 0.5, 0.5), "part://cube")]), tmp_path, SIZE, 0.5)
    assert not stale.exists()
    assert read_render_notes(tmp_path) == {"notes": [], "uncapped": []}


def test_no_section_no_note(tmp_path: Path) -> None:
    v = np.array([[-1.0, 0.0, -1.0], [1.0, 0.0, -1.0], [0.0, 0.0, 1.0]])
    scene = Scene([Mesh(v, np.array([[0, 1, 2]]), (0.5, 0.5, 0.5), "part://sheet")])
    render_views(scene, tmp_path, SIZE)
    assert scene.notes == [] and not (tmp_path / RENDER_NOTES).exists()


def test_build_summary_names_the_part_in_plain_words(
    bracket: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end: an open part goes through ``n2f build`` and the note comes out."""
    from napkin2factory.geometry import kit

    monkeypatch.setattr(kit, "run", lambda name, args, ctx: _open_sheet())
    result = CliRunner().invoke(app, ["build", "--target", "geometry", "-C", str(bracket)])
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    name = load_product(bracket).parts["l-bracket"].name
    assert f"Cut-away picture of {name}: its 3D surface has a gap" in out
    assert "part://" not in out.split("note", 1)[1]  # owner words: no identifiers
    notes = read_render_notes(bracket / "build" / "parts" / "l-bracket" / "renders")
    assert notes["uncapped"] == ["part://l-bracket"]

    as_json = CliRunner().invoke(
        app, ["build", "--target", "geometry", "--json", "-C", str(bracket)]
    )
    assert as_json.exit_code == 0, as_json.output
    data: dict[str, Any] = json.loads(as_json.output)
    assert data["render_notes"]["part://l-bracket"]["uncapped"] == ["part://l-bracket"]


def test_note_lines_for_an_assembly_and_an_unknown_remark(bracket: Path) -> None:
    from napkin2factory.geometry.build import render_note_lines

    product = load_product(bracket)
    asm_id = next(iter(product.assemblies))
    lines = render_note_lines(
        product,
        {
            f"asm://{asm_id}": {"notes": ["n"], "uncapped": ["part://l-bracket#1"]},
            "part://l-bracket": {"notes": ["something new"], "uncapped": []},
        },
    )
    asm_name = product.assemblies[asm_id].name
    part_name = product.parts["l-bracket"].name
    assert lines[0].startswith(f"Cut-away picture of {asm_name}: {part_name} has a gap in its")
    assert lines[1] == f"Pictures of {part_name}: the renderer left a remark in renders/notes.json."
