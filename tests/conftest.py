"""Shared fixtures: paths to examples, a helper that copies a product, and the CLI runner."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import os
import shutil
import subprocess
import sys
import traceback
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import pytest

# Never spawn the background CAD-kernel warm-up of `n2f init` from the suite (B-0016); the
# subprocess CLI runs inherit this. Tests of the warm-up itself clear it explicitly.
os.environ.setdefault("N2F_NO_WARMUP", "1")

# No warm engine in the suite (S-305): a subprocess CLI run would start a background process per
# product folder. tests/unit/test_engine_*.py opt in with their own fixture and always stop it.
os.environ.setdefault("N2F_NO_ENGINE", "1")

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Let `--dist loadgroup` see the ``xdist_group`` marks under pytest 9 (S-196).

    pytest-xdist 3.8 groups a test by appending ``@<group>`` to ``item._nodeid``, which
    pytest 9.2 no longer reads (an item's id lives in ``item._id``): without this, a marked
    module is spread over the workers and each one builds its shared product again, and
    modules whose tests build on each other fail. A no-op when xdist's write took effect.
    """
    if not getattr(config.option, "loadgroup", False):
        return
    for item in items:
        grouped = vars(item).get("_nodeid")  # where xdist's write lands: Node has __slots__
        if grouped and grouped != item.nodeid:
            from _pytest.nodeid import NodeId  # pytest >= 9.2 only

            item._id = NodeId.parse(grouped)
    if hasattr(config, "workerinput"):  # on a test worker, where xdist wrote the suffixes
        stray = ungrouped(items)
        if stray:
            # Not pytest.UsageError: raised on a worker, xdist swallows its message and shows
            # an unrelated assertion; this one is printed (INTERNALERROR, exit code 3).
            raise UngroupedTests(
                f"{len(stray)} tests marked xdist_group would not stay on one worker under "
                f"--dist loadgroup (first: {stray[0]}). The work-around above for pytest 9.2 "
                "no longer takes effect (S-196): a pytest or pytest-xdist upgrade changed "
                "how a test's id is stored. Fix it, or run with XDIST= (serially)."
            )


class UngroupedTests(RuntimeError):
    """Marked tests would be spread over the workers: their shared product breaks (S-196)."""


def xdist_group_name(item: Any) -> str | None:
    """The group pytest-xdist files ``item`` under (its ``xdist_group`` marks), or None."""
    names = {
        str(m.args[0] if m.args else m.kwargs.get("name", "default"))
        for m in item.iter_markers("xdist_group")
    }
    return "_".join(sorted(names)) if names else None


def ungrouped(items: Iterable[Any]) -> list[str]:
    """Ids of the marked items whose node id does not end in ``@<group>`` (S-196).

    xdist's ``loadgroup`` scheduler keeps tests together only by that suffix; a marked test
    without it is spread over the workers like any other.
    """
    stray = []
    for item in items:
        group = xdist_group_name(item)
        if group is not None and not item.nodeid.endswith(f"@{group}"):
            stray.append(item.nodeid)
    return stray


def is_swiftshader_flake(message: str) -> bool:
    """True for SwiftShader's shader-validation hiccup (B-0024), which is not a page defect.

    Under load the software GL sometimes reports ``THREE.WebGLProgram: Shader Error …
    VALIDATE_STATUS false`` with an empty info log; the same page loads cleanly the next time.
    """
    return (
        "THREE.WebGLProgram: Shader Error" in message
        and "VALIDATE_STATUS false" in message
        and message.rstrip().endswith("Program Info Log:")
    )


def real_page_errors(errors: list[str]) -> list[str]:
    """The page errors that are not the SwiftShader flake (B-0024)."""
    return [e for e in errors if not is_swiftshader_flake(e)]


def copy_product(
    src: Path, dst: Path, git: bool = True, prebuilt: bool = False, render: bool = True
) -> Path:
    """Copy a product directory and optionally start change tracking (D23).

    The copy leaves ``build/`` behind, so the test's first build is a cold one. With
    ``prebuilt=True`` it is a copy of the product already built once in this test session
    (``render`` as the test's own builds use it), ``build/`` included, so the test's first
    build skips what is up to date (S-196). Use it where the test's subject is not the cold
    build: a test that asserts what its first build ran keeps the default.
    """
    if prebuilt:
        shutil.copytree(_prebuilt(src, dst.name, git, render), dst, symlinks=True)
        return dst
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("build", "__pycache__", ".git"))
    if git:
        from napkin2factory.core.vcs import Vcs

        v = Vcs(dst)
        v.init()
        v.snapshot("Start")
    return dst


