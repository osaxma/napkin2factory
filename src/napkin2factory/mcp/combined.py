"""The seven MCP tools, each a short sequence of ``n2f`` steps (S-327, S-308, M8).

An agent client sees seven tools, not one per verb: ``n2f_init_product``, ``n2f_napkin_sync``,
``n2f_promote_or_switch``, ``n2f_context``, ``n2f_sync``, ``n2f_decide`` and ``n2f_ecr``. A call
runs its steps in order through :class:`~napkin2factory.mcp.tools.StepRunner` (the folder's warm
engine, else a cold process), and answers with one JSON object::

    {"tool": ..., "ok": ..., "steps": [{"command", "exit", "engine", "seconds", "error"?}],
     ...the tool's summary fields..., "next": {"tool": ..., "arguments": {...}} | {"say": ...}}

The agent is the first caller (S-308): every outcome says what happened and the exact next call.
The result is small by default (S-327): a step carries no verb output unless it failed, lists are
cut at :data:`LIST_CAP` with a ``more`` count, and ``full: true`` adds each step's verb JSON.
This module does not import the protocol library.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from napkin2factory.mcp.tools import (
    MAX_TEXT,
    Step,
    StepRunner,
    Tool,
    ToolError,
    ToolResult,
    _tail,
    build_argv,
    build_tools,
)

LIST_CAP = 10  # items of a list in a summary
TEXT_CAP = 300  # characters of one text in a summary
REASON_CAP = 1200  # characters of one screening reason: its numbers, limit and formula
SUMMARY_LIMIT = 4000  # characters of a default result (a test holds the real results to it)
PAGE_LIMIT = 4000  # a docs page longer than this is offered as sections (S-327)

#: The gate-failing exit of ``n2f check``: an outcome the tool reports, not a stop.
CHECK_EXIT = 5

#: ``n2f_promote_or_switch`` actions and the ``concept`` verb each runs.
CONCEPT_ACTIONS: dict[str, tuple[str, ...]] = {
    "new": ("concept", "new"),
    "promote": ("concept", "promote"),
    "switch": ("concept", "switch"),
    "fork": ("concept", "fork-from-model"),
    "reject": ("concept", "reject"),
    "compare": ("concept", "compare"),
    "list": ("concept", "list"),
    "show": ("concept", "show"),
}

#: ``n2f_ecr`` actions and the verb each runs; the first group changes state.
ECR_CHANGING: dict[str, tuple[str, ...]] = {
    "quick": ("ecr", "quick"),
    "start": ("ecr", "start"),
    "approve": ("ecr", "approve"),
    "close": ("ecr", "close"),
    "abort": ("ecr", "abort"),
    "undo": ("undo",),
    "redo": ("redo",),
    "rollback": ("rollback",),
}
ECR_READING: dict[str, tuple[str, ...]] = {
    "impact": ("ecr", "impact"),
    "list": ("ecr", "list"),
    "show": ("ecr", "show"),
    "checkpoints": ("checkpoints",),
}
ECR_ACTIONS = {**ECR_CHANGING, **ECR_READING}

#: Where a CLI command named in a verb's ``next`` is covered by a tool: command path ->
#: (tool, action or None, the name its one positional word takes or None). A command not here
#: has no tool, so its ``next`` goes to the agent as ``{"say": ...}``. A test walks the real
#: command tree against this table and ``UNMAPPED``.
COMMAND_TOOLS: dict[tuple[str, ...], tuple[str, str | None, str | None]] = {
    ("init",): ("n2f_init_product", None, None),
    ("status",): ("n2f_sync", None, None),
    ("validate",): ("n2f_sync", None, None),
    ("lint",): ("n2f_sync", None, None),
    ("build",): ("n2f_sync", None, None),
    ("check",): ("n2f_sync", None, None),
    ("decide",): ("n2f_decide", None, "check"),
    ("docs",): ("n2f_context", None, "topic"),
    ("context",): ("n2f_context", None, "uri"),
    ("concept", "lint"): ("n2f_napkin_sync", None, None),
    ("concept", "build"): ("n2f_napkin_sync", None, "concept"),
    ("concept", "board"): ("n2f_napkin_sync", None, None),
    ("concept", "new"): ("n2f_promote_or_switch", "new", "title"),
    ("concept", "promote"): ("n2f_promote_or_switch", "promote", "concept_id"),
    ("concept", "switch"): ("n2f_promote_or_switch", "switch", "concept_id"),
    ("concept", "fork-from-model"): ("n2f_promote_or_switch", "fork", None),
    ("concept", "reject"): ("n2f_promote_or_switch", "reject", "concept_id"),
    ("concept", "compare"): ("n2f_promote_or_switch", "compare", "cards"),
    ("concept", "list"): ("n2f_promote_or_switch", "list", None),
    ("concept", "show"): ("n2f_promote_or_switch", "show", "concept_id"),
    ("ecr", "quick"): ("n2f_ecr", "quick", None),
    ("ecr", "start"): ("n2f_ecr", "start", None),
    ("ecr", "impact"): ("n2f_ecr", "impact", "ecr_id"),
    ("ecr", "approve"): ("n2f_ecr", "approve", "ecr_id"),
    ("ecr", "close"): ("n2f_ecr", "close", "ecr_id"),
    ("ecr", "abort"): ("n2f_ecr", "abort", "ecr_id"),
    ("ecr", "list"): ("n2f_ecr", "list", None),
    ("ecr", "show"): ("n2f_ecr", "show", "ecr_id"),
    ("undo",): ("n2f_ecr", "undo", None),
    ("redo",): ("n2f_ecr", "redo", None),
    ("rollback",): ("n2f_ecr", "rollback", "target"),
    ("checkpoints",): ("n2f_ecr", "checkpoints", None),
}

#: Verbs with no tool: they write outside the folder, need the owner, or are not for an agent
#: here. Their ``next`` is passed on as text. A test keeps this list equal to what is left.
UNMAPPED: frozenset[tuple[str, ...]] = frozenset(
    {
        ("diff",),
        ("discard",),
        ("doctor",),
        ("graph",),
        ("impact",),
        ("publish",),
        ("release",),
        ("signoff",),
        ("snapshot",),
        ("version",),
    }
)


def command_to_call(command: str) -> dict[str, Any] | None:
    """The tool call that covers the CLI ``command`` (``n2f ecr list ...``), or None.

    Only the verb and its one leading positional word are carried over; a word like ``<name>``
    (a placeholder) is left out. ``--dir`` and ``--json`` never matter to a tool.
    """
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    if words and words[0] == "n2f":
        words = words[1:]
    path = next(
        (words[:n] for n in (2, 1) if tuple(words[:n]) in COMMAND_TOOLS and len(words) >= n), None
    )
    if path is None:
        return None
    tool, action, positional = COMMAND_TOOLS[tuple(path)]
    arguments: dict[str, Any] = {}
    if action:
        arguments["action"] = action
    rest = words[len(path) :]
    if positional and rest and not rest[0].startswith("-") and "<" not in rest[0]:
        arguments[positional] = rest[0]
    return {"tool": tool, "arguments": arguments}


def next_from(text: str, fallback: str | None = None) -> dict[str, Any]:
    """``next`` for a verb's own advice: the first command in backticks a tool covers, else text."""
    for found in re.findall(r"`(n2f [^`]+)`", text):
        call = command_to_call(found)
        if call is not None:
            return call
    return {"say": _clip(fallback if fallback is not None else text)}


