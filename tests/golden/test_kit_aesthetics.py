"""M3 (v0.2): kit aesthetic parameters (N7) reach geometry, and only for parts that opt in.

Goldens live in ``goldens/aesthetics.json``.  The default-is-unchanged guarantee is checked
three ways: the generator goldens in this folder (unchanged), every generator with a style
in the context but no opting-in role (fingerprints identical), and the enclosure example
built with an ``appliance`` style and no roles (``tess_hash`` identical).
"""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pytest

from napkin2factory.core.model.style import StyleFile
from napkin2factory.geometry.kit import GENERATORS, KitContext, run
from tests.conftest import EXAMPLES, copy_product, n2f
from tests.golden.conftest import fingerprint

# Each generator's basic case with every style-touched argument left unset.
UNSET = {
    "plate": {"width": 100, "depth": 80, "thickness": 3, "holes": {"diameter": 6.6}},
    "block": {"length": 200, "width": 100, "height": 50},
    "tube": {"size": 25, "wall": 2, "length": 300},
    "panel": {"width": 400, "height": 300, "thickness": 2},
    "hole_pattern": {
        "plate_width": 120,
        "plate_depth": 100,
        "thickness": 5,
        "diameter": 8,
        "spacing": [80, 60],
    },
    "bracket_l": {"length": 60, "height": 40, "width": 50, "thickness": 2},
    "enclosure": {"length": 200, "width": 120, "height": 80, "thickness": 1.5},
    "frame": {"length": 600, "width": 400, "height": 700, "member": {"size": 30, "wall": 2}},
}
#: A style that changes every shape cue it can.
LOUD = StyleFile.model_validate(
    {
        "preset": "appliance",
        "radius_scale": 2.0,
        "corner_radius": "6 mm",
        "overhang": "20 mm",
        "reveal": "4 mm",
        "vent_pattern": "holes",
    }
).resolved()


def _ctx(style: StyleFile | None = None, role: str | None = None, **kw: object) -> KitContext:
    return KitContext("x", style=style, role=role, **kw)  # type: ignore[arg-type]


def test_every_generator_has_an_unset_case() -> None:
    assert set(UNSET) == set(GENERATORS)


@pytest.mark.parametrize("name", sorted(UNSET))
@pytest.mark.parametrize("role", [None, "lining", "fastener", "default"])
def test_style_without_an_opting_in_role_changes_nothing(name: str, role: str | None) -> None:
    """The opt-in rule: refractory bricks never grow fillets because the shell is rounded."""
    plain = run(name, UNSET[name], _ctx())
    styled = run(name, UNSET[name], _ctx(LOUD, role))
    assert fingerprint(styled) == fingerprint(plain)
    assert styled.notes == plain.notes


@pytest.mark.parametrize("name", sorted(UNSET))
def test_industrial_defaults_change_nothing_even_for_a_body(name: str) -> None:
    """A product without style.yaml gets industrial, whose cues are no-ops."""
    plain = run(name, UNSET[name], _ctx())
    styled = run(name, UNSET[name], _ctx(StyleFile().resolved(), "body"))
    assert fingerprint(styled) == fingerprint(plain)


@pytest.mark.parametrize("name", sorted(UNSET))
def test_massing_ignores_style(name: str) -> None:
    plain = run(name, UNSET[name], _ctx(fidelity="massing"))
    styled = run(name, UNSET[name], _ctx(LOUD, "body", fidelity="massing"))
    assert fingerprint(styled) == fingerprint(plain)


CORNER = StyleFile.model_validate({"corner_radius": "6 mm"}).resolved()


@pytest.mark.parametrize(
    "name, args, height",
    [
        ("plate", {"width": 100, "depth": 80, "thickness": 3}, 3),
        ("panel", {"width": 100, "height": 80, "thickness": 3}, 3),
        ("block", {"length": 100, "width": 80, "height": 30}, 30),
    ],
)
def test_style_corner_radius(check_golden, name: str, args: dict, height: float) -> None:  # type: ignore[no-untyped-def]
    plain = run(name, args, _ctx())
    r = run(name, args, _ctx(CORNER, "door"))
    fp = check_golden("aesthetics", f"{name}-corner-radius-6", r)
    # four vertical edges become four cylinder faces; each corner loses (1 - pi/4) r^2 h
    assert fp["faces"] == len(plain.shape.faces()) + 4
    assert math.isclose(
        plain.shape.volume - r.shape.volume, (4 - math.pi) * 36 * height, rel_tol=1e-3
    )
    # the part's own value wins, even an explicit zero
    explicit = {**args, ("fillet" if name == "block" else "corner_radius"): 0}
    assert fingerprint(run(name, explicit, _ctx(CORNER, "door"))) == fingerprint(plain)


