"""A domain's interface kind is treated by its spec's type (S-144, the seam E4 needs).

A small domain defined here registers ``pass-through``, a kind whose spec subclasses the
core's ``BoltPatternSpec`` (adding ``passes``), with its own check, and ``tag-joint``, a kind
with a plain ``InterfaceSpec``.  The product ``tests/fixtures/products/pass-through``: a box
and a cover (both with geometry) joined by a one-hole pass-through, a bought sleeve with no
shape in a second hole of the box, and a tag joint on the box and the cover.

The pass-through gets everything a ``bolt-pattern`` gets: the hole is cut, the holes are
matched, the joint is lined up in the assembly, then the kind's own check runs and the worse
status wins.  The tag joint is checked by its kind alone, as before.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from napkin2factory.core.checks.interface import check_interface
from napkin2factory.core.domain import Domain, InterfaceKind
from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import Product, load_product, validate
from napkin2factory.core.model.interfaces import BoltPatternSpec, InterfaceSpec
from napkin2factory.core.registry import installed
from napkin2factory.report.builder import _spec_summary
from tests.conftest import FIXTURES, copy_product

PRODUCT = FIXTURES / "products" / "pass-through"


class PassSpec(BoltPatternSpec):
    """A one-hole joint that names what passes through it."""

    passes: list[str] = []


class TagSpec(InterfaceSpec):
    """A plain domain spec: the core cuts and matches nothing."""

    tag: str


def check_pass(product: Product, iface: Any, build_dir: Path) -> dict[str, Any]:
    """The kind's own check: something must pass through."""
    n = len(iface.spec.passes)
    if not n:
        return {"status": "fail", "message": "nothing passes through: name what crosses here"}
    return {
        "status": "pass",
        "message": "1 thing passes through" if n == 1 else f"{n} things pass through",
    }


def check_tag(product: Product, iface: Any, build_dir: Path) -> dict[str, Any]:
    """The plain kind's check."""
    return {"status": "warn", "message": f"tagged {iface.spec.tag}", "parties": {"tag": 1}}


DOMAIN = Domain(
    name="passage",
    title="Pass-through joints (test)",
    root=Path(__file__).resolve().parent,
    interface_kinds=(
        InterfaceKind("pass-through", "Pass-through", spec=PassSpec, check=check_pass),
        InterfaceKind("tag-joint", "Tag joint", spec=TagSpec, check=check_tag),
    ),
)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, Product]]:
    """The product built once (no renders), the test domain registered for the module."""
    with installed(DOMAIN):
        root = copy_product(PRODUCT, tmp_path_factory.mktemp("pt") / "pass-through", git=True)
        product = load_product(root)
        run_build(product, render=False, quiet=True)
        yield root, product


