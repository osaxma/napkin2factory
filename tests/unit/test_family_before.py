"""A rule family can run before a named family (``RuleFamily.before``, S-143).

A domain cannot add an ``after`` to the mechanical families, and the order breaks ties by
installation order, so a family declared ``after=("part",)`` alone lands after ``doc``: a
manual page showing its outputs rendered from the previous build's files.  Here a test-only
domain, the *beacon* (``model/beacon/<id>.yaml`` names a part and a colour; its rule writes
``build/beacon/<id>.json``; its doc helper reads that file and records the rule's output
key), declares ``after=("part",), before=("doc",)``.  Its rules run before every ``doc:``
rule, the ``docs`` target builds them, and a page showing the colour is right after ONE
build, first build and after an edit alike.  Without the domain the order is today's.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from napkin2factory.core.domain import Domain, HelperContext, ModelFamily, RuleFamily
from napkin2factory.core.graph.hashing import sha256_json
from napkin2factory.core.graph.rules import (
    Rule,
    RuleBuild,
    RunContext,
    RunResult,
    build_rules,
    rules_for_target,
)
from napkin2factory.core.graph.runner import explain_build, run_build
from napkin2factory.core.loader import load_product
from napkin2factory.core.model.base import Model, PartUri, Slug
from napkin2factory.core.registry import installed, registry

#: The mechanical families in build order: what every product without a ``before`` gets.
MECHANICAL = ("validate", "part", "asm", "drawing", "bom", "asmsheet", "doc")
CONSUMERS = ("checks", "report", "site")


def _families() -> list[str]:
    """The rule families in build order, the other installed domains' left out."""
    reg = registry()
    return [
        f.name
        for f in reg.rule_families()
        if reg.owner("rule family", f.name).name in ("mechanical", "beacon")
    ]


def _ours(kinds: tuple[str, ...]) -> tuple[str, ...]:
    """A target's rule kinds, the other installed domains' left out."""
    return tuple(k for k in kinds if k in (*MECHANICAL, *CONSUMERS, "beacon"))


class Beacon(Model):
    """A beacon: a name, the part it sits on, and its colour."""

    id: Slug
    name: str
    part: PartUri
    colour: str


def _beacons(product: Any) -> dict[str, Beacon]:
    return dict(product.families.get("beacon", {}))


def _beacon_rules(b: RuleBuild) -> list[Rule]:
    return [
        Rule(
            id=f"beacon:{bid}",
            kind="beacon",
            produces=f"beacon://{bid}",
            inputs={},
            run=_make_run(bid),
            description=f"the colour record of beacon://{bid}",
            depends_on=[f"part:{b_.part.id}"],
        )
        for bid, b_ in sorted(_beacons(b.product).items())
    ]


def _make_run(bid: str) -> Any:
    def run(ctx: RunContext) -> RunResult:
        beacon = ctx.proxy(_beacons(ctx.product)[bid], f"beacon://{bid}")
        record = {"id": bid, "colour": beacon.colour}
        out = ctx.build_dir / "beacon" / f"{bid}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
        return RunResult(reads=[], outputs=[out], output_hash=sha256_json(record))

    return run


def _beacon_helper(h: HelperContext) -> Any:
    """``beacon("widget")`` in a page: the colour the beacon rule wrote (its output key)."""

    def beacon(bid: str) -> str:
        h.log.add(f"beacon://{bid}")  # the rule's output hash: its rerun reruns the page
        path = h.product.paths.build / "beacon" / f"{bid}.json"
        if not path.is_file():
            return "missing"
        return str(json.loads(path.read_text(encoding="utf-8"))["colour"])

    return beacon


def make_domain(root: Path, before: tuple[str, ...] = ("doc",)) -> Domain:
    """The beacon domain; ``before=()`` is the v0.5 contract (the defect S-143 fixes)."""
    return Domain(
        name="beacon",
        root=root,
        families=(ModelFamily("beacon", Beacon, "model/beacon"),),
        rule_families=(
            RuleFamily(
                "beacon",
                _beacon_rules,
                after=("part",),
                before=before,
                produces="beacon://",
                output_dir="beacon",
            ),
        ),
        doc_helpers={"beacon": _beacon_helper},
    )