def test_style_chamfer_on_block(check_golden) -> None:  # type: ignore[no-untyped-def]
    style = StyleFile.model_validate({"chamfer": "3 mm"}).resolved()
    args = {"length": 100, "width": 80, "height": 30}
    r = run("block", args, _ctx(style, "controls"))
    fp = check_golden("aesthetics", "block-chamfer-3", r)
    assert fp["faces"] == 26  # 6 faces + 12 edge chamfers + 8 corner triangles
    assert r.shape.volume < 100 * 80 * 30
    # a part with its own fillet keeps it; the style chamfer does not join it
    own = run("block", {**args, "fillet": 5}, _ctx(style, "controls"))
    assert fingerprint(own) == fingerprint(run("block", {**args, "fillet": 5}, _ctx()))


def test_a_style_default_that_does_not_fit_is_skipped_with_a_note() -> None:
    big = StyleFile.model_validate({"corner_radius": "60 mm"}).resolved()
    args = {"width": 100, "height": 80, "thickness": 3}
    r = run("panel", args, _ctx(big, "door"))
    assert fingerprint(r) == fingerprint(run("panel", args, _ctx()))
    assert r.notes and "style corner_radius 60 mm not applied" in r.notes[0]


def test_radius_scale_on_bends() -> None:
    style = StyleFile.model_validate({"radius_scale": 2.0}).resolved()
    enc = run("enclosure", UNSET["enclosure"], _ctx(style, "body"))
    assert enc.features.bends[0].radius == pytest.approx(3.0)  # 1.5 mm × 2
    br = run("bracket_l", UNSET["bracket_l"], _ctx(style, "trim"))
    assert br.features.bends[0].radius == pytest.approx(4.0)
    explicit = {**UNSET["bracket_l"], "bend_radius": 2}
    assert run("bracket_l", explicit, _ctx(style, "trim")).features.bends[0].radius == 2


def test_frame_overhang(check_golden) -> None:  # type: ignore[no-untyped-def]
    args = UNSET["frame"]
    plain = run("frame", args, _ctx())
    r = run("frame", {**args, "overhang": 20}, _ctx())
    fp = check_golden("aesthetics", "frame-overhang-20", r)
    p_bb, bb = plain.shape.bounding_box().size, r.shape.bounding_box().size
    assert bb.X == pytest.approx(p_bb.X + 40, abs=1e-3)
    assert bb.Y == pytest.approx(p_bb.Y + 40, abs=1e-3)
    assert bb.Z == pytest.approx(p_bb.Z, abs=1e-3)
    assert len(r.shape.solids()) == 1, "the ring sits on the legs: one weldment"
    assert fp["features"]["members"] == len(plain.features.members)
    # from the style, for a stand only
    style = StyleFile.model_validate({"overhang": "20 mm"}).resolved()
    assert fingerprint(run("frame", args, _ctx(style, "stand"))) == fp
    # an explicit overhang that cannot sit on the legs fails; a style one is skipped
    with pytest.raises(ValueError, match="size − wall"):
        run("frame", {**args, "overhang": 29}, _ctx())
    big = StyleFile.model_validate({"overhang": "40 mm"}).resolved()
    skipped = run("frame", args, _ctx(big, "stand"))
    assert fingerprint(skipped) == fingerprint(plain) and skipped.notes


@pytest.mark.parametrize("pattern", ["slots", "holes"])
def test_enclosure_vent(check_golden, pattern: str) -> None:  # type: ignore[no-untyped-def]
    args = {
        **UNSET["enclosure"],
        "vent": {"face": "back", "pattern": pattern, "count": 6, "size": 6, "pitch": 15},
    }
    r = run("enclosure", args, _ctx())
    fp = check_golden("aesthetics", f"enclosure-vent-{pattern}", r)
    vents = [c for c in r.features.cutouts if (c.label or "").startswith("vent-")]
    assert len(vents) == 6 and fp["features"]["cutouts"] == 6
    assert {c.face for c in vents} == {"back"}
    assert r.flat_pattern is not None and len(r.flat_pattern.cutouts) == 6
    plain = run("enclosure", UNSET["enclosure"], _ctx())
    assert r.shape.volume < plain.shape.volume
    # flat area × thickness still matches the solid (the vents are real openings)
    assert r.flat_pattern.area < plain.flat_pattern.area


