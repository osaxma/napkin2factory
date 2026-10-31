"""M3 (v0.2): styled concept screenshots through the inline viewer (N6), and the fallback.

The product is the M2 fixture: the bracket plus ``tests/fixtures/concepts/product-green-red``.
Viewer tests are skipped (same reason string as the report test) when Chromium is missing.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import numpy as np
import pytest

from napkin2factory.concepts.build import build_concept
from napkin2factory.concepts.screenshot import (
    NO_PLAYWRIGHT_ENV,
    ScreenshotSession,
    card_materials,
    styled_page,
    styled_screenshots,
)
from napkin2factory.core import concepts as cm
from napkin2factory.core.model.style import StyleFile
from napkin2factory.core.style import load_style
from napkin2factory.geometry.render import image_variance
from tests.conftest import EXAMPLES, FIXTURES, copy_product

CONCEPTS = FIXTURES / "concepts" / "product-green-red" / "concepts"
TIMING = os.environ.get("N2F_TIMING") == "1"
RED = "#c0392b"


def _product(dest: Path, style: str | None = None) -> Path:
    root = copy_product(EXAMPLES / "bracket", dest, git=False)
    shutil.copytree(CONCEPTS, root / "concepts")
    if style is not None:
        (root / "style.yaml").write_text(style)
    return root


def _chromium_or_skip() -> None:
    pytest.importorskip("playwright")
    from playwright.sync_api import Error, sync_playwright

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]
            )
            browser.close()
    except Error as exc:
        pytest.skip(f"Playwright Chromium unavailable: {exc}")


def _hsv(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Hue (degrees), saturation and value (0..1) of every pixel."""
    from PIL import Image

    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64) / 255.0
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(axis=-1), rgb.min(axis=-1)
    delta = mx - mn
    safe = np.where(delta == 0, 1, delta)
    hue = np.where(
        mx == r, ((g - b) / safe) % 6, np.where(mx == g, (b - r) / safe + 2, (r - g) / safe + 4)
    )
    hue = np.where(delta == 0, 0, hue * 60.0)
    sat = np.where(mx == 0, 0, delta / np.where(mx == 0, 1, mx))
    return hue, sat, mx


def _hex_hsv(hex_: str) -> tuple[float, float, float]:
    import colorsys

    r, g, b = (int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360, s, v


@pytest.fixture(scope="module")
def viewer_product(tmp_path_factory: pytest.TempPathFactory) -> Path:
    _chromium_or_skip()
    root = _product(
        tmp_path_factory.mktemp("shots") / "p", f"preset: industrial\npalette: {{body: '{RED}'}}\n"
    )
    with ScreenshotSession() as session:
        for cid in ("C-001", "C-002"):
            build_concept(root, cm.load_card(root, cid), session=session)
    return root


def test_styled_screenshot_is_a_product_image(viewer_product: Path) -> None:
    from PIL import Image

    renders = viewer_product / "build" / "concepts" / "C-002" / "renders"
    iso = renders / "styled-iso.png"
    assert iso.is_file() and (renders / "styled-front.png").is_file()
    image = np.asarray(Image.open(iso).convert("RGB"))
    assert image.shape[1] >= 1200 and image.shape[0] >= 900
    assert image_variance(image) > 100, "the screenshot is blank"
    # the body's palette colour is in the pixels: lighting changes value, not hue
    hue, sat, _ = _hsv(iso)
    h0, _, _ = _hex_hsv(RED)
    near = (np.abs((hue - h0 + 180) % 360 - 180) <= 12) & (sat >= 0.35)
    assert near.mean() >= 0.02, f"only {near.mean():.1%} of pixels carry the body colour"
    card = cm.load_card(viewer_product, "C-002")
    assert card.screening is not None
    assert not any("styled screenshots unavailable" in n for n in card.screening.notes)


def test_grey_palette_reads_as_grey(viewer_product: Path, tmp_path: Path) -> None:
    """Industrial's grey body: low saturation, darker than the neutral background."""
    root = viewer_product
    card = cm.load_card(root, "C-002")
    style = StyleFile().resolved()
    out = tmp_path / "renders"
    result = styled_screenshots(
        card, root / "build" / "concepts" / "C-002" / "massing.glb", style, out
    )
    assert result.method == "viewer", result.notes
    _, sat, val = _hsv(result.paths["iso"])
    body = (sat <= 0.15) & (val >= 0.15) & (val <= 0.6)
    assert body.mean() >= 0.02
    assert (sat > 0.35).mean() < 0.01, "no hash colours in a grey picture"


def test_method_is_viewer_and_page_is_self_contained(viewer_product: Path) -> None:
    page = viewer_product / "build" / "concepts" / "C-001" / "renders" / "styled.html"
    html = page.read_text()
    assert '<script type="module">' in html
    for ref in ("http://", "https://", 'src="', "href="):
        assert ref not in html.split('<script type="module">', 1)[0], ref
    card = cm.load_card(viewer_product, "C-001")
    mats = card_materials(card, load_style(viewer_product))
    assert set(mats) == {f"concept://C-001/{c.as_}" for c in card.massing}
    assert mats["concept://C-001/body"]["color"] == RED
    assert styled_page(b"glTF", mats, StyleFile().resolved()).count('data-n2f-options="') == 1


def test_fallback_without_playwright(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(NO_PLAYWRIGHT_ENV, "1")
    root = _product(tmp_path / "p")
    built = build_concept(root, cm.load_card(root, "C-002"))
    shots = built.screenshots
    assert shots is not None and shots.method == "zbuffer-fallback"
    renders = root / "build" / "concepts" / "C-002" / "renders"
    for view in ("iso", "front"):
        styled = renders / f"styled-{view}.png"
        assert styled.is_file()
        assert styled.read_bytes() == (renders / f"{view}.png").read_bytes()
    note = (
        "styled screenshots unavailable (N2F_NO_PLAYWRIGHT=1 is set): "
        "showing correctness renders [revisit]"
    )
    assert shots.notes == [note]
    assert note in built.screening.notes
    card = cm.load_card(root, "C-002")
    assert card.screening is not None and note in card.screening.notes
    assert note in " ".join(capsys.readouterr().err.split())
    assert built.to_dict(root)["screenshots"]["method"] == "zbuffer-fallback"


def test_session_warns_once(monkeypatch: pytest.MonkeyPatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv(NO_PLAYWRIGHT_ENV, "1")
    with ScreenshotSession() as s:
        assert s.page() is None and s.unavailable == "N2F_NO_PLAYWRIGHT=1 is set"
        s.warn("first")
        s.warn("second")
    err = capsys.readouterr().err
    assert "first" in err and "second" not in err


@pytest.mark.skipif(not TIMING, reason="timing assertions run only under N2F_TIMING=1 (D30)")
def test_two_cards_through_one_session_are_quick(viewer_product: Path, tmp_path: Path) -> None:
    root = viewer_product
    style = load_style(root)
    cards = [cm.load_card(root, cid) for cid in ("C-001", "C-002")]
    with ScreenshotSession() as session:
        styled_screenshots(
            cards[0], root / "build/concepts/C-001/massing.glb", style, tmp_path / "w", session
        )  # warm: browser started, bundle parsed once
        t0 = time.perf_counter()
        for card in cards:
            glb = root / "build" / "concepts" / card.id / "massing.glb"
            r = styled_screenshots(card, glb, style, tmp_path / card.id, session)
            assert r.method == "viewer"
        elapsed = time.perf_counter() - t0
    print(f"styled screenshots, two cards, one session (warm): {elapsed:.2f} s")
    assert elapsed < 15, f"two cards took {elapsed:.1f} s"