def _features(build: Path, part: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((build / "parts" / part / "features.json").read_text())
    return data


def _copy_build(root: Path, dst: Path) -> Path:
    shutil.copytree(root / "build", dst)
    return dst


def test_the_hole_is_cut_in_both_parties_by_the_specs_type(built: tuple[Path, Product]) -> None:
    root, _ = built
    box, cover = _features(root / "build", "box"), _features(root / "build", "cover")
    box_pats = {p["interface"]: p for p in box["patterns"]}
    assert set(box_pats) == {"iface://box-cover", "iface://box-sleeve"}
    assert box_pats["iface://box-cover"]["diameter"] == pytest.approx(8.0)
    assert box_pats["iface://box-sleeve"]["diameter"] == pytest.approx(12.0)
    assert [p["interface"] for p in cover["patterns"]] == ["iface://box-cover"]
    # the tag joint (a plain spec) cuts nothing
    assert not any(h.get("interface") == "iface://box-tag" for h in box["holes"] + cover["holes"])


def test_the_holes_match_line_up_and_the_kinds_check_runs_after(
    built: tuple[Path, Product],
) -> None:
    root, product = built
    rep = check_interface(product, product.interfaces["box-cover"], root / "build")
    assert rep.status == "pass", rep.message
    assert rep.parties["part://box"]["status"] == "pass"
    assert rep.parties["part://cover"]["status"] == "pass"
    assert rep.alignment["status"] == "pass"
    # the core's words first, then the kind's
    assert rep.message == (
        "the hole lines up on both parts, and in the assembled pass-through kit "
        "(within 0.01 mm); 2 things pass through"
    )
    assert rep.to_dict()["kind_check"] == {
        "status": "pass",
        "message": "2 things pass through",
        "parties": {},
    }


def test_the_rows_in_the_built_checks(built: tuple[Path, Product]) -> None:
    root, _ = built
    rows = {
        r["id"]: r for r in json.loads((root / "build/checks/checks.json").read_text())["results"]
    }
    assert rows["iface://box-cover"]["status"] == "pass"
    assert rows["iface://box-cover"]["evidence"]["alignment"]  # the world frames, as for bolts
    assert rows["iface://box-sleeve"]["message"] == (
        "the hole is cut in box; sleeve has no shape to check it against; 1 thing passes through"
    )
    assert rows["iface://box-tag"]["status"] == "warn"


def test_a_moved_hole_fails_before_the_kinds_check(
    built: tuple[Path, Product], tmp_path: Path
) -> None:
    root, product = built
    build = _copy_build(root, tmp_path / "build")
    feats = _features(build, "cover")
    for p in feats["patterns"]:
        p["centers"] = [[c[0] + 2.0, c[1], c[2]] for c in p["centers"]]
    (build / "parts/cover/features.json").write_text(json.dumps(feats))
    rep = check_interface(product, product.interfaces["box-cover"], build)
    assert rep.status == "fail"
    assert rep.message.startswith("the holes on Box and Cover do not match")
    assert rep.message.endswith("; 2 things pass through")


def test_a_moved_part_fails_the_alignment(built: tuple[Path, Product], tmp_path: Path) -> None:
    root, product = built
    build = _copy_build(root, tmp_path / "build")
    path = build / "assemblies/kit/instances.json"
    rows = json.loads(path.read_text())
    for r in rows:
        if r["uri"] == "part://cover":
            r["translation"][2] += 5.0
    path.write_text(json.dumps(rows))
    rep = check_interface(product, product.interfaces["box-cover"], build)
    assert rep.status == "fail"
    assert rep.alignment["status"] == "fail"
    assert "Box and Cover do not line up" in rep.message
    assert "Move the holes or the parts" in rep.message


def test_the_kinds_failing_check_wins(built: tuple[Path, Product], tmp_path: Path) -> None:
    root, _ = built
    other = copy_product(root, tmp_path / "pass-through", git=False)
    path = other / "model/interfaces/box-cover.yaml"
    path.write_text(path.read_text().replace("passes: [one, two]", "passes: []"))
    product = load_product(other)
    rep = check_interface(product, product.interfaces["box-cover"], root / "build")
    assert rep.status == "fail"
    assert rep.alignment["status"] == "pass"  # the core's part passed
    assert rep.message.startswith("the hole lines up on both parts, and in the assembled")
    assert rep.message.endswith("; nothing passes through: name what crosses here")


def test_a_plain_spec_kind_is_checked_by_its_kind_alone(built: tuple[Path, Product]) -> None:
    root, product = built
    rep = check_interface(product, product.interfaces["box-tag"], root / "build")
    assert rep.to_dict() == {
        "status": "warn",
        "message": "tagged blue",
        "parties": {"tag": 1},
        "alignment": {},
    }


def test_the_report_summarises_the_spec_by_its_type(built: tuple[Path, Product]) -> None:
    root, product = built
    summary = _spec_summary(product.interfaces["box-cover"].spec)
    assert summary.startswith("1 × ⌀8")
    assert summary.endswith(", rect")
    assert _spec_summary(product.interfaces["box-tag"].spec) == "TagSpec"
    html = (root / "build/report/index.html").read_text()
    assert summary in html and "PassSpec" not in html


def test_a_missing_fastener_is_refused_for_a_domain_kind(
    built: tuple[Path, Product], tmp_path: Path
) -> None:
    """The fastener check goes by the spec's type too (the domain is registered by ``built``)."""
    root = copy_product(PRODUCT, tmp_path / "pass-through", git=False)
    path = root / "model/interfaces/box-cover.yaml"
    path.write_text(
        path.read_text().replace("passes: [one, two]", "passes: [one], fastener: part://nut")
    )
    _, problems = validate(root)
    assert any("fastener part://nut is not a part" in str(p) for p in problems.errors), (
        problems.errors
    )