FILES = {
    "n2f.yaml": """schema: 1
system: '>=0.5,<0.6'
product: {id: beacon-box, name: Beacon box, description: A product with one beacon.}
units: metric
""",
    "operator.yaml": "persona: owner\n",
    "model/parameters.yaml": "parameters: {}\n",
    "model/requirements.yaml": "requirements: []\n",
    "model/decisions.yaml": "decisions: []\n",
    "model/parts/plate.yaml": """id: plate
rev: A
name: Plate
kind: custom
process: machining
material: {name: aluminium, spec: "6082"}
finish: anodised
tolerance_class: ISO2768-m
geometry: {kit: block, args: {length: 60 mm, width: 40 mm, height: 5 mm}}
cost: {unit: 1 USD, basis: estimate}
lead_time: 1 d
""",
    "model/assemblies/box.yaml": """id: box
rev: A
name: Beacon box
children:
  - {part: part://plate, qty: 1}
""",
    "model/beacon/widget.yaml": "id: widget\nname: Widget\npart: part://plate\ncolour: red\n",
    "model/docs/guide.md": """---
id: guide
title: Guide
audience: [owner]
---
# Guide

The beacon on the {{ part("plate").name }} shows {{ beacon("widget") }}.
""",
}


def _write_product(root: Path, with_beacon: bool = True) -> Path:
    for rel, text in FILES.items():
        if rel.startswith("model/beacon") and not with_beacon:
            continue
        if rel == "model/docs/guide.md" and not with_beacon:
            text = text.replace(' shows {{ beacon("widget") }}', "")
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def code_root(tmp_path: Path) -> Path:
    """The beacon domain's package folder (its code hash; one file)."""
    root = tmp_path / "beacon_domain"
    root.mkdir()
    (root / "code.py").write_text("# the beacon domain's code\n", encoding="utf-8")
    return root


@pytest.fixture
def beacon(code_root: Path) -> Iterator[Domain]:
    """The beacon domain registered with ``before=("doc",)``."""
    with installed(make_domain(code_root)) as domain:
        yield domain


def _page(root: Path) -> str:
    return (root / "build/docs/guide/page.md").read_text(encoding="utf-8")


def test_the_family_runs_before_every_doc_rule(beacon: Domain, tmp_path: Path) -> None:
    names = _families()
    assert names == ["validate", "part", "asm", "drawing", "bom", "asmsheet", "beacon", "doc"] + [
        *CONSUMERS
    ]
    product = load_product(_write_product(tmp_path / "p"))
    order = [r.id for r in build_rules(product)]
    docs = [i for i, rid in enumerate(order) if rid.startswith("doc:")]
    assert docs and order.index("part:plate") < order.index("beacon:widget") < min(docs)


def test_the_docs_target_builds_the_family(beacon: Domain, tmp_path: Path) -> None:
    targets = registry().target_kinds()
    assert "beacon" in targets["docs"] and "beacon" in targets["all"]
    assert targets["beacon"] == ("validate", "part", "beacon")
    assert "beacon" not in targets["bom"] and "beacon" not in targets["drawings"]
    product = load_product(_write_product(tmp_path / "p"))
    picked = [r.id for r in rules_for_target(build_rules(product), "docs")]
    assert picked.index("beacon:widget") < picked.index("doc:guide")
    plan = [rid for rid, _, _ in explain_build(product, target="docs")]
    assert "beacon:widget" in plan


