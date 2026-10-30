"""M0 viewer skeleton proof (D13): one fully inlined page loads from ``file://``."""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

import pytest

from napkin2factory.report.inline import (
    ADDONS,
    THREE_VERSION,
    VENDOR_DIR,
    bundle_viewer,
    inline_module_script,
)

#: sha256 of the vendored three.js r170 files, recorded in DECISIONS.md (D13).
VENDOR_SHA256 = {
    "three.module.js": "ce1fa418de16a19495a9f72495580e3015d7745c296d3ce0485897f902ddedfb",
    "GLTFLoader.js": "45139faddd5aaf48ed2d62203d976e5cbd703db1a592de40527f9f6cf58abd44",
    "OrbitControls.js": "80efaadea4f8a636a65fb0bd08bfef62f3d93a0bb94e2e7500f23176c5c07f4e",
    "BufferGeometryUtils.js": "c25b7930e570e9ec56173cd3b866ec8d2e10016630db3937efb439daf1cedbf6",
}


def test_vendored_three_is_pinned() -> None:
    assert THREE_VERSION == "0.170.0"
    for name, digest in VENDOR_SHA256.items():
        assert hashlib.sha256((VENDOR_DIR / name).read_bytes()).hexdigest() == digest, name
    assert set(ADDONS) <= set(VENDOR_SHA256)


def test_bundle_has_no_imports_or_exports() -> None:
    js = bundle_viewer()
    assert not re.search(r"^import\s", js, re.MULTILINE)
    assert not re.search(r"^export\s", js, re.MULTILINE)
    for name in ("GLTFLoader", "OrbitControls", "n2fCreateViewer"):
        assert name in js


def _cube_glb() -> bytes:
    import numpy as np
    from build123d import Box

    from napkin2factory.geometry.glb import GlbInstance, GlbMesh, write_glb

    verts, tris = Box(10, 10, 10).tessellate(0.1)
    mesh = GlbMesh(
        uri="part://cube",
        vertices=np.asarray([(v.X, v.Y, v.Z) for v in verts], dtype=np.float32),
        triangles=np.asarray(tris, dtype=np.uint32),
        color=(0.7, 0.4, 0.2),
    )
    return write_glb(
        [mesh],
        [
            GlbInstance("part://cube#1", "part://cube"),
            GlbInstance("part://cube#2", "part://cube", translation=(20.0, 0.0, 0.0)),
        ],
    )


def build_skeleton_page() -> str:
    glb = base64.b64encode(_cube_glb()).decode()
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>n2f viewer skeleton</title>"
        "<style>#view{width:400px;height:300px}</style></head><body>"
        "<div id='view' data-n2f-glb='glb-data'></div>"
        f"<script type='text/plain' id='glb-data'>{glb}</script>"
        + inline_module_script(bundle_viewer())
        + "</body></html>"
    )


def test_skeleton_page_is_self_contained(tmp_path: Path) -> None:
    html = build_skeleton_page()
    from selectolax.lexbor import LexborHTMLParser as HTMLParser

    tree = HTMLParser(html)
    assert not [s for s in tree.css("script[src]")]
    assert not tree.css("link")
    assert not re.search(r"\b(?:src|href)\s*=\s*['\"]?(?:https?:)?//", html)
    body = html.split('<script type="module">', 1)[1]
    assert not re.search(r"^\s*import\s.*from\s", body, re.MULTILINE)
    (tmp_path / "skeleton.html").write_text(html, encoding="utf-8")


def test_skeleton_page_loads_from_file_url(tmp_path: Path) -> None:
    """The real proof: Chromium opens the page from disk, the viewer parses the GLB,
    and reports both instances of the single cube mesh."""
    pytest.importorskip("playwright")
    from playwright.sync_api import Error, sync_playwright

    page_path = tmp_path / "skeleton.html"
    page_path.write_text(build_skeleton_page(), encoding="utf-8")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]
            )
    except Error as exc:  # browser not installed: logged in BACKLOG.md (B-0001)
        pytest.skip(f"Playwright Chromium unavailable: {exc}")
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(page_path.as_uri())
        nodes = page.evaluate("window.n2fViewerReady.then(() => window.n2fViewer.nodes())")
        count = page.evaluate("window.n2fViewer.instanceCount('part://cube')")
        browser.close()
    assert errors == [], errors
    assert nodes == ["part://cube"]
    assert count == 2
