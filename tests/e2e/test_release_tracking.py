"""M6: release and diff refuse a folder without change tracking, and the advice works (D23).

Split from test_release_diff.py so it runs beside that file's shared release (S-080).
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import EXAMPLES, copy_product
from tests.e2e.test_release_diff import _run


def test_release_requires_project_root(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=False)
    r = _run("release", "v1.0.0", cwd=root, ok=False)
    assert r.returncode == 4 and "n2f init ." in r.stderr
    r = _run("diff", "v1.0.0", "working", cwd=root, ok=False)
    assert r.returncode == 4 and "n2f init ." in r.stderr
    # and the advice works: init on the existing folder sets up tracking (gate-2 B2)
    r = _run("init", ".", cwd=root)
    assert "change tracking set up" in r.stdout
    r = _run("init", ".", cwd=root)
    assert "already has change tracking" in r.stdout
    # the bracket has no safety requirements, so with tracking set up it releases
    r = _run("release", "v1.0.0", "--no-render", cwd=root)
    assert "Revision" in r.stdout and "released" in r.stdout
