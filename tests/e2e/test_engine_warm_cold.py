"""A command gives the same stdout, stderr and exit code through the warm engine as cold (S-310).

The engine runs the CLI's own command in a long-lived process; this is the test that it does so
without leaking one request into the next: a fixed list of commands (read-only or idempotent, one
failing, one with ``--json``) runs in a fresh process (``N2F_NO_ENGINE=1``) and through a
started engine, and the three streams are compared.
"""

from __future__ import annotations

import io
import json
import os
import re
import signal
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

from napkin2factory.cli import engine as eng
from napkin2factory.cli.kernel import KERNEL_NOTE
from tests.conftest import EXAMPLES, EngineGuard, copy_product, engine_processes, n2f

COMMANDS: list[list[str]] = [
    ["status"],
    ["status", "--json"],
    ["check"],
    ["validate"],
    ["graph", "--format", "json"],
    ["build", "--offline"],
    ["check", "--scope", "asm://nope"],  # fails: exit 1 and a ✗ line
    ["build", "--no-such-option"],  # a usage error: exit 2 and click's own message
    ["check", "--scope", "asm://nope", "--json"],  # the same failure as one JSON object
    ["build", "--no-such-option", "--json"],  # a usage error as one JSON object
]


def _quiet(stderr: str) -> str:
    """Cold ``build`` says the CAD kernel is loading; a warm engine already has it (by design)."""
    return "".join(ln for ln in stderr.splitlines(keepends=True) if KERNEL_NOTE not in ln)


@pytest.fixture
def product(tmp_path: Path, engines: EngineGuard) -> Path:
    """A built bracket copy (long path: the socket is in /tmp) with its engine started."""
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", prebuilt=True)
    engines.start(root)
    return root


def test_each_command_matches_a_cold_run(product: Path) -> None:
    for argv in COMMANDS:
        cold = n2f(*argv, cwd=product, process=True, env={"N2F_NO_ENGINE": "1"})
        warm = n2f(*argv, cwd=product, process=True)
        assert warm.returncode == cold.returncode, argv
        assert warm.stdout == cold.stdout, argv
        assert _quiet(warm.stderr) == _quiet(cold.stderr), argv
    info = eng.engine_status(product)
    assert info is not None and info["requests"] == len(COMMANDS)  # none fell back to cold
    codes = {
        tuple(argv): n2f(*argv, cwd=product, env={"N2F_NO_ENGINE": "1"}).returncode
        for argv in COMMANDS[-4:-2]
    }
    assert sorted(codes.values()) == [1, 2]  # one failure of the command, one usage error


def test_colour_and_width_follow_each_request_not_the_last_one(product: Path) -> None:
    def run(env: dict[str, str], engine: bool) -> tuple[int, str, str]:
        extra = {} if engine else {"N2F_NO_ENGINE": "1"}
        r = n2f("status", cwd=product, process=True, env={**env, **extra})
        return r.returncode, r.stdout, r.stderr

    colour = {"FORCE_COLOR": "1", "COLUMNS": "60"}
    plain = {"COLUMNS": "200"}
    cold_colour, cold_plain = run(colour, False), run(plain, False)
    assert "\x1b[" in cold_colour[1] and "\x1b[" not in cold_plain[1]
    assert run(colour, True) == cold_colour
    assert run(plain, True) == cold_plain  # nothing of the coloured request is left
    assert run(colour, True) == cold_colour


def test_a_terminal_request_gets_terminal_output(product: Path) -> None:
    out: list[str] = []
    s = eng.connect(eng.socket_path(product))
    assert s is not None
    env = {"TERM": "xterm-256color", "COLUMNS": "60"}
    code = eng.converse(
        s,
        ["status"],
        str(product),
        on_out=out.append,
        on_err=out.append,
        env=env,
        tty=True,
        cols=60,
    )
    assert code == 0 and "\x1b[" in "".join(out)
    assert max(len(ln) for ln in "".join(out).splitlines()) < 400  # lines, not one long blob


