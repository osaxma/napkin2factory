"""M1 viewer explode tests (B-0304): per-unit n2f_explode directions and one-axis fallback."""

from __future__ import annotations

import base64
import json
import struct
from pathlib import Path

import pytest

from napkin2factory.report.inline import bundle_viewer, inline_module_script
from tests.conftest import real_page_errors


def _three_part_glb() -> bytes:
    """Build a GLB with three distinct part meshes at different coordinates."""
    import numpy as np
    from build123d import Box

    from napkin2factory.geometry.glb import GlbInstance, GlbMesh, write_glb

    verts, tris = Box(10, 10, 10).tessellate(0.1)
    v_arr = np.asarray([(v.X, v.Y, v.Z) for v in verts], dtype=np.float32)
    t_arr = np.asarray(tris, dtype=np.uint32)
    meshes = [
        GlbMesh(uri="part://a", vertices=v_arr, triangles=t_arr, color=(0.7, 0.3, 0.2)),
        GlbMesh(uri="part://b", vertices=v_arr, triangles=t_arr, color=(0.2, 0.6, 0.3)),
        GlbMesh(uri="part://c", vertices=v_arr, triangles=t_arr, color=(0.2, 0.4, 0.7)),
    ]
    instances = [
        GlbInstance("part://a#1", "part://a", translation=(10.0, 0.0, 0.0)),
        GlbInstance("part://b#1", "part://b", translation=(0.0, 20.0, 10.0)),
        GlbInstance("part://c#1", "part://c", translation=(0.0, 0.0, 30.0)),
    ]
    return write_glb(meshes, instances)


def _patch_glb_explode(glb: bytes, explode_by_node: dict[str, dict[str, object]]) -> bytes:
    """Rewrite the GLB JSON chunk so top-level nodes carry n2f_explode in extras."""
    magic, version, _total = struct.unpack_from("<4sII", glb, 0)
    assert magic == b"glTF" and version == 2
    json_len, json_type = struct.unpack_from("<II", glb, 12)
    assert json_type == 0x4E4F534A
    doc = json.loads(glb[20 : 20 + json_len].decode("utf-8"))
    rest = glb[20 + json_len :]
    for node in doc["nodes"]:
        if node["name"] in explode_by_node:
            node.setdefault("extras", {})["n2f_explode"] = explode_by_node[node["name"]]
    raw = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    raw += b" " * ((4 - len(raw) % 4) % 4)
    total = 12 + 8 + len(raw) + len(rest)
    return (
        struct.pack("<4sII", b"glTF", 2, total)
        + struct.pack("<II", len(raw), json_type)
        + raw
        + rest
    )


def _build_explode_page(glb_bytes: bytes) -> str:
    """Return a self-contained HTML page with a viewer for the given GLB bytes."""
    glb = base64.b64encode(glb_bytes).decode()
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>n2f viewer explode</title>"
        "<style>body{margin:0}#view{width:600px;height:400px}</style></head><body>"
        "<div id='view' data-n2f-glb='glb-data' "
        "data-explode-axis='z' data-explode-spacing='80'></div>"
        f"<script type='text/plain' id='glb-data'>{glb}</script>"
        + inline_module_script(bundle_viewer())
        + "</body></html>"
    )


