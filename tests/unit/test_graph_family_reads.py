"""The build graph's reads of a domain's family listing and of an interface's fields.

v0.5 defects found during v0.6 wave 2: a family had no membership key, so a file added to it
reran nothing that listed it (B-0140, S-165); an interface field read was valued as the whole
joint, which ``n2f impact`` does not match (B-0136, S-166); a ``rule:<x>`` key no rule
answers read "unbuilt" forever (B-0135, S-167).  The tally domain
(``tests/fixtures/domains/tally/``) lists its family the plain way and reads one field of the
toy product's joint; the toy domain is installed for the toy product.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest

from napkin2factory.core import registry as registry_mod
from napkin2factory.core.domain import Domain, ModelFamily, RuleFamily
from napkin2factory.core.errors import N2FError
from napkin2factory.core.graph.impact import compute_impact, parse_set
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.graph.recording import Members, recording_into
from napkin2factory.core.graph.rules import Rule, RunResult, build_rules
from napkin2factory.core.graph.runner import explain_build, run_build
from napkin2factory.core.graph.values import value_of
from napkin2factory.core.loader import load_product
from napkin2factory.core.registry import installed
from tests.conftest import FIXTURES, copy_product
from tests.fixtures.domains import tally, toy

A = "id: a\nname: First\ncount: 2\n"
B = "id: b\nname: Second\ncount: 3\n"
PAGE = "---\nid: folder\ntitle: Folder\naudience: [owner]\n---\n\nBuilt in {{ tally_folder() }}.\n"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """The toy product with one tally, built once with the toy and tally domains installed."""
    with ExitStack() as stack:
        stack.enter_context(installed(toy.DOMAIN))
        stack.enter_context(installed(tally.DOMAIN))
        root = copy_product(FIXTURES / "products" / "toy", tmp_path_factory.mktemp("t") / "toy")
        (root / "model/tally").mkdir()
        (root / "model/tally/a.yaml").write_text(A)
        (root / "model/docs/folder.md").write_text(PAGE)
        run_build(load_product(root), render=False, quiet=True)
        yield root


def _rows(root: Path) -> set[str]:
    data = json.loads((root / "build/checks/checks.json").read_text())
    return {r["id"] for r in data["results"] if r["kind"] == "tally"}


def _total(root: Path) -> int:
    total: int = json.loads((root / "build/tally/sum.json").read_text())["total"]
    return total


def test_listing_a_family_records_its_membership_key(built: Path) -> None:
    entries = Manifest.load(built / "build").entries
    assert "set://tally" in entries["checks"].reads  # the tally stage listed it
    # the domain's own rules record no listing of its families: they hold the ids as an input
    assert "set://tally" not in entries["tally:sum"].reads
    assert "ids" in entries["tally:sum"].inputs


def test_adding_a_file_reruns_what_lists_the_family_in_one_build(built: Path) -> None:
    product = load_product(built)
    report = compute_impact(product, [parse_set("tally://b#count=3")])
    assert "set://tally" in report.edited_keys
    (built / "model/tally/b.yaml").write_text(B)
    try:
        product = load_product(built)
        will = {rid for rid, run, _ in explain_build(product, render=False) if run}
        ran = set(run_build(product, render=False, quiet=True)["ran"])
        assert {"tally:sum", "checks"} <= ran
        assert ran <= will
        assert ran <= set(report.rules), sorted(ran - set(report.rules))  # impact ⊇ rebuild
        assert _rows(built) == {"tally://a", "tally://b"}
        assert _total(built) == 5
    finally:
        (built / "model/tally/b.yaml").unlink(missing_ok=True)
        run_build(load_product(built), render=False, quiet=True)
    assert _rows(built) == {"tally://a"}  # removing it reruns them too, in one build
    assert _total(built) == 2


def test_removing_the_last_file_reruns_what_lists_the_family(built: Path) -> None:
    (built / "model/tally/a.yaml").unlink()
    try:
        ran = set(run_build(load_product(built), render=False, quiet=True)["ran"])
        assert {"tally:sum", "checks"} <= ran
        assert _rows(built) == set()
        assert _total(built) == 0
    finally:
        (built / "model/tally/a.yaml").write_text(A)
        run_build(load_product(built), render=False, quiet=True)
    assert _rows(built) == {"tally://a"}


def test_an_existing_object_edit_does_not_touch_the_membership_key(built: Path) -> None:
    report = compute_impact(load_product(built), [parse_set("tally://a#count=4")])
    assert "set://tally" not in report.edited_keys
    assert "tally:sum" in report.rules


@pytest.mark.parametrize(
    ("uri", "old", "new", "joint_reruns"),
    [
        ("iface://plate-peg#spec.snap=loose", "snap: firm", "snap: loose", True),
        (
            "iface://plate-peg#description=a peg",
            "spec: {snap: firm}",
            "spec: {snap: firm}\ndescription: a peg",
            False,
        ),
    ],
)
def test_an_interface_field_read_is_valued_by_its_field(
    built: Path, uri: str, old: str, new: str, joint_reruns: bool
) -> None:
    """Impact ⊇ rebuild for an edit of the field read and of another field (B-0136)."""
    file = built / "model/interfaces/plate-peg.yaml"
    text = file.read_text()
    report = compute_impact(load_product(built), [parse_set(uri)])
    try:
        assert text.count(old) == 1
        file.write_text(text.replace(old, new))
        ran = set(run_build(load_product(built), render=False, quiet=True)["ran"])
        assert ran <= set(report.rules), sorted(ran - set(report.rules))
        assert ("tally:joint" in ran) is joint_reruns
        assert ("tally:joint" in report.rules) is joint_reruns
    finally:
        file.write_text(text)
        run_build(load_product(built), render=False, quiet=True)


def test_the_membership_value_follows_the_ids(built: Path) -> None:
    product = load_product(built)
    manifest = Manifest.load(built / "build")
    before = value_of(product, manifest, built / "build", "set://tally")
    edited = value_of(product, manifest, built / "build", "tally://a#count")
    assert edited == "2"
    assert value_of(product, manifest, built / "build", "set://nonesuch").startswith("unknown")
    (built / "model/tally/b.yaml").write_text(B)
    try:
        after = value_of(load_product(built), manifest, built / "build", "set://tally")
    finally:
        (built / "model/tally/b.yaml").unlink()
    assert after != before


def test_members_record_only_inside_a_run() -> None:
    class Log:
        def __init__(self) -> None:
            self.keys: list[str] = []

        def add(self, key: str) -> None:
            self.keys.append(key)

    m = Members("tally", {"a": 1})
    log = Log()
    assert dict(m) == {"a": 1} and "a" in m  # outside a run: nothing to record into
    uses: list[Any] = [
        lambda: dict(m),
        lambda: list(m),
        lambda: len(m),
        lambda: "a" in m,
        lambda: m.get("z"),
        lambda: m["a"],
        lambda: sorted(m.items()),
        lambda: list(m.values()),
        lambda: m.copy(),
    ]
    for use in uses:
        log.keys.clear()
        with recording_into(log):
            use()
        assert log.keys and set(log.keys) == {"set://tally"}
    log.keys.clear()
    with recording_into(log):
        assert dict.__contains__(m, "a")  # the core's own lookups record nothing
    with recording_into(log, skip=frozenset({"tally"})):
        assert list(m) == ["a"]  # a rule of the family's own domain records nothing
    assert log.keys == []


def test_a_family_named_like_a_system_set_is_refused() -> None:
    clash = Domain(name="clash", families=(ModelFamily("parts", schema=tally.Tally, folder="x"),))
    with pytest.raises(ValueError, match="model family 'parts', a name the system's own sets"):
        registry_mod.register(clash)
    assert "clash" not in [d.name for d in registry_mod.registry().domains]


def test_a_rule_key_no_rule_answers_is_refused(built: Path) -> None:
    """B-0135: ``rule:<x>`` is rule ``<x>``'s output; a key with no such rule never changes."""

    def rules(_: Any) -> list[Rule]:
        def run(ctx: Any) -> RunResult:
            return RunResult(reads=[], outputs=[], output_hash="")

        return [Rule(id="skew:_all", kind="skew", produces="rule:skew-all", inputs={}, run=run)]

    skew = Domain(name="skew", root=tally.ROOT, rule_families=(RuleFamily("skew", rules),))
    with installed(skew):
        with pytest.raises(N2FError, match="rule family 'skew': rule 'skew:_all' produces"):
            build_rules(load_product(built))


def test_a_doc_helper_sees_the_build_folder_the_rule_ran_with(built: Path, tmp_path: Path) -> None:
    """B-0147: the docs rule hands its own build folder to the helpers (``h.build_dir``)."""
    assert "Built in build." in (built / "build/docs/folder/page.md").read_text()
    elsewhere = tmp_path / "elsewhere"
    run_build(load_product(built), target="docs", render=False, quiet=True, build_dir=elsewhere)
    assert "Built in elsewhere." in (elsewhere / "docs/folder/page.md").read_text()