def _clip(text: str, limit: int = TEXT_CAP) -> str:
    """``text`` cut to ``limit`` characters."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def compact(value: Any, depth: int = 0, levels: int = 2) -> Any:
    """A short form of a verb's JSON for a summary: scalars, short lists, no deep objects.

    ``levels=3`` keeps a listing's rows (``ecr list``: result, requests, one request); the
    trial's agent saw "5 fields" where the requests were (S-333).
    """
    if isinstance(value, str):
        return _clip(value)
    if isinstance(value, bool | int | float) or value is None:
        return value
    if isinstance(value, list):
        if depth >= levels:
            return f"{len(value)} items"
        shown = [compact(v, depth + 1, levels) for v in value[:LIST_CAP]]
        return shown if len(value) <= LIST_CAP else [*shown, f"… {len(value) - LIST_CAP} more"]
    if isinstance(value, dict):
        if depth >= levels:
            return f"{len(value)} fields"
        return {str(k): compact(v, depth + 1, levels) for k, v in list(value.items())[:20]}
    return _clip(str(value))


class _Stop(Exception):
    """A step failed and ends the tool; ``reason`` says what to tell the agent."""

    def __init__(self, step: Step, error: dict[str, Any], index: int) -> None:
        """Keep the failing ``step``, its ``error`` object and its 1-based ``index``."""
        super().__init__(error.get("message", ""))
        self.step = step
        self.error = error
        self.index = index


def _parse(step: Step) -> Any:
    """The step's stdout as JSON, or None."""
    try:
        return json.loads(step.stdout) if step.stdout.strip() else None
    except ValueError:
        return None


def _error_of(step: Step) -> dict[str, Any]:
    """The verb's error object (short), or its last words when it printed none."""
    data = _parse(step)
    if isinstance(data, dict) and "error" in data:
        out = {k: _clip(str(data[k])) for k in ("error", "message", "next", "look_at") if k in data}
        if "rerun" in data:
            out["rerun"] = _clip(str(data["rerun"]))
        return out
    return {"message": _clip(_tail(step.stderr or step.stdout, 6))}


class StepSource(Protocol):
    """What the tools need of a runner: run ``argv``. Tests give a fake one."""

    async def run(self, argv: list[str]) -> Step:
        """Run the CLI with ``argv``."""
        ...


class _Call:
    """One tool call: its steps so far, and the helper that runs the next one."""

    def __init__(self, runner: StepSource, verbs: dict[tuple[str, ...], Tool], folder: Path):
        self.runner = runner
        self.verbs = verbs
        self.folder = folder
        self.steps: list[Step] = []

    async def go(
        self, path: tuple[str, ...], args: dict[str, Any], ok_exits: tuple[int, ...] = (0,)
    ) -> Any:
        """Run the verb at ``path`` with ``args``; its JSON, or stop the tool when it failed."""
        argv = build_argv(self.verbs[path], args, self.folder)
        step = await self.runner.run(argv)
        self.steps.append(step)
        data = _parse(step)
        failed = step.exit not in ok_exits or (
            isinstance(data, dict) and data.get("error") == "engine_stopped"
        )
        if failed:
            raise _Stop(step, _error_of(step), len(self.steps))
        return data

    def step_dicts(self, full: bool) -> list[dict[str, Any]]:
        """The steps as the result lists them."""
        out = []
        for st in self.steps:
            d: dict[str, Any] = {
                "command": "n2f "
                + shlex.join(a for a in st.argv if not a.startswith("--dir=") and a != "--"),
                "exit": st.exit,
                "engine": st.engine,
                "seconds": st.seconds,
            }
            data = _parse(st)
            if isinstance(data, dict) and "error" in data:
                d["error"] = _error_of(st)
            elif st.exit not in (0, CHECK_EXIT):
                d["error"] = _error_of(st)
            if full:
                d["result"] = data if data is not None else {"output": _tail(st.stdout, 200)}
            out.append(d)
        return out


