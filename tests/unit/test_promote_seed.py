"""Promotion seeds a model that builds (B-0316, S-336).

A block-built bench (``tests/fixtures/concepts/promote-seed/``, a copy of the persona trial's
card under a neutral id) is promoted into a blank product and built once; tests read copies.
The ``structure`` verify kind's plumbing is tested on a card the structural screen covers today
(the table example's tube-legged card), against the card's own screening.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from napkin2factory.concepts.promote import promote
from napkin2factory.core import concepts as cm
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES, FIXTURES, n2f

# the module's shared products are built once, on one worker (S-196)
pytestmark = pytest.mark.xdist_group("test_promote_seed")

NOW = dt.datetime(2026, 11, 8, 12, 0, 0)
BENCH = FIXTURES / "concepts" / "promote-seed" / "concepts"
PRODUCT = "bench"
#: part id -> qty the bench's 14 rough shapes group into
BENCH_PARTS = {"leg": 4, "joist-level": 2, "joist": 3, "rail": 2, "worktop": 2, "shelf": 1}


def _blank(root: Path, name: str) -> Path:
    r = n2f("init", str(root), "--name", name, "--no-tracking")
    assert r.returncode == 0, r.stderr
    return root


def _screened(root: Path) -> None:
    from napkin2factory.concepts.build import build_concepts

    done, errors = build_concepts(root, list(cm.load_concepts(root).values()), render=False)
    assert errors == [] and done


@pytest.fixture(scope="module")
def bench(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Any]:
    """The bench promoted into a blank product and built once (no pictures)."""
    root = _blank(tmp_path_factory.mktemp("bench") / PRODUCT, "Bench")
    shutil.copytree(BENCH, root / "concepts", dirs_exist_ok=True)
    _screened(root)
    result = promote(root, "C-001", now=NOW, snapshot=False)
    r = n2f("build", "--no-render", cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    return root, result


def _copy(src: Path, dst: Path) -> Path:
    shutil.copytree(src, dst, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
    return dst


def _world_boxes(root: Path) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Each built instance's world box by label, from the part's local box and the placement."""
    from napkin2factory.domains.mechanical.structure import _location
    from napkin2factory.geometry.assembly import transform_points

    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    records = json.loads((root / "build/assemblies" / PRODUCT / "instances.json").read_text())
    for rec in records:
        pid = rec["uri"].removeprefix("part://")
        bbox = json.loads((root / "build/parts" / pid / "props.json").read_text())["bbox"]
        (x0, y0, z0), (x1, y1, z1) = bbox["min"], bbox["max"]
        corners = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])
        pts = transform_points(corners, _location(rec["translation"], rec["rotation"]))
        out[rec["label"]] = (pts.min(axis=0), pts.max(axis=0))
    return out


def test_promotion_writes_parts_sizes_and_a_layout(bench: tuple[Path, Any]) -> None:
    root, result = bench
    product = load_product(root)
    assert {pid: p.qty for pid, p in ((s.id, s) for s in result.seed.parts)} == BENCH_PARTS
    assert set(product.parts) == set(BENCH_PARTS)
    top = product.assemblies[PRODUCT]
    assert [(c.part.id, c.qty) for c in top.children if c.part] == list(BENCH_PARTS.items())
    assert top.geometry != "none" and (root / "model/geometry/bench.py").is_file()
    leg = product.parts["leg"]
    assert leg.kind == "custom" and leg.material is not None and leg.cost is None  # no cost (§3)
    assert leg.geometry.args["length"] == "70 mm"  # type: ignore[union-attr]
    # the card's top is 1600 x 800: those envelope numbers drive x and y, the height is new
    assert result.seed.sizes == {"x": "worktop-width", "y": "worktop-depth", "z": "overall-height"}
    assert product.parameters["overall-height"].value == 770
    assert "rough shapes" in (product.parameters["overall-height"].description or "")
    # a part that spans an overall size follows it: its length is that size less its gaps
    assert product.parameters["joist-length"].expr == "worktop-width - joist-length-gap"
    assert float(product.parameter_value("joist-length").to("mm").magnitude) == 1330.0
    assert product.parts["worktop"].geometry.args["length"] == "param://worktop-width"  # type: ignore[union-attr]


