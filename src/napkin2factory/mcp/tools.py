"""The verb table behind the seven MCP tools, and the step runner (S-255, R14, S-327).

The tools an agent sees are the seven in ``combined.py``. This module is what they are built
from: :func:`build_tools` walks the Typer/Click tree and makes one :class:`Tool` (a *verb
entry*, not an MCP tool) from every leaf command, with the parameters the command takes.
:func:`build_argv` turns a verb entry and an argument dict into a command line, checking every
argument: unknown key, ``dir`` refused, types, choices, paths inside the folder. A verb added to
the CLI appears here with no edit. This module does not import the protocol library.

A step runs the CLI with ``--json`` whenever the verb has it and the folder the server was
opened on fixed as ``--dir``. An argument may not point anywhere else: ``dir`` is in no
schema, and a path argument that resolves outside the folder (``..``, an absolute path, a
symlink out) is refused (Track D section 3.4). Steps run one at a time (a lock in the
runner), as the CLI does not expect two runs on one folder.

Verbs left out, and why:

* ``mcp``: the server itself.
* ``serve``: it never returns (the report web server), so a call would hang; open
  ``build/report/index.html`` instead.
* ``skill``: it writes outside the product folder (a skills folder of the client).
* ``engine start|status|stop``: the warm engine's own controls; a step uses the engine when
  one is up (see :class:`StepRunner`), and an agent has no reason to manage it.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from napkin2factory.cli import engine

SKIPPED: frozenset[tuple[str, ...]] = frozenset(
    {
        ("mcp",),
        ("serve",),
        ("skill",),
        ("engine", "start"),
        ("engine", "status"),
        ("engine", "stop"),
    }
)

# A string option that names a file inside the folder. Path-typed options are found from their
# type; this is the one place a verb takes a path as plain text.
_PATH_TEXT_PARAMS = frozenset({"patch"})

DEFAULT_TIMEOUT = 1800.0  # seconds; a cold build of the largest example takes about a minute
MAX_TEXT = 200_000  # characters of one result (only with ``full``, S-327)
STDERR_LINES = 20


class ToolError(Exception):
    """A call that cannot run: the arguments are wrong. The message is for the agent."""


@dataclass(frozen=True)
class ToolResult:
    """What a call returns: the text, whether it failed, and the process exit code."""

    text: str
    is_error: bool
    exit_code: int | None = None


@dataclass(frozen=True)
class Param:
    """One exposed parameter of a verb."""

    key: str  # the property name in the tool's schema
    arg: Any  # the Click parameter
    positional: bool
    kind: str  # "text" | "integer" | "number" | "boolean" | "path"
    multiple: bool
    choices: tuple[str, ...] | None


@dataclass(frozen=True)
class Tool:
    """One verb as a tool."""

    name: str
    path: tuple[str, ...]
    description: str
    schema: dict[str, Any]
    params: tuple[Param, ...]
    # How the folder reaches the verb: the ``--dir`` option, a positional ``directory`` (``init``)
    # or nothing (``docs``, ``doctor``, ``version``).
    folder_option: str | None
    folder_positional: bool
    json_option: str | None


def _leaves(command: Any, path: tuple[str, ...]) -> list[tuple[tuple[str, ...], Any]]:
    """Every leaf command below ``command`` with its path, in name order."""
    children = getattr(command, "commands", None)
    if children is None:
        return [(path, command)]
    out: list[tuple[tuple[str, ...], Any]] = []
    for name in sorted(children):
        out.extend(_leaves(children[name], (*path, name)))
    return out


def _long(opts: list[str]) -> str:
    """The longest spelling of an option (``--dir`` over ``-C``)."""
    return max(opts, key=len)


def _kind(param: Any) -> str:
    """The schema kind of a Click parameter."""
    if getattr(param, "is_flag", False):
        return "boolean"
    name = str(param.type.name)
    if name in ("integer", "int"):
        return "integer"
    if name == "float":
        return "number"
    if name == "boolean":
        return "boolean"
    if name == "path":
        return "path"
    return "text"


def _json_default(value: Any) -> Any:
    """``value`` if it can sit in a schema as a default, else ``None``."""
    if value is None or value == [] or value == "":
        return None
    if isinstance(value, bool | int | float | str):
        return value
    return None


def _schema_of(param: Param) -> dict[str, Any]:
    """The JSON schema of one parameter."""
    item: dict[str, Any]
    if param.kind == "boolean":
        item = {"type": "boolean"}
    elif param.kind == "integer":
        item = {"type": "integer"}
    elif param.kind == "number":
        item = {"type": "number"}
    else:
        item = {"type": "string"}
    if param.choices:
        item["enum"] = list(param.choices)
    out: dict[str, Any] = {"type": "array", "items": item} if param.multiple else item
    bits: list[str] = []
    help_text = getattr(param.arg, "help", None)
    if help_text:
        bits.append(str(help_text).strip())
    if param.kind == "path":
        bits.append("A path inside the product folder.")
    if bits:
        out["description"] = " ".join(bits)
    default = _json_default(getattr(param.arg, "default", None))
    if default is not None and not param.positional:
        out["default"] = default
    return out


def _tool_of(path: tuple[str, ...], command: Any) -> Tool:
    """Make the tool of one leaf command."""
    folder_option: str | None = None
    folder_positional = False
    json_option: str | None = None
    params: list[Param] = []
    used: set[str] = set()
    for arg in command.params:
        if arg.name == "help":
            continue
        positional = type(arg).__name__.endswith("Argument")
        kind = _kind(arg)
        if not positional and "--dir" in arg.opts:
            folder_option = "--dir"
            continue
        if positional and arg.name == "directory" and kind == "path":
            folder_positional = True
            continue
        if not positional and "--json" in arg.opts:
            json_option = "--json"
            continue
        key = arg.name if positional else _long(arg.opts).lstrip("-").replace("-", "_")
        if key in used:
            key = str(arg.name)
        used.add(key)
        choices = tuple(arg.type.choices) if str(arg.type.name) == "choice" else None
        params.append(Param(key, arg, positional, kind, bool(arg.multiple), choices))
    properties = {p.key: _schema_of(p) for p in params}
    required = [p.key for p in params if getattr(p.arg, "required", False)]
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    name = "n2f_" + "_".join(part.replace("-", "_") for part in path)
    help_text = (command.help or "").strip()
    description = help_text or f"Runs `n2f {' '.join(path)}`."
    return Tool(
        name=name,
        path=path,
        description=description,
        schema=schema,
        params=tuple(params),
        folder_option=folder_option,
        folder_positional=folder_positional,
        json_option=json_option,
    )


def build_tools(app: typer.Typer | None = None) -> list[Tool]:
    """One tool per leaf command of ``app`` (the real ``n2f`` application by default)."""
    if app is None:
        from napkin2factory.cli.app import app as real_app

        app = real_app
    root = typer.main.get_command(app)
    tools: list[Tool] = []
    for path, command in _leaves(root, ()):
        if not path or path in SKIPPED or getattr(command, "hidden", False):
            continue
        tools.append(_tool_of(path, command))
    return tools


def _inside(folder: Path, value: str) -> str:
    """``value`` if it names something inside ``folder``; otherwise refuse."""
    root = folder.resolve()
    target = (root / value).resolve()
    if target != root and root not in target.parents:
        raise ToolError(f"{value!r} is outside the product folder; this server acts only inside it")
    return value


def _check(param: Param, value: Any, folder: Path) -> list[str]:
    """The command-line text of one value of ``param`` (one entry per repeat)."""
    values = value if param.multiple else [value]
    if param.multiple and not isinstance(value, list):
        raise ToolError(f"{param.key!r} must be a list")
    out: list[str] = []
    for item in values:
        if param.kind == "boolean":
            if not isinstance(item, bool):
                raise ToolError(f"{param.key!r} must be true or false")
            out.append("true" if item else "false")
            continue
        if param.kind == "integer":
            if isinstance(item, bool) or not isinstance(item, int):
                raise ToolError(f"{param.key!r} must be a whole number")
        elif param.kind == "number":
            if isinstance(item, bool) or not isinstance(item, int | float):
                raise ToolError(f"{param.key!r} must be a number")
        elif not isinstance(item, str):
            raise ToolError(f"{param.key!r} must be text")
        text = str(item)
        if param.choices and text not in param.choices:
            raise ToolError(f"{param.key!r} must be one of: {', '.join(param.choices)}")
        if param.kind == "path" or param.key in _PATH_TEXT_PARAMS:
            _inside(folder, text)
        out.append(text)
    return out


def build_argv(tool: Tool, arguments: dict[str, Any], folder: Path) -> list[str]:
    """The command line (after the interpreter) that runs ``tool`` on ``folder``.

    Raises:
        ToolError: an unknown argument (``dir`` included), a missing required one, a value of
            the wrong type, or a path outside the folder.
    """
    by_key = {p.key: p for p in tool.params}
    for key in arguments:
        if key not in by_key:
            if key in ("dir", "directory", "C"):
                raise ToolError(f"{key!r} cannot be set: this server acts only inside {folder}")
            raise ToolError(
                f"unknown argument {key!r}; the arguments are: {', '.join(by_key) or 'none'}"
            )
    for p in tool.params:
        if getattr(p.arg, "required", False) and p.key not in arguments:
            raise ToolError(f"{p.key!r} is required")
    options: list[str] = []
    positionals: list[str] = []
    for p in tool.params:
        if p.key not in arguments or arguments[p.key] is None:
            continue
        values = _check(p, arguments[p.key], folder)
        if p.positional:
            positionals.extend(values)
            continue
        flag = _long(p.arg.opts)
        if p.kind == "boolean" and getattr(p.arg, "is_flag", False):
            on = values == ["true"]
            default = bool(getattr(p.arg, "default", False))
            secondary = list(getattr(p.arg, "secondary_opts", []) or [])
            if on and not default:
                options.append(flag)
            elif not on and default and secondary:
                options.append(_long(secondary))
            continue
        # ``--name=value`` keeps a value that starts with a dash from being read as an option.
        options.extend(f"{flag}={v}" for v in values)
    if tool.json_option:
        options.append(tool.json_option)
    if tool.folder_option:
        options.append(f"{tool.folder_option}={folder}")
    if tool.folder_positional:
        positionals.insert(0, str(folder))
    argv = [*tool.path, *options]
    if positionals:
        argv.extend(["--", *positionals])
    return argv


def _clip(text: str) -> str:
    """``text`` cut to :data:`MAX_TEXT` characters, saying so."""
    if len(text) <= MAX_TEXT:
        return text
    return text[:MAX_TEXT] + f"\n[output cut at {MAX_TEXT} characters]"


def _tail(text: str, lines: int = STDERR_LINES) -> str:
    """The last ``lines`` lines of ``text``."""
    return "\n".join(text.strip().splitlines()[-lines:])


@dataclass(frozen=True)
class Step:
    """One finished command: what ran, how it ended, and through which process."""

    argv: list[str]
    exit: int
    stdout: str
    stderr: str
    engine: str  # "warm" (the folder's engine ran it) or "cold" (a process of its own)
    seconds: float


class StepRunner:
    """Runs the steps of one product folder: through its warm engine, else as a process.

    The engine takes the same argv and streams back the same output (``cli/engine.py``, S-305).
    When none answers (off, absent, refused) the CLI runs as a process, and ``capture`` has
    started an engine for the next step. A verb the engine never forwards (``init``,
    ``decide``) also starts one afterwards, so no call leaves the folder without an engine
    (S-327). Steps take turns.
    """

    def __init__(self, folder: Path, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Open the runner on ``folder``."""
        self.folder = folder.resolve()
        self.timeout = timeout
        self._lock = asyncio.Lock()
        self._had_engine = False

    async def start(self) -> None:
        """At server start: note whether an engine answers; start one for a product folder."""
        if engine.engine_disabled():
            return
        self._had_engine = await asyncio.to_thread(engine.engine_status, self.folder) is not None
        await self._ensure_engine()

    async def close(self) -> None:
        """At server exit: stop an engine this server started; leave another's alone (S-291).

        One still loading the CAD kernel does not answer yet, so it is found by its lock or pid
        file and stopped all the same (an agent session leaves no process behind).
        """
        if engine.engine_disabled() or self._had_engine:
            return
        await asyncio.to_thread(self._stop_ours)

    def _stop_ours(self) -> None:
        """Stop the folder's engine if one runs or is loading."""
        running = engine.engine_status(self.folder) is not None
        if running or engine.engine_starting(self.folder):
            engine.stop_engine(self.folder, wait=5.0)

    async def _ensure_engine(self) -> None:
        """Start the folder's engine when it is a product folder and none runs or starts."""
        if engine.engine_disabled() or not (self.folder / "n2f.yaml").is_file():
            return
        await asyncio.to_thread(engine.spawn, self.folder)

    async def run(self, argv: list[str]) -> Step:
        """Run ``argv`` (the arguments after ``n2f``) in the folder and report how it ended."""
        async with self._lock:
            began = time.monotonic()
            step = await self._run(argv)
            step = Step(
                step.argv, step.exit, step.stdout, step.stderr, step.engine,
                round(time.monotonic() - began, 2),
            )  # fmt: skip
            if step.engine == "cold" and engine.verb_class(argv) is None:
                await self._ensure_engine()
            return step

    async def _run(self, argv: list[str]) -> Step:
        """The step, without its timing."""
        if not (self.folder / "n2f.yaml").is_file():
            # Not a product yet (an empty folder before init): no engine is started here, as
            # `capture` would; `n2f docs` and `init` run cold (S-291, S-327).
            return await self._cold(argv)
        try:
            warm = await asyncio.to_thread(engine.capture, self.folder, argv, self.timeout)
        except TimeoutError:
            return Step(argv, 124, "", self._timed_out(), "warm", 0.0)
        if warm is not None:
            return Step(argv, warm[0], warm[1], warm[2], "warm", 0.0)
        return await self._cold(argv)

    async def _cold(self, argv: list[str]) -> Step:
        """Run ``argv`` as a process of its own."""
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "napkin2factory.cli",
            *argv,
            cwd=self.folder,
            env=dict(os.environ),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), self.timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return Step(argv, 124, "", self._timed_out(), "cold", 0.0)
        return Step(
            argv,
            proc.returncode or 0,
            out.decode("utf-8", "replace"),
            err.decode("utf-8", "replace"),
            "cold",
            0.0,
        )

    def _timed_out(self) -> str:
        """The stderr of a step that ran too long."""
        return f"stopped: the command ran longer than {self.timeout:.0f} s"