def test_a_page_reading_the_family_is_fresh_after_one_build(beacon: Domain, tmp_path: Path) -> None:
    root = _write_product(tmp_path / "p")
    summary = run_build(load_product(root), target="docs", render=False, quiet=True)
    ran = summary["ran"]
    assert ran.index("part:plate") < ran.index("beacon:widget") < ran.index("doc:guide")
    assert "shows red." in _page(root)  # the first build: the file exists when the page renders
    reads = json.loads((root / "build/docs/guide/reads.json").read_text(encoding="utf-8"))
    assert "beacon://widget" in reads["reads"]

    path = root / "model/beacon/widget.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("red", "blue"), encoding="utf-8")
    summary = run_build(load_product(root), render=False, quiet=True)
    ran = summary["ran"]
    assert ran.index("beacon:widget") < ran.index("doc:guide")
    assert "shows blue." in _page(root)  # the same build, not the next one

    again = run_build(load_product(root), render=False, quiet=True)
    assert not [r for r in again["ran"] if r.startswith(("beacon:", "doc:"))]


def test_without_before_the_family_runs_after_doc(code_root: Path, tmp_path: Path) -> None:
    """The v0.5 defect, kept as a control: ``after`` alone puts the family after ``doc``."""
    with installed(make_domain(code_root, before=())):
        names = [f.name for f in registry().rule_families()]
        assert names.index("beacon") > names.index("doc")
        assert "beacon" not in registry().target_kinds()["docs"]
        root = _write_product(tmp_path / "p")
        run_build(load_product(root), target="beacon", render=False, quiet=True)
        run_build(load_product(root), target="docs", render=False, quiet=True)
        assert "shows red." in _page(root)
        path = root / "model/beacon/widget.yaml"
        path.write_text(path.read_text(encoding="utf-8").replace("red", "blue"), encoding="utf-8")
        run_build(load_product(root), render=False, quiet=True)
        assert "shows red." in _page(root)  # stale: the page rendered before the rule ran


def test_a_before_cycle_names_both_families(code_root: Path) -> None:
    domain = make_domain(code_root)
    looped = Domain(
        name="beacon",
        root=code_root,
        rule_families=(RuleFamily("beacon", _beacon_rules, after=("doc",), before=("part",)),),
    )
    with installed(looped), pytest.raises(ValueError, match="wait for each other") as err:
        registry().rule_families()
    assert "beacon" in str(err.value) and "part" in str(err.value)
    # a reads_all family waits for every producer, so it cannot run before one
    late = Domain(
        name="beacon",
        root=code_root,
        rule_families=(RuleFamily("beacon", _beacon_rules, before=("doc",), reads_all=True),),
    )
    with installed(late), pytest.raises(ValueError, match="wait for each other") as err:
        registry().rule_families()
    assert "beacon" in str(err.value) and "doc" in str(err.value)
    with installed(domain):  # the registry is usable again once they are gone
        assert "beacon" in [f.name for f in registry().rule_families()]


def test_a_before_naming_a_reader_of_all_or_nothing_installed_changes_nothing(
    code_root: Path,
) -> None:
    with installed(make_domain(code_root, before=())):
        plain = [f.name for f in registry().rule_families()]
        plain_targets = registry().target_kinds()
    with installed(make_domain(code_root, before=("checks", "not-installed"))):
        assert [f.name for f in registry().rule_families()] == plain
        assert registry().target_kinds() == plain_targets


def test_a_product_without_such_a_family_builds_in_todays_order(tmp_path: Path) -> None:
    assert _families() == [*MECHANICAL, *CONSUMERS]
    targets = registry().target_kinds()
    assert _ours(targets["docs"]) == ("validate", "part", "asm", "bom", "doc")
    assert _ours(targets["bom"]) == ("validate", "part", "asm", "bom")
    root = _write_product(tmp_path / "p", with_beacon=False)
    product = load_product(root)
    kinds = [r.kind for r in build_rules(product)]
    assert list(dict.fromkeys(kinds)) == [*MECHANICAL, *CONSUMERS]
    summary = run_build(product, target="docs", render=False, quiet=True)
    ran = list(dict.fromkeys(r.split(":", 1)[0] for r in summary["ran"]))
    assert ran == ["validate", "part", "asm", "bom", "doc"]
