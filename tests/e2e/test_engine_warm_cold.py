"""A command gives the same stdout, stderr and exit code through the warm engine as cold (S-305).

The engine runs the CLI's own command in a long-lived process; this is the test that it does so
without leaking one request into the next: a fixed list of commands (read-only or idempotent, one
failing, one with ``--json``) runs in a fresh process (``N2F_NO_ENGINE=1``) and through a
started engine, and the three streams are compared.
"""

from __future__ import annotations

import io
import os
import sys
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
        for argv in COMMANDS[-2:]
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


def test_a_command_cut_short_by_the_engine_dying_is_not_rerun(
    product: Path, engines: EngineGuard
) -> None:
    # N2F_TEST_EXIT_AFTER makes the build call os._exit(3) after one rule: the engine dies
    # in the middle of the command
    r = n2f(
        "build",
        "--clean",
        "--offline",
        cwd=product,
        process=True,
        env={"N2F_TEST_EXIT_AFTER": "part:l-bracket"},
    )
    assert r.returncode == 70
    assert r.stderr.strip().endswith("the n2f engine stopped during the command; run it again")
    assert "built: " not in r.stdout  # it did not finish, and nothing ran it a second time cold
    assert _gone(product)
    # the next command still works: cold, and it starts a fresh engine
    again = n2f("validate", cwd=product, process=True)
    assert again.returncode == 0, again.stderr
    engines.track(product)


def _gone(root: Path) -> bool:
    import time

    deadline = time.monotonic() + 10
    while engine_processes(root) and time.monotonic() < deadline:
        time.sleep(0.1)
    return not engine_processes(root)
