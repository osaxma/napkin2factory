"""The warm engine's wire: framing, ordering, refusals and failures (S-305).

No process is started: the engine side runs in a thread of the test on one end of a socket
pair and the client side talks to the other, with a fake runner in place of the CLI.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TextIO

import pytest

from napkin2factory import __version__
from napkin2factory.cli import engine as eng


def _runner(fn: Callable[[dict[str, Any], TextIO, TextIO], int]) -> eng.Runner:
    return fn


@contextmanager
def served(
    root: Path, runner: eng.Runner, **kwargs: Any
) -> Iterator[tuple[eng.Engine, socket.socket]]:
    """An engine (inline: the request runs in the connection's thread) and a client socket."""
    server_end, client_end = socket.socketpair()
    engine = eng.Engine(root, runner, code="c0de", version=__version__, inline=True, **kwargs)
    thread = threading.Thread(target=engine.handle, args=(server_end,), daemon=True)
    thread.start()
    try:
        yield engine, client_end
    finally:
        client_end.close()
        thread.join(5)
        server_end.close()


def _converse(sock: socket.socket, **kwargs: Any) -> tuple[int, list[tuple[str, str]]]:
    events: list[tuple[str, str]] = []
    code = eng.converse(
        sock,
        kwargs.pop("argv", ["status"]),
        kwargs.pop("cwd", "/"),
        on_out=lambda d: events.append(("out", d)),
        on_err=lambda d: events.append(("err", d)),
        version=kwargs.pop("version", __version__),
        code=kwargs.pop("code", "c0de"),
        python=kwargs.pop("python", sys.executable),
        **kwargs,
    )
    return code, events


def test_run_streams_out_and_err_in_order_and_ends_with_exit(tmp_path: Path) -> None:
    def run(req: dict[str, Any], out: TextIO, err: TextIO) -> int:
        out.write("one\n")
        err.write("two\n")
        out.write("three ")
        out.write("four\n")
        return 3

    with served(tmp_path, _runner(run)) as (engine, sock):
        code, events = _converse(sock)
    assert code == 3
    assert events == [("out", "one\n"), ("err", "two\n"), ("out", "three "), ("out", "four\n")]
    assert engine.requests == 1


def test_request_carries_argv_cwd_env_and_terminal(tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, Any] = {}

    def run(req: dict[str, Any], out: TextIO, err: TextIO) -> int:
        seen.update(req, out_tty=out.isatty(), err_tty=err.isatty())
        return 0

    monkeypatch.setenv("N2F_PROBE", "yes")
    monkeypatch.setenv("SOMETHING_ELSE", "no")
    with served(tmp_path, _runner(run)) as (_, sock):
        _converse(sock, argv=["check", "--all"], cwd="/x", tty=True, etty=False, cols=88)
    assert seen["argv"] == ["check", "--all"] and seen["cwd"] == "/x" and seen["cols"] == 88
    assert seen["v"] == 1 and seen["t"] == "run"
    assert seen["env"]["N2F_PROBE"] == "yes" and "SOMETHING_ELSE" not in seen["env"]
    assert seen["out_tty"] is True and seen["err_tty"] is False


def test_a_multibyte_character_survives_the_chunks(tmp_path: Path) -> None:
    with served(tmp_path, _runner(lambda r, o, e: o.write("✓ built\n") and 0)) as (_, sock):
        _, events = _converse(sock)
    assert events == [("out", "✓ built\n")]


@pytest.mark.parametrize(
    ("kwargs", "stale"),
    [
        ({"version": "0.0.1"}, True),
        ({"code": "other"}, True),
        ({"python": "/not/this/python"}, False),
    ],
)
def test_hello_mismatch_is_refused_before_anything_runs(
    tmp_path: Path, kwargs: dict[str, Any], stale: bool
) -> None:
    ran: list[int] = []
    with served(tmp_path, _runner(lambda r, o, e: ran.append(1) or 0)) as (engine, sock):
        with pytest.raises(eng.NotReady) as info:
            _converse(sock, **kwargs)
    assert info.value.stale is stale and info.value.why
    assert engine.stale is stale and not ran


def test_an_internal_failure_is_an_error_object_then_exit_70(tmp_path: Path) -> None:
    def run(req: dict[str, Any], out: TextIO, err: TextIO) -> int:
        out.write("partial\n")
        raise RuntimeError("boom")

    with served(tmp_path, _runner(run)) as (_, sock):
        code, events = _converse(sock)
    assert code == 70
    assert events[0] == ("out", "partial\n")
    assert events[-1] == ("err", "n2f engine: RuntimeError: boom\n")


def test_a_bad_request_is_exit_70_not_a_crash(tmp_path: Path) -> None:
    with served(tmp_path, _runner(lambda r, o, e: 0)) as (_, sock):
        wire = eng.Wire(sock)
        wire.send("hello", pkg=__version__, code="c0de", py=sys.executable)
        assert wire.recv() == {"v": 1, "t": "ready"}
        wire.send("run", argv="not a list", cwd="/", env={})
        kinds = []
        while (msg := wire.recv()) is not None:
            kinds.append(msg["t"])
            if msg["t"] == "exit":
                assert msg["code"] == 70
                break
    assert kinds == ["error", "exit"]


def test_run_before_hello_is_refused(tmp_path: Path) -> None:
    with served(tmp_path, _runner(lambda r, o, e: 0)) as (engine, sock):
        wire = eng.Wire(sock)
        wire.send("run", argv=["status"], cwd="/", env={})
        reply = wire.recv()
    assert reply is not None and reply["t"] == "refuse" and engine.requests == 0


def test_another_protocol_version_is_refused(tmp_path: Path) -> None:
    with served(tmp_path, _runner(lambda r, o, e: 0)) as (_, sock):
        sock.sendall(b'{"v": 2, "t": "hello"}\n')
        reply = json.loads(sock.makefile("rb").readline())
    assert reply["t"] == "refuse" and "protocol" in reply["why"]


def test_the_client_refuses_a_reply_in_another_version() -> None:
    server_end, client_end = socket.socketpair()
    server_end.sendall(b'{"v": 2, "t": "ready"}\n')
    with pytest.raises(eng.NotReady):
        _converse(client_end)
    client_end.close()
    server_end.close()


def test_silence_after_hello_is_not_ready() -> None:
    server_end, client_end = socket.socketpair()
    server_end.close()  # nothing answers
    with pytest.raises(eng.NotReady):
        _converse(client_end)
    client_end.close()


def test_a_connection_dropped_after_run_is_dropped_not_not_ready() -> None:
    server_end, client_end = socket.socketpair()

    def crash() -> None:
        wire = eng.Wire(server_end)
        wire.recv()
        wire.send("ready")
        wire.recv()  # the run
        wire.send("out", d="half\n")
        server_end.close()  # the engine dies mid-command

    threading.Thread(target=crash, daemon=True).start()
    seen: list[str] = []
    with pytest.raises(eng.Dropped):
        eng.converse(
            client_end,
            ["build"],
            "/",
            on_out=seen.append,
            on_err=seen.append,
            version=__version__,
            code="c0de",
        )
    assert seen == ["half\n"]
    client_end.close()


def test_the_engine_leaves_after_its_request_limit(tmp_path: Path) -> None:
    engine_ref: list[eng.Engine] = []
    with served(tmp_path, _runner(lambda r, o, e: 0), max_requests=1) as (engine, sock):
        engine_ref.append(engine)
        _converse(sock)
    assert engine_ref[0].done.is_set()


def test_the_engine_leaves_after_a_request_when_the_package_changed(tmp_path: Path) -> None:
    with served(tmp_path, _runner(lambda r, o, e: 0), code_now=lambda: "changed") as (engine, sock):
        _converse(sock)
    assert engine.done.is_set()


def test_a_client_that_left_while_waiting_gets_nothing_run(tmp_path: Path) -> None:
    ran: list[int] = []
    server_end, client_end = socket.socketpair()
    engine = eng.Engine(
        tmp_path, _runner(lambda r, o, e: ran.append(1) or 0), code="c", version="v", inline=True
    )
    wire = eng.Wire(server_end)
    client_end.close()
    engine._serve_run(wire, {"argv": ["status"], "cwd": "/", "env": {}})
    server_end.close()
    assert ran == []


def test_the_command_is_never_run_cold_after_run_was_sent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "n2f.yaml").write_text("x: 1\n")
    (tmp_path / "build").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("N2F_NO_ENGINE", raising=False)
    server_end, client_end = socket.socketpair()
    monkeypatch.setattr(eng, "connect", lambda *a, **k: client_end)

    def crash() -> None:
        wire = eng.Wire(server_end)
        wire.recv()
        wire.send("ready")
        wire.recv()
        server_end.close()

    # the hello check needs this process's own code and version, which converse computes
    threading.Thread(target=crash, daemon=True).start()
    assert eng.try_forward(["status"]) == 70
    assert capsys.readouterr().err == "the n2f engine stopped during the command; run it again\n"
    client_end.close()


