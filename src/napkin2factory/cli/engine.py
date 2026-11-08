"""The warm engine: one long-running ``n2f`` process per product folder (S-305).

A command pays about 1.1 s for the interpreter and the package imports and 2.8 s for the CAD
kernel before it does any work. The engine holds both: the first allow-listed command in a
product folder starts it in the background (that command itself runs cold, in its own process),
and the next commands send their arguments to it over a Unix socket and print what it streams
back. The engine runs the very same Typer command in-process, so there is one code path; the
design, the stale-state risks and the wire format are in
``docs/handoffs/v0.9-warm-process-design.md``.

This module imports only the standard library at the top, because the client side runs before
the package's own imports (``cli/entry.py``): everything heavy is imported inside the engine
process or inside a function. ``N2F_NO_ENGINE=1`` turns the whole thing off.
"""

from __future__ import annotations

import codecs
import contextlib
import fcntl
import hashlib
import io
import json
import os
import queue
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
from collections.abc import Buffer, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    import typer

PROTOCOL = 1
NO_ENGINE_ENV = "N2F_NO_ENGINE"
IDLE_ENV = "N2F_ENGINE_IDLE"  # seconds; the engine's own start-up environment (tests)
MAX_REQUESTS_ENV = "N2F_ENGINE_MAX_REQUESTS"
IDLE_SECONDS = 15 * 60
MAX_REQUESTS = 200  # the CAD kernel leaks a little per build; a recycle bounds memory
CONNECT_TIMEOUT = 1.0
HELLO_TIMEOUT = 1.0
EXIT_INTERNAL = 70  # EX_SOFTWARE: the engine failed, or stopped under a command


@dataclass(frozen=True)
class VerbClass:
    """What a dropped connection means for a verb the engine forwards (S-310)."""

    changes_state: bool
    #: For a verb that changes state: the read-only command that shows whether it happened.
    look_at: str | None = None


SAFE = VerbClass(False)


def _changes(look_at: str) -> VerbClass:
    return VerbClass(True, look_at)


#: Every verb the engine forwards, by command path, and its class. ``SAFE``: the rules re-run only
#: what is stale (or the verb only reads), so repeating it is harmless: after a dropped connection
#: the client runs it again cold. ``changes_state``: it writes the product or its history, so it is
#: never repeated: the client says what happened, what to look at (``look_at``) and what to run
#: next. A verb not in this table is not forwarded; ``NEVER_FORWARD`` names the ones that chose
#: not to be, and a test fails for a verb in neither (a new verb has to choose).
VERB_CLASSES: dict[tuple[str, ...], VerbClass] = {
    ("build",): SAFE,
    ("check",): SAFE,
    ("status",): SAFE,
    ("impact",): SAFE,
    ("graph",): SAFE,
    ("validate",): SAFE,
    ("lint",): SAFE,
    ("checkpoints",): SAFE,
    ("context",): SAFE,
    ("docs",): SAFE,
    ("undo",): _changes("n2f checkpoints"),
    ("redo",): _changes("n2f checkpoints"),
    ("rollback",): _changes("n2f checkpoints"),
    ("ecr", "impact"): SAFE,
    ("ecr", "list"): SAFE,
    ("ecr", "show"): SAFE,
    ("ecr", "start"): _changes("n2f ecr list"),
    ("ecr", "quick"): _changes("n2f ecr list"),
    ("ecr", "approve"): _changes("n2f ecr list"),
    ("ecr", "close"): _changes("n2f ecr list"),
    ("ecr", "abort"): _changes("n2f ecr list"),
    ("concept", "list"): SAFE,
    ("concept", "show"): SAFE,
    ("concept", "build"): SAFE,
    ("concept", "board"): SAFE,
    ("concept", "lint"): SAFE,
    ("concept", "compare"): SAFE,
    ("concept", "new"): _changes("n2f concept list"),
    ("concept", "promote"): _changes("n2f concept list"),
    ("concept", "reject"): _changes("n2f concept list"),
    ("concept", "switch"): _changes("n2f checkpoints"),
    ("concept", "fork-from-model"): _changes("n2f concept list"),
}

#: The verbs that run in the client's own process: they write outside the product, never return,
#: ask questions, or are the engine's own controls.
NEVER_FORWARD: frozenset[tuple[str, ...]] = frozenset(
    {
        ("init",),
        ("release",),
        ("diff",),
        ("publish",),
        ("serve",),
        ("mcp",),
        ("skill",),
        ("doctor",),
        ("snapshot",),
        ("discard",),
        ("decide",),
        ("signoff",),
        ("version",),
        ("engine", "start"),
        ("engine", "status"),
        ("engine", "stop"),
    }
)

_GROUPS: frozenset[str] = frozenset(path[0] for path in VERB_CLASSES if len(path) > 1)

#: Environment the request carries: these prefixes and names. The engine sets exactly these
#: from the request (and unsets those the client lacks) and puts everything back afterwards.
ENV_PREFIXES: tuple[str, ...] = ("N2F_", "GIT_")
ENV_NAMES: frozenset[str] = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "NO_COLOR",
        "FORCE_COLOR",
        "CLICOLOR",
        "CLICOLOR_FORCE",
        "TERM",
        "COLORTERM",
        "COLUMNS",
        "LINES",
        "TERMINAL_WIDTH",
    }
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]  # src/napkin2factory
_SKIP_DIRS = frozenset({"__pycache__", "vendor", "templates"})


# ---------------------------------------------------------------------------------------------
# paths