def _capped(out: dict[str, Any], key: str, items: list[Any]) -> None:
    """Put at most :data:`LIST_CAP` of ``items`` in ``out[key]``, counting the rest in ``more``."""
    out[key] = items[:LIST_CAP]
    if len(items) > LIST_CAP:
        out.setdefault("more", {})[key] = len(items) - LIST_CAP


# ---------------------------------------------------------------------------------------------
# the tools


def _need(args: dict[str, Any], *keys: str) -> None:
    """Refuse a call that lacks a required argument."""
    for key in keys:
        if args.get(key) in (None, ""):
            raise ToolError(f"{key!r} is required")


def _only(args: dict[str, Any], keys: tuple[str, ...], kinds: dict[str, type]) -> dict[str, Any]:
    """The arguments of ``keys`` that are set, each checked against its type."""
    out: dict[str, Any] = {}
    for key in keys:
        value = args.get(key)
        if value is None:
            continue
        if kinds[key] is bool and not isinstance(value, bool):
            raise ToolError(f"{key!r} must be true or false")
        if kinds[key] is str and not isinstance(value, str):
            raise ToolError(f"{key!r} must be text")
        out[key] = value
    return out


def _gates(status: Any) -> tuple[list[str], list[str]]:
    """(names of the gates not yet passed, their blockers) from ``status --json``."""
    gates = status.get("gates", []) if isinstance(status, dict) else []
    open_names = [g["name"] for g in gates if not g.get("ok")]
    blockers = [str(b) for g in gates if not g.get("ok") for b in g.get("blockers", [])]
    return open_names, blockers


async def init_product(c: _Call, args: dict[str, Any]) -> dict[str, Any]:
    """Make the product folder: ``init <folder>``."""
    _need(args, "name", "units")
    if (c.folder / "n2f.yaml").exists():
        return {
            "ok": False,
            "error": {"message": "this folder already has a product (n2f.yaml)"},
            "next": {"tool": "n2f_sync", "arguments": {}},
        }
    keys = ("name", "region", "units", "maker", "template", "style")
    data = await c.go(("init",), _only(args, keys, dict.fromkeys(keys, str)))
    data = data if isinstance(data, dict) else {}
    from napkin2factory.cli.init import cost_init_feedback

    region = args.get("region")
    maker = args.get("maker")
    costs, confirm, ask = cost_init_feedback(region, maker)
    out: dict[str, Any] = {
        "ok": True,
        "product": data.get("product"),
        "files": data.get("files"),
        "costs": data.get("costs") or costs,
        "read_first": ["AGENTS.md", "roles/pm.md"],
        "next": {
            "say": (
                "Read AGENTS.md and roles/pm.md in the folder. Then call n2f_promote_or_switch "
                "with action=new and title=<the owner's idea in a few words>."
            )
        },
    }
    conf = data.get("confirm") or confirm
    if conf:
        out["confirm"] = conf
    ask_qs = data.get("ask") or ask
    if ask_qs:
        out["ask"] = ask_qs
    return out


def _card(card: dict[str, Any]) -> dict[str, Any]:
    """One screened napkin card, short: id, title, verdict, the reasons it is not green."""
    rules = (card.get("screening") or {}).get("rules", [])
    reasons = [
        # The whole reason: what was computed, against what limit, and how (a 300-character cut
        # sent a trial agent to the source for the rest of a sag screen, S-333).
        {
            "id": r.get("id"),
            "status": r.get("status"),
            "message": _clip(str(r.get("message")), REASON_CAP),
        }
        for r in rules
        if r.get("status") in ("fail", "warn")
    ]
    out: dict[str, Any] = {
        "id": card.get("id"),
        "title": _clip(str(card.get("title")), 80),
        "screened": "fail" if card.get("verdict") == "red" else "pass",
        "verdict": card.get("verdict"),
        "summary": _clip(str(card.get("summary")), 160),
    }
    _capped(out, "reasons", reasons[:3])
    if len(reasons) > 3:
        out["more_reasons"] = len(reasons) - 3
    return out


def _finding(problem: Any, folder: Path) -> Any:
    """One lint finding as an object with the file relative to the folder (not its repr)."""
    if not isinstance(problem, dict):
        return _clip(str(problem))
    out = {k: problem[k] for k in ("subject", "message", "hint", "severity") if problem.get(k)}
    if problem.get("file"):
        path = Path(str(problem["file"]))
        out["file"] = str(path.relative_to(folder)) if path.is_relative_to(folder) else str(path)
    return {k: _clip(str(v)) for k, v in out.items()}


