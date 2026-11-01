"""Gate E B1, B4 and C7 (S-138): the build graph stays honest.

B1: rules record some objects whole (``iface://x``, ``dec://DEC-xxx``, ``calc://m.f``), and an
edit names a field of one (``iface://x#spec.depth``).  Impact must still name every rule the
build would rerun.  Each test predicts with :func:`compute_impact` before the edit, makes the
edit in the file, and compares with :func:`explain_build`, the build's own dry run (a superset
of what a build reruns: it assumes every upstream rerun changes its output).  The kiln is built
once, without renders (about 40 s on the reference host).

B4: the core's open-set tables (``core/data/*.yaml``) are inputs of the rules that read them,
so editing the driver words reruns every output that prints them.

C7: a ``--set`` that is not a valid edit is a plain error, never a traceback.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from napkin2factory.cli.app import app
from napkin2factory.core import registry as registry_mod
from napkin2factory.core.errors import N2FError
from napkin2factory.core.graph.impact import compute_impact, parse_set
from napkin2factory.core.graph.rules import build_rules
from napkin2factory.core.graph.runner import explain_build, run_build
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES, copy_product


@pytest.fixture(scope="module")
def kiln(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """A copy of the kiln built once without renders."""
    root = copy_product(EXAMPLES / "kiln", tmp_path_factory.mktemp("impact") / "kiln", git=False)
    run_build(load_product(root), render=False, quiet=True)
    yield root


def _would_run(root: Path) -> set[str]:
    return {rid for rid, run, _ in explain_build(load_product(root), render=False) if run}


def _predict_then_edit(root: Path, uri_value: str, file: Path, old: str, new: str) -> Any:
    """Impact of ``uri_value`` on the built product, then the same edit made in ``file``."""
    report = compute_impact(load_product(root), [parse_set(uri_value)])
    text = file.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    file.write_text(text.replace(old, new), encoding="utf-8")
    return report


def test_an_interface_field_edit_names_every_rule_the_rebuild_runs(kiln: Path) -> None:
    """The parts read ``iface://door-guard-standoff`` whole; the edit names ``#spec.depth``."""
    file = kiln / "model/interfaces/door-guard-standoff.yaml"
    text = file.read_text(encoding="utf-8")
    try:
        report = _predict_then_edit(
            kiln,
            "iface://door-guard-standoff#spec.depth=12 mm",
            file,
            "depth: 10 mm",
            "depth: 12 mm",
        )
        will = _would_run(kiln)
        assert {"part:door-tray", "part:door-guard", "checks"} <= will  # the edit is real
        assert will <= set(report.rules), sorted(will - set(report.rules))
        assert {"door-tray", "door-guard"} <= set(report.parts)
    finally:
        file.write_text(text, encoding="utf-8")


def test_a_decided_choice_field_edit_names_the_checks(kiln: Path) -> None:
    """The checks read a decided choice's ``dec://DEC-xxx`` whole; the edit names a field."""
    from napkin2factory.core.checks.choices import append_decision, decision_entry

    product = load_product(kiln)
    rows = json.loads((kiln / "build/checks/checks.json").read_text())["results"]
    row = next(r for r in rows if r["status"] == "choice")
    entry = decision_entry(product, row, row["detail"]["options"][0]["id"], "a tester", "note one")
    file = product.paths.decisions
    text = file.read_text(encoding="utf-8")
    try:
        append_decision(file, entry)
        run_build(load_product(kiln), render=False, quiet=True)
        assert (
            f"dec://{entry['id']}"
            in json.loads((kiln / "build/.n2f/manifest.json").read_text())["entries"]["checks"][
                "reads"
            ]
        )
        report = _predict_then_edit(
            kiln, f"dec://{entry['id']}#rationale=note two", file, "note one", "note two"
        )
        will = _would_run(kiln)
        assert "checks" in will
        assert will <= set(report.rules), sorted(will - set(report.rules))
    finally:
        file.write_text(text, encoding="utf-8")
        run_build(load_product(kiln), render=False, quiet=True)


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("manifest://scope=x", "needs a selector"),
        ("calc://power", "--set expects <uri>=<value>"),
        ("nonsense=3", "nonsense"),
        ("part://No Such#name=x", "part://No Such"),
    ],
)
def test_a_bad_set_is_a_plain_error(text: str, said: str) -> None:
    """C7: the error names the edit and what is wrong with it (an N2FError, so the CLI says it)."""
    with pytest.raises(N2FError) as err:
        parse_set(text)
    assert said in str(err.value) and "Traceback" not in str(err.value)


