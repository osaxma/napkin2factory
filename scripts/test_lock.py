#!/usr/bin/env python3
"""Run a command while holding this clone's one test-run lock (S-196).

``python3 scripts/test_lock.py CMD...`` runs CMD once no other test run of this clone is
running. Every folder of the clone (the main folder and each task folder) shares one lock
file in git's common directory, so two agents' suites never compete for the same cores: a
contended run takes longer for both and its timings mean nothing. When the lock is busy,
this says once which folder holds it and since when, then waits.

- The lock is an ``fcntl.flock``: the system drops it when the holder exits, even when it
  is killed, so a stale lock cannot block anyone.
- Re-entrant: CMD runs with ``N2F_TEST_LOCK_HELD=1``; with that already set, CMD just runs
  (``make check`` takes the lock once for all its test steps).
- ``N2F_TEST_LOCK=0`` runs CMD without the lock. ``N2F_TEST_LOCK_FILE`` names another lock
  file (the tests of this script use it).
- SIGINT and SIGTERM reach CMD; the exit status is CMD's (128 + n if a signal n ended it).

Standard library only: it runs before ``uv sync`` has made an environment.
"""

from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import FrameType

LOCK_NAME = "n2f-tests.lock"


def lock_path() -> Path:
    """The lock file: in git's common directory, else the system temp directory."""
    override = os.environ.get("N2F_TEST_LOCK_FILE")
    if override:
        return Path(override)
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return Path(tempfile.gettempdir()) / LOCK_NAME
    return (Path.cwd() / out).resolve() / LOCK_NAME


def _holder_line() -> str:
    return f"{os.getcwd()}\t{os.getpid()}\t{time.strftime('%Y-%m-%d %H:%M:%S')}\n"


def _describe(holder: str) -> str:
    parts = holder.strip().split("\t")
    if len(parts) != 3:
        return "another test run"
    folder, pid, since = parts
    return f"the test run in {folder} (process {pid}, since {since})"


def acquire(path: Path) -> int:
    """Take the lock, waiting (and saying so once) while another run holds it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        holder = os.pread(fd, 4096, 0).decode(errors="replace")
        print(
            f"Waiting: {_describe(holder)} is using this machine; "
            "this run starts when it ends (one test run at a time).",
            file=sys.stderr,
            flush=True,
        )
        fcntl.flock(fd, fcntl.LOCK_EX)
    os.ftruncate(fd, 0)
    os.pwrite(fd, _holder_line().encode(), 0)
    return fd


def _in_terminal_foreground() -> bool:
    """True when a Ctrl-C at the terminal reaches the child without our help."""
    try:
        return os.tcgetpgrp(sys.stdin.fileno()) == os.getpgrp()
    except OSError:
        return False


def run(cmd: list[str]) -> int:
    """Run ``cmd`` with the lock held; return its exit status."""
    env = dict(os.environ, N2F_TEST_LOCK_HELD="1")
    child = subprocess.Popen(cmd, env=env)

    def forward(signum: int, _frame: FrameType | None) -> None:
        # The terminal sends Ctrl-C to its whole foreground group, the child included:
        # a second copy would cut short the child's own clean-up.
        if signum == signal.SIGINT and _in_terminal_foreground():
            return
        child.send_signal(signum)

    signal.signal(signal.SIGINT, forward)
    signal.signal(signal.SIGTERM, forward)
    code = child.wait()
    return 128 - code if code < 0 else code


def main(argv: list[str]) -> int:
    """Entry point: ``test_lock.py CMD...``."""
    if not argv:
        print("usage: python3 scripts/test_lock.py CMD...", file=sys.stderr)
        return 2
    if os.environ.get("N2F_TEST_LOCK_HELD") == "1" or os.environ.get("N2F_TEST_LOCK") == "0":
        try:
            os.execvp(argv[0], argv)
        except OSError as exc:
            print(f"test_lock.py: cannot run {argv[0]}: {exc}", file=sys.stderr)
            return 127
    path = lock_path()
    try:
        fd = acquire(path)
    except KeyboardInterrupt:
        return 130
    try:
        return run(argv)
    except OSError as exc:
        print(f"test_lock.py: cannot run {argv[0]}: {exc}", file=sys.stderr)
        return 127
    finally:
        os.close(fd)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