async def napkin_sync(c: _Call, args: dict[str, Any]) -> dict[str, Any]:
    """Lint the cards, build them, rebuild the board."""
    given = _only(args, ("concept", "render"), {"concept": str, "render": bool})
    lint = await c.go(("concept", "lint"), {}, ok_exits=(0, 1))
    raw = (lint or {}).get("problems", []) if isinstance(lint, dict) else []
    problems = [_finding(p, c.folder) for p in raw]
    if (isinstance(lint, dict) and not lint.get("ok", True)) or c.steps[-1].exit != 0:
        out: dict[str, Any] = {"ok": False, "lint": {"ok": False}}
        _capped(out["lint"], "problems", problems)
        out["next"] = {
            "say": "Fix the card files the findings name (concepts/), then call n2f_napkin_sync."
        }
        return out
    build_args: dict[str, Any] = {}
    if given.get("concept"):
        build_args["concept_id"] = given["concept"]
    else:
        build_args["all"] = True
    if given.get("render") is False:
        build_args["no_render"] = True
    built = await c.go(("concept", "build"), build_args)
    board = await c.go(("concept", "board"), {})
    cards = [_card(x) for x in (built or {}).get("concepts", [])]
    out = {"ok": True}
    _capped(out, "cards", cards)
    out["lint"] = {"ok": True}
    if isinstance(built, dict) and built.get("errors"):
        _capped(out, "build_errors", [_clip(str(e)) for e in built["errors"]])
    out["board"] = (board or {}).get("board") if isinstance(board, dict) else None
    pick = next((x for x in cards if x["verdict"] != "red"), cards[0] if cards else None)
    if pick is None:
        out["next"] = {"tool": "n2f_promote_or_switch", "arguments": {"action": "new"}}
    else:
        out["next"] = {
            "tool": "n2f_promote_or_switch",
            "arguments": {"action": "promote", "concept_id": pick["id"]},
            "first": "show the owner the board and ask which card to promote",
        }
    return out


def _seeded_view(seeded: dict[str, Any]) -> dict[str, Any]:
    """What promotion seeded as short lines (a deep object would read as "N fields", S-336)."""
    parts = [
        f"{p['uri']} x{p['qty']} ({p['kit']})"
        + (f", follows {', '.join(p['stretched_by'])}" if p.get("stretched_by") else "")
        for p in seeded.get("parts", [])
    ]
    view: dict[str, Any] = {
        "model_seeded": bool(seeded.get("model")),
        "parts": parts,
        "overall_sizes": seeded.get("overall_sizes", {}),
        "layout": seeded.get("layout", []),
        "structure_checks": seeded.get("structure_checks", []),
    }
    if seeded.get("skipped"):
        view["skipped"] = seeded["skipped"]
    elif seeded.get("model"):
        view["note"] = (
            "promotion seeded the parts, layout and structure checks: call n2f_sync to build "
            "and check, and never rewrite them by hand (change the overall sizes in "
            "parameters.yaml, or a part's row in its geometry module)"
        )
    return compact(view, 0, 3)  # type: ignore[no-any-return]


async def promote_or_switch(c: _Call, args: dict[str, Any]) -> dict[str, Any]:
    """Run one ``concept`` verb."""
    action = args.get("action")
    if action not in CONCEPT_ACTIONS:
        raise ToolError(f"'action' must be one of: {', '.join(CONCEPT_ACTIONS)}")
    rest = {k: v for k, v in args.items() if k != "action"}
    if action == "switch" and "concept_id" in rest:
        rest["card"] = rest.pop("concept_id")
    data = await c.go(CONCEPT_ACTIONS[action], rest)
    out: dict[str, Any] = {"ok": True, "action": action, "result": compact(data)}
    if action == "promote" and isinstance(data, dict) and isinstance(data.get("seeded"), dict):
        out["result"]["seeded"] = _seeded_view(data["seeded"])
    if action in ("promote", "switch"):
        out["next"] = {"tool": "n2f_sync", "arguments": {}}
    elif action in ("new", "fork"):
        cid = data.get("id") if isinstance(data, dict) else None
        out["next"] = {
            "tool": "n2f_napkin_sync",
            "arguments": {"concept": cid} if cid else {},
            "first": "fill in the card's file under concepts/ with your own file tools",
        }
    else:
        out["next"] = {
            "say": (
                "Show the owner the cards. When they choose one, call n2f_promote_or_switch "
                "with action=promote and concept_id=<its id>."
            )
        }
    return out


def _sections(text: str) -> list[tuple[str, str]]:
    """(heading, body including the heading line) for each heading outside code fences."""
    lines = text.splitlines()
    marks: list[tuple[int, str]] = []
    fenced = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and re.match(r"#{1,6} \S", line):
            marks.append((i, line.lstrip("#").strip()))
    out = []
    for n, (start, heading) in enumerate(marks):
        end = marks[n + 1][0] if n + 1 < len(marks) else len(lines)
        out.append((heading, "\n".join(lines[start:end]).strip()))
    return out