def test_vent_pattern_comes_from_the_style_when_the_vent_names_none() -> None:
    args = {**UNSET["enclosure"], "vent": {"face": "left", "count": 3, "size": 6, "pitch": 15}}
    assert run("enclosure", args, _ctx()).features.cutouts[0].width == 6  # slots
    holes = run("enclosure", args, _ctx(LOUD, "body")).features.cutouts
    assert holes[0].width == holes[0].height == 6
    with pytest.raises(ValueError, match="pitch"):
        run("enclosure", {**args, "vent": {**args["vent"], "pitch": 5}}, _ctx())


@pytest.mark.parametrize("name, height_key", [("panel", "height"), ("plate", "depth")])
def test_fit_to_reveal(name: str, height_key: str) -> None:
    opening = {"fit_to": {"width": 300, "height": 200}, "thickness": 2}

    def size(ctx: KitContext, **extra: object) -> tuple[float, float]:
        bb = run(name, {**opening, **extra}, ctx).shape.bounding_box().size
        return (round(bb.X, 6), round(bb.Y, 6))

    assert size(_ctx()) == (296, 196)  # schema default reveal 2 mm
    assert size(_ctx(LOUD, "door")) == (292, 192)  # the style's 4 mm reveal
    assert size(_ctx(LOUD, "door"), reveal=1) == (298, 198)  # the part's own wins
    assert size(_ctx(LOUD, None)) == (296, 196)  # no role: the style does not apply
    with pytest.raises(ValueError, match="not both"):
        run(name, {**opening, "width": 10}, _ctx())
    with pytest.raises(ValueError, match="fit_to"):
        run(name, {"width": 10, "thickness": 2}, _ctx())
    assert height_key in ("height", "depth")


def _tess_hashes(root: Path) -> dict[str, str]:
    return {
        p.parent.name: json.loads(p.read_text())["tess_hash"]
        for p in (root / "build" / "parts").glob("*/props.json")
    }


def test_enclosure_example_without_roles_ignores_style(tmp_path: Path) -> None:
    """v0.1 products build byte-identical until a part opts in (N7)."""
    plain = copy_product(EXAMPLES / "enclosure", tmp_path / "plain", git=False)
    styled = copy_product(EXAMPLES / "enclosure", tmp_path / "styled", git=False)
    (styled / "style.yaml").write_text(
        "preset: appliance\nradius_scale: 2\ncorner_radius: 8 mm\nreveal: 4 mm\n"
    )
    for root in (plain, styled):
        r = n2f("build", "--target", "geometry", "--no-render", cwd=root)
        assert r.returncode == 0, r.stderr
    assert _tess_hashes(styled) == _tess_hashes(plain)


def test_an_opted_in_part_follows_style_yaml(tmp_path: Path) -> None:
    """A part with a styling role reads style.yaml (a recorded read): edits rebuild it."""
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", git=False)
    lid = root / "model" / "parts" / "lid.yaml"
    lid.write_text(lid.read_text().replace("    corner_radius: 5 mm\n", "") + "role: door\n")
    (root / "style.yaml").write_text("preset: industrial\ncorner_radius: 8 mm\n")

    def build() -> str:
        r = n2f("build", "--no-render", cwd=root)
        assert r.returncode == 0, r.stdout + r.stderr
        return r.stdout

    build()
    first = _tess_hashes(root)
    (root / "style.yaml").write_text("preset: industrial\ncorner_radius: 12 mm\n")
    out = build()
    second = _tess_hashes(root)
    assert "built part:lid (style:geometry" in out and "built part:base" not in out, out
    assert second["lid"] != first["lid"]
    assert {k: v for k, v in second.items() if k != "lid"} == {
        k: v for k, v in first.items() if k != "lid"
    }
    # a palette edit changes no geometry, so no part rebuilds
    (root / "style.yaml").write_text(
        "preset: industrial\ncorner_radius: 12 mm\npalette: {door: '#123456'}\n"
    )
    out = build()
    assert "built part:" not in out, out
    shutil.rmtree(root / "build")
