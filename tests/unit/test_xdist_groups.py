"""The ``xdist_group`` marks keep a module on one worker, or the run stops (S-196).

tests/conftest.py makes pytest-xdist's ``loadgroup`` marks work under pytest 9.2 through a
private pytest API; these tests catch the day an upgrade breaks that.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import (
    ROOT,
    UngroupedTests,
    pytest_collection_modifyitems,
    ungrouped,
    xdist_group_name,
)


@dataclass
class _Mark:
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class _Item:
    nodeid: str
    marks: list[_Mark] = field(default_factory=list)

    def iter_markers(self, name: str) -> list[_Mark]:
        assert name == "xdist_group"
        return self.marks


def test_the_group_name_is_xdists() -> None:
    assert xdist_group_name(_Item("t.py::a")) is None
    assert xdist_group_name(_Item("t.py::a", [_Mark(("t",))])) == "t"
    assert xdist_group_name(_Item("t.py::a", [_Mark(kwargs={"name": "n"})])) == "n"
    assert xdist_group_name(_Item("t.py::a", [_Mark(("b",)), _Mark(("a",))])) == "a_b"


def test_a_marked_test_without_its_suffix_is_named() -> None:
    items = [
        _Item("t.py::plain"),
        _Item("t.py::kept@t", [_Mark(("t",))]),
        _Item("t.py::spread", [_Mark(("t",))]),
    ]
    assert ungrouped(items) == ["t.py::spread"]


def test_a_worker_stops_when_a_marked_test_would_be_spread() -> None:
    worker = SimpleNamespace(option=SimpleNamespace(loadgroup=True), workerinput={})
    items: list[Any] = [_Item("t.py::spread", [_Mark(("t",))])]
    with pytest.raises(UngroupedTests, match="S-196"):
        pytest_collection_modifyitems(worker, items)  # type: ignore[arg-type]
    serial = SimpleNamespace(option=SimpleNamespace(loadgroup=False))
    pytest_collection_modifyitems(serial, items)  # type: ignore[arg-type]


def test_a_marked_module_runs_on_one_worker(tmp_path: Path) -> None:
    """Real pytest and xdist, two workers: every test of the marked module shares one."""
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    tests = "\n".join(
        f"def test_{i}():\n    record()\n" for i in range(6)
    )  # six tests, two workers: unmarked, they would be spread over both
    (tmp_path / "test_grouped.py").write_text(
        "import os, pytest\n"
        'pytestmark = pytest.mark.xdist_group("grouped")\n'
        "def record():\n"
        "    with open('workers.txt', 'a') as f:\n"
        "        f.write(os.environ['PYTEST_XDIST_WORKER'] + '\\n')\n" + tests
    )
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "tests.conftest", "-p", "no:cacheprovider"]
        + ["-n", "2", "--dist", "loadgroup", "-q", "test_grouped.py"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    workers = (tmp_path / "workers.txt").read_text().split()
    assert len(workers) == 6 and len(set(workers)) == 1, workers