def runtime_dir(root: Path) -> Path:
    """The engine's folder for the product at ``root``: socket, pid file, lock and log (S-313).

    ``/tmp/n2f-<uid>/<first 16 hex of sha256(realpath of the product)>/``: always in the user's
    runtime area, never in the product. ``build/`` is generated output, and a socket, a lock and a
    pid file are runtime state, not output: kept there they would be copied, hashed and shipped with
    it (``ecr impact`` copies ``build/``). The path also stays short for any product location (a
    Unix socket path holds about 104 bytes). It is not about ``n2f status``, which does not read
    whether ``build/`` exists (S-314).
    """
    real = os.path.realpath(root)
    digest = hashlib.sha256(os.fsencode(real)).hexdigest()[:16]
    return Path("/tmp") / f"n2f-{os.getuid()}" / digest


def socket_path(root: Path) -> Path:
    """The engine's socket (0600) in :func:`runtime_dir`."""
    return runtime_dir(root) / "engine.sock"


def pid_path(root: Path) -> Path:
    """The pid file: JSON with the pid, the socket path and when the engine started."""
    return runtime_dir(root) / "engine.pid"


def lock_path(root: Path) -> Path:
    """The lock the running engine holds (``flock``); free when no engine runs."""
    return runtime_dir(root) / "engine.lock"


def log_path(root: Path) -> Path:
    """What the engine process wrote to its stdout and stderr (a crash shows here)."""
    return runtime_dir(root) / "engine.log"


def prepare_runtime_dir(root: Path) -> Path:
    """Create the engine's folder for ``root`` (mode 0700) and return it.

    Raises:
        PermissionError: it, or ``/tmp/n2f-<uid>``, is owned by someone else, open to group or
            others, or a symbolic link.
    """
    folder = runtime_dir(root)
    for part in (folder.parent, folder):
        part.mkdir(mode=0o700, exist_ok=True)
        if part.is_symlink():
            raise PermissionError(f"{part} is a symbolic link")
        st = part.stat()
        if st.st_uid != os.getuid():
            raise PermissionError(f"{part} is not owned by this user")
        if st.st_mode & 0o077:
            raise PermissionError(f"{part} is open to other users (mode {st.st_mode & 0o777:o})")
    return folder


# ---------------------------------------------------------------------------------------------
# what is loaded


def package_code() -> str:
    """A short hash of the newest modification time of the package's files.

    The client and the engine run this same function: the engine records it at start and the
    client sends it in ``hello``, so a package edited or upgraded after the engine started is
    noticed on the next command.
    """
    newest = 0
    count = 0
    for dirpath, dirnames, filenames in os.walk(PACKAGE_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            if name.endswith((".py", ".yaml", ".j2", ".js", ".html", ".css")):
                try:
                    mtime = os.stat(os.path.join(dirpath, name)).st_mtime_ns
                except OSError:
                    continue
                count += 1
                newest = max(newest, mtime)
    return hashlib.sha256(f"{newest}:{count}".encode()).hexdigest()[:16]


def _version() -> str:
    from napkin2factory import __version__

    return __version__


def engine_disabled(env: Mapping[str, str] | None = None) -> bool:
    """True when ``N2F_NO_ENGINE`` asks for no engine (set and not empty or ``0``)."""
    return (env if env is not None else os.environ).get(NO_ENGINE_ENV, "") not in ("", "0")


# ---------------------------------------------------------------------------------------------
# the wire


class ProtocolError(Exception):
    """The other side sent something that is not this protocol."""


class Wire:
    """Newline-delimited JSON over a connected socket; one writer lock for every sender."""

    def __init__(self, sock: socket.socket) -> None:
        """Wrap ``sock``."""
        self.sock = sock
        self._reader = sock.makefile("rb")
        self._lock = threading.Lock()
        self.broken = False

    def send(self, kind: str, **fields: Any) -> bool:
        """Send one object; False (and every later send is dropped) once the peer is gone."""
        data = (json.dumps({"v": PROTOCOL, "t": kind, **fields}) + "\n").encode("utf-8")
        with self._lock:
            if self.broken:
                return False
            try:
                self.sock.sendall(data)
            except OSError:
                self.broken = True
                return False
        return True

    def recv(self) -> dict[str, Any] | None:
        """The next object, or None at end of stream.

        Raises:
            ProtocolError: not JSON, not an object, or a different protocol version.
        """
        line = self._reader.readline()
        if not line:
            return None
        try:
            obj = json.loads(line)
        except ValueError as exc:
            raise ProtocolError(f"not JSON: {exc}") from exc
        if not isinstance(obj, dict) or "t" not in obj:
            raise ProtocolError("not a protocol object")
        if obj.get("v") != PROTOCOL:
            raise ProtocolError(f"protocol version {obj.get('v')!r}, expected {PROTOCOL}")
        return obj

    def peer_closed(self) -> bool:
        """True when the peer has closed its end (nothing more will be read or written)."""
        try:
            data = self.sock.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT)
        except BlockingIOError:
            return False
        except OSError:
            return True
        return data == b""

    def close(self) -> None:
        """Close the socket."""
        with contextlib.suppress(OSError):
            self._reader.close()
        with contextlib.suppress(OSError):
            self.sock.close()


# ---------------------------------------------------------------------------------------------
# the server (runs in the engine process)

Runner = Callable[[dict[str, Any], TextIO, TextIO], int]