def test_a_bad_set_on_the_command_line_prints_no_traceback(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    result = CliRunner().invoke(
        app, ["impact", "-C", str(root), "--set", "manifest://scope=x"], env={"COLUMNS": "200"}
    )
    assert result.exit_code == 1, result.output
    assert "needs a selector" in result.output
    assert "Traceback" not in result.output and not isinstance(result.exception, ValueError)


# ---- B4: the core's tables are inputs ---------------------------------------------------------


def _edited_tables(tmp_path: Path, name: str, old: str, new: str) -> Path:
    """A copy of ``core/data`` with one table edited."""
    data = tmp_path / "data"
    shutil.copytree(registry_mod.DATA, data)
    table = data / f"{name}.yaml"
    text = table.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    table.write_text(text.replace(old, new), encoding="utf-8")
    return data


DRIVER_WORDS = "serviced or replaced as one unit"


def test_editing_the_driver_words_reruns_every_output_that_prints_them(
    kiln: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = json.loads((kiln / "build/.n2f/manifest.json").read_text())["entries"]
    printing = {
        rid
        for rid, entry in entries.items()
        for rel in entry["outputs"]
        if DRIVER_WORDS.encode() in (kiln / "build" / rel).read_bytes()
    }
    assert {"bom", "asmsheet:door", "doc:assembly", "report", "site"} <= printing
    data = _edited_tables(tmp_path, "drivers", DRIVER_WORDS, "lifted off and swapped whole")
    monkeypatch.setattr(registry_mod, "DATA", data)
    will = _would_run(kiln)
    assert printing <= will, sorted(printing - will)
    assert not {r for r in will if r.startswith(("part:", "asm:", "drawing:"))}


@pytest.mark.parametrize(
    ("table", "old", "new", "moves"),
    [
        ("drivers", DRIVER_WORDS, "lifted off and swapped whole", {"validate", "bom"}),
        (
            "style_roles",
            '{id: opening, words: "a door, lid or hatch", styled: true',
            '{id: opening, words: "a door, lid or hatch", styled: false',
            {"validate", "checks", "report", "roles"},
        ),
        ("processes", "Sheet metal", "Sheet-metal work", {"validate", "checks"}),
    ],
)
def test_a_table_edit_moves_the_keys_of_the_rules_that_read_it(
    table: str, old: str, new: str, moves: set[str], tmp_path: Path
) -> None:
    """Exactly the rules reading the table move: ``roles`` stands for every part with a role."""
    product = load_product(EXAMPLES / "kiln")
    before = {r.id: dict(r.inputs) for r in build_rules(product, render=False)}
    data = _edited_tables(tmp_path, table, old, new)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(registry_mod, "DATA", data)
        registry_mod._style_roles_table.cache_clear()
        try:
            after = {r.id: dict(r.inputs) for r in build_rules(product, render=False)}
        finally:
            registry_mod._style_roles_table.cache_clear()
    roles = {f"part:{p.id}" for p in product.parts_with_geometry() if p.role}
    assert roles  # the kiln names roles, so the style-role case is not empty
    expected = (moves - {"roles"}) | (roles if "roles" in moves else set())
    assert {rid for rid in before if before[rid] != after[rid]} == expected