def test_two_products_through_one_engine_stay_apart(tmp_path: Path, engines: EngineGuard) -> None:
    a = copy_product(EXAMPLES / "bracket", tmp_path / "alpha", prebuilt=True)
    b = copy_product(EXAMPLES / "bracket", tmp_path / "bravo", prebuilt=True)
    manifest = b / "n2f.yaml"  # a second product with another name: its output must say so
    manifest.write_text(
        manifest.read_text().replace("Wall bracket for a 10 kg shelf", "Garden hook for a planter")
    )
    engines.start(a)
    sock = eng.socket_path(a)

    def through_a(cwd: Path, *argv: str) -> tuple[int, str, str]:
        s = eng.connect(sock)
        assert s is not None
        out: list[str] = []
        err: list[str] = []
        code = eng.converse(
            s, list(argv), str(cwd), on_out=out.append, on_err=err.append, env={"COLUMNS": "200"}
        )
        return code, "".join(out), "".join(err)

    for cwd in (a, b, a, b):
        cold = n2f("status", cwd=cwd)  # in this process: cold enough, and quick
        assert through_a(cwd, "status") == (cold.returncode, cold.stdout, cold.stderr)
        assert ("Garden hook" in cold.stdout) == (cwd == b)  # each answer is its own product's
    cold = n2f("check", cwd=b)
    assert through_a(b, "check") == (cold.returncode, cold.stdout, cold.stderr)


def test_a_request_leaves_the_engine_process_as_it_found_it(product: Path) -> None:
    before = (dict(os.environ), os.getcwd(), list(sys.argv), list(sys.path), set(sys.modules))
    out, err = io.StringIO(), io.StringIO()
    req = {
        "argv": ["build", "--offline"],  # sets N2F_OFFLINE for itself
        "cwd": str(product),
        "env": {"N2F_PROBE": "1", "COLUMNS": "120"},
        "tty": False,
        "cols": None,
    }
    code = eng.run_in_process(req, out, err, product)
    assert code == 0, err.getvalue()
    assert "already up to date" in out.getvalue()
    assert (dict(os.environ), os.getcwd(), list(sys.argv), list(sys.path)) == before[:4]
    added = set(sys.modules) - before[4]
    assert not [m for m in added if m.startswith("n2f_")]


def _kill_engine_when_busy(root: Path) -> threading.Thread:
    """A thread that SIGKILLs the engine of ``root`` as soon as it is running a command."""

    def watch() -> None:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            info = eng.engine_status(root)
            if info is not None and info["busy"]:
                os.kill(int(info["pid"]), signal.SIGKILL)
                return
            time.sleep(0.02)

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    return thread


def _no_timings(text: str) -> str:
    return re.sub(r"\d+\.\ds", "<t>s", text)


def test_a_safe_command_cut_short_by_the_engine_dying_is_run_again_once(
    product: Path, engines: EngineGuard
) -> None:
    argv = ["build", "--clean", "--offline"]
    cold = n2f(*argv, cwd=product, process=True, env={"N2F_NO_ENGINE": "1"})
    assert cold.returncode == 0, cold.stderr
    watcher = _kill_engine_when_busy(product)  # the engine dies in the middle of the rebuild
    r = n2f(*argv, cwd=product, process=True)
    watcher.join(5)
    assert r.returncode == 0, r.stderr
    assert r.stderr.count(eng.RERUN_LINE) == 1 and r.stderr.startswith(eng.RERUN_LINE)
    # not a terminal: the engine's partial output was held, so nothing is printed twice
    assert _no_timings(r.stdout) == _no_timings(cold.stdout)
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("  built ")]
    assert len(lines) == len(set(lines)) and r.stdout.count("✓ built:") == 1
    # the engine is replaced for the next command
    engines.track(product)
    assert n2f("validate", cwd=product, process=True).returncode == 0