class _Sink(io.BufferedIOBase):
    """Bytes written to a stream become ``out``/``err`` chunks on the wire."""

    def __init__(self, wire: Wire, kind: str, tty: bool) -> None:
        super().__init__()
        self._wire, self._kind, self._tty = wire, kind, tty
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def writable(self) -> bool:
        return True

    def isatty(self) -> bool:
        return self._tty

    def write(self, b: Buffer, /) -> int:
        data = bytes(b)
        text = self._decoder.decode(data)
        if text:
            self._wire.send(self._kind, d=text)
        return len(data)


def make_stream(wire: Wire, kind: str, tty: bool) -> TextIO:
    """A text stream whose writes are sent as ``kind`` chunks (``out`` or ``err``)."""
    return io.TextIOWrapper(
        _Sink(wire, kind, tty),  # type: ignore[type-var]  # typeshed wants a read/write buffer
        encoding="utf-8",
        errors="replace",
        write_through=True,
    )


class Engine:
    """The listening side: answers ``hello``, runs ``run`` requests one at a time."""

    def __init__(
        self,
        root: Path,
        runner: Runner,
        *,
        code: str,
        version: str,
        python: str | None = None,
        idle: float = IDLE_SECONDS,
        max_requests: int = MAX_REQUESTS,
        inline: bool = False,
        code_now: Callable[[], str] = package_code,
    ) -> None:
        """An engine for ``root``; ``inline`` runs a request in the connection's own thread."""
        self.root = Path(root)
        self.runner = runner
        self.code, self.version = code, version
        self.python = python or sys.executable
        self.idle, self.max_requests = idle, max_requests
        self.inline = inline
        self.code_now = code_now
        self.requests = 0
        self.started = time.time()
        self.warm = False  # True once the CAD kernel is preloaded (the engine answers promptly)
        self.last_active = time.monotonic()
        self.done = threading.Event()
        self.stale = False
        self._busy = 0
        self._busy_lock = threading.Lock()
        self._jobs: queue.Queue[Callable[[], None]] = queue.Queue()
        self._inline_lock = threading.Lock()

    # -- one connection ------------------------------------------------------------------

    def handle(self, conn: socket.socket) -> None:
        """Talk to one client until it is served or gone (runs in the connection's thread)."""
        wire = Wire(conn)
        ready = False
        try:
            while True:
                try:
                    msg = wire.recv()
                except ProtocolError as exc:
                    wire.send("refuse", why=f"protocol: {exc}")
                    return
                except OSError:
                    return
                if msg is None:
                    return
                kind = msg["t"]
                if kind == "hello":
                    why = self._mismatch(msg)
                    if why is not None:
                        wire.send("refuse", why=why)
                        if why.startswith("package"):
                            self.stale = True  # leave once idle: the next command starts a new one
                        return
                    ready = True
                    wire.send("ready")
                elif kind == "run":
                    if not ready:
                        wire.send("refuse", why="protocol: run before hello")
                        return
                    self._submit(lambda: self._serve_run(wire, msg))
                    return
                elif kind == "stop":
                    wire.send("bye")
                    self.done.set()
                    return
                elif kind == "status":
                    wire.send("status", **self.status())
                    return
                else:
                    wire.send("refuse", why=f"protocol: unknown type {kind!r}")
                    return
        finally:
            wire.close()

    def _mismatch(self, hello: dict[str, Any]) -> str | None:
        if hello.get("pkg") != self.version:
            return f"package: version {hello.get('pkg')} differs from the engine's {self.version}"
        if hello.get("code") != self.code:
            return "package: files changed since the engine started"
        if hello.get("py") != self.python:
            return "interpreter differs"
        return None

    def status(self) -> dict[str, Any]:
        """What ``n2f engine status`` shows."""
        return {
            "pid": os.getpid(),
            "root": str(self.root),
            "requests": self.requests,
            "started": self.started,
            "idle_s": round(time.monotonic() - self.last_active, 1),
            "idle_left_s": round(max(0.0, self.idle - (time.monotonic() - self.last_active)), 1),
            "busy": self._busy > 0,
            "warm": self.warm,
            "version": self.version,
        }

    # -- running ----------------------------------------------------------------------------

    def _submit(self, job: Callable[[], None]) -> None:
        """Run ``job`` on the engine's work thread and wait for it (the lock of one at a time)."""
        with self._busy_lock:
            self._busy += 1
        try:
            if self.inline:
                with self._inline_lock:
                    job()
                return
            finished = threading.Event()

            def wrapped() -> None:
                try:
                    job()
                finally:
                    finished.set()

            self._jobs.put(wrapped)
            finished.wait()
        finally:
            with self._busy_lock:
                self._busy -= 1
            self.last_active = time.monotonic()

    def _serve_run(self, wire: Wire, msg: dict[str, Any]) -> None:
        """Run one request and stream its output; the ``exit`` object is always the last."""
        if wire.peer_closed():  # the client gave up while it waited its turn: run nothing
            return
        self.requests += 1
        code = EXIT_INTERNAL
        try:
            _check_request(msg)
            out = make_stream(wire, "out", bool(msg.get("tty")))
            err = make_stream(wire, "err", bool(msg.get("etty", msg.get("tty"))))
            try:
                code = self.runner(msg, out, err)
            finally:
                with contextlib.suppress(Exception):
                    out.flush()
                    err.flush()
        except Exception as exc:
            wire.send("error", msg=f"{type(exc).__name__}: {exc}")
            code = EXIT_INTERNAL
        wire.send("exit", code=code)
        if self.requests >= self.max_requests or self.code_now() != self.code:
            self.done.set()

    # -- the engine process ---------------------------------------------------------------

    def run_jobs(self, tick: float = 0.25) -> None:
        """The work thread's loop: take jobs one at a time until told to stop or idle."""
        self.last_active = time.monotonic()  # idle counts from serving, not from start-up
        while not self.done.is_set():
            try:
                job = self._jobs.get(timeout=tick)
            except queue.Empty:
                if self._busy == 0 and (
                    (self.warm and time.monotonic() - self.last_active > self.idle) or self.stale
                ):
                    return
                if not self.root.is_dir():
                    return
                continue
            job()
            self.last_active = time.monotonic()