async def context(c: _Call, args: dict[str, Any]) -> dict[str, Any]:
    """A module's slice (``context``) or a docs page (``docs``), a section at a time."""
    uri, topic, section = args.get("uri"), args.get("topic"), args.get("section")
    if uri and topic:
        raise ToolError("give one of 'uri' or 'topic', not both")
    if section is not None and not topic:
        raise ToolError("'section' goes with 'topic'")
    if uri:
        if not isinstance(uri, str) or not uri.startswith("asm://"):
            return {
                "ok": False,
                "error": {"message": f"no context for {_clip(str(uri), 80)!r}"},
                "kinds": ["asm://<assembly id>"],
                "next": {"tool": "n2f_context", "arguments": {"topic": "agent-guide"}},
            }
        data = await c.go(("context",), {"module": uri})
        return {
            "ok": True,
            "uri": uri,
            "context": compact(data),
            "next": {"say": "Use this slice to edit the module's files, then call n2f_sync."},
        }
    if not topic:
        data = await c.go(("docs",), {})
        names = [t.get("topic") for t in (data or {}).get("topics", [])]
        return {
            "ok": True,
            "topics": names,
            "next": {"tool": "n2f_context", "arguments": {"topic": "agent-guide"}},
        }
    if topic == "materials":
        data = await c.go(("docs",), {"topic": topic})
        text = str((data or {}).get("text", ""))
        if section is None:
            return {"ok": True, "topic": topic, "text": text, "next": {"say": "Read it, then act."}}
        from napkin2factory.cli.docs import (
            format_material_row_whole,
            known_materials,
            lookup_material,
        )

        want = str(section).strip()
        row = lookup_material(want)
        if row is None:
            names = known_materials()
            msg = f"no material {_clip(want, 80)!r}; known materials: {', '.join(names)}"
            return {
                "ok": False,
                "error": {"message": msg},
                "materials": names,
                "next": {"tool": "n2f_context", "arguments": {"topic": "materials"}},
            }
        whole_text = format_material_row_whole(row)
        return {
            "ok": True,
            "topic": "materials",
            "section": row["name"],
            "material": row,
            "text": whole_text,
            "next": {"say": f"Use {row['name']} on your card massing, then call n2f_napkin_sync."},
        }
    data = await c.go(("docs",), {"topic": topic})
    text = str((data or {}).get("text", ""))
    parts = _sections(text)
    if section is None and len(text) <= PAGE_LIMIT:
        return {"ok": True, "topic": topic, "text": text, "next": {"say": "Read it, then act."}}
    listing = [{"n": i, "heading": h, "chars": len(b)} for i, (h, b) in enumerate(parts, 1)]
    if section is None:
        return {
            "ok": True,
            "topic": topic,
            "chars": len(text),
            "sections": listing[:40],
            "next": {"tool": "n2f_context", "arguments": {"topic": topic, "section": 1}},
            "then": "ask for the section you need by number or heading",
        }
    want = str(section).strip()
    hit = None
    if want.isdigit() and 1 <= int(want) <= len(parts):
        hit = int(want) - 1
    else:
        low = want.lower()
        hit = next(
            (i for i, (h, _) in enumerate(parts) if h.lower() == low),
            next((i for i, (h, _) in enumerate(parts) if low and low in h.lower()), None),
        )
    if hit is None:
        return {
            "ok": False,
            "error": {"message": f"no section {_clip(want, 80)!r} in {topic}"},
            "sections": listing[:40],
            "next": {"tool": "n2f_context", "arguments": {"topic": topic, "section": 1}},
        }
    nxt = {"tool": "n2f_context", "arguments": {"topic": topic, "section": hit + 2}}
    return {
        "ok": True,
        "topic": topic,
        "section": {"n": hit + 1, "heading": parts[hit][0]},
        "text": parts[hit][1],
        "next": nxt if hit + 1 < len(parts) else {"say": "That was the last section."},
    }


async def sync(c: _Call, args: dict[str, Any]) -> dict[str, Any]:
    """validate, lint, build, check, status: the gates and what fails."""
    given = _only(args, ("target", "part", "render"), {"target": str, "part": str, "render": bool})
    build_args = {k: v for k, v in given.items() if k in ("target", "part")}
    if given.get("render") is False:
        build_args["no_render"] = True
    await c.go(("validate",), {})
    await c.go(("lint",), {})
    await c.go(("build",), build_args)
    check = await c.go(("check",), {}, ok_exits=(0, CHECK_EXIT))
    status = await c.go(("status",), {})
    check = check if isinstance(check, dict) else {}
    results = check.get("results", [])
    failing = [
        {"id": r.get("id"), "message": _clip(str(r.get("message")), 200)}
        for r in results
        if r.get("status") == "fail"
    ]
    choices = [
        {
            "check": r.get("id"),
            "options": [
                {"id": o.get("id"), "summary": _clip(str(o.get("summary")), 120)}
                for o in (r.get("detail") or {}).get("options", [])
            ][:5],
        }
        for r in results
        if r.get("status") == "choice"
    ]
    open_gates, blockers = _gates(status)
    out: dict[str, Any] = {"ok": True, "check_exit": c.steps[3].exit}
    out["gates"] = [
        {"name": g["name"], "ok": bool(g.get("ok"))} for g in (status or {}).get("gates", [])
    ]
    out["counts"] = check.get("summary")
    _capped(out, "failing_checks", failing)
    _capped(out, "open_choices", choices)
    _capped(out, "blockers", [_clip(b, 200) for b in blockers])
    report = c.folder / "build" / "report" / "index.html"
    out["report"] = "build/report/index.html" if report.is_file() else None
    extra = ""
    if "more" in out:
        extra = " More are not shown: call n2f_sync with full=true."
    if choices:
        first = choices[0]
        out["next"] = {
            "tool": "n2f_decide",
            "arguments": {
                "check": first["check"],
                "pick": (first["options"][0]["id"] if first["options"] else "<option id>"),
                "by": "<the owner's name>",
            },
            "first": "ask the owner which option they want; do not choose for them",
        }
    elif failing:
        f = failing[0]
        out["next"] = {
            "say": f"Fix {f['id']}: {f['message']} Edit the model files, then call n2f_sync."
            + extra
        }
    elif open_gates:
        step = (status or {}).get("next_step") or "; ".join(blockers)
        out["next"] = next_from(str(step))
    else:
        out["next"] = {"say": "All gates pass. Show the owner build/report/index.html."}
    return out


async def decide(c: _Call, args: dict[str, Any]) -> dict[str, Any]:
    """Record the owner's pick for an open choice, then show the gates."""
    _need(args, "check", "pick", "by")
    keys = ("check", "pick", "by", "note")
    data = await c.go(("decide",), _only(args, keys, dict.fromkeys(keys, str)))
    status = await c.go(("status",), {})
    open_gates, _ = _gates(status)
    return {
        "ok": True,
        "decision": compact(data),
        "gates_open": open_gates,
        "next": {
            "tool": "n2f_sync",
            "arguments": {},
            "first": "make the change the pick needs in the model files",
        },
    }


