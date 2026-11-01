"""Layout marks on the styled concept pictures (B-0032, review gate B C16) and blank captures
(B-0051).

The door, hinge side, handle and controls panel are drawn from the card's ``layout`` words as
flat ink on the silhouette; a capture that comes back blank is rendered once more, then falls
back to the correctness renders with a note.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from napkin2factory.concepts.screenshot import (
    FACES,
    INK_DARK,
    INK_LIGHT,
    ScreenshotSession,
    blank_capture,
    ink_for,
    layout_marks,
    styled_page,
    styled_screenshots,
    transient_gl_error,
)
from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.model.style import StyleFile


def _card(layout: dict[str, str], *names: str) -> ConceptCard:
    massing = [
        {"kit": "block", "as": n, "args": {"length": "10 mm", "width": "10 mm", "height": "10 mm"}}
        for n in names
    ]
    return ConceptCard.model_validate(
        {"id": "C-009", "title": "t", "layout": layout, "massing": massing}
    )


INDUSTRIAL = StyleFile().resolved()
APPLIANCE = StyleFile(preset="appliance").resolved()


def test_faces_are_right_handed() -> None:
    for name, (n, u, v) in FACES.items():
        cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        assert cross == n, name


def test_hinged_left_door_on_the_front_with_a_controls_box_on_the_right() -> None:
    card = _card(
        {"load": "front", "door": "hinged-left", "controls": "side-right"},
        "body",
        "door",
        "controls",
    )
    marks = layout_marks(card, INDUSTRIAL)
    door, controls = marks["door"], marks["controls"]
    assert marks["body"] == ["concept://C-009/body"]
    assert door["nodes"] == ["concept://C-009/door"]
    assert door["face"]["name"] == "front" and door["hinge"] == "u-"
    assert door["ink"] == INK_LIGHT  # industrial's dark door
    assert controls["nodes"] == ["concept://C-009/controls"]
    assert controls["face"]["name"] == "right"
    assert controls["ink"] == INK_DARK  # industrial's orange controls
    assert layout_marks(card, APPLIANCE)["door"]["ink"] == INK_DARK  # a light door


@pytest.mark.parametrize(
    ("layout", "face", "hinge"),
    [
        ({"door": "hinged-right"}, "front", "u+"),
        ({"door": "Hinged Left"}, "front", "u-"),
        ({"load": "top", "door": "hinged-back"}, "top", "v+"),
        ({"load": "side-left", "door": "hinged-back"}, "left", "u-"),  # facing the left side
        ({"load": "side-left", "door": "hinged-left"}, "left", None),  # names the face
        ({"door": "hinged-top"}, "front", "v+"),
        ({"door": "sliding"}, "front", None),
        ({"door": "lift-off"}, "front", None),
    ],
)
def test_door_face_and_hinge_edge(layout: dict[str, str], face: str, hinge: str | None) -> None:
    door = layout_marks(_card(layout, "body"), INDUSTRIAL)["door"]
    assert door["face"]["name"] == face and door["hinge"] == hinge
    assert door["nodes"] == []  # no door shape: drawn on the body's face


@pytest.mark.parametrize("words", ["", "none", "no door"])
def test_no_door_words_no_door_mark(words: str) -> None:
    assert layout_marks(_card({"door": words}, "body"), INDUSTRIAL)["door"] is None


@pytest.mark.parametrize(
    ("words", "face", "band"),
    [
        ("top", "top", "upper"),
        ("side-left", "left", "upper"),
        ("front-below", "front", "lower"),
        ("below", "front", "lower"),
        ("front", "front", "upper"),
    ],
)
def test_controls_panel_on_the_named_face(words: str, face: str, band: str) -> None:
    controls = layout_marks(_card({"controls": words}, "body"), INDUSTRIAL)["controls"]
    assert controls["face"]["name"] == face and controls["band"] == band
    assert controls["nodes"] == []


@pytest.mark.parametrize("words", ["", "none", "remote", "app"])
def test_controls_words_that_name_no_place_draw_nothing(words: str) -> None:
    assert layout_marks(_card({"controls": words}, "body"), INDUSTRIAL)["controls"] is None


def test_ink_for() -> None:
    assert ink_for("#3f444a") == INK_LIGHT
    assert ink_for("#e6e3dc") == INK_DARK
    assert ink_for("#e07a2e") == INK_DARK
    assert ink_for("#000") == INK_LIGHT
    assert ink_for("not a colour") == INK_DARK


def test_page_carries_the_marks_as_data() -> None:
    marks = layout_marks(_card({"door": "hinged-left"}, "body"), INDUSTRIAL)
    page = styled_page(b"glTF", {}, INDUSTRIAL, marks)
    assert page.count('id="n2f-layout-marks"') == 1
    assert "n2fLayoutMarks" in page and "n2fMarksReady" in page
    assert 'id="n2f-layout-marks"' not in styled_page(b"glTF", {}, INDUSTRIAL)


# ---- blank captures (B-0051) ------------------------------------------------------------


def _png(picture: bool, size: tuple[int, int] = (120, 90), bg: Any = (244, 244, 242)) -> bytes:
    from PIL import Image, ImageDraw

    im = Image.new("RGB", size, bg)
    if picture:
        ImageDraw.Draw(im).rectangle((40, 20, 80, 70), fill=(75, 81, 87))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def test_blank_capture_detection() -> None:
    from PIL import Image

    assert blank_capture(_png(False))
    assert blank_capture(_png(False, bg=(0, 0, 0)))  # a lost GL context
    assert not blank_capture(_png(True))
    assert blank_capture(b"")
    assert blank_capture(b"not a png")
    # a faint gradient on the backdrop is still blank; a few stray pixels too
    ramp = np.tile(np.linspace(236, 248, 120, dtype=np.uint8), (90, 1))
    buf = io.BytesIO()
    Image.fromarray(np.stack([ramp] * 3, axis=-1)).save(buf, "PNG")
    assert blank_capture(buf.getvalue())
    speck = np.full((90, 120, 3), 244, dtype=np.uint8)
    speck[45, 60] = 0
    buf = io.BytesIO()
    Image.fromarray(speck).save(buf, "PNG")
    assert blank_capture(buf.getvalue())
    # a fully transparent capture flattens to one colour
    buf = io.BytesIO()
    Image.new("RGBA", (120, 90), (0, 0, 0, 0)).save(buf, "PNG")
    assert blank_capture(buf.getvalue())


class _FakePage:
    """A browser page whose snapshots come from a script: one entry per page load.

    ``errors`` gives, per load, a page error the viewer raises instead of loading.
    """

    def __init__(self, loads: list[bool], errors: list[str | None] | None = None) -> None:
        self.loads = loads
        self.errors = errors or []
        self.goto_count = 0
        self.session: ScreenshotSession | None = None

    def goto(self, url: str) -> None:
        self.goto_count += 1

    def evaluate(self, expr: str, arg: Any = None) -> Any:
        if "n2fMarksReady" in expr:
            i = self.goto_count - 1
            error = self.errors[i] if i < len(self.errors) else None
            if error is not None and self.session is not None:
                self.session._errors.append(error)
                return False
            return True
        picture = self.loads[min(self.goto_count, len(self.loads)) - 1]
        return "data:image/png;base64," + base64.b64encode(_png(picture)).decode()


def _session(fake: _FakePage) -> ScreenshotSession:
    session = ScreenshotSession()
    session._started = True
    session._page = fake
    fake.session = session
    return session


def _shoot(tmp_path: Path, fake: _FakePage) -> Any:
    card = _card({"door": "hinged-left"}, "body")
    glb = tmp_path / "massing.glb"
    glb.write_bytes(b"glTF")
    out = tmp_path / "renders"
    out.mkdir()
    for view in ("iso", "front"):
        (out / f"{view}.png").write_bytes(_png(True))
    return styled_screenshots(card, glb, INDUSTRIAL, out, _session(fake))


def test_a_blank_capture_is_rendered_once_more(tmp_path: Path) -> None:
    fake = _FakePage([False, True])
    result = _shoot(tmp_path, fake)
    assert result.method == "viewer" and result.retried and fake.goto_count == 2
    assert not blank_capture(result.paths["iso"].read_bytes())


def test_a_good_capture_is_not_retried(tmp_path: Path) -> None:
    fake = _FakePage([True])
    result = _shoot(tmp_path, fake)
    assert result.method == "viewer" and not result.retried and fake.goto_count == 1


def test_two_blank_captures_fall_back_with_a_note(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _FakePage([False, False])
    result = _shoot(tmp_path, fake)
    assert result.method == "zbuffer-fallback" and fake.goto_count == 2
    assert result.notes == [
        "styled screenshots unavailable (the viewer drew a blank iso and front picture "
        "twice): showing correctness renders [revisit]"
    ]
    assert "blank" in capsys.readouterr().err


SHADER_ERROR = "THREE.WebGLProgram: Shader Error 0 - VALIDATE_STATUS false"


def test_a_shader_error_under_load_is_rendered_once_more(tmp_path: Path) -> None:
    fake = _FakePage([True, True], errors=[SHADER_ERROR, None])
    result = _shoot(tmp_path, fake)
    assert result.method == "viewer" and result.retried and fake.goto_count == 2


def test_a_second_shader_error_falls_back(tmp_path: Path) -> None:
    fake = _FakePage([True, True], errors=[SHADER_ERROR, SHADER_ERROR])
    result = _shoot(tmp_path, fake)
    assert result.method == "zbuffer-fallback" and fake.goto_count == 2
    assert "Shader Error" in result.notes[0]


def test_other_viewer_errors_are_not_retried(tmp_path: Path) -> None:
    fake = _FakePage([True, True], errors=["ReferenceError: n2fViewer is not defined"])
    result = _shoot(tmp_path, fake)
    assert result.method == "zbuffer-fallback" and fake.goto_count == 1
    assert not transient_gl_error("ReferenceError: n2fViewer is not defined")
    assert transient_gl_error(SHADER_ERROR)


# ---- in the browser ---------------------------------------------------------------------


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


@pytest.fixture(scope="module")
def fronts(tmp_path_factory: pytest.TempPathFactory) -> dict[str, np.ndarray]:
    """The fixture's C-001 from the front: no layout, door hinged left, door hinged right."""
    import shutil

    from PIL import Image

    from napkin2factory.concepts.build import build_concept
    from napkin2factory.core import concepts as cm
    from tests.conftest import EXAMPLES, FIXTURES, copy_product

    _chromium_or_skip()
    tmp = tmp_path_factory.mktemp("marks")
    root = copy_product(EXAMPLES / "bracket", tmp / "p", git=False)
    shutil.copytree(FIXTURES / "concepts" / "product-green-red" / "concepts", root / "concepts")
    built = build_concept(root, cm.load_card(root, "C-001"), render=False)
    glb = built.massing.paths["glb"]
    out: dict[str, np.ndarray] = {}
    with ScreenshotSession() as session:
        for name, layout in (
            ("bare", {}),
            ("left", {"door": "hinged-left"}),
            ("right", {"door": "hinged-right"}),
        ):
            card = built.card.model_copy(update={"layout": layout})
            shot = styled_screenshots(card, glb, INDUSTRIAL, tmp / name, session)
            assert shot.method == "viewer", shot.notes
            out[name] = np.asarray(Image.open(shot.paths["front"]).convert("RGB"), dtype=np.int16)
    return out


def test_the_hinge_side_shows_in_the_picture(fronts: dict[str, np.ndarray]) -> None:
    """The heavy hinge edge sits on the side the words name; the handle is opposite."""
    sides = {}
    for name in ("left", "right"):
        diff = (np.abs(fronts[name] - fronts["bare"]) > 30).any(axis=-1)
        assert diff.mean() > 0.003, f"no door marks drawn for hinged-{name}"
        cols = np.nonzero(diff.any(axis=0))[0]
        mid = (cols.min() + cols.max()) / 2
        xs = np.nonzero(diff)[1]
        sides[name] = (xs < mid).sum() / max((xs > mid).sum(), 1)
    assert sides["left"] > 1.5, sides
    assert sides["right"] < 1 / 1.5, sides
