"""The warm engine's life: start, status, stop, stale files, idle, recycle (S-305).

Real engine processes, each in a throwaway product folder and each stopped (and checked gone) at
the end of its test by the ``engines`` fixture.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import stat
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from napkin2factory.cli import engine as eng
from tests.conftest import EngineGuard, engine_processes, n2f


def _wait(cond: Callable[[], bool], seconds: float = 20.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.1)
    return cond()


def test_start_status_second_start_stop(short_product: Path, engines: EngineGuard) -> None:
    started = n2f("engine", "start", cwd=short_product, process=True)
    assert started.returncode == 0, started.stderr
    assert "running" in started.stdout
    (line,) = engine_processes(short_product)
    assert "napkin2factory.cli.engine" in line
    sock = eng.socket_path(short_product)
    assert sock.exists() and eng.pid_path(short_product).is_file()
    assert stat.S_IMODE(sock.stat().st_mode) == 0o600

    status = n2f("engine", "status", "--json", cwd=short_product)
    info = json.loads(status.stdout)
    assert info["running"] is True and info["busy"] is False
    pid = info["pid"]
    assert str(pid) in line

    again = n2f("engine", "start", cwd=short_product)  # no second engine
    assert again.returncode == 0 and "already running" in again.stdout
    assert len(engine_processes(short_product)) == 1
    assert json.loads(n2f("engine", "status", "--json", cwd=short_product).stdout)["pid"] == pid

    plain = n2f("engine", "status", cwd=short_product).stdout
    assert f"process {pid}" in plain and "commands served" in plain

    stopped = n2f("engine", "stop", cwd=short_product)
    assert stopped.returncode == 0 and "stopped" in stopped.stdout
    assert _wait(lambda: not engine_processes(short_product), 10)
    assert not sock.exists() and not eng.pid_path(short_product).exists()
    assert "no engine" in n2f("engine", "status", cwd=short_product).stdout
    assert "no engine was running" in n2f("engine", "stop", cwd=short_product).stdout


def test_a_command_through_the_engine_counts_and_matches_the_cold_one(
    short_product: Path, engines: EngineGuard, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COLUMNS", "200")  # what n2f() gives the cold run
    engines.start(short_product)
    code, out, err = eng.capture(short_product, ["validate", f"--dir={short_product}"]) or (
        -1,
        "",
        "",
    )
    assert code == 0, err
    cold = n2f("validate", f"--dir={short_product}", cwd=short_product, env={"N2F_NO_ENGINE": "1"})
    assert (cold.returncode, cold.stdout, cold.stderr) == (code, out, err)
    info = eng.engine_status(short_product)
    assert info is not None and info["requests"] == 1


def test_a_stale_pid_file_and_socket_are_cleaned_up(
    short_product: Path, engines: EngineGuard
) -> None:
    eng.prepare_runtime_dir(short_product)
    dead = os.fork()
    if dead == 0:
        os._exit(0)
    os.waitpid(dead, 0)
    eng.pid_path(short_product).write_text(
        json.dumps({"pid": dead, "socket": str(eng.socket_path(short_product))}) + "\n"
    )
    leftover = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    leftover.bind(os.fspath(eng.socket_path(short_product)))
    leftover.close()  # the file stays, nobody listens
    assert eng.engine_status(short_product) is None
    assert eng.stop_engine(short_product) == "none"  # removes both
    assert not eng.socket_path(short_product).exists()
    assert not eng.pid_path(short_product).exists()

    # and a start over stale files works: the new engine replaces them
    eng.pid_path(short_product).write_text(json.dumps({"pid": dead}) + "\n")
    leftover = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    leftover.bind(os.fspath(eng.socket_path(short_product)))
    leftover.close()
    pid = engines.start(short_product)
    assert pid != dead
    assert json.loads(eng.pid_path(short_product).read_text())["pid"] == pid


def test_no_engine_env_never_starts_or_connects(
    short_product: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("N2F_NO_ENGINE", "1")
    result = n2f("validate", cwd=short_product, process=True)
    assert result.returncode == 0, result.stderr
    time.sleep(0.5)
    assert engine_processes(short_product) == []
    assert not eng.lock_path(short_product).exists()
    assert not eng.socket_path(short_product).exists()
    assert eng.capture(short_product, ["validate"]) is None
    assert eng.after_cold(["validate"]) is None
    assert engine_processes(short_product) == []


def test_the_first_command_runs_cold_and_starts_the_engine_for_the_next(
    short_product: Path, engines: EngineGuard
) -> None:
    assert eng.engine_status(short_product) is None
    first = n2f("validate", cwd=short_product, process=True)
    assert first.returncode == 0, first.stderr
    assert _wait(lambda: eng.engine_status(short_product) is not None, 30)
    info = eng.engine_status(short_product)
    assert info is not None and info["requests"] == 0  # the first one did not go through it
    # the product was never built, and the engine neither needed nor made a build folder
    assert not (short_product / "build").exists()
    second = n2f("validate", cwd=short_product, process=True)
    assert (second.returncode, second.stdout, second.stderr) == (
        first.returncode,
        first.stdout,
        first.stderr,
    )
    info = eng.engine_status(short_product)
    assert info is not None and info["requests"] == 1


def test_the_engine_leaves_when_idle(
    short_product: Path, engines: EngineGuard, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("N2F_ENGINE_IDLE", "3")  # long enough that a loaded host sees it start
    engines.start(short_product)
    assert _wait(lambda: not engine_processes(short_product), 15)
    assert _wait(lambda: not eng.socket_path(short_product).exists(), 5)
    assert not eng.pid_path(short_product).exists()


def test_the_engine_is_recycled_after_its_request_limit(
    short_product: Path, engines: EngineGuard, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("N2F_ENGINE_MAX_REQUESTS", "2")
    pid = engines.start(short_product)
    argv = ["validate", f"--dir={short_product}"]
    for _ in range(2):
        got = eng.capture(short_product, argv)
        assert got is not None and got[0] == 0
    assert _wait(lambda: not engine_processes(short_product), 10)  # it left on its own
    assert not eng.socket_path(short_product).exists()
    # the next command is not served warm; it starts a fresh engine for the one after
    assert eng.capture(short_product, argv) is None
    monkeypatch.delenv("N2F_ENGINE_MAX_REQUESTS")
    assert _wait(lambda: (eng.engine_status(short_product) or {}).get("pid", pid) != pid, 30)


def test_a_killed_engine_between_commands_costs_one_cold_run(
    short_product: Path, engines: EngineGuard
) -> None:
    pid = engines.start(short_product)
    os.kill(pid, signal.SIGKILL)
    assert _wait(lambda: not engine_processes(short_product), 10)
    # its socket and pid file are still there: stale
    assert eng.socket_path(short_product).exists()
    result = n2f("validate", cwd=short_product, process=True)  # cold, and starts a new engine
    assert result.returncode == 0, result.stderr
    cold = n2f("validate", cwd=short_product, env={"N2F_NO_ENGINE": "1"})
    assert result.stdout == cold.stdout
    assert _wait(lambda: (eng.engine_status(short_product) or {}).get("pid", pid) != pid, 30)
    # a different process holds the files now, and the stale ones are gone
    assert json.loads(eng.pid_path(short_product).read_text())["pid"] != pid


def test_a_package_change_makes_the_engine_leave(
    short_product: Path, engines: EngineGuard, monkeypatch: pytest.MonkeyPatch
) -> None:
    engines.start(short_product)
    monkeypatch.setattr(eng, "package_code", lambda: "something-else")
    assert eng.capture(short_product, ["validate"]) is None  # refused: run it cold
    assert _wait(lambda: not engine_processes(short_product), 15)


def test_status_says_whether_the_next_command_starts_an_engine(
    short_product: Path, engines: EngineGuard
) -> None:
    plain = n2f("engine", "status", cwd=short_product)
    assert plain.returncode == 0
    assert "no engine is running" in plain.stdout and "will start one" in plain.stdout
    assert "n2f engine start" in plain.stdout
    info = json.loads(n2f("engine", "status", "--json", cwd=short_product).stdout)
    assert info["running"] is False and info["will_start_on_next_command"] is True
    assert info["start_command"] == "n2f engine start" and info["pid"] is None
    assert info["socket"] == str(eng.socket_path(short_product)) and info["reason"]
    assert info["idle_s"] is None and info["idle_left_s"] is None and info["version"]

    off = n2f("engine", "status", cwd=short_product, env={"N2F_NO_ENGINE": "1"})
    assert "none will start by itself" in off.stdout and "N2F_NO_ENGINE" in off.stdout
    assert "n2f engine start" in off.stdout
    off_json = json.loads(
        n2f("engine", "status", "--json", cwd=short_product, env={"N2F_NO_ENGINE": "1"}).stdout
    )
    assert off_json["will_start_on_next_command"] is False
    assert "N2F_NO_ENGINE" in off_json["reason"]

    pid = engines.start(short_product)
    up = json.loads(n2f("engine", "status", "--json", cwd=short_product).stdout)
    assert up["running"] is True and up["pid"] == pid and up["will_start_on_next_command"] is False
    assert 0 <= up["idle_s"] < 60 and 800 < up["idle_left_s"] <= 900  # the 15 minute default
    assert "leaves after" in n2f("engine", "status", cwd=short_product).stdout


def test_engine_start_refuses_when_the_engine_is_off(short_product: Path) -> None:
    r = n2f("engine", "start", "--json", cwd=short_product, env={"N2F_NO_ENGINE": "1"})
    assert r.returncode == 1
    obj = json.loads(r.stdout)
    assert obj["error"] == "engine_disabled" and "N2F_NO_ENGINE" in obj["next"]
    assert engine_processes(short_product) == []


def test_init_starts_the_engine_and_the_first_build_is_served_by_it(
    tmp_path: Path, engines: EngineGuard
) -> None:
    import re
    import shutil

    from napkin2factory.cli.kernel import KERNEL_NOTE

    live = tmp_path / "a" / "prod"
    live.parent.mkdir()
    made = n2f("init", str(live), "--template", "bracket", "--json")
    assert made.returncode == 0, made.stderr
    assert json.loads(made.stdout)["kernel_warmup"] is True  # the engine is the warm-up
    engines.track(live)
    assert not (live / "build").exists()  # init built nothing; the engine made no build folder
    assert _wait(lambda: eng.engine_status(live) is not None, 40)
    twin = tmp_path / "b" / "prod"  # the same product, to build cold
    twin.parent.mkdir()
    shutil.copytree(live, twin, symlinks=True)

    warm = n2f("build", "--offline", cwd=live, process=True)
    assert warm.returncode == 0, warm.stderr
    info = eng.engine_status(live)
    assert info is not None and info["requests"] == 1  # the very first build was served warm
    cold = n2f("build", "--offline", cwd=twin, process=True, env={"N2F_NO_ENGINE": "1"})
    assert cold.returncode == 0, cold.stderr

    def plain(text: str) -> str:
        text = re.sub(r"\d+\.\ds", "<t>s", text)
        return "".join(ln for ln in text.splitlines(keepends=True) if KERNEL_NOTE not in ln)

    assert plain(warm.stdout) == plain(cold.stdout)
    assert plain(warm.stderr) == plain(cold.stderr)