def _vitals(status: Any) -> dict[str, Any]:
    """The vitals ``status --json`` has: the open gates and how many blockers they hold."""
    open_names, blockers = _gates(status)
    return {"gates_open": open_names, "blockers": len(blockers)}


async def ecr(c: _Call, args: dict[str, Any]) -> dict[str, Any]:
    """One change-request verb; a state-changing one is wrapped in two ``status`` steps."""
    action = args.get("action")
    if action not in ECR_ACTIONS:
        raise ToolError(f"'action' must be one of: {', '.join(ECR_ACTIONS)}")
    rest = {k: v for k, v in args.items() if k != "action"}
    changing = action in ECR_CHANGING
    before = _vitals(await c.go(("status",), {})) if changing else None
    data = await c.go(ECR_ACTIONS[action], rest)
    stepped: list[str] = []
    if action in ("undo", "redo"):
        data, stepped = await _whole_change(c, action, rest, data)
    levels = 3 if action in ("list", "show", "checkpoints") else 2
    out: dict[str, Any] = {"ok": True, "action": action, "result": compact(data, levels=levels)}
    if stepped:
        out["undid" if action == "undo" else "redid"] = stepped
    if changing and before is not None:
        after = _vitals(await c.go(("status",), {}))
        delta: dict[str, Any] = {
            "blockers": after["blockers"] - before["blockers"],
            "gates_opened": [g for g in after["gates_open"] if g not in before["gates_open"]],
            "gates_closed": [g for g in before["gates_open"] if g not in after["gates_open"]],
        }
        if isinstance(data, dict):
            for key in ("mass", "cost"):
                if isinstance(data.get(key), dict):
                    delta[key] = {k: data[key].get(k) for k in ("before", "after", "delta", "unit")}
            if isinstance(data.get("restored"), dict):
                delta["restored"] = {k: data["restored"].get(k) for k in ("label", "mass", "cost")}
        out |= {"before": before, "after": after, "delta": delta}
    out["next"] = _ecr_next(action, data)
    return out


def _name(value: Any) -> str:
    """The label of a checkpoint given as an object or as text."""
    label = value.get("label") if isinstance(value, dict) else value
    return str(label or "")


async def _whole_change(
    c: _Call, action: str, rest: dict[str, Any], first: Any
) -> tuple[Any, list[str]]:
    """Take ``undo`` or ``redo`` to the end of a change request, as the owner sees one.

    A change request leaves several checkpoints (``Started ECR-n``, its edit, the saved
    record); one ``undo`` steps over one. When the checkpoint just stepped over belongs to a
    request, the step is repeated while the state now in effect still belongs to the same
    request, and for ``undo`` stops once it is the ``Started`` one: the product is as before
    the request. A step over a checkpoint of no request stays one step (S-329).
    Returns the last result and the labels stepped over.
    """
    verb = "Undid: " if action == "undo" else "Redid: "

    def stepped_over(data: Any) -> str:
        label = _name(data.get("checkpoint")) if isinstance(data, dict) else ""
        return label.removeprefix(verb)

    data = first
    labels: list[str] = []
    done = "undone" if action == "undo" else "redone"
    if not (isinstance(data, dict) and data.get(done, True)):
        return data, labels
    labels.append(stepped_over(data))
    found = re.search(r"ECR-\d+", labels[0])
    for _ in range(4):
        if found is None or not isinstance(data, dict):
            break
        now = _name(data.get("restored"))
        if found.group(0) not in now or (action == "undo" and now.startswith("Started")):
            break
        again = await c.go(ECR_ACTIONS[action], rest)
        if not (isinstance(again, dict) and again.get(done, True)):
            break
        data = again
        labels.append(stepped_over(data))
    return data, labels


def _ecr_next(action: str, data: Any) -> dict[str, Any]:
    """What to call after an ``n2f_ecr`` action."""
    ecr_id = data.get("id") if isinstance(data, dict) else None
    if action == "start" and ecr_id:
        return {"tool": "n2f_ecr", "arguments": {"action": "impact", "ecr_id": ecr_id}}
    if action == "impact" and ecr_id:
        return {
            "tool": "n2f_ecr",
            "arguments": {"action": "approve", "ecr_id": ecr_id, "by": "<the owner's name>"},
            "first": "show the owner the impact and ask whether to approve",
        }
    if action == "approve":
        return {
            "say": "Make the approved edits in the model files, then call n2f_sync, "
            "then n2f_ecr with action=close."
        }
    if action == "list":
        return {"tool": "n2f_ecr", "arguments": {"action": "checkpoints"}}
    if action in ("show", "checkpoints"):
        return {"tool": "n2f_sync", "arguments": {}}
    return {"tool": "n2f_sync", "arguments": {}}


# ---------------------------------------------------------------------------------------------
# the tool list and the runner

_FULL = {"type": "boolean", "description": "Add each step's full verb JSON (long)."}
_S = {"type": "string"}
_B = {"type": "boolean"}


def _obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    """An input schema: ``props`` plus ``full``, nothing else allowed."""
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {**props, "full": _FULL},
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


@dataclass(frozen=True)
class CombinedTool:
    """One of the seven tools: name, description, input schema and the function behind it."""

    name: str
    description: str
    schema: dict[str, Any]
    run: Callable[[_Call, dict[str, Any]], Awaitable[dict[str, Any]]]