def test_viewer_explode_directions_and_fallback(tmp_path: Path) -> None:
    """Verify per-unit n2f_explode vectors, zero-dir stay, explodeInfo, and one-axis fallback."""
    pytest.importorskip("playwright")
    from playwright.sync_api import Error, sync_playwright

    raw_glb = _three_part_glb()
    patched_glb = _patch_glb_explode(
        raw_glb,
        {
            "part://a#1": {"dir": [1.0, 0.0, 0.0], "distance": 30.0, "source": "interface"},
            "part://b#1": {"dir": [0.0, -1.0, 0.0], "distance": 40.0, "source": "declared"},
            "part://c#1": {"dir": [0.0, 0.0, 1.0], "distance": 50.0, "source": "fallback"},
        },
    )
    page_with_extras = tmp_path / "explode_extras.html"
    page_with_extras.write_text(_build_explode_page(patched_glb), encoding="utf-8")
    page_without_extras = tmp_path / "explode_legacy.html"
    page_without_extras.write_text(_build_explode_page(raw_glb), encoding="utf-8")

    read_positions_js = """(() => {
        const out = {};
        window.n2fViewer.scene.traverse((o) => {
            if (o.userData && o.userData.n2f_kind === 'instance' && o.userData.n2f_uri) {
                out[o.userData.n2f_uri] = o.position.toArray();
            }
        });
        return out;
    })()"""

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]
            )
        except Error as exc:  # browser not installed: logged in BACKLOG.md (B-0001)
            pytest.skip(f"Playwright Chromium unavailable: {exc}")
        page = browser.new_page(viewport={"width": 600, "height": 400})
        page.set_default_timeout(15000)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(page_with_extras.as_uri())

        nodes = page.evaluate("window.n2fViewerReady.then(() => window.n2fViewer.nodes())")
        assert nodes == ["part://a", "part://b", "part://c"]

        def need_gl() -> None:
            """Skip when the host lost WebGL (software GL under load, S-232)."""
            ok = page.evaluate(
                "window.n2fViewer.glState !== 'unavailable' && "
                "window.n2fViewer.renderer.domElement.getBoundingClientRect().width > 0"
            )
            if not ok:
                pytest.skip("WebGL unavailable on this host (S-232)")

        need_gl()

        # explodeInfo() lists all three top-level units with their source strings.
        info = page.evaluate("window.n2fViewer.explodeInfo()")
        assert info == {
            "part://a#1": {"dir": [1.0, 0.0, 0.0], "distance": 30.0, "source": "interface"},
            "part://b#1": {"dir": [0.0, -1.0, 0.0], "distance": 40.0, "source": "declared"},
            "part://c#1": {"dir": [0.0, 0.0, 1.0], "distance": 50.0, "source": "fallback"},
        }

        # Case 1: explode(1) moves by dir * distance; explode(0.5) moves half; explode(0) restores.
        pos_full = page.evaluate(f"window.n2fViewer.explode(1); {read_positions_js}")
        assert pos_full["part://a"] == pytest.approx([40.0, 0.0, 0.0])
        assert pos_full["part://b"] == pytest.approx([0.0, -20.0, 10.0])
        assert pos_full["part://c"] == pytest.approx([0.0, 0.0, 80.0])

        pos_half = page.evaluate(f"window.n2fViewer.explode(0.5); {read_positions_js}")
        assert pos_half["part://a"] == pytest.approx([25.0, 0.0, 0.0])
        assert pos_half["part://b"] == pytest.approx([0.0, 0.0, 10.0])
        assert pos_half["part://c"] == pytest.approx([0.0, 0.0, 55.0])

        pos_zero = page.evaluate(f"window.n2fViewer.explode(0); {read_positions_js}")
        assert pos_zero["part://a"] == pytest.approx([10.0, 0.0, 0.0])
        assert pos_zero["part://b"] == pytest.approx([0.0, 20.0, 10.0])
        assert pos_zero["part://c"] == pytest.approx([0.0, 0.0, 30.0])

        # Case 3 (reusing the first page): a zero dir (or missing extra on one child) stays put.
        pos_zero_dir = page.evaluate(
            f"""(() => {{
                window.n2fViewer.scene.traverse((o) => {{
                    const u = o.userData;
                    if (u && u.n2f_uri === 'part://a' && u.n2f_explode) {{
                        u.n2f_explode.dir = [0, 0, 0];
                    }}
                    if (u && u.n2f_uri === 'part://b' && u.n2f_explode) {{
                        delete u.n2f_explode;
                    }}
                }});
                window.n2fViewer.explode(1);
                return {read_positions_js};
            }})()"""
        )
        assert pos_zero_dir["part://a"] == pytest.approx([10.0, 0.0, 0.0])
        assert pos_zero_dir["part://b"] == pytest.approx([0.0, 20.0, 10.0])
        assert pos_zero_dir["part://c"] == pytest.approx([0.0, 0.0, 80.0])

        pos_restored = page.evaluate(f"window.n2fViewer.explode(0); {read_positions_js}")
        assert pos_restored["part://a"] == pytest.approx([10.0, 0.0, 0.0])
        assert pos_restored["part://b"] == pytest.approx([0.0, 20.0, 10.0])
        assert pos_restored["part://c"] == pytest.approx([0.0, 0.0, 30.0])

        # Case 2: a second GLB without extras still explodes along the single explodeAxis ('z').
        page.goto(page_without_extras.as_uri())
        legacy_nodes = page.evaluate("window.n2fViewerReady.then(() => window.n2fViewer.nodes())")
        assert legacy_nodes == ["part://a", "part://b", "part://c"]
        need_gl()

        assert page.evaluate("window.n2fViewer.explodeInfo()") == {}
        legacy_full = page.evaluate(f"window.n2fViewer.explode(1); {read_positions_js}")
        assert legacy_full["part://a"] == pytest.approx([10.0, 0.0, 0.0])
        assert legacy_full["part://b"] == pytest.approx([0.0, 20.0, 90.0])
        assert legacy_full["part://c"] == pytest.approx([0.0, 0.0, 190.0])

        legacy_zero = page.evaluate(f"window.n2fViewer.explode(0); {read_positions_js}")
        assert legacy_zero["part://a"] == pytest.approx([10.0, 0.0, 0.0])
        assert legacy_zero["part://b"] == pytest.approx([0.0, 20.0, 10.0])
        assert legacy_zero["part://c"] == pytest.approx([0.0, 0.0, 30.0])

        browser.close()

    assert real_page_errors(errors) == [], errors