def _check_request(msg: dict[str, Any]) -> None:
    argv, cwd, env = msg.get("argv"), msg.get("cwd"), msg.get("env", {})
    if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        raise ValueError("argv must be a list of strings")
    if not isinstance(cwd, str) or not isinstance(env, dict):
        raise ValueError("cwd must be text and env an object")


def _exit_code(code: Any) -> tuple[int, str]:
    """``SystemExit.code`` as (exit status, text for stderr)."""
    if code is None:
        return 0, ""
    if isinstance(code, int):
        return code, ""
    return 1, f"{code}\n"


def _managed(name: str) -> bool:
    return name in ENV_NAMES or name.startswith(ENV_PREFIXES)


def _is_product_module(name: str, mod: Any, root: Path) -> bool:
    if name.startswith("n2f_"):
        return True
    file = getattr(mod, "__dict__", {}).get("__file__")
    return isinstance(file, str) and file.startswith(str(root) + os.sep)


def _drop_product_modules(root: Path) -> None:
    """Forget the product's own Python (geometry, calcs, screens, helpers they import)."""
    for name, mod in list(sys.modules.items()):
        if _is_product_module(name, mod, root):
            del sys.modules[name]


def _reset_package_state() -> None:
    """Clear what the package keeps per process and a different product or edit could outdate.

    Content-keyed caches (the style, finishes, quantity parsing) stay. The module caches of
    the product's calc and pack modules and the git-identity fallback are per process: they
    are cleared so a request starts like a fresh command.
    """
    from napkin2factory.core import packs, vcs
    from napkin2factory.core.checks import calcs

    packs._MODULE_CACHE.clear()
    calcs._MODULE_CACHE.clear()
    vcs._FALLBACK_IDENTITY_CACHE.clear()


def run_in_process(req: dict[str, Any], out: TextIO, err: TextIO, root: Path) -> int:
    """Run ``req`` as ``n2f`` would in a fresh process; return its exit code.

    The environment, working folder, ``sys.argv``, ``sys.path`` and the product's modules are
    put back afterwards, so nothing one request does reaches the next.
    """
    from rich.console import Console

    from napkin2factory.cli.app import run_app
    from napkin2factory.cli.common import console, err_console

    saved_env = dict(os.environ)
    saved_cwd = os.getcwd()
    saved_argv, saved_path = sys.argv, list(sys.path)
    saved_std = (sys.stdin, sys.stdout, sys.stderr)
    before = set(sys.modules)
    code = 0
    try:
        for name in [n for n in os.environ if _managed(n)]:
            del os.environ[name]
        os.environ.update({k: str(v) for k, v in req.get("env", {}).items() if _managed(k)})
        cols = req.get("cols")
        if isinstance(cols, int) and cols > 0 and "COLUMNS" not in os.environ:
            os.environ["COLUMNS"] = str(cols)
        os.chdir(req["cwd"])
        sys.argv = ["n2f", *req["argv"]]
        sys.stdin, sys.stdout, sys.stderr = io.StringIO(""), out, err
        _drop_product_modules(root)
        _reset_package_state()
        # The consoles read the environment and the terminal when they are made: make them again
        # for this request's streams (same objects, other modules hold them).
        Console.__init__(console, highlight=False)
        Console.__init__(err_console, stderr=True, highlight=False)
        try:
            run_app(list(req["argv"]), prog_name=str(req.get("prog") or "n2f"))
        except SystemExit as exc:
            code, text = _exit_code(exc.code)
            if text:
                err.write(text)
        except Exception as exc:
            tb = traceback.format_exc()
            err.write(tb)
            argv = list(req.get("argv", []))
            if "--json" in argv:
                lines = tb.rstrip().splitlines()
                last_line = lines[-1] if lines else str(exc)
                klass = verb_class(argv)
                if klass is not None and klass.changes_state and klass.look_at:
                    dir_toks = _dir_tokens(argv)
                    if dir_toks:
                        cmd = shlex.join([*shlex.split(klass.look_at), *dir_toks])
                    else:
                        cmd = klass.look_at
                else:
                    cmd = (
                        f"N2F_NO_ENGINE=1 n2f {shlex.join(argv)}" if argv else "N2F_NO_ENGINE=1 n2f"
                    )
                payload = {
                    "error": "engine_internal",
                    "message": last_line,
                    "next": cmd,
                    "log": str(log_path(root)),
                }
                out.write(json.dumps(payload) + "\n")
                code = EXIT_INTERNAL
            else:
                code = 1
    finally:
        with contextlib.suppress(Exception):
            out.flush()
            err.flush()
        sys.stdin, sys.stdout, sys.stderr = saved_std
        sys.argv = saved_argv
        sys.path[:] = saved_path
        os.environ.clear()
        os.environ.update(saved_env)
        with contextlib.suppress(OSError):
            os.chdir(saved_cwd)
        for name in set(sys.modules) - before:
            if _is_product_module(name, sys.modules[name], root):
                del sys.modules[name]
    return code