def _fake_engine_that_dies_on_run(root: Path) -> tuple[threading.Thread, socket.socket]:
    """Listens where the engine of ``root`` would; says ready, drops the connection on ``run``."""
    sock = eng.socket_path(root)
    eng.prepare_runtime_dir(root)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(os.fspath(sock))
    server.listen(4)

    def serve() -> None:
        try:
            conn, _ = server.accept()
        except OSError:
            return
        wire = eng.Wire(conn)
        wire.recv()
        wire.send("ready")
        wire.recv()  # the run: now the engine "crashes" before doing or answering anything
        wire.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return thread, server


def test_a_state_changing_command_cut_short_is_never_rerun(
    tmp_path: Path, engines: EngineGuard
) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket")  # with its history
    engines.track(root)
    manifest = root / "n2f.yaml"
    manifest.write_text(manifest.read_text().replace("A single", "One single"))
    assert n2f("snapshot", "-m", "second", cwd=root).returncode == 0

    def count() -> int:
        out = n2f("checkpoints", "--all", "--json", cwd=root).stdout
        data = json.loads(out)
        rows = data["checkpoints"] if isinstance(data, dict) else data
        return len(rows)

    before = count()
    assert before >= 2
    thread, server = _fake_engine_that_dies_on_run(root)
    try:
        r = n2f("undo", "--dir", str(root), cwd=root, process=True)
        thread.join(10)
    finally:
        server.close()
        eng.socket_path(root).unlink(missing_ok=True)
    cmd = f"n2f undo --dir {root}"
    assert r.returncode == 70 and r.stdout == ""
    assert f"the n2f engine stopped during `{cmd}`; the change may or may not have been made." in (
        r.stderr
    )
    assert f"look at: n2f checkpoints --dir {root}" in r.stderr
    assert r.stderr.strip().endswith(f"if it did not happen, run again: {cmd}")
    assert count() == before  # nothing ran it a second time

    thread, server = _fake_engine_that_dies_on_run(root)
    try:
        j = n2f("undo", "--json", cwd=root, process=True)
        thread.join(10)
    finally:
        server.close()
        eng.socket_path(root).unlink(missing_ok=True)
    assert j.returncode == 70
    assert json.loads(j.stdout) == {
        "error": "engine_stopped",
        "message": "the n2f engine stopped during `n2f undo --json`; the change may or may not "
        "have been made",
        "next": "run `n2f checkpoints` to see whether it happened; if not, run "
        "`n2f undo --json` again",
        "changes_state": True,
        "outcome": "unknown",
        "look_at": "n2f checkpoints",
        "rerun": "n2f undo --json",
        "exit": 70,
    }
    assert "may or may not have been made" in j.stderr
    assert count() == before
    # and the rerun it asks for does what it says (so the assertions above could have failed)
    assert n2f("undo", cwd=root).returncode == 0
    assert count() == before + 1


def _gone(root: Path) -> bool:
    import time

    deadline = time.monotonic() + 10
    while engine_processes(root) and time.monotonic() < deadline:
        time.sleep(0.1)
    return not engine_processes(root)


def test_json_errors_are_the_same_objects_warm_and_cold(product: Path) -> None:
    for argv, code, error in (
        (["check", "--scope", "asm://nope", "--json"], 1, "error"),
        (["build", "--no-such-option", "--json"], 2, "usage_error"),
    ):
        cold = n2f(*argv, cwd=product, process=True, env={"N2F_NO_ENGINE": "1"})
        warm = n2f(*argv, cwd=product, process=True)
        assert (warm.returncode, warm.stdout) == (
            cold.returncode,
            cold.stdout,
        ) and code == warm.returncode
        obj = json.loads(warm.stdout)
        assert obj["error"] == error and obj["message"] and obj["next"]
    info = eng.engine_status(product)
    assert info is not None and info["requests"] == 2  # both went through the engine
