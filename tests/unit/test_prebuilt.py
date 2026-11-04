"""A prebuilt copy (``copy_product(prebuilt=True)``) is a valid build where it lands (S-196).

The suite builds each shared example once per session and hands out copies, build/ included.
That only saves work if the copied build is up to date at its new path: nothing in it may
name the folder it was built in.
"""

from __future__ import annotations

from pathlib import Path

from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES, _prebuilt, copy_product


def test_a_prebuilt_copy_rebuilds_nothing_and_names_no_other_folder(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", prebuilt=True, render=False)
    source = _prebuilt(EXAMPLES / "bracket", "b", git=True, render=False)
    assert source != root and (root / ".git").is_dir()
    assert run_build(load_product(root), render=False, quiet=True)["ran"] == []
    needle = str(source.parent).encode()
    named = [p for p in (root / "build").rglob("*") if p.is_file() and needle in p.read_bytes()]
    assert named == []


def test_a_prebuilt_copy_is_the_tests_own(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", prebuilt=True, render=False)
    (root / "build" / "report").rename(root / "gone")
    again = copy_product(
        EXAMPLES / "bracket", tmp_path / "other" / "b", prebuilt=True, render=False
    )
    assert (again / "build" / "report").is_dir()