def _factors(root: Path) -> dict[str, str]:
    """The structural factors the bench's own screening computed (the screen judges it, B-0317)."""
    card = cm.load_card(root, "C-001")
    assert card.screening is not None
    names = ("yield_factor", "buckling_factor", "tip_over_factor")
    return {k: v.value for k, v in card.screening.computed.items() if k in names}


def test_json_lists_what_was_seeded_and_names_the_build(bench: tuple[Path, Any]) -> None:
    _, result = bench
    data = result.to_dict()
    assert data["next"] == "n2f build"
    seeded = data["seeded"]
    assert seeded["model"] is True and seeded["skipped"] is None
    leg = next(p for p in seeded["parts"] if p["uri"] == "part://leg")
    assert leg["qty"] == 4 and leg["kit"] == "block"
    assert leg["stretched_by"] == ["param://leg-height"]
    assert seeded["overall_sizes"]["z"] == "param://overall-height"
    assert seeded["layout"] == ["model/geometry/bench.py"]
    assert len(seeded["structure_checks"]) == 1 + len(_factors(bench[0]))
    assert any(a["uri"] == "asm://bench" and a["top"] for a in data["assemblies"])
    assert "build next" in data["summary"] and "never the seeded parts" in data["summary"]


def test_every_instance_lands_in_its_rough_shapes_box(bench: tuple[Path, Any]) -> None:
    root, _ = bench
    from napkin2factory.concepts.massing import compose

    card = cm.load_card(root, "C-001")
    want = {
        p.name: (np.array(p.bbox_min), np.array(p.bbox_max))
        for p in compose(card, write=False).pieces
    }
    got = _world_boxes(root)
    assert set(got) == set(want) and len(got) == 14
    for name, (lo, hi) in want.items():
        assert np.allclose(got[name][0], lo, atol=0.1), name
        assert np.allclose(got[name][1], hi, atol=0.1), name


