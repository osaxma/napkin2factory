"""v0.4 M5: promotion keeps the napkin's modules; start flat, split for a reason (P10, P11).

A fresh ``n2f init`` product (the blank template: no assembly) gets the card in
``tests/fixtures/concepts/promote-modules/``, built once per module without pictures and
promoted once; tests read copies. Goldens under ``promote-modules-golden/`` are the assembly
files and ``requirements.yaml`` promotion writes; regenerate with ``N2F_PROMOTE_GOLDEN=1``
after an intended change and review the diff. The suggestion-only path runs on a copy of the
kiln, which already has its assemblies (DoD 6).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from napkin2factory.concepts.promote import promote
from napkin2factory.core import concepts as cm
from napkin2factory.core.errors import GateBlocked
from napkin2factory.core.loader import load_product
from napkin2factory.core.model import ConceptCard
from tests.conftest import EXAMPLES, FIXTURES, copy_product, n2f

NOW = dt.datetime(2026, 11, 1, 12, 0, 0)
CARDS = FIXTURES / "concepts" / "promote-modules" / "concepts"
GOLDEN = FIXTURES / "concepts" / "promote-modules-golden"
PRODUCT = "module-kiln"
#: golden file → file in the product
GOLDEN_FILES = {
    f"{PRODUCT}.yaml": f"model/assemblies/{PRODUCT}.yaml",
    "door.yaml": "model/assemblies/door.yaml",
    "controls.yaml": "model/assemblies/controls.yaml",
    "stand.yaml": "model/assemblies/stand.yaml",
    "requirements.yaml": "model/requirements.yaml",
}


@pytest.fixture(scope="module")
def fresh(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A blank ``n2f init`` product with the card built (no pictures), not yet promoted."""
    from napkin2factory.concepts.build import build_concepts

    root = tmp_path_factory.mktemp("fresh") / PRODUCT
    r = n2f("init", str(root), "--name", "Module kiln", "--no-tracking")
    assert r.returncode == 0, r.stderr
    assert not list((root / "model" / "assemblies").glob("*.yaml"))
    shutil.copytree(CARDS, root / "concepts", dirs_exist_ok=True)
    done, errors = build_concepts(root, list(cm.load_concepts(root).values()), render=False)
    assert errors == [] and len(done) == 1
    return root


@pytest.fixture(scope="module")
def promoted(fresh: Path, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Any]:
    """The fresh product after ``promote C-001`` (one promotion shared by the tests)."""
    root = tmp_path_factory.mktemp("promoted") / PRODUCT
    shutil.copytree(fresh, root, ignore=shutil.ignore_patterns("build"))
    result = promote(root, "C-001", now=NOW, snapshot=False)
    return root, result


def _reqs(root: Path) -> list[dict[str, Any]]:
    data: dict[str, Any] = yaml.safe_load((root / "model" / "requirements.yaml").read_text())
    return list(data["requirements"])


def test_promotion_seeds_the_top_assembly_stubs_and_budgets(promoted: tuple[Path, Any]) -> None:
    root, result = promoted
    for name, rel in GOLDEN_FILES.items():
        text = (root / rel).read_text(encoding="utf-8")
        golden = GOLDEN / name
        if os.environ.get("N2F_PROMOTE_GOLDEN") == "1":
            golden.parent.mkdir(parents=True, exist_ok=True)
            golden.write_text(text, encoding="utf-8")
        assert text == golden.read_text(encoding="utf-8"), f"{rel} differs from {golden}"
    model = load_product(root)
    top = model.assemblies[PRODUCT]
    assert [c.uri for c in top.children] == ["asm://door", "asm://controls", "asm://stand"]
    assert model.assemblies["door"].driver == ["built-as-unit", "serviced-as-unit"]
    assert model.assemblies["controls"].driver == [
        "separate-process-or-supplier",
        "tested-as-unit",
    ]
    assert model.assemblies["stand"].driver == []  # named by its line only: no reason given
    assert all(not model.assemblies[m].children for m in ("door", "controls", "stand"))
    assert [a["uri"] for a in result.to_dict()["assemblies"]] == [
        f"asm://{PRODUCT}",
        "asm://door",
        "asm://controls",
        "asm://stand",
    ]
    assert "3 modules: door, controls and stand, each still empty" in result.summary()
    assert "9 about module sizes" in result.summary()
    assert any("body belongs to no module" in n for n in result.notes)
    # the site and form requirements go to the seeded top assembly, not `unallocated`
    by_title = {r["title"]: r for r in _reqs(root)}
    alcove = by_title["Fits the alcove with the door open"]
    assert alcove["verify"]["target"] == f"asm://{PRODUCT}#props.bbox.x"
    assert alcove["allocation"][0] == f"asm://{PRODUCT}"
    assert by_title["Rounded exposed corners"]["allocation"] == [f"asm://{PRODUCT}"]
    assert not any("no assembly yet" in n for n in result.notes)
    # the decision names the structure and links every seeded assembly
    dec = model.decisions[result.dec_id]
    assert "the top assembly module-kiln holds door (built as one unit" in dec.decision
    assert {f"asm://{a}" for a in (PRODUCT, "door", "controls", "stand")} <= {
        str(u) for u in dec.links
    }