def build_combined() -> list[CombinedTool]:
    """The seven tools, in the order an agent uses them."""
    return [
        CombinedTool(
            "n2f_init_product",
            "Make a new product folder here. Ask the owner for the name, units, region and "
            "maker first; never infer region or maker from the machine or its time zone.",
            _obj(
                {
                    "name": {**_S, "description": "Product display name."},
                    "units": {"type": "string", "enum": ["metric", "imperial"]},
                    "region": {
                        "type": "string",
                        "enum": ["US", "UK", "EU", "AU", "SA"],
                        "description": "Where it is built and bought. Ask the owner, never infer.",
                    },
                    "maker": {
                        "type": "string",
                        "enum": ["owner", "shop"],
                        "description": (
                            "Who makes the custom parts (owner builds from retail stock; "
                            "shop quotes job-shop rates). Ask the owner, never infer."
                        ),
                    },
                    "template": {**_S, "description": "blank (default), bracket or enclosure."},
                    "style": {**_S, "description": "industrial (default), appliance or lab."},
                },
                ["name", "units"],
            ),
            init_product,
        ),
        CombinedTool(
            "n2f_napkin_sync",
            "Check the napkin cards, build them (rough 3D, screening) and refresh the board. "
            "One card or all.",
            _obj(
                {
                    "concept": {**_S, "description": "One card id, e.g. C-002. Default: all."},
                    "render": {**_B, "description": "Draw the pictures (default true)."},
                }
            ),
            napkin_sync,
        ),
        CombinedTool(
            "n2f_promote_or_switch",
            "Work with napkin cards: new, promote (make the product from a card), switch, "
            "fork (a card from the current model), reject, compare, list, show.",
            _obj(
                {
                    "action": {"type": "string", "enum": list(CONCEPT_ACTIONS)},
                    "title": {**_S, "description": "new, fork: the card's title."},
                    "from": {**_S, "description": "new: the card to start from."},
                    "concept_id": {**_S, "description": "promote, switch, reject, show."},
                    "cards": {**_S, "description": "compare: the card ids."},
                    "override": {**_B, "description": "promote, switch: go on despite red."},
                    "fresh": {**_B, "description": "switch: start from the card, not the model."},
                    "reason": _S,
                    "by": {**_S, "description": "Who decided."},
                },
                ["action"],
            ),
            promote_or_switch,
        ),
        CombinedTool(
            "n2f_context",
            "Read what you need: a docs page by topic (long pages come as a list of sections; "
            "ask for one with section) or one assembly's slice by uri. No arguments lists topics.",
            _obj(
                {
                    "topic": {**_S, "description": "e.g. agent-guide."},
                    "section": {**_S, "description": "With topic: a heading or its number."},
                    "uri": {**_S, "description": "asm://<assembly id>."},
                }
            ),
            context,
        ),
        CombinedTool(
            "n2f_sync",
            "After editing the model files: validate, lint, build, check and report the gates, "
            "the failing checks and any choice waiting on the owner.",
            _obj(
                {
                    "target": {**_S, "description": "What to build (default all)."},
                    "part": {**_S, "description": "Build one part only."},
                    "render": {**_B, "description": "Draw pictures and drawings (default true)."},
                }
            ),
            sync,
        ),
        CombinedTool(
            "n2f_decide",
            "Record the owner's pick for a choice that n2f_sync listed. Never pick for them.",
            _obj(
                {
                    "check": {**_S, "description": "The choice's check id."},
                    "pick": {**_S, "description": "The option id or number."},
                    "by": {**_S, "description": "The owner's name."},
                    "note": {**_S, "description": "Why, in their words."},
                },
                ["check", "pick", "by"],
            ),
            decide,
        ),
        CombinedTool(
            "n2f_ecr",
            "Change a finished design through a change request. quick: one edit in one call. "
            "start, impact, approve, close, abort: the full path. undo, redo, rollback, "
            "checkpoints: history. list, show: read. Changing actions report the vitals before "
            "and after.",
            _obj(
                {
                    "action": {"type": "string", "enum": list(ECR_ACTIONS)},
                    "set": {
                        "type": "array",
                        "items": _S,
                        "description": "quick, start: edits as uri=value, e.g. "
                        "param://<parameter id>=<value with unit>.",
                    },
                    "title": _S,
                    "reason": _S,
                    "kind": {**_S, "description": "start: parametric (default)."},
                    "task": {"type": "array", "items": _S, "description": "start: follow-ups."},
                    "by": {**_S, "description": "Who."},
                    "ecr_id": {**_S, "description": "e.g. ECR-001."},
                    "note": _S,
                    "target": {**_S, "description": "rollback: the checkpoint."},
                    "all": {**_B, "description": "checkpoints: include undone ones."},
                },
                ["action"],
            ),
            ecr,
        ),
    ]


