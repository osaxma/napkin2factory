"""scripts/test_lock.py: one test run at a time per clone (S-196)."""

from __future__ import annotations

import fcntl
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/test_lock.py"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("test_lock_script", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def lock_file(tmp_path: Path) -> Path:
    return tmp_path / "n2f-tests.lock"


def _env(lock_file: Path, **extra: str) -> dict[str, str]:
    # this suite itself runs under the lock (make sets N2F_TEST_LOCK_HELD): start clean
    env = {k: v for k, v in os.environ.items() if not k.startswith("N2F_TEST_LOCK")}
    return dict(env, N2F_TEST_LOCK_FILE=str(lock_file), **extra)


def _locked(*cmd: str) -> list[str]:
    return [sys.executable, str(SCRIPT), *cmd]


@pytest.fixture
def held(lock_file: Path) -> Iterator[int]:
    """Another run holding the lock: this test process, from the folder /elsewhere."""
    fd = os.open(lock_file, os.O_RDWR | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)
    os.write(fd, b"/elsewhere/task-x\t4242\t2026-11-04 09:15:00\n")
    try:
        yield fd
    finally:
        os.close(fd)


def _wait_for(path: Path, text: str, seconds: float = 20.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists() and text in path.read_text():
            return
        time.sleep(0.05)
    raise AssertionError(f"{text!r} never appeared in {path}")


def test_exit_code_passes_through(lock_file: Path) -> None:
    done = subprocess.run(
        _locked(sys.executable, "-c", "import sys; sys.exit(7)"), env=_env(lock_file)
    )
    assert done.returncode == 7


def test_a_free_lock_records_who_holds_it(lock_file: Path, tmp_path: Path) -> None:
    probe = "import os; print(os.environ['N2F_TEST_LOCK_HELD'])"
    done = subprocess.run(
        _locked(sys.executable, "-c", probe),
        env=_env(lock_file),
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0 and done.stdout.strip() == "1"
    folder, pid, since = lock_file.read_text().strip().split("\t")
    assert Path(folder).resolve() == tmp_path.resolve() and pid.isdigit() and since


def test_a_busy_lock_waits_and_says_who_holds_it(
    lock_file: Path, held: int, tmp_path: Path
) -> None:
    err = tmp_path / "stderr.txt"
    with err.open("w") as stderr:
        proc = subprocess.Popen(
            _locked(sys.executable, "-c", "print('ran')"),
            env=_env(lock_file),
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
        )
        try:
            _wait_for(err, "Waiting")
            time.sleep(0.3)
            assert proc.poll() is None  # still waiting: the command has not run
            message = err.read_text()
            assert "/elsewhere/task-x" in message and "since 2026-11-04 09:15:00" in message
            fcntl.flock(held, fcntl.LOCK_UN)
            out, _ = proc.communicate(timeout=20)
        finally:
            if proc.poll() is None:
                proc.kill()
    assert proc.returncode == 0 and out.strip() == "ran"
    assert err.read_text().count("Waiting") == 1  # said once


def test_re_entrant_and_switch_off_run_at_once_while_held(lock_file: Path, held: int) -> None:
    quick = (sys.executable, "-c", "pass")
    for extra in ({"N2F_TEST_LOCK_HELD": "1"}, {"N2F_TEST_LOCK": "0"}):
        done = subprocess.run(_locked(*quick), env=_env(lock_file, **extra), timeout=20)
        assert done.returncode == 0


def test_a_nested_call_does_not_wait_for_itself(lock_file: Path) -> None:
    done = subprocess.run(
        _locked(*_locked(sys.executable, "-c", "import sys; sys.exit(3)")),
        env=_env(lock_file),
        timeout=20,
    )
    assert done.returncode == 3


def test_sigterm_reaches_the_command(lock_file: Path) -> None:
    script = "import sys, time; print('ready', flush=True); time.sleep(60)"
    proc = subprocess.Popen(
        _locked(sys.executable, "-c", script),
        env=_env(lock_file),
        stdout=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert proc.stdout and proc.stdout.readline().strip() == "ready"
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=20) == 128 + signal.SIGTERM
    finally:
        if proc.poll() is None:
            proc.kill()


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_the_lock_lives_in_gits_common_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mod = _module()
    monkeypatch.delenv("N2F_TEST_LOCK_FILE", raising=False)
    monkeypatch.chdir(REPO)
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert mod.lock_path() == (REPO / common).resolve() / "n2f-tests.lock"
    outside = tmp_path / "not-a-clone"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    assert mod.lock_path().name == "n2f-tests.lock"
    assert mod.lock_path().parent != (REPO / common).resolve()
