"""Drawings engine (D11, M5): SVG views, dimensions, hole table, title block, flat DXF."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from lxml import etree

from tests.conftest import EXAMPLES, copy_product

SVG_NS = "{http://www.w3.org/2000/svg}"


def _build(src: Path, dst: Path) -> Path:
    from napkin2factory.core.graph.runner import run_build
    from napkin2factory.core.loader import load_product

    root = copy_product(src, dst, git=False)
    run_build(load_product(root), target="drawings", quiet=True, render=False)
    return root


@pytest.fixture(scope="module")
def enclosure(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _build(EXAMPLES / "enclosure", tmp_path_factory.mktemp("drw") / "e")


@pytest.fixture(scope="module")
def bracket(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _build(EXAMPLES / "bracket", tmp_path_factory.mktemp("drw") / "b")


@pytest.fixture
def product_root(request: pytest.FixtureRequest) -> Path:
    return request.getfixturevalue(request.param)


ALL = [("enclosure", "base"), ("enclosure", "lid"), ("bracket", "l-bracket")]
SHEET_METAL = [("enclosure", "base"), ("bracket", "l-bracket")]


def _svg(root: Path, pid: str) -> etree._Element:
    return etree.parse(str(root / "build" / "drawings" / f"{pid}.svg")).getroot()


def _group(svg: etree._Element, gid: str) -> etree._Element | None:
    found = svg.findall(f".//{SVG_NS}g[@id='{gid}']")
    assert len(found) <= 1, f"duplicate group {gid}"
    return found[0] if found else None


def _texts(el: etree._Element) -> list[str]:
    return ["".join(t.itertext()) for t in el.iter(f"{SVG_NS}text")]


def _flat_json(root: Path, pid: str) -> dict:
    return json.loads((root / "build" / "parts" / pid / "flat_pattern.json").read_text())


def _shoelace(pts: list[tuple[float, float]]) -> float:
    s = 0.0
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


@pytest.mark.parametrize(("product_root", "pid"), ALL, indirect=["product_root"])
def test_views_exist_with_paths(product_root: Path, pid: str) -> None:
    svg = _svg(product_root, pid)
    assert svg.get("viewBox") == "0 0 420 297"
    for view in ("view-front", "view-top", "view-right", "view-iso"):
        g = _group(svg, view)
        assert g is not None, view
        assert g.findall(f".//{SVG_NS}path"), f"{view} has no paths"


@pytest.mark.parametrize(("product_root", "pid"), ALL, indirect=["product_root"])
def test_third_angle_arrangement(product_root: Path, pid: str) -> None:
    svg = _svg(product_root, pid)
    box = {
        v: [float(n) for n in _group(svg, f"view-{v}").get("data-bbox").split()]  # type: ignore[union-attr]
        for v in ("front", "top", "right")
    }
    fx, fy, fw, fh = box["front"]
    tx, ty, tw, th = box["top"]
    rx, ry, rw, rh = box["right"]
    assert ty + th < fy, "top view must sit above the front view"
    assert abs(tx - fx) < 1e-6 and abs(tw - fw) < 1e-6, "top and front share x extent"
    assert rx > fx + fw, "right view must sit to the right of the front view"
    assert abs(ry - fy) < 1e-6 and abs(rh - fh) < 1e-6, "right and front share y extent"


@pytest.mark.parametrize(("product_root", "pid"), SHEET_METAL, indirect=["product_root"])
def test_sheet_metal_has_flat_view_with_bends(product_root: Path, pid: str) -> None:
    svg = _svg(product_root, pid)
    flat = _group(svg, "view-flat")
    assert flat is not None
    bends = [ln for ln in flat.iter(f"{SVG_NS}line") if ln.get("class") == "bend"]
    assert len(bends) == len(_flat_json(product_root, pid)["bend_lines"])
    assert all(ln.get("stroke-dasharray") for ln in bends)


def test_lid_cut_sheet_has_flat_view_and_dxf(enclosure: Path) -> None:
    """Every part with a flat pattern gets a DXF, cut-sheet parts included (S-034)."""
    assert _group(_svg(enclosure, "lid"), "view-flat") is not None
    assert (enclosure / "build" / "drawings" / "lid-flat.dxf").exists()
    meta = json.loads((enclosure / "build" / "drawings" / "lid.json").read_text())
    assert meta["has_flat"] is True and meta["dxf"] == "lid-flat.dxf"
    import ezdxf

    doc = ezdxf.readfile(str(enclosure / "build" / "drawings" / "lid-flat.dxf"))
    circles = [e for e in doc.modelspace() if e.dxftype() == "CIRCLE"]
    assert len(circles) == 4  # the interface holes reached the flat pattern


def test_hidden_lines_are_dashed(enclosure: Path) -> None:
    front = _group(_svg(enclosure, "base"), "view-front")
    assert front is not None
    hidden = [p for p in front.iter(f"{SVG_NS}path") if p.get("class") == "hidden"]
    visible = [p for p in front.iter(f"{SVG_NS}path") if p.get("class") == "visible"]
    assert hidden and visible
    assert all(p.get("stroke-dasharray") for p in hidden)
    assert not any(p.get("stroke-dasharray") for p in visible)


@pytest.mark.parametrize(
    ("product_root", "pid", "expected"),
    [
        ("enclosure", "lid", {"224.0", "174.0", "1.5"}),
        ("enclosure", "base", {"224.0", "174.0", "80.0", "200.0", "150.0", "12.0", "R1.5"}),
        ("bracket", "l-bracket", {"120.0", "60.0", "80.0", "4.0", "R4.0", "⌀9.0", "20.0"}),
    ],
    indirect=["product_root"],
)
def test_dimension_texts(product_root: Path, pid: str, expected: set[str]) -> None:
    dims = _group(_svg(product_root, pid), "dims")
    assert dims is not None
    assert expected <= set(_texts(dims))


@pytest.mark.parametrize(("product_root", "pid"), ALL, indirect=["product_root"])
def test_dimension_text_stays_outside_every_view(product_root: Path, pid: str) -> None:
    from napkin2factory.drawings.svg import Box, Text

    svg = _svg(product_root, pid)
    views = []
    for g in svg.iter(f"{SVG_NS}g"):
        if (g.get("id") or "").startswith("view-"):
            x, y, w, h = (float(n) for n in g.get("data-bbox").split())  # type: ignore[union-attr]
            views.append((g.get("id"), Box(x + 0.01, y + 0.01, x + w - 0.01, y + h - 0.01)))
    dims = _group(svg, "dims")
    assert dims is not None
    for t in dims.iter(f"{SVG_NS}text"):
        m = re.match(r"rotate\(([-\d.]+)", t.get("transform") or "")
        box = Text(
            float(t.get("x")),  # type: ignore[arg-type]
            float(t.get("y")),  # type: ignore[arg-type]
            t.text or "",
            size=float(t.get("font-size")),  # type: ignore[arg-type]
            anchor=t.get("text-anchor") or "middle",
            angle=float(m.group(1)) if m else 0.0,
        ).bbox()
        for vid, vb in views:
            assert not box.overlaps(vb), f"dimension {t.text!r} overlaps {vid}"


def test_hole_table_for_lid(enclosure: Path) -> None:
    table = _group(_svg(enclosure, "lid"), "hole-table")
    assert table is not None
    texts = _texts(table)
    assert "⌀4.5" in texts
    assert {"A1", "A2", "A3", "A4"} <= set(texts)
    assert texts.count("⌀4.5") == 4
    assert "4" in texts  # qty of the ⌀4.5 group
    assert {"32.0", "192.0", "6.0", "168.0"} <= set(texts)  # from the lower-left corner


def test_titleblock_fields(enclosure: Path) -> None:
    tb = _group(_svg(enclosure, "lid"), "titleblock")
    assert tb is not None
    text = " ".join(_texts(tb))
    for needle in (
        "part://lid",
        "Lid",
        "1.5 mm CR4 (DC01)",
        "mild steel",
        "cut-sheet",
        "powder coat, grey",
        "ISO2768-m",
        "unsnapshotted",  # the temp copy is not tracked, so there is no snapshot date
        "A3",
    ):
        assert needle in text, needle
    meta = json.loads((enclosure / "build" / "drawings" / "lid.json").read_text())
    assert meta["scale"] in text
    from napkin2factory import __version__

    assert f"napkin2factory {__version__}" in text
    rev = [t for t in tb.iter(f"{SVG_NS}text") if t.get("class") == "rev"]
    assert [t.text for t in rev] == ["A"]


@pytest.mark.parametrize(("product_root", "pid"), SHEET_METAL, indirect=["product_root"])
def test_flat_dxf(product_root: Path, pid: str) -> None:
    import ezdxf

    path = product_root / "build" / "drawings" / f"{pid}-flat.dxf"
    doc = ezdxf.readfile(str(path))
    assert doc.header["$INSUNITS"] == 4
    names = {layer.dxf.name for layer in doc.layers}
    assert {"OUTLINE", "HOLES", "CUTOUTS", "BEND", "BEND-TEXT", "NOTES"} <= names
    assert doc.layers.get("BEND").dxf.linetype == "DASHED"
    msp = doc.modelspace()
    flat = _flat_json(product_root, pid)
    outlines = msp.query('LWPOLYLINE[layer=="OUTLINE"]')
    assert len(outlines) == 1 and outlines[0].closed
    area = _shoelace([(x, y) for x, y in outlines[0].vertices()])
    expected = _shoelace([tuple(p) for p in flat["outline"]])
    assert abs(area - expected) / expected < 0.005
    bends = msp.query('LINE[layer=="BEND"]')
    assert len(bends) == len(flat["bend_lines"])
    assert len(msp.query('TEXT[layer=="BEND-TEXT"]')) == len(flat["bend_lines"])
    assert len(msp.query('CIRCLE[layer=="HOLES"]')) == len(flat["holes"])
    assert len(msp.query('LWPOLYLINE[layer=="CUTOUTS"]')) == len(flat["cutouts"])
    notes = " ".join(t.dxf.text for t in msp.query('TEXT[layer=="NOTES"]'))
    assert f"part://{pid}" in notes and "THICKNESS" in notes and "UP" in notes


def test_json_sidecar(enclosure: Path, bracket: Path) -> None:
    base = json.loads((enclosure / "build" / "drawings" / "base.json").read_text())
    assert base["has_flat"] is True
    assert base["views"] == ["top", "front", "right", "iso", "flat"]
    assert base["holes"] == 4 and base["dims"] >= 10
    assert re.fullmatch(r"\d+(\.\d+)?:\d+(\.\d+)?", base["scale"])
    lb = json.loads((bracket / "build" / "drawings" / "l-bracket.json").read_text())
    assert lb["holes"] == 4 and lb["has_flat"] is True


def _ctx(root: Path, date: str):  # type: ignore[no-untyped-def]
    from napkin2factory.core.graph.rules import RunContext
    from napkin2factory.core.loader import load_product

    product = load_product(root)
    return RunContext(product=product, build_dir=product.paths.build, snapshot_date=date)


def test_output_hash_ignores_snapshot_date(enclosure: Path) -> None:
    from napkin2factory.drawings.engine import make_drawing

    svg_path = enclosure / "build" / "drawings" / "lid.svg"
    r1 = make_drawing(_ctx(enclosure, "2026-01-01"), "lid")
    text1 = svg_path.read_text()
    r2 = make_drawing(_ctx(enclosure, "2026-10-30"), "lid")
    text2 = svg_path.read_text()
    assert "2026-01-01" in text1 and "2026-10-30" in text2
    assert r1.output_hash == r2.output_hash
    strip = re.compile(r'<g id="titleblock">.*?</svg>', re.S)
    assert strip.sub("", text1) == strip.sub("", text2)


def test_reads_outputs_and_no_temp_files(enclosure: Path) -> None:
    from napkin2factory.drawings.engine import make_drawing

    r = make_drawing(_ctx(enclosure, "2026-01-01"), "base")
    uri = "part://base"
    assert r.reads == [
        uri,
        f"{uri}#rev",
        f"{uri}#name",
        f"{uri}#material",
        f"{uri}#process",
        f"{uri}#finish",
        f"{uri}#tolerance_class",
    ]
    names = sorted(p.name for p in r.outputs)
    assert names == ["base-flat.dxf", "base.json", "base.svg"]
    assert all(p.is_file() for p in r.outputs)
    assert not list((enclosure / "build" / "drawings").glob(".*.tmp"))


def test_projection_failure_names_part_and_writes_nothing(
    enclosure: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from napkin2factory.drawings import engine

    svg_path = enclosure / "build" / "drawings" / "lid.svg"
    before = svg_path.read_bytes()

    def boom(*_a: object, **_k: object) -> None:
        raise ValueError("HLR exploded")

    monkeypatch.setattr(engine, "project_shape", boom)
    with pytest.raises(RuntimeError, match=r"part://lid.*front view.*HLR exploded"):
        engine.make_drawing(_ctx(enclosure, "2026-01-01"), "lid")
    assert svg_path.read_bytes() == before
    assert not list((enclosure / "build" / "drawings").glob(".*.tmp"))


def test_compose_machined_part_without_holes_or_dims() -> None:
    from build123d import Box, BuildPart, Cylinder, Locations

    from napkin2factory.drawings.sheet import SheetInput, TitleFields, compose
    from napkin2factory.drawings.views import ALL_VIEWS, ORTHO_VIEWS, ortho_extents, project_shape

    with BuildPart() as bp:
        Box(80, 40, 20)
        with Locations((0, 0, 20)):
            Cylinder(15, 20)
    shape = bp.part
    bb = shape.bounding_box()
    lo, hi = (bb.min.X, bb.min.Y, bb.min.Z), (bb.max.X, bb.max.Y, bb.max.Z)
    center = tuple((a + b) / 2 for a, b in zip(lo, hi, strict=True))
    views = {v: project_shape(shape, v, center) for v in ALL_VIEWS}  # type: ignore[arg-type]
    for v in ORTHO_VIEWS:
        ortho_extents(views[v], lo, hi)
    title = TitleFields("part://boss", "Boss", "B", "6061-T6", "machining", "—", "—", "x", "d")
    sheet = compose(
        SheetInput(
            title=title,
            views=views,
            bbox_min=lo,
            bbox_max=hi,
            bbox_size=(bb.size.X, bb.size.Y, bb.size.Z),
            dims=[],
            holes=[],
        )
    )
    svg = etree.fromstring(sheet.svg.encode())
    assert _group(svg, "hole-table") is None and _group(svg, "view-flat") is None
    assert {"80.0", "40.0", "40.0"} <= set(_texts(_group(svg, "dims")))  # type: ignore[arg-type]
    assert sheet.meta["scale"] == "2:1" or sheet.meta["scale_factor"] >= 1.0
    assert '<g id="titleblock">' not in sheet.hash_text