def test_try_forward_does_nothing_when_off_or_not_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "n2f.yaml").write_text("x: 1\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("N2F_NO_ENGINE", "1")
    monkeypatch.setattr(
        eng, "connect", lambda *a, **k: pytest.fail("connected with the engine off")
    )
    assert eng.try_forward(["status"]) is None
    monkeypatch.delenv("N2F_NO_ENGINE")
    for argv in (
        ["init", "x"],
        ["release"],
        ["serve"],
        ["mcp"],
        ["doctor"],
        ["decide", "x"],
        [],
        ["status", "--help"],
    ):
        assert eng.try_forward(argv) is None, argv


def test_product_of_reads_dir_and_walks_up(tmp_path: Path) -> None:
    prod = tmp_path / "p"
    (prod / "sub").mkdir(parents=True)
    (prod / "n2f.yaml").write_text("x: 1\n")
    assert eng.product_of(["status"], cwd=prod / "sub") == prod.resolve()
    assert eng.product_of(["status", f"--dir={prod}"], cwd=tmp_path) == prod.resolve()
    assert eng.product_of(["status", "-C", str(prod)], cwd=tmp_path) == prod.resolve()
    assert eng.product_of(["status", "--dir", str(tmp_path)], cwd=prod) is None
    assert eng.product_of(["status"], cwd=tmp_path) is None


def test_only_the_listed_verbs_go_through_the_engine() -> None:
    for argv in (["build"], ["check", "--all"], ["ecr", "impact"], ["concept", "build"], ["undo"]):
        assert eng.verb_allowed(argv), argv
    for argv in (["version"], ["doctor"], ["decide", "x"], ["signoff", "x"], ["engine", "stop"]):
        assert not eng.verb_allowed(argv), argv