def _preload_kernel(engine: Engine) -> None:
    """Import the CAD kernel before the engine binds its socket (S-311).

    The import holds the interpreter for seconds under load, so a thread doing it starved the
    accept loop (a status call timed out right after ``engine start``). Imported first, the
    engine is unreachable, and a command meanwhile simply runs cold, until it can answer.
    """
    with contextlib.suppress(Exception):
        import build123d  # noqa: F401
    engine.last_active = time.monotonic()
    engine.warm = True


def serve_main() -> None:
    """Entry of the engine process, started by :func:`spawn` with the product folder as argument."""
    root = Path(os.path.realpath(sys.argv[1]))
    prepare_runtime_dir(root)
    lock = os.open(lock_path(root), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return  # another engine holds this product
    code = package_code()
    sock = socket_path(root)
    with contextlib.suppress(FileNotFoundError):
        sock.unlink()  # a stale one: we hold the lock, so nobody serves it
    # named at once, so `engine stop` can end an engine that is still importing (S-311)
    pid_path(root).write_text(
        json.dumps({"pid": os.getpid(), "socket": str(sock), "started": time.time()}) + "\n",
        encoding="utf-8",
    )
    import napkin2factory.cli.app  # noqa: F401  (the package imports: the 1.1 s a client saves)

    idle = float(os.environ.get(IDLE_ENV, IDLE_SECONDS))
    limit = int(os.environ.get(MAX_REQUESTS_ENV, MAX_REQUESTS))
    engine = Engine(
        root,
        lambda req, out, err: run_in_process(req, out, err, root),
        code=code,
        version=_version(),
        idle=idle,
        max_requests=limit,
    )
    _preload_kernel(engine)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old_umask = os.umask(0o177)
    try:
        server.bind(os.fspath(sock))
    finally:
        os.umask(old_umask)
    os.chmod(sock, 0o600)
    server.listen(16)
    pid_path(root).write_text(
        json.dumps({"pid": os.getpid(), "socket": str(sock), "started": engine.started}) + "\n",
        encoding="utf-8",
    )

    def accept_loop() -> None:
        while not engine.done.is_set():
            try:
                conn, _ = server.accept()
            except OSError:
                return
            threading.Thread(target=engine.handle, args=(conn,), daemon=True).start()

    def stop(_signum: int, _frame: Any) -> None:
        engine.done.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    threading.Thread(target=accept_loop, daemon=True).start()
    try:
        engine.run_jobs()
    finally:
        engine.done.set()
        with contextlib.suppress(OSError):
            server.close()
        for path in (sock, pid_path(root)):
            with contextlib.suppress(OSError):
                path.unlink()
        sys.stdout.flush()
        os._exit(0)  # a kernel import may still be running in its thread


# ---------------------------------------------------------------------------------------------
# the client


class NotReady(Exception):
    """No engine took the command (nothing was run): run it cold."""

    def __init__(self, why: str, stale: bool = False) -> None:
        super().__init__(why)
        self.why, self.stale = why, stale


class Dropped(Exception):
    """The connection broke after ``run`` was sent: the command may have partly executed."""


def request_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """The part of the environment a request carries."""
    return {k: v for k, v in (env if env is not None else os.environ).items() if _managed(k)}


def terminal_columns() -> int | None:
    """The width of the terminal the client sits in, as Rich would find it, or None."""
    for fd in (0, 1, 2):
        try:
            return os.get_terminal_size(fd).columns
        except OSError:
            continue
    return None


def _program_name() -> str:
    try:
        from click.utils import _detect_program_name

        return str(_detect_program_name())
    except Exception:
        return "n2f"


def converse(
    sock: socket.socket,
    argv: list[str],
    cwd: str,
    *,
    on_out: Callable[[str], None],
    on_err: Callable[[str], None],
    version: str | None = None,
    code: str | None = None,
    python: str | None = None,
    env: Mapping[str, str] | None = None,
    tty: bool = False,
    etty: bool | None = None,
    cols: int | None = None,
    prog: str | None = None,
    deadline: float | None = None,
) -> int:
    """Say hello on a connected ``sock``, send the command, relay its output, return its exit code.

    Raises:
        NotReady: refused, closed or silent before ``ready``; nothing ran.
        Dropped: the stream ended after ``run`` was sent, without an ``exit``.
    """
    wire = Wire(sock)
    try:
        sock.settimeout(HELLO_TIMEOUT)
        try:
            wire.send(
                "hello",
                pkg=version if version is not None else _version(),
                code=code if code is not None else package_code(),
                py=python or sys.executable,
            )
            reply = wire.recv()
        except (OSError, ProtocolError) as exc:
            raise NotReady(f"no hello reply: {exc}") from exc
        if reply is None:
            raise NotReady("closed before ready")
        if reply["t"] == "refuse":
            why = str(reply.get("why", ""))
            raise NotReady(why, stale=why.startswith("package"))
        if reply["t"] != "ready":
            raise NotReady(f"unexpected {reply['t']!r} for hello")
        sock.settimeout(None)
        sent = wire.send(
            "run",
            argv=argv,
            cwd=cwd,
            env=request_env(env),
            tty=tty,
            etty=tty if etty is None else etty,
            cols=cols,
            prog=prog or _program_name(),
        )
        if not sent:
            raise Dropped("send failed")
        error: str | None = None
        while True:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("the command ran longer than allowed")
                sock.settimeout(remaining)
            try:
                msg = wire.recv()
            except TimeoutError:
                raise
            except (OSError, ProtocolError) as exc:
                raise Dropped(str(exc)) from exc
            if msg is None:
                raise Dropped("closed")
            kind = msg["t"]
            if kind == "out":
                on_out(str(msg.get("d", "")))
            elif kind == "err":
                on_err(str(msg.get("d", "")))
            elif kind == "error":
                error = str(msg.get("msg", ""))
            elif kind == "exit":
                if error is not None:
                    on_err(f"n2f engine: {error}\n")
                return int(msg.get("code", EXIT_INTERNAL))
    finally:
        wire.close()


def connect(sock_path: Path, timeout: float = CONNECT_TIMEOUT) -> socket.socket | None:
    """A connected socket to the engine at ``sock_path``, or None."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(os.fspath(sock_path))
    except OSError:
        s.close()
        return None
    return s


def verb_path(argv: list[str]) -> tuple[str, ...]:
    """The command path of ``argv``: ``("build",)``, or ``("ecr", "impact")`` for a group verb."""
    if not argv:
        return ()
    if argv[0] in _GROUPS:
        sub = next((a for a in argv[1:] if not a.startswith("-")), None)
        return (argv[0], sub) if sub is not None else (argv[0],)
    return (argv[0],)


def verb_class(argv: list[str]) -> VerbClass | None:
    """The class of the verb ``argv`` runs, or None when it is not in :data:`VERB_CLASSES`."""
    return VERB_CLASSES.get(verb_path(argv))


def verb_allowed(argv: list[str]) -> bool:
    """True when ``argv`` is a command the engine may run (it is in :data:`VERB_CLASSES`)."""
    if verb_class(argv) is None:
        return False
    return not any(a in ("--help", "-h") for a in argv)


def _dir_tokens(argv: list[str]) -> list[str]:
    """The ``--dir``/``-C`` words of ``argv``: a command built with them acts on the same folder."""
    out: list[str] = []
    for i, arg in enumerate(argv):
        if arg in ("--dir", "-C") and i + 1 < len(argv):
            out += [arg, argv[i + 1]]
        elif arg.startswith(("--dir=", "-C")) and arg != "-C":
            out.append(arg)
        elif arg == "--":
            break
    return out


def stopped_during(argv: list[str], klass: VerbClass) -> tuple[str, str]:
    """(stdout, stderr) for a state-changing verb whose engine stopped under it; never rerun.

    The text names what happened, what to look at to learn whether it happened and the exact
    command to run if it did not. With ``--json`` in ``argv`` stdout is one JSON object with the
    same facts (the machine-readable outcome); stderr always has the text.
    """
    cmd = "n2f " + shlex.join(argv)
    look = shlex.join([*shlex.split(klass.look_at or "n2f status"), *_dir_tokens(argv)])
    text = (
        f"the n2f engine stopped during `{cmd}`; the change may or may not have been made.\n"
        f"look at: {look}\n"
        f"if it did not happen, run again: {cmd}\n"
    )
    stdout = ""
    if "--json" in argv:
        stdout = (
            json.dumps(
                {
                    "error": "engine_stopped",
                    "message": (
                        f"the n2f engine stopped during `{cmd}`; the change may or may not have "
                        "been made"
                    ),
                    "next": f"run `{look}` to see whether it happened; if not, run `{cmd}` again",
                    "changes_state": True,
                    "outcome": "unknown",
                    "look_at": look,
                    "rerun": cmd,
                    "exit": EXIT_INTERNAL,
                },
                indent=2,
            )
            + "\n"
        )
    return stdout, text


RERUN_LINE = "the n2f engine stopped during this command; running it again without the engine\n"


def product_of(argv: list[str], cwd: Path | None = None) -> Path | None:
    """The product folder ``argv`` acts on (``--dir``/``-C``, else upward from ``cwd``), or None."""
    base = Path(cwd) if cwd is not None else Path.cwd()
    given: str | None = None
    for i, arg in enumerate(argv):
        if arg in ("--dir", "-C") and i + 1 < len(argv):
            given = argv[i + 1]
        elif arg.startswith("--dir="):
            given = arg[len("--dir=") :]
        elif arg.startswith("-C") and len(arg) > 2:
            given = arg[2:]
        elif arg == "--":
            break
    if given is not None:
        folder = (base / given).resolve()
        return folder if (folder / "n2f.yaml").is_file() else None
    cur = base.resolve()
    for p in (cur, *cur.parents):
        if (p / "n2f.yaml").is_file():
            return p
    return None


_spawned = False


def spawn(root: Path) -> subprocess.Popen[bytes] | None:
    """Start an engine for the product at ``root`` in the background unless one runs or starts.

    Any initialised product folder qualifies (built or not); the engine's files live in
    :func:`runtime_dir`, never in the product. Returns the process, or None when nothing was
    started (an engine holds the lock, or the runtime folder is not usable).
    """
    global _spawned
    try:
        prepare_runtime_dir(root)
        fd = os.open(lock_path(root), os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return None  # an engine holds the lock: running, or still starting
    finally:
        os.close(fd)
    _spawned = True
    try:
        with open(log_path(root), "wb") as log:  # a crash leaves its traceback here
            return subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "from napkin2factory.cli.engine import serve_main; serve_main()",
                    str(root),
                ],
                cwd="/",
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
    except OSError:
        return None


def request_stop(root: Path) -> bool:
    """Ask the engine of ``root`` to exit once it is idle; True when one answered."""
    s = connect(socket_path(root))
    if s is None:
        return False
    wire = Wire(s)
    try:
        s.settimeout(HELLO_TIMEOUT)
        wire.send("stop")
        return wire.recv() is not None
    except (OSError, ProtocolError):
        return False
    finally:
        wire.close()


def stop_engine(root: Path, wait: float = 15.0) -> str:
    """Stop the engine of ``root``; returns what happened: ``stopped``, ``none`` or ``killed``.

    It asks politely (the engine finishes the request in flight), then SIGTERM, then SIGKILL,
    and removes a stale socket and pid file.
    """
    pid = _pid_of(root)
    asked = request_stop(root)
    if pid is None and not asked:
        _remove_stale(root)
        return "none"
    killed = False
    deadline = time.monotonic() + (wait if asked else 0.0)
    while time.monotonic() < deadline:
        if pid is None or not _alive(pid):
            break
        time.sleep(0.05)
    else:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            if pid is not None and _alive(pid) and _is_engine_process(pid):
                with contextlib.suppress(OSError):
                    os.kill(pid, sig)
                killed = True
                for _ in range(100):
                    if not _alive(pid):
                        break
                    time.sleep(0.05)
    _remove_stale(root)
    return "killed" if killed else "stopped"


def _pid_of(root: Path) -> int | None:
    try:
        pid = int(json.loads(pid_path(root).read_text(encoding="utf-8"))["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return pid if _alive(pid) else None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # a zombie child we started (the tests') counts as gone
    try:
        out = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False
        ).stdout.strip()
    except OSError:
        return True
    return bool(out) and not out.startswith("Z")


def _is_engine_process(pid: int) -> bool:
    try:
        out = subprocess.run(
            ["ps", "-ww", "-o", "command=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except OSError:
        return False
    return "napkin2factory.cli.engine" in out


def _remove_stale(root: Path) -> None:
    """Remove the socket and pid file when no engine holds the lock."""
    try:
        fd = os.open(lock_path(root), os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    finally:
        os.close(fd)
    for path in (socket_path(root), pid_path(root)):
        with contextlib.suppress(OSError):
            path.unlink()


def engine_status(root: Path) -> dict[str, Any] | None:
    """The running engine's status object, or None when none answers."""
    s = connect(socket_path(root))
    if s is None:
        return None
    wire = Wire(s)
    try:
        s.settimeout(HELLO_TIMEOUT)
        wire.send("status")
        reply = wire.recv()
    except (OSError, ProtocolError):
        return None
    finally:
        wire.close()
    if reply is None or reply["t"] != "status":
        return None
    return {k: v for k, v in reply.items() if k not in ("v", "t")} | {
        "socket": str(socket_path(root))
    }


def try_forward(argv: list[str]) -> int | None:
    """Run ``argv`` through the product's engine; return its exit code, or None to run cold.

    None means the command did not complete in the engine and the caller runs it cold: the verb
    is not forwarded, the engine is off, absent, refused or silent (nothing ran, no message), or
    the connection dropped after ``run`` for a ``SAFE`` verb (one line on stderr first, since
    repeating it is harmless). A dropped connection under a verb that changes state is never
    repeated: it prints what happened, what to look at and what to run, and returns 70.

    When stdout is not a terminal the output is held until the engine's ``exit``, so a command
    that is run again never repeats partial output; on a terminal it streams live.
    """
    if engine_disabled() or not verb_allowed(argv):
        return None
    klass = verb_class(argv)
    assert klass is not None
    try:  # nothing here has run the command: whatever goes wrong, run it cold
        root = product_of(argv)
        if root is None:
            return None
        s = connect(socket_path(root))
        if s is None:
            spawn(root)
            return None
        stdout, stderr = sys.stdout, sys.stderr
        cwd, tty, etty, cols = os.getcwd(), stdout.isatty(), stderr.isatty(), terminal_columns()
    except Exception:
        return None

    held: list[tuple[TextIO, str]] = []

    def write(stream: TextIO) -> Callable[[str], None]:
        def put(text: str) -> None:
            if tty:
                stream.write(text)
                stream.flush()
            else:
                held.append((stream, text))

        return put

    try:
        code = converse(
            s, argv, cwd, on_out=write(stdout), on_err=write(stderr), tty=tty, etty=etty, cols=cols
        )
        for stream, text in held:
            stream.write(text)
        for stream in {id(st): st for st, _ in held}.values():
            stream.flush()
        return code
    except NotReady as exc:
        if exc.stale:
            request_stop(root)
        return None
    except Dropped:
        if not klass.changes_state:
            sys.stderr.write(RERUN_LINE)
            sys.stderr.flush()
            return None
        out, err = stopped_during(argv, klass)
        if out:
            sys.stdout.write(out)
            sys.stdout.flush()
        sys.stderr.write(err)
        return EXIT_INTERNAL
    except BrokenPipeError:
        return 141
    except KeyboardInterrupt:
        return 130


def after_cold(argv: list[str]) -> None:
    """After a cold run, start the engine if none is up (the product may have just been built)."""
    if _spawned or engine_disabled() or not verb_allowed(argv):
        return
    with contextlib.suppress(Exception):
        root = product_of(argv)
        if root is not None and connect(socket_path(root)) is None:
            spawn(root)


def capture(
    root: Path, argv: list[str], timeout: float | None = None
) -> tuple[int, str, str] | None:
    """Run ``argv`` in ``root`` through its engine and return (exit code, stdout, stderr).

    None when the caller should run the command itself: no engine took it (off, absent,
    refused: nothing ran; an engine is started for the next call), or the connection dropped
    after ``run`` under a ``SAFE`` verb (repeating it is harmless). A drop under a verb that
    changes state is never repeated: exit code 70 and the same outcome as the CLI client
    (:func:`stopped_during`). For the MCP server (S-255), which runs without a terminal.
    """
    if engine_disabled() or not verb_allowed(argv):
        return None
    s = connect(socket_path(root))
    if s is None:
        spawn(root)
        return None
    out: list[str] = []
    err: list[str] = []
    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        code = converse(s, argv, str(root), on_out=out.append, on_err=err.append, deadline=deadline)
    except NotReady as exc:
        if exc.stale:
            request_stop(root)
        return None
    except Dropped:
        klass = verb_class(argv)
        if klass is None or not klass.changes_state:
            return None
        stdout, stderr = stopped_during(argv, klass)
        return EXIT_INTERNAL, stdout, stderr
    return code, "".join(out), "".join(err)


# ---------------------------------------------------------------------------------------------
# the verbs `n2f engine start|status|stop`


def engine_starting(root: Path) -> bool:
    """True when an engine process for ``root`` holds the lock but does not answer yet."""
    try:
        fd = os.open(lock_path(root), os.O_RDWR)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    finally:
        os.close(fd)
    return False


def start_outlook(root: Path) -> tuple[bool, str]:
    """Whether the next forwarded command in ``root`` will start an engine, and why (not)."""
    if engine_disabled():
        return False, "N2F_NO_ENGINE is set, so commands run in their own process"
    if engine_starting(root):
        return (
            False,
            "an engine for this product is still loading; commands run normally until it is ready",
        )
    return True, "this folder is an initialised product and N2F_NO_ENGINE is not set"


def status_report(root: Path, dir_given: bool = False) -> dict[str, Any]:
    """Everything ``n2f engine status --json`` says about the engine of ``root``."""
    info = engine_status(root)
    will, reason = start_outlook(root)
    where = f" --dir {shlex.quote(str(root))}" if dir_given else ""
    return {
        "running": info is not None,
        "will_start_on_next_command": info is None and will,
        "reason": "an engine is running" if info is not None else reason,
        "start_command": f"n2f engine start{where}",
        "socket": str(socket_path(root)),
        "pid": None if info is None else info["pid"],
        "idle_s": None if info is None else info["idle_s"],
        "idle_left_s": None if info is None else info["idle_left_s"],
        "requests": None if info is None else info["requests"],
        "busy": None if info is None else info["busy"],
        "version": _version() if info is None else info["version"],
    }


def engine_app() -> typer.Typer:
    """The ``n2f engine`` verbs (built on demand: typer is not imported on the client path)."""
    import typer

    from napkin2factory.cli.common import (
        DirOption,
        JsonOption,
        emit_json,
        handle_errors,
        product_root,
    )
    from napkin2factory.core.errors import N2FError

    app = typer.Typer(
        help=(
            "The warm engine: a background process per product that keeps its n2f commands fast. "
            "Not this: `n2f serve` (the report on localhost), `n2f mcp` (tools over stdio)."
        ),
        no_args_is_help=True,
    )

    @app.command("start")
    @handle_errors
    def start(dir_: Path | None = DirOption, json_out: bool = JsonOption) -> None:
        """Start the engine for this product now (`n2f init` and the first command also do)."""
        root = product_root(dir_)
        if engine_disabled():
            raise N2FError(
                "N2F_NO_ENGINE is set, so commands would not use an engine",
                code="engine_disabled",
                next="unset N2F_NO_ENGINE, then run `n2f engine start`",
            )
        started = False
        status = engine_status(root)
        proc = None
        if status is None:
            proc = spawn(root)
            started = proc is not None
            deadline = time.monotonic() + 30.0
            while status is None and time.monotonic() < deadline:
                status = engine_status(root)
                if status is None and proc is not None and proc.poll() is not None:
                    raise N2FError(
                        "the engine stopped while starting",
                        code="engine_failed",
                        next=f"read {log_path(root)}",
                    )
                if status is None and proc is None and not engine_starting(root):
                    break
                time.sleep(0.1)
        if json_out:
            emit_json({**status_report(root, dir_ is not None), "started": started})
        elif status is None:
            typer.echo("the engine is still loading; `n2f engine status` says when it answers")
        elif not started:
            typer.echo("the engine is already running")
        else:
            typer.echo(f"the engine is running (process {status['pid']})")

    @app.command("status")
    @handle_errors
    def status(dir_: Path | None = DirOption, json_out: bool = JsonOption) -> None:
        """Say whether this product's engine runs; if not, whether the next command starts one."""
        root = product_root(dir_)
        report = status_report(root, dir_ is not None)
        if json_out:
            emit_json(report)
        elif report["running"]:
            busy = "running a command" if report["busy"] else f"idle {report['idle_s']:.0f} s"
            typer.echo(
                f"the engine is running (process {report['pid']}, {report['requests']} commands "
                f"served, {busy}; it leaves after {report['idle_left_s']:.0f} s more idle)"
            )
        elif report["will_start_on_next_command"]:
            typer.echo(
                "no engine is running for this product. The next build, check or other command "
                f"will start one ({report['reason']}). To start it now: {report['start_command']}"
            )
        else:
            typer.echo(
                f"no engine is running for this product, and none will start by itself: "
                f"{report['reason']}. To start one now: {report['start_command']}"
            )

    @app.command("stop")
    @handle_errors
    def stop(dir_: Path | None = DirOption, json_out: bool = JsonOption) -> None:
        """Stop this product's engine (it finishes the command in progress first)."""
        root = product_root(dir_)
        result = stop_engine(root)
        if json_out:
            emit_json({"running": False, "result": result})
        else:
            typer.echo("no engine was running" if result == "none" else "the engine is stopped")

    return app
