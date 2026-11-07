"""M1 viewer interaction tests (V3): click-only picking, isolation and section cuts."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from napkin2factory.report.inline import bundle_viewer, inline_module_script
from tests.conftest import real_page_errors


def _two_part_glb() -> bytes:
    """Build a GLB with two distinct part meshes side by side along X."""
    import numpy as np
    from build123d import Box

    from napkin2factory.geometry.glb import GlbInstance, GlbMesh, write_glb

    verts, tris = Box(10, 10, 10).tessellate(0.1)
    v_arr = np.asarray([(v.X, v.Y, v.Z) for v in verts], dtype=np.float32)
    t_arr = np.asarray(tris, dtype=np.uint32)
    left = GlbMesh(uri="part://left", vertices=v_arr, triangles=t_arr, color=(0.7, 0.3, 0.2))
    right = GlbMesh(uri="part://right", vertices=v_arr, triangles=t_arr, color=(0.2, 0.5, 0.7))
    return write_glb(
        [left, right],
        [
            GlbInstance("part://left#1", "part://left", translation=(-20.0, 0.0, 0.0)),
            GlbInstance("part://right#1", "part://right", translation=(20.0, 0.0, 0.0)),
        ],
    )


def build_interaction_page() -> str:
    """Return a self-contained HTML page with two parts and viewer controls."""
    glb = base64.b64encode(_two_part_glb()).decode()
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>n2f viewer interaction</title>"
        "<style>body{margin:0}#view{width:600px;height:400px}</style></head><body>"
        "<div id='view' data-n2f-glb='glb-data'></div>"
        "<input id='section' type='checkbox'>"
        "<select id='section-axis'><option value='x'>X</option><option value='y'>Y</option>"
        "<option value='z' selected>Z</option></select>"
        "<input id='section-offset' type='range' min='0' max='1' step='0.01' value='0.5'>"
        "<button id='show-all' type='button'>Show all</button>"
        f"<script type='text/plain' id='glb-data'>{glb}</script>"
        + inline_module_script(bundle_viewer())
        + "</body></html>"
    )


def test_viewer_picking_isolation_and_section_cuts(tmp_path: Path) -> None:
    """Verify click-only picking, orbit drag, frame, ghost and 3-axis section cuts."""
    pytest.importorskip("playwright")
    from playwright.sync_api import Error, sync_playwright

    page_path = tmp_path / "interaction.html"
    page_path.write_text(build_interaction_page(), encoding="utf-8")
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
        page.goto(page_path.as_uri())

        nodes = page.evaluate(
            """window.n2fViewerReady.then(() => {
                window.__events = [];
                window.__selected = undefined;
                document.getElementById('view').addEventListener('n2f:select', (ev) => {
                    window.__selected = ev.detail.uri;
                    window.__events.push(ev.detail.uri);
                });
                return window.n2fViewer.nodes();
            })"""
        )
        assert nodes == ["part://left", "part://right"]

        # 1. Click on part://left selects it.
        left_pt = page.evaluate("window.n2fViewer.screenPoint('part://left')")
        assert left_pt is not None
        page.mouse.move(left_pt["x"], left_pt["y"])
        page.mouse.down()
        page.mouse.up()
        assert page.evaluate("window.__selected") == "part://left"

        # 2. Drag of 40 px across the canvas moves the camera and leaves selection unchanged.
        cam_before = page.evaluate("window.n2fViewer.camera.position.toArray()")
        ev_count_before = page.evaluate("window.__events.length")
        # A drag that starts without a real mouse move first is, under heavy CPU load, sometimes
        # delivered to the page not at all (measured: an empty event log, ten busy loops), so
        # the drag moves first and is tried a few times; one that moved the camera proves the
        # path, and every try must leave the selection alone.
        for _ in range(4):
            page.mouse.move(left_pt["x"] - 30, left_pt["y"] - 30)  # a real move first: hover is set
            page.mouse.move(left_pt["x"], left_pt["y"], steps=3)
            page.mouse.down()
            page.mouse.move(left_pt["x"] + 40, left_pt["y"] + 10, steps=5)
            page.mouse.up()
            assert page.evaluate("window.__selected") == "part://left"
            try:  # OrbitControls (damped) moves the camera in the frame loop
                page.wait_for_function(
                    "(b) => window.n2fViewer.camera.position.toArray().some((v, i) => v !== b[i])",
                    arg=cam_before,
                    timeout=1500,
                )
                break
            except Error:
                continue
        cam_after = page.evaluate("window.n2fViewer.camera.position.toArray()")
        assert cam_after != cam_before
        assert page.evaluate("window.__selected") == "part://left"
        assert page.evaluate("window.__events.length") == ev_count_before

        # 3. Click on empty canvas clears selection to null without moving camera.
        page.evaluate("window.n2fViewer.fit()")
        cam_fit = page.evaluate("window.n2fViewer.camera.position.toArray()")
        page.mouse.move(10, 10)
        page.mouse.down()
        page.mouse.up()
        assert page.evaluate("window.__selected") is None
        assert page.evaluate("window.n2fViewer.camera.position.toArray()") == cam_fit

        # 4. frame('part://right') moves controls.target to near that part's centre (20, 0, 0).
        target = page.evaluate(
            "window.n2fViewer.frame('part://right'); window.n2fViewer.controls.target.toArray()"
        )
        assert abs(target[0] - 20.0) < 0.5 and abs(target[1]) < 0.5 and abs(target[2]) < 0.5
        page.evaluate("window.n2fViewer.fit()")

        # 5. ghost(['part://left']) makes part://right transparent (< 0.2) and leaves left at 1.
        opacities = page.evaluate(
            """(() => {
                window.n2fViewer.ghost(['part://left']);
                const out = {};
                window.n2fViewer.scene.traverse((o) => {
                    if (o.isMesh && o.userData.n2f_uri) {
                        out[o.userData.n2f_uri] = o.material.opacity;
                    }
                });
                return out;
            })()"""
        )
        assert opacities["part://left"] == pytest.approx(1.0)
        assert opacities["part://right"] < 0.2

        # Clicking on the ghosted part's screen point does not select it.
        right_pt = page.evaluate("window.n2fViewer.screenPoint('part://right')")
        assert right_pt is not None
        page.mouse.move(right_pt["x"], right_pt["y"])
        page.mouse.down()
        page.mouse.up()
        assert page.evaluate("window.__selected") != "part://right"

        # Re-ghost and verify ghost([]) restores all parts to opacity 1.
        restored = page.evaluate(
            """(() => {
                window.n2fViewer.ghost(['part://left']);
                window.n2fViewer.ghost([]);
                const out = {};
                window.n2fViewer.scene.traverse((o) => {
                    if (o.isMesh && o.userData.n2f_uri) {
                        out[o.userData.n2f_uri] = o.material.opacity;
                    }
                });
                return out;
            })()"""
        )
        assert restored["part://left"] == pytest.approx(1.0)
        assert restored["part://right"] == pytest.approx(1.0)

        # 6. Section cuts: section('x', 0.5), section(false), section('y', 0.3) -> section(true).
        sec_x = page.evaluate(
            """(() => {
                window.n2fViewer.section('x', 0.5);
                const planes = window.n2fViewer.renderer.clippingPlanes;
                return {
                    count: planes.length,
                    normal: planes[0].normal.toArray(),
                    constant: planes[0].constant,
                    state: window.n2fViewer.sectionState(),
                };
            })()"""
        )
        assert sec_x["count"] == 1
        assert sec_x["normal"] == [-1, 0, 0]
        assert sec_x["state"] == {"on": True, "axis": "x", "offset": 0.5}

        sec_off = page.evaluate(
            """(() => {
                window.n2fViewer.section(false);
                return {
                    count: window.n2fViewer.renderer.clippingPlanes.length,
                    state: window.n2fViewer.sectionState(),
                };
            })()"""
        )
        assert sec_off["count"] == 0
        assert sec_off["state"]["on"] is False

        sec_y = page.evaluate(
            """(() => {
                window.n2fViewer.section('y', 0.3);
                const c1 = window.n2fViewer.renderer.clippingPlanes[0].constant;
                window.n2fViewer.section(false);
                window.n2fViewer.section(true);
                const planes = window.n2fViewer.renderer.clippingPlanes;
                return {
                    count: planes.length,
                    normal: planes[0].normal.toArray(),
                    constant: planes[0].constant,
                    expectedConstant: c1,
                    state: window.n2fViewer.sectionState(),
                };
            })()"""
        )
        assert sec_y["count"] == 1
        assert sec_y["normal"] == [0, -1, 0]
        assert sec_y["constant"] == pytest.approx(sec_y["expectedConstant"])
        assert sec_y["state"] == {"on": True, "axis": "y", "offset": 0.3}

        browser.close()

    assert real_page_errors(errors) == [], errors