def test_three_budgets_per_module_from_the_rough_shapes(promoted: tuple[Path, Any]) -> None:
    root, _ = promoted
    budgets = [r for r in _reqs(root) if r["source"] == "concept C-001 massing"]
    got = {
        r["verify"]["target"]: (r["verify"]["op"], r["verify"]["value"], r["allocation"])
        for r in budgets
    }
    # the massing lines: door 300 × 3 × 300, controls 60 × 120 × 160, a 400 × 400 × 300 frame
    want = {
        "door": ("300 mm", "3 mm", "300 mm"),
        "controls": ("60 mm", "120 mm", "160 mm"),
        "stand": ("400 mm", "400 mm", "300 mm"),
    }
    assert len(budgets) == 9
    for module, values in want.items():
        for axis, value in zip("xyz", values, strict=True):
            assert got[f"asm://{module}#props.bbox.{axis}"] == ("<=", value, [f"asm://{module}"])
    for r in budgets:
        assert "(computed from the rough shapes on C-001)" in r["statement"]
        assert r["verify"]["kind"] == "geometry_prop" and r["priority"] == "must"
        assert "changing a budget is a decision" in r["rationale"]


def test_build_and_check_are_green_with_empty_modules_as_warn(
    promoted: tuple[Path, Any], tmp_path: Path
) -> None:
    root = copy_product(promoted[0], tmp_path / PRODUCT, git=False)
    r = n2f("build", "--no-render", cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    r = n2f("check", "--json", cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    payload = json.loads(r.stdout)
    rows = {row["id"]: row for row in payload["results"]}
    assert payload["summary"]["fail"] == 0
    for module in ("door", "controls", "stand"):
        row = rows[f"rule://general-v0/module-has-parts@{module}"]
        assert row["status"] == "warn" and row["subject"] == f"asm://{module}"
        assert row["message"].endswith(
            "has no parts yet: give it its parts, or fold it into the assembly above it"
        )
        assert f"layout://{module}" not in rows  # nothing to lay out: the rule speaks for it
    assert rows[f"rule://general-v0/module-has-parts@{PRODUCT}"]["status"] == "pass"
    # a budget on an empty stub waits for parts instead of passing at 0 mm
    budget_rows = [row for row in payload["results"] if row.get("kind") == "requirement"]
    door_x = next(
        row
        for row in budget_rows
        if row.get("title") == "The door module fits the width the concept gave it"
    )
    assert door_x["status"] == "skip" and "no parts yet" in door_x["message"]


def test_a_card_without_modules_seeds_no_structure(fresh: Path, tmp_path: Path) -> None:
    root = tmp_path / PRODUCT
    shutil.copytree(fresh, root, ignore=shutil.ignore_patterns("build"))
    path = cm.card_path(root, "C-001")
    data = yaml.safe_load(path.read_text())
    data.pop("modules")
    for call in data["massing"]:
        call.pop("module", None)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    result = promote(root, "C-001", now=NOW, snapshot=False)
    assert result.assemblies == [] and result.suggestion is None
    assert not list((root / "model" / "assemblies").glob("*.yaml"))
    assert any("no assembly yet" in n for n in result.notes)  # as in v0.3 (P14)


def test_a_module_named_like_the_product_is_refused(fresh: Path, tmp_path: Path) -> None:
    root = tmp_path / PRODUCT
    shutil.copytree(fresh, root, ignore=shutil.ignore_patterns("build"))
    path = cm.card_path(root, "C-001")
    path.write_text(path.read_text().replace("module: stand", f"module: {PRODUCT}"))
    before = (root / "model" / "requirements.yaml").read_text()
    with pytest.raises(GateBlocked, match="the product's own name"):
        promote(root, "C-001", now=NOW, snapshot=False)
    assert (root / "model" / "requirements.yaml").read_text() == before
    assert not list((root / "model" / "assemblies").glob("*.yaml"))


# --- the kiln: assemblies exist, so promotion only suggests -----------------------------


def test_promotion_on_the_kiln_only_suggests_modules(tmp_path: Path) -> None:
    from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip

    root = copy_product(EXAMPLES / "kiln", tmp_path / "kiln", git=False)
    card = cm.card_path(root, "C-003")  # rewind the shipped choice, as demo-napkin.sh does
    doc = load_roundtrip(card)
    doc["status"], doc["decision"] = "exploring", None
    dump_roundtrip(card, doc, explicit_null=True)
    decs_path = root / "model" / "decisions.yaml"
    decs = load_roundtrip(decs_path)
    decs["decisions"] = [
        d for d in decs["decisions"] if "concepts/C-003.yaml" not in (d.get("sources") or [])
    ]
    dump_roundtrip(decs_path, decs)
    assemblies = sorted(p.name for p in (root / "model" / "assemblies").glob("*.yaml"))
    texts = {p: p.read_text() for p in (root / "model" / "assemblies").glob("*.yaml")}
    result = promote(root, "C-003", now=NOW, snapshot=False)
    assert sorted(p.name for p in (root / "model" / "assemblies").glob("*.yaml")) == assemblies
    assert {p: p.read_text() for p in texts} == texts
    assert result.assemblies == []
    assert not any(r.about == "budget" for r in result.requirements)
    assert result.suggestion is not None
    assert result.suggestion.startswith(
        "C-003 sketches these modules: door (built as one unit) and controls (made by another "
        "process or supplier). The product already has its assemblies, so nothing was changed"
    )
    assert "door is already a sub-assembly" in result.suggestion
    dec = load_product(root).decisions[result.dec_id]
    assert "suggested, not written" in dec.context
    r = n2f("concept", "lint", cwd=root)
    assert r.returncode == 0 and "worth a look" not in r.stdout.lower(), r.stdout


# --- concept lint and the board -----------------------------------------------------------


def _lint(tmp_path: Path, card: dict[str, Any]) -> list[Any]:
    (tmp_path / "concepts").mkdir()
    base = {"id": "C-001", "title": "t", "massing": []}
    (tmp_path / "concepts" / "C-001.yaml").write_text(yaml.safe_dump({**base, **card}))
    return [p for p in cm.lint_concepts(tmp_path).items if p.rule == "C9-modules"]


def test_lint_warns_on_an_unknown_driver_never_fails(tmp_path: Path) -> None:
    rows = _lint(
        tmp_path,
        {
            "modules": {"door": {"driver": ["built-as-unit", "bolted-on"], "build": "kit"}},
            "massing": [{"kit": "block", "as": "door", "module": "door"}],
        },
    )
    assert [p.severity for p in rows] == ["warn", "warn"]
    assert "'bolted-on' is not a reason a module is built on its own" in rows[0].message
    assert "built-as-unit, tested-as-unit" in rows[0].hint
    assert "build 'kit' is neither unit nor phantom" in rows[1].message


def test_lint_warns_on_modules_lines_and_entries_that_do_not_meet(tmp_path: Path) -> None:
    rows = _lint(
        tmp_path,
        {
            "modules": {"controls": {"driver": ["tested-as-unit"]}},
            "massing": [{"kit": "block", "as": "door", "module": "door"}],
        },
    )
    messages = [p.message for p in rows]
    assert all(p.severity == "warn" for p in rows)
    assert any("module controls: no rough shape belongs to it" in m for m in messages)
    assert any("module door has no entry under modules:" in m for m in messages)


def test_card_schema_reads_modules_and_dumps_a_v03_card_unchanged() -> None:
    card = ConceptCard.model_validate(
        {
            "id": "C-001",
            "title": "t",
            "modules": {"door": {"driver": ["built-as-unit"]}, "trim": None},
            "massing": [
                {"kit": "block", "as": "door", "module": "door"},
                {"kit": "block", "as": "stand", "module": "stand"},
                {"kit": "block", "as": "body"},
            ],
        }
    )
    assert card.module_names() == ["door", "trim", "stand"]
    assert card.module_entry("trim").driver == [] and card.module_entry("stand").build == "unit"
    assert cm.module_words(card) == [
        "door (built as one unit)",
        "trim (no reason given yet)",
        "stand (no reason given yet)",
    ]
    plain = ConceptCard.model_validate({"id": "C-002", "title": "t", "massing": [card.massing[2]]})
    dumped = plain.model_dump(mode="json", by_alias=True)
    assert "modules" not in dumped and "module" not in dumped["massing"][0]


def test_board_lists_each_cards_modules() -> None:
    from napkin2factory.concepts.board import gather, render_board

    data = gather(EXAMPLES / "kiln")
    words = {c["id"]: c["modules"] for c in data["cards"]}
    assert words["C-003"] == [
        "door (built as one unit)",
        "controls (made by another process or supplier)",
    ]
    page = render_board(data)
    assert (
        '<h3>Modules</h3><p class="modules">door (built as one unit); controls (made by '
        "another process or supplier)</p>" in page
    )
