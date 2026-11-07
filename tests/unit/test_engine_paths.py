"""Where the warm engine's socket lives (S-305): in the product when it fits, else in /tmp."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import uuid
from pathlib import Path

import pytest

from napkin2factory.cli import engine as eng
from tests.conftest import EngineGuard


def test_a_short_product_path_keeps_the_socket_in_the_product(short_product: Path) -> None:
    sock = eng.socket_path(short_product)
    assert sock == Path(os.path.realpath(short_product)) / "build" / ".n2f" / "engine.sock"
    assert len(os.fsencode(sock)) <= eng.SOCKET_BYTES
    assert eng.pid_path(short_product).parent == sock.parent


def test_a_long_product_path_gets_a_hashed_socket_in_tmp(tmp_path: Path) -> None:
    deep = tmp_path / ("d" * 40) / ("e" * 40) / "product"
    deep.mkdir(parents=True)
    sock = eng.socket_path(deep)
    digest = hashlib.sha256(os.fsencode(os.path.realpath(deep))).hexdigest()[:16]
    assert sock == Path("/tmp") / f"n2f-{os.getuid()}" / f"{digest}.sock"
    assert len(os.fsencode(sock)) <= eng.SOCKET_BYTES
    # the pid file and lock stay beside the product either way
    assert eng.pid_path(deep) == Path(deep) / "build" / ".n2f" / "engine.pid"
    assert eng.lock_path(deep).parent == eng.pid_path(deep).parent
    assert eng.socket_path(deep) == sock  # stable


def test_the_socket_path_of_a_symlinked_product_is_the_real_one(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    assert eng.socket_path(link) == eng.socket_path(real)


def test_a_long_path_engine_runs_and_uses_the_tmp_socket(
    engines: EngineGuard, tmp_path: Path
) -> None:
    from tests.conftest import EXAMPLES, copy_product

    root = copy_product(
        EXAMPLES / "bracket", tmp_path / ("d" * 40) / ("e" * 40) / "bracket", git=False
    )
    sock = eng.socket_path(root)
    assert sock.parent.parent == Path("/tmp")
    pid = engines.start(root)
    assert pid > 0
    assert stat.S_IMODE(sock.stat().st_mode) == 0o600
    assert stat.S_IMODE(sock.parent.stat().st_mode) == 0o700
    assert eng.pid_path(root).is_file()
    assert str(sock) in eng.pid_path(root).read_text()
    info = eng.engine_status(root)
    assert info is not None and info["socket"] == str(sock)
    engines.stop_all()
    assert not sock.exists() and not eng.pid_path(root).exists()


def test_a_socket_folder_open_to_others_is_refused() -> None:
    # the rule applies to /tmp/n2f-<uid>, the folder the engine makes itself
    shared = Path("/tmp") / f"n2f-{uuid.uuid4().hex[:8]}"
    shared.mkdir(mode=0o755)
    os.chmod(shared, 0o755)
    try:
        with pytest.raises(PermissionError, match="open to other users"):
            eng.prepare_socket_dir(shared / "x.sock")
    finally:
        shutil.rmtree(shared, ignore_errors=True)


def test_a_socket_folder_that_is_a_symbolic_link_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = Path("/tmp") / f"n2f-{uuid.uuid4().hex[:8]}"
    link.symlink_to(target)
    try:
        with pytest.raises(PermissionError, match="symbolic link"):
            eng.prepare_socket_dir(link / "x.sock")
    finally:
        link.unlink()


def test_the_folder_is_created_0700(tmp_path: Path) -> None:
    sock = Path("/tmp") / f"n2f-{uuid.uuid4().hex[:8]}" / "x.sock"
    try:
        eng.prepare_socket_dir(sock)
        assert stat.S_IMODE(sock.parent.stat().st_mode) == 0o700
        eng.prepare_socket_dir(sock)  # again: fine
    finally:
        shutil.rmtree(sock.parent, ignore_errors=True)