class ToolRunner:
    """Lists the seven tools of one product folder and runs their calls."""

    def __init__(
        self,
        folder: Path,
        verbs: list[Tool] | None = None,
        steps: StepSource | None = None,
        timeout: float = 1800.0,
    ) -> None:
        """Open the runner on ``folder``; ``steps`` replaces the real step runner (tests)."""
        self.folder = folder.resolve()
        self.tools = build_combined()
        self._by_name = {t.name: t for t in self.tools}
        self._verbs = {v.path: v for v in (verbs if verbs is not None else build_tools())}
        self.steps: StepSource = steps if steps is not None else StepRunner(self.folder, timeout)

    async def start(self) -> None:
        """Start the folder's engine when it is a product folder and none answers."""
        if isinstance(self.steps, StepRunner):
            await self.steps.start()

    async def close(self) -> None:
        """Stop the engine this server started (not another's)."""
        if isinstance(self.steps, StepRunner):
            await self.steps.close()

    async def call(self, name: str, arguments: dict[str, Any] | None) -> ToolResult:
        """Run the tool ``name``; a bad call comes back as an error result, never raises."""
        tool = self._by_name.get(name)
        if tool is None:
            return ToolResult(
                f"no tool named {name!r}; the tools are: {', '.join(self._by_name)}", True
            )
        args = dict(arguments or {})
        try:
            for key in args:
                if key in ("dir", "directory", "C"):
                    raise ToolError(
                        f"{key!r} cannot be set: this server acts only inside {self.folder}"
                    )
                if key not in tool.schema["properties"]:
                    allowed = ", ".join(tool.schema["properties"])
                    raise ToolError(f"unknown argument {key!r}; the arguments are: {allowed}")
            full = args.pop("full", False)
            if not isinstance(full, bool):
                raise ToolError("'full' must be true or false")
        except ToolError as exc:
            return self._refusal(name, str(exc))
        problem = self._missing_or_unknown(tool, args)
        if problem is not None:
            return problem
        call = _Call(self.steps, self._verbs, self.folder)
        try:
            body = await tool.run(call, args)
        except ToolError as exc:
            return self._refusal(name, str(exc), call, full)
        except _Stop as stop:
            body = self._stopped(stop)
        ok = bool(body.pop("ok", True))
        payload: dict[str, Any] = {"tool": name, "ok": ok, "steps": call.step_dicts(full)}
        payload |= body
        nxt = payload.pop("next", None)
        if nxt is not None:
            payload["next"] = nxt
        text = _render(payload, full)
        last = call.steps[-1].exit if call.steps else None
        return ToolResult(text, not ok, None if ok else last)

    def _missing_or_unknown(self, tool: CombinedTool, args: dict[str, Any]) -> ToolResult | None:
        """Every missing required argument and every value outside its list, in one refusal.

        A small model fixes one named argument per call; naming them all with their allowed
        values, and for a new product saying the owner has the answers, saves it a loop and a
        guess (S-328).
        """
        props: dict[str, Any] = tool.schema["properties"]
        missing = [
            k for k in tool.schema.get("required", []) if k != "full" and args.get(k) in (None, "")
        ]
        wrong = [
            k
            for k, v in args.items()
            if "enum" in props.get(k, {}) and v not in (None, "") and v not in props[k]["enum"]
        ]
        if not missing and not wrong:
            return None

        def named(key: str) -> str:
            allowed = props.get(key, {}).get("enum")
            return f"{key} (one of {', '.join(allowed)})" if allowed else key

        parts = []
        if missing:
            parts.append("missing: " + "; ".join(named(k) for k in missing))
        if wrong:
            parts.append("not allowed: " + "; ".join(f"{named(k)}, got {args[k]!r}" for k in wrong))
        message = ". ".join(parts)
        keys = ", ".join(missing + wrong)
        if tool.name == "n2f_init_product":
            say = f"Ask the owner for {keys}, then call {tool.name} again with every argument."
        else:
            say = f"Call {tool.name} again with {keys} set ({message})."
        payload = {
            "tool": tool.name,
            "ok": False,
            "steps": [],
            "error": {"message": message, "missing": missing, "not_allowed": wrong},
            "allowed": {k: props[k]["enum"] for k in missing + wrong if "enum" in props.get(k, {})},
            "next": {"say": say},
        }
        return ToolResult(_render(payload, False), True, None)

    def _refusal(
        self, name: str, message: str, call: _Call | None = None, full: bool = False
    ) -> ToolResult:
        """The result of a call that was refused before or between steps."""
        payload = {
            "tool": name,
            "ok": False,
            "steps": call.step_dicts(full) if call else [],
            "error": {"message": message},
            "next": {"say": f"Fix the arguments ({message}) and call {name} again."},
        }
        return ToolResult(_render(payload, full), True, None)

    def _stopped(self, stop: _Stop) -> dict[str, Any]:
        """The summary of a tool whose step failed."""
        err = stop.error
        if err.get("error") == "engine_stopped":
            look = str(err.get("look_at", ""))
            nxt = command_to_call(look)
            return {
                "ok": False,
                "failed_step": stop.index,
                "error": err,
                "next": nxt or {"say": f"Run `{look}` to see whether the change happened."},
                "then": "if it did not happen, repeat this call",
            }
        advice = str(err.get("next") or "")
        text = f"{err.get('message', '')} {advice}"
        return {
            "ok": False,
            "failed_step": stop.index,
            "error": err,
            "next": next_from(
                text, f"{err.get('message', 'The step failed')} Fix it, then repeat this call."
            ),
        }


def _render(payload: dict[str, Any], full: bool) -> str:
    """The result as JSON text, held to its size (S-327).

    Without ``full`` the longest list of the summary loses items (counted in ``more``) until
    the text fits :data:`SUMMARY_LIMIT`. With ``full`` it is cut to :data:`MAX_TEXT` by
    dropping step results, largest first.
    """
    text = json.dumps(payload, ensure_ascii=False)
    if not full:
        while len(text) > SUMMARY_LIMIT:
            lists = [k for k, v in payload.items() if isinstance(v, list) and k != "steps" and v]
            if not lists:
                break
            key = max(lists, key=lambda k: len(json.dumps(payload[k])))
            payload[key].pop()
            more = payload.setdefault("more", {})
            more[key] = more.get(key, 0) + 1
            text = json.dumps(payload, ensure_ascii=False)
        return text
    if len(text) <= MAX_TEXT:
        return text
    for step in sorted(payload["steps"], key=lambda s: -len(json.dumps(s.get("result", "")))):
        if "result" in step:
            step["result"] = {"cut": "too long for one result"}
            text = json.dumps(payload, ensure_ascii=False)
            if len(text) <= MAX_TEXT:
                break
    return text