def test_a_longer_bench_moves_the_legs_and_stretches_the_spans(
    bench: tuple[Path, Any], tmp_path: Path
) -> None:
    root = _copy(bench[0], tmp_path / PRODUCT)
    before = _world_boxes(root)
    path = root / "model/parameters.yaml"
    text = path.read_text()
    assert "worktop-width: {value: 1600" in text
    path.write_text(text.replace("worktop-width: {value: 1600", "worktop-width: {value: 1800"))
    r = n2f("build", "--no-render", cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    after = _world_boxes(root)

    def centre_x(box: tuple[np.ndarray, np.ndarray]) -> float:
        return float((box[0][0] + box[1][0]) / 2)

    def length(box: tuple[np.ndarray, np.ndarray]) -> float:
        return float(box[1][0] - box[0][0])

    for leg in ("leg-front-left", "leg-back-left"):
        assert centre_x(before[leg]) == pytest.approx(-700, abs=0.1)
        assert centre_x(after[leg]) == pytest.approx(-800, abs=0.1)
    for leg in ("leg-front-right", "leg-back-right"):
        assert centre_x(after[leg]) == pytest.approx(800, abs=0.1)
    for spans in (
        "worktop",
        "worktop-lower-skin",
        "joist-front",
        "joist-middle",
        "rail-back",
        "shelf",
    ):
        assert length(after[spans]) - length(before[spans]) == pytest.approx(200, abs=0.1), spans
    for kept in ("leg-front-left", "joist-level-left"):  # same size, only moved
        assert length(after[kept]) == pytest.approx(length(before[kept]), abs=0.1)


def test_check_runs_on_the_seeded_model(bench: tuple[Path, Any], tmp_path: Path) -> None:
    root = _copy(bench[0], tmp_path / PRODUCT)
    r = n2f("check", "--json", cwd=root)
    payload = json.loads(r.stdout)
    rows = {row["id"]: row for row in payload["results"]}
    failing = {i for i, row in rows.items() if row["status"] == "fail"}
    # every piece meets the next face to face, so nothing fails and joints are not required
    assert failing == set(), failing
    assert r.returncode == 0, r.stdout[-600:] + r.stderr[-300:]
    assert rows["count://bench"]["status"] == "pass"
    assert rows["req://REQ-001"]["status"] == "pass"  # the width: a real geometry check now
    # the sag requirement reports the card's own screening figure, and one factor requirement
    # exists for every factor the screening computed (yield and buckling; no edge load, no tip-over)
    model = load_product(root)
    card = cm.load_card(root, "C-001")
    assert card.screening is not None
    figure = float(card.screening.computed["deflection"].value.split()[0])
    sag = rows["req://REQ-004"]
    assert model.requirements["REQ-004"].verify.kind == "structure"  # type: ignore[union-attr]
    assert sag["status"] == "pass"
    assert float(re.search(r"deflection = ([0-9.]+)", sag["message"]).group(1)) == pytest.approx(  # type: ignore[union-attr]
        figure, rel=0.01
    )
    factors = _factors(root)
    assert set(factors) >= {"yield_factor", "buckling_factor"}
    for name, text in factors.items():
        req = next(
            r
            for r in model.requirements.values()
            if r.verify and str(r.verify.target or "").endswith(f"#props.{name}")
        )
        row = rows[f"req://{req.id}"]
        assert row["status"] == "pass"
        assert float(row["message"].split("=")[1].split()[0]) == pytest.approx(
            float(text), rel=0.01
        )


def test_an_uncovered_construction_is_never_a_pass(
    bench: tuple[Path, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from napkin2factory.concepts.screens import structural
    from napkin2factory.core.checks.evaluators import EvalContext, evaluate_requirement
    from napkin2factory.core.model.concepts import RuleRow

    root, _ = bench
    why = "not run: this card is a gantry, which the structural check does not model"
    row = RuleRow(id="structural-deflection", status="skip", message=why)
    monkeypatch.setattr(structural, "run", lambda card, massing, values: [row])
    product = load_product(root)
    res = evaluate_requirement(
        EvalContext(product, root / "build"), product.requirements["REQ-004"]
    )
    assert res.status == "needs-human" and why in res.message


def test_a_bench_that_meets_face_to_face_has_no_overlap_note(bench: tuple[Path, Any]) -> None:
    _, result = bench
    assert not any("overlap" in n for n in result.notes)


def test_the_trial_bench_as_drawn_screens_red_on_overlap(tmp_path: Path) -> None:
    """Joists through the level boards and a shelf through the rails: the napkin says so."""
    drawn = FIXTURES / "concepts" / "promote-seed-drawn" / "concepts"
    root = _blank(tmp_path / "drawn", "Drawn")
    shutil.copytree(drawn, root / "concepts", dirs_exist_ok=True)
    _screened(root)
    card = cm.load_card(root, "C-001")
    assert card.screening is not None and card.verdict == "red"
    row = next(r for r in card.screening.rules if r.id == "rough-shapes-overlap")
    assert row.status == "fail" and "8 pair(s)" in row.message
    assert "joist-level-left and joist-" in row.message and "cm³" in row.message
    assert "meet face to face, or make one shorter" in row.message
    # the corrected bench has no such row at all
    root2 = _blank(tmp_path / "fixed", "Fixed")
    shutil.copytree(BENCH, root2 / "concepts", dirs_exist_ok=True)
    _screened(root2)
    fixed = cm.load_card(root2, "C-001")
    assert fixed.screening is not None
    assert "rough-shapes-overlap" not in {r.id for r in fixed.screening.rules}


def test_a_product_with_parts_is_not_seeded(tmp_path: Path) -> None:
    root = _blank(tmp_path / "held", "Held")
    shutil.copytree(BENCH, root / "concepts", dirs_exist_ok=True)
    (root / "model/parts/knob.yaml").write_text(
        "id: knob\nname: Knob\nkind: reference\nnotes: supplied by the owner\n", encoding="utf-8"
    )
    _screened(root)
    result = promote(root, "C-001", now=NOW, snapshot=False)
    assert not result.seed.seeded and "already has parts" in (result.seed.skipped or "")
    assert any("already has parts" in n for n in result.notes)
    assert result.to_dict()["seeded"]["model"] is False
    assert sorted(p.name for p in (root / "model/parts").glob("*.yaml")) == ["knob.yaml"]
    assert not (root / "model/geometry").exists() or not list(
        (root / "model/geometry").glob("*.py")
    )
    assert not list((root / "model/assemblies").glob("*.yaml"))
    reqs = yaml.safe_load((root / "model/requirements.yaml").read_text())["requirements"]
    assert {r["verify"]["kind"] for r in reqs} <= {"geometry_prop", "manual", "bom_rollup", "rule"}
    assert "overall-height" not in (root / "model/parameters.yaml").read_text()


def test_a_turned_part_keeps_its_arguments_and_says_so(tmp_path: Path) -> None:
    from napkin2factory.concepts.promote import plan_modules, plan_seed
    from napkin2factory.core.model import ConceptCard

    root = _blank(tmp_path / "turned", "Turned")
    card = ConceptCard.model_validate(
        {
            "id": "C-001",
            "title": "Turned",
            "massing": [
                {
                    "kit": "block",
                    "as": "top",
                    "material": "plywood",
                    "args": {"length": 800, "width": 400, "height": 20},
                    "at": {"z": 700},
                },
                {
                    "kit": "block",
                    "as": "brace",
                    "material": "plywood",
                    "args": {"length": 600, "width": 40, "height": 40},
                    "at": {"rz": "45 deg"},
                },
            ],
        }
    )
    product = load_product(root)
    notes: list[str] = []
    plan = plan_seed(card, product, [], plan_modules(card, product, notes), notes)
    assert plan.seeded and any("turned 45 degrees" in n for n in notes)
    assert "brace-length" not in "".join(plan.param_lines)  # the turned brace is not stretched
    assert "length: 600" in plan.texts["model/parts/brace.yaml"].replace("'", "")


def test_part_ids_follow_the_longest_common_prefix() -> None:
    from napkin2factory.concepts.promote.seeding import _prefix

    assert _prefix(["leg-front-left", "leg-front-right", "leg-back-left"]) == "leg"
    assert _prefix(["leg-front-left", "leg-front-right"]) == "leg-front"
    assert _prefix(["left-leg", "right-leg"]) == "left-leg"
    assert _prefix(["shelf"]) == "shelf"


@pytest.mark.parametrize("kit", ["block", "plate", "tube", "frame"])
def test_each_stretchable_kit_declares_which_argument_runs_along_which_axis(kit: str) -> None:
    from napkin2factory.geometry import kit as kit_mod

    mod = kit_mod.get_module(kit)
    args = {
        "block": {"length": 1, "width": 1, "height": 1},
        "plate": {"width": 1, "depth": 1, "thickness": 1},
        "tube": {"size": 5, "length": 100, "axis": "y"},
        "frame": {"length": 1, "width": 1, "height": 1, "member": {"size": 1}},
    }[kit]
    axes = mod.size_axes(mod.ARGS.model_validate(args))
    assert axes and set(axes.values()) <= {"x", "y", "z"}
    assert axes == {"tube": {"length": "y"}}.get(kit, axes)


def test_the_structure_kind_reproduces_the_cards_own_screening(tmp_path: Path) -> None:
    """On a card the screen covers today, the built model reports the card's own numbers."""
    root = _blank(tmp_path / "tubes", "Tubes")
    card = yaml.safe_load((EXAMPLES / "table" / "concepts" / "C-001.yaml").read_text())
    for key in ("status", "screening", "decision"):
        card.pop(key, None)
    (root / "concepts").mkdir(exist_ok=True)
    (root / "concepts" / "C-001.yaml").write_text(yaml.safe_dump(card, sort_keys=False))
    _screened(root)
    screened = cm.load_card(root, "C-001")
    assert screened.screening is not None
    computed = {k: v.value for k, v in screened.screening.computed.items()}
    result = promote(
        root, "C-001", override=True, reason="a test of the structure kind", now=NOW, snapshot=False
    )
    r = n2f("build", "--no-render", cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    rows = {
        row["id"]: row
        for row in json.loads(n2f("check", "--json", cwd=root).stdout)["results"]
        if row["id"].startswith("req://")
    }
    structure = {
        r.data["verify"]["target"].split("props.")[1]: rows[f"req://{r.id}"]
        for r in result.requirements
        if r.data["verify"]["kind"] == "structure"
    }
    assert set(structure) == {"deflection", "yield_factor", "buckling_factor", "tip_over_factor"}

    def number(text: str) -> float:
        return float(re.match(r"[-+0-9.eE]+", text).group(0))  # type: ignore[union-attr]

    got = {k: number(v["message"].split("=")[1].strip()) for k, v in structure.items()}
    for measure, value in got.items():
        assert value == pytest.approx(number(computed[measure]), rel=0.01), measure
    # the card sags past its own limit, so the sag requirement fails and the factors pass
    assert structure["deflection"]["status"] == "fail"
    assert {structure[m]["status"] for m in got if m != "deflection"} == {"pass"}
    assert result.to_dict()["seeded"]["structure_checks"] == [
        f"req://{r.id}" for r in result.requirements if r.data["verify"]["kind"] == "structure"
    ]
