"""Where the warm engine keeps its files (S-313): always the user's runtime folder."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import uuid
from pathlib import Path

import pytest

from napkin2factory.cli import engine as eng
from tests.conftest import EXAMPLES, EngineGuard, copy_product


def test_the_runtime_folder_is_per_user_and_per_product(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    digest = hashlib.sha256(os.fsencode(os.path.realpath(a))).hexdigest()[:16]
    assert eng.runtime_dir(a) == Path("/tmp") / f"n2f-{os.getuid()}" / digest
    assert eng.runtime_dir(a) != eng.runtime_dir(b)
    assert eng.runtime_dir(a) == eng.runtime_dir(a)  # stable
    for path in (eng.socket_path(a), eng.pid_path(a), eng.lock_path(a), eng.log_path(a)):
        assert path.parent == eng.runtime_dir(a)
        assert tmp_path not in path.parents  # nothing under the product
    assert len(os.fsencode(eng.socket_path(a))) < 60


def test_a_product_under_a_very_deep_path_has_the_same_short_socket(tmp_path: Path) -> None:
    deep = tmp_path / ("d" * 60) / ("e" * 60) / "product"
    deep.mkdir(parents=True)
    assert len(os.fsencode(deep)) > 150
    sock = eng.socket_path(deep)
    assert len(os.fsencode(sock)) <= 100
    assert sock.parent == eng.runtime_dir(deep)


def test_the_runtime_folder_of_a_symlinked_product_is_the_real_ones(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    assert eng.runtime_dir(link) == eng.runtime_dir(real)


def test_a_deep_product_runs_an_engine_with_private_files(
    engines: EngineGuard, tmp_path: Path
) -> None:
    root = copy_product(
        EXAMPLES / "bracket", tmp_path / ("d" * 60) / ("e" * 60) / "bracket", git=False
    )
    pid = engines.start(root)
    assert pid > 0
    folder = eng.runtime_dir(root)
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert stat.S_IMODE(folder.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(eng.socket_path(root).stat().st_mode) == 0o600
    assert eng.pid_path(root).is_file() and eng.lock_path(root).is_file()
    assert str(eng.socket_path(root)) in eng.pid_path(root).read_text()
    assert not (root / "build").exists()  # the engine never makes the product's build folder
    info = eng.engine_status(root)
    assert info is not None and info["socket"] == str(eng.socket_path(root))
    engines.stop_all()
    assert not eng.socket_path(root).exists() and not eng.pid_path(root).exists()


def _fake_home(monkeypatch: pytest.MonkeyPatch, name: str) -> Path:
    """Point the runtime area at a throwaway ``/tmp/n2f-<name>`` (the real one is ``n2f-<uid>``)."""
    base = Path("/tmp") / f"n2f-{name}"
    monkeypatch.setattr(eng, "runtime_dir", lambda root: base / "product")
    return base


def test_a_runtime_folder_open_to_others_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = _fake_home(monkeypatch, f"t{uuid.uuid4().hex[:8]}")
    base.mkdir(mode=0o755)
    os.chmod(base, 0o755)
    try:
        with pytest.raises(PermissionError, match="open to other users"):
            eng.prepare_runtime_dir(tmp_path)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_a_runtime_folder_that_is_a_symbolic_link_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = _fake_home(monkeypatch, f"t{uuid.uuid4().hex[:8]}")
    target = tmp_path / "target"
    target.mkdir()
    base.symlink_to(target)
    try:
        with pytest.raises(PermissionError, match="symbolic link"):
            eng.prepare_runtime_dir(tmp_path)
    finally:
        base.unlink()


def test_the_runtime_folder_is_created_0700(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = _fake_home(monkeypatch, f"t{uuid.uuid4().hex[:8]}")
    try:
        folder = eng.prepare_runtime_dir(tmp_path)
        assert stat.S_IMODE(base.stat().st_mode) == 0o700
        assert stat.S_IMODE(folder.stat().st_mode) == 0o700
        assert eng.prepare_runtime_dir(tmp_path) == folder  # again: fine
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_status_is_the_same_with_no_build_folder_and_with_an_empty_one(tmp_path: Path) -> None:
    """``n2f status`` does not read whether ``build/`` exists; the engine puts nothing in it."""
    from tests.conftest import EXAMPLES, copy_product, n2f

    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket")
    assert not (root / "build").exists()
    bare = [n2f("status", cwd=root), n2f("status", "--json", cwd=root)]
    (root / "build").mkdir()
    empty = [n2f("status", cwd=root), n2f("status", "--json", cwd=root)]
    for before, after in zip(bare, empty, strict=True):
        assert before.returncode == after.returncode
        assert before.stdout == after.stdout