def copy_kiln_as_designed(dst: Path, git: bool = False) -> Path:
    """A copy of the kiln with the two values its open change request ECR-001 carries put back.

    The upgrade to schema 2 applied ECR-001's edits to the shipped kiln (chamber height
    250 mm, heat-up time 9 h, S-261). Tests that guard the kiln as it was designed (its
    reference numbers, its napkin cards) read it through this, at 200 mm and 7 h.
    """
    from napkin2factory.core.graph.impact import parse_set
    from napkin2factory.core.loader import load_product
    from napkin2factory.ecr.apply import _set_in_yaml

    root = copy_product(EXAMPLES / "kiln", dst, git=git)
    for edit in ("param://chamber-height=200 mm", "param://heat-up-time=7 hour"):
        _set_in_yaml(load_product(root), parse_set(edit))
    return root


_PREBUILT_ROOT: list[Path] = []  # set once per test process by _prebuilt_root


@pytest.fixture(scope="session", autouse=True)
def _prebuilt_root(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Where this session's prebuilt products live: one folder for all its workers (S-196).

    Under xdist each worker's temp root is ``<session temp>/popen-gw<n>``; their parent is
    the session's own, new for every run, so a prebuilt product is never reused across runs
    and is always built by the code under test.
    """
    base = tmp_path_factory.getbasetemp()
    if os.environ.get("PYTEST_XDIST_WORKER"):
        base = base.parent
    _PREBUILT_ROOT[:] = [base / "n2f-prebuilt"]


def _prebuilt(src: Path, name: str, git: bool, render: bool) -> Path:
    """The built copy of ``src`` for this session, building it under a lock if it is the first.

    It is built in a folder called ``name``, the copy's own: a product's name falls back to
    its folder's (vcs.py). Every worker asking for the same (product, name, tracking, renders)
    waits on one file lock; the first builds into a scratch folder and renames it into place,
    so a half-built product is never copied.
    """
    if not _PREBUILT_ROOT:
        raise RuntimeError("copy_product(prebuilt=True) needs the _prebuilt_root fixture")
    root = _PREBUILT_ROOT[0]
    root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{src.resolve()}|{name}|{git}|{render}".encode()).hexdigest()[:16]
    done = root / key / name
    with open(root / f"{key}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not done.is_dir():
            from napkin2factory.core.graph.runner import run_build
            from napkin2factory.core.loader import load_product

            scratch = root / f"{key}.partial"
            shutil.rmtree(scratch, ignore_errors=True)
            built = copy_product(src, scratch / name, git=git)
            run_build(load_product(built), render=render, quiet=True)
            scratch.rename(root / key)
    return done


@pytest.fixture
def bracket(tmp_path: Path) -> Path:
    """A fresh tracked copy of examples/bracket."""
    return copy_product(EXAMPLES / "bracket", tmp_path / "bracket")


@pytest.fixture
def enclosure(tmp_path: Path) -> Path:
    """A fresh tracked copy of examples/enclosure."""
    return copy_product(EXAMPLES / "enclosure", tmp_path / "enclosure")


#: ``N2F_TEST_SUBPROCESS=1`` runs every ``n2f()`` call as a real process (make check-full).
SUBPROCESS_ENV = "N2F_TEST_SUBPROCESS"


def n2f(
    *args: str, cwd: Path | None = None, env: dict[str, str] | None = None, process: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run the CLI with ``args`` in ``cwd``; the result is the process's, whichever way it ran.

    By default the CLI runs inside the test process (S-196): a new process costs about 3 s
    of imports (build123d) per call, and the suite makes hundreds. ``process=True`` (a test
    of the entry point itself) or ``N2F_TEST_SUBPROCESS=1`` (every call, the nightly) runs
    ``python -m napkin2factory.cli`` instead, so coverage and the venv apply as they would.
    """
    full_env = {"PYTHONIOENCODING": "utf-8", "COLUMNS": "200", **(env or {})}
    if process or os.environ.get(SUBPROCESS_ENV) == "1":
        return subprocess.run(
            [sys.executable, "-m", "napkin2factory.cli", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            env={**os.environ, **full_env},
            check=False,
        )
    return _n2f_in_process(list(args), cwd, full_env)


def _n2f_in_process(
    args: list[str], cwd: Path | None, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """``n2f`` inside this process, isolated the way a new process would be (S-196).

    The working folder and every environment variable are restored afterwards (a command may
    set one, as ``build`` sets N2F_OFFLINE). The shared rich consoles are made at import,
    with the width and colours of whatever terminal the test run started in; for the call
    they take ``COLUMNS`` and no colour, as a process writing into a pipe does. An exception
    that escapes the app is printed to stderr, exit code 1, as Python does.
    """
    from typer.testing import CliRunner

    from napkin2factory.cli.app import app
    from napkin2factory.cli.common import console, err_console

    consoles = (console, err_console)
    saved = [(c._width, c._color_system) for c in consoles]
    saved_env = dict(os.environ)
    try:
        for c in consoles:
            c._width = int(env["COLUMNS"])
            c._color_system = None
        with contextlib.chdir(cwd or Path.cwd()):
            result = CliRunner().invoke(app, args, env=env, prog_name="n2f")
    finally:
        for c, (width, colours) in zip(consoles, saved, strict=True):
            c._width, c._color_system = width, colours
        os.environ.clear()
        os.environ.update(saved_env)
    stderr = result.stderr
    if result.exception is not None and not isinstance(result.exception, SystemExit):
        stderr += "".join(traceback.format_exception(result.exception))
    return subprocess.CompletedProcess(["n2f", *args], result.exit_code, result.stdout, stderr)


# --- the warm engine (S-305): tests opt in, and every engine they start is stopped ----------


def engine_processes(root: Path) -> list[str]:
    """Command lines of the engine processes serving ``root`` (empty when none is alive)."""
    out = subprocess.run(
        ["ps", "-axww", "-o", "pid=,stat=,command="], capture_output=True, text=True, check=False
    ).stdout
    real = os.path.realpath(root)
    found = []
    for line in out.splitlines():
        fields = line.split(None, 2)
        if len(fields) == 3 and "napkin2factory.cli.engine" in fields[2] and real in fields[2]:
            if not fields[1].startswith("Z"):  # a finished child not yet reaped is not running
                found.append(line)
    return found


class EngineGuard:
    """Starts engines for a test and makes sure none outlives it (S-291, S-305)."""

    def __init__(self) -> None:
        """No engines yet."""
        self.roots: list[Path] = []
        self.procs: list[subprocess.Popen[bytes]] = []

    def start(self, root: Path, timeout: float = 40.0) -> int:
        """Start the engine of ``root``, wait until it answers, return its process id."""
        import time

        from napkin2factory.cli import engine

        root = Path(os.path.realpath(root))
        if root not in self.roots:
            self.roots.append(root)
        (root / "build").mkdir(exist_ok=True)
        proc = engine.spawn(root)
        if proc is not None:
            self.procs.append(proc)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            info = engine.engine_status(root)
            if info is not None:
                return int(info["pid"])
            time.sleep(0.1)
        raise AssertionError(f"the engine of {root} did not start in {timeout:.0f} s")

    def track(self, root: Path) -> None:
        """Include ``root`` in the final check (an engine a command started by itself)."""
        root = Path(os.path.realpath(root))
        if root not in self.roots:
            self.roots.append(root)

    def stop_all(self) -> None:
        """Stop every engine of this test and assert nothing is left: process, socket, pid file."""
        import time

        from napkin2factory.cli import engine

        for root in self.roots:
            if (root / "build").is_dir():
                engine.stop_engine(root, wait=10.0)
        for proc in self.procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        left = []
        for root in self.roots:
            deadline = time.monotonic() + 5
            while engine_processes(root) and time.monotonic() < deadline:
                time.sleep(0.1)
            if engine_processes(root):
                left.append(f"process for {root}")
            if engine.socket_path(root).exists():
                left.append(f"socket {engine.socket_path(root)}")
            if engine.pid_path(root).exists():
                left.append(f"pid file of {root}")
        self.roots.clear()
        self.procs.clear()
        assert not left, f"an engine was left behind: {left}"


@pytest.fixture
def engines(monkeypatch: pytest.MonkeyPatch) -> Iterator[EngineGuard]:
    """Engines allowed (``N2F_NO_ENGINE`` removed), each one stopped and checked at the end."""
    monkeypatch.delenv("N2F_NO_ENGINE", raising=False)
    guard = EngineGuard()
    yield guard
    guard.stop_all()


@pytest.fixture
def short_product(engines: EngineGuard) -> Iterator[Path]:
    """A bracket model (not built, ``build/`` empty) at a short path: the socket sits in it."""
    import tempfile

    base = Path(os.path.realpath(tempfile.mkdtemp(prefix="n2f-t-", dir="/tmp")))
    root = copy_product(EXAMPLES / "bracket", base / "bracket", git=False)
    (root / "build").mkdir()
    engines.track(root)
    yield root
    engines.stop_all()
    shutil.rmtree(base, ignore_errors=True)
