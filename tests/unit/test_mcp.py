"""The seven MCP tools (S-255, R14, S-327): sequencing with a fake step runner, the argument
checks, the sizes, the `next` mapping against the real command tree, and the skill file."""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import typer
import yaml
from mcp import types

from napkin2factory.cli.app import app
from napkin2factory.mcp import combined
from napkin2factory.mcp import tools as tools_mod
from napkin2factory.mcp.combined import (
    COMMAND_TOOLS,
    CONCEPT_ACTIONS,
    ECR_ACTIONS,
    PAGE_LIMIT,
    SUMMARY_LIMIT,
    UNMAPPED,
    ToolRunner,
    command_to_call,
    next_from,
)
from napkin2factory.mcp.server import INSTRUCTIONS, make_server
from napkin2factory.mcp.tools import SKIPPED, Step, ToolError, build_argv, build_tools
from tests.conftest import n2f

SKILL = Path(__file__).resolve().parents[2] / "src" / "napkin2factory" / "skill" / "SKILL.md"
SEVEN = [
    "n2f_init_product",
    "n2f_napkin_sync",
    "n2f_promote_or_switch",
    "n2f_context",
    "n2f_sync",
    "n2f_decide",
    "n2f_ecr",
]


def _leaf_paths(command: Any, path: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    kids = getattr(command, "commands", None)
    if kids is None:
        return {path}
    out: set[tuple[str, ...]] = set()
    for name, child in kids.items():
        out |= _leaf_paths(child, (*path, name))
    return out


class Fake:
    """A step runner with no process: canned (exit, json) by command path; logs every run."""

    def __init__(self, answers: dict[tuple[str, ...], Any]) -> None:
        self.answers = answers
        self.ran: list[list[str]] = []

    async def run(self, argv: list[str]) -> Step:
        self.ran.append(argv)
        key = tuple(w for w in argv if not w.startswith("-"))
        for n in (2, 1):
            if key[:n] in self.answers:
                ans = self.answers[key[:n]]
                code, data = ans if isinstance(ans, tuple) else (0, ans)
                return Step(argv, code, json.dumps(data), "", "warm", 0.1)
        return Step(argv, 0, "{}", "", "warm", 0.1)

    def paths(self) -> list[str]:
        return [" ".join(w for w in a if not w.startswith("-")) for a in self.ran]


def _runner(tmp_path: Path, answers: dict[tuple[str, ...], Any]) -> tuple[ToolRunner, Fake]:
    fake = Fake(answers)
    return ToolRunner(tmp_path, steps=fake), fake


def _call(runner: ToolRunner, _tool: str, **args: Any) -> tuple[dict[str, Any], bool]:
    res = asyncio.run(runner.call(_tool, args))
    return json.loads(res.text), res.is_error


STATUS = {
    "gates": [
        {"name": "design", "ok": True, "blockers": []},
        {"name": "verify", "ok": False, "blockers": ["REQ-009: needs sign-off"]},
    ],
    "next_step": "REQ-009: sign off with `n2f signoff REQ-009 --by <name>`",
}


def test_the_seven_tools_and_their_schemas() -> None:
    tools = ToolRunner(Path("/tmp")).tools
    assert [t.name for t in tools] == SEVEN
    for t in tools:
        assert t.schema["additionalProperties"] is False
        assert t.schema["properties"]["full"]["type"] == "boolean"
        assert "dir" not in t.schema["properties"]
        assert "experimental" not in t.description.lower() and t.description
    by = {t.name: t.schema for t in tools}
    assert by["n2f_init_product"]["required"] == ["name", "units"]
    assert by["n2f_ecr"]["properties"]["set"]["type"] == "array"
    assert set(by["n2f_ecr"]["properties"]["action"]["enum"]) == set(ECR_ACTIONS)
    assert set(by["n2f_promote_or_switch"]["properties"]["action"]["enum"]) == set(CONCEPT_ACTIONS)


def test_instructions_are_short_generic_and_say_experimental_once() -> None:
    assert len(INSTRUCTIONS) < 1500
    assert INSTRUCTIONS.lower().count("experimental") == 1
    for tool in SEVEN:
        assert tool in INSTRUCTIONS
    assert "agent-guide" in INSTRUCTIONS and "section" in INSTRUCTIONS
    for word in ("claude", "anthropic", "openai", "gemini", "cursor", "codex", "gpt"):
        assert word not in INSTRUCTIONS.lower()


def test_every_action_and_mapped_command_exists_in_the_real_command_tree() -> None:
    leaves = _leaf_paths(typer.main.get_command(app))
    for path in (*CONCEPT_ACTIONS.values(), *ECR_ACTIONS.values(), *COMMAND_TOOLS):
        assert path in leaves, path
    names = {t.name: t for t in ToolRunner(Path("/tmp")).tools}
    for tool, action, positional in COMMAND_TOOLS.values():
        props = names[tool].schema["properties"]
        assert action is None or action in props["action"]["enum"]
        assert positional is None or positional in props, (tool, positional)
    # a verb added to the CLI has to choose: a tool, or the unmapped list
    assert leaves - SKIPPED - set(COMMAND_TOOLS) == UNMAPPED
    assert not UNMAPPED & set(COMMAND_TOOLS)


def test_next_commands_become_tool_calls() -> None:
    assert command_to_call("n2f ecr list --dir /x") == {
        "tool": "n2f_ecr",
        "arguments": {"action": "list"},
    }
    assert command_to_call("n2f concept promote C-002 --by <name>") == {
        "tool": "n2f_promote_or_switch",
        "arguments": {"action": "promote", "concept_id": "C-002"},
    }
    assert command_to_call("n2f checkpoints")["tool"] == "n2f_ecr"  # type: ignore[index]
    assert command_to_call("n2f decide fastening://a/b --pick 1")["arguments"] == {  # type: ignore[index]
        "check": "fastening://a/b"
    }
    assert command_to_call("n2f release v1.0") is None
    assert next_from("run `n2f release v1` or `n2f build`") == {
        "tool": "n2f_sync",
        "arguments": {},
    }
    assert next_from("sign off: `n2f signoff REQ-1 --by <name>`")["say"].startswith("sign off")


def test_argument_checks(tmp_path: Path) -> None:
    folder = tmp_path / "product"
    folder.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (folder / "link").symlink_to(elsewhere)
    verbs = {t.name: t for t in build_tools()}
    assert build_argv(verbs["n2f_status"], {}, folder) == ["status", "--json", f"--dir={folder}"]
    for bad in ("../elsewhere/x", str(elsewhere / "x"), "link/x", "/etc/passwd"):
        with pytest.raises(ToolError, match="outside the product folder"):
            build_argv(verbs["n2f_diff"], {"ref_a": "a", "ref_b": "b", "out": bad}, folder)
    with pytest.raises(ToolError, match="whole number"):
        build_argv(verbs["n2f_build"], {"jobs": "two"}, folder)
    assert build_argv(verbs["n2f_init"], {"name": "T"}, folder)[-2:] == ["--", str(folder)]
    runner, fake = _runner(folder, {})
    for args, text in (
        ({"dir": "/"}, "only inside"),
        ({"C": "/"}, "only inside"),
        ({"nope": 1}, "unknown argument"),
        ({"render": "yes"}, "true or false"),
        ({"full": "yes"}, "true or false"),
    ):
        body, err = _call(runner, "n2f_sync", **args)
        assert err and text in body["error"]["message"] and body["steps"] == []
        assert "next" in body
    body, err = _call(runner, "n2f_decide", check="x")
    assert err and body["error"]["missing"] == ["pick", "by"]
    body, err = _call(runner, "n2f_ecr", action="frobnicate")
    assert (
        err and body["error"]["not_allowed"] == ["action"] and "undo" in body["allowed"]["action"]
    )
    body, err = _call(runner, "n2f_ecr", action="list", bogus="1")
    assert err and "unknown argument" in body["error"]["message"]
    assert fake.ran == []
    assert asyncio.run(runner.call("n2f_nothing", {})).is_error


def test_sync_runs_five_steps_and_a_failing_check_is_an_outcome(tmp_path: Path) -> None:
    check = {
        "summary": {"fail": 1, "pass": 3},
        "results": [{"id": "req://REQ-1", "status": "fail", "message": "too heavy"}],
    }
    runner, fake = _runner(tmp_path, {("check",): (5, check), ("status",): STATUS})
    body, err = _call(runner, "n2f_sync")
    assert fake.paths() == ["validate", "lint", "build", "check", "status"]
    assert not err and body["ok"] and body["check_exit"] == 5
    assert body["failing_checks"] == [{"id": "req://REQ-1", "message": "too heavy"}]
    assert [s["engine"] for s in body["steps"]] == ["warm"] * 5
    assert all("error" not in s and "result" not in s for s in body["steps"])
    assert body["gates"][1] == {"name": "verify", "ok": False}
    assert "Fix req://REQ-1" in body["next"]["say"]


def test_a_failing_step_stops_and_names_a_next_call(tmp_path: Path) -> None:
    err_obj = {"error": "model_error", "message": "bad", "next": "run `n2f concept list`"}
    runner, fake = _runner(tmp_path, {("validate",): (3, err_obj)})
    body, is_err = _call(runner, "n2f_sync")
    assert is_err and not body["ok"] and fake.paths() == ["validate"]
    assert body["failed_step"] == 1 and body["steps"][0]["error"]["message"] == "bad"
    assert body["next"] == {"tool": "n2f_promote_or_switch", "arguments": {"action": "list"}}


def test_sync_sizes_more_and_full(tmp_path: Path) -> None:
    results = [
        {"id": f"req://R{i}", "status": "fail", "message": "x" * 500, "detail": {"blob": "y" * 900}}
        for i in range(30)
    ]
    choice = {
        "id": "fastening://a/b",
        "status": "choice",
        "detail": {"options": [{"id": f"o{i}", "summary": "s" * 400} for i in range(9)]},
    }
    check = {"summary": {}, "results": [*results, choice]}
    status = {"gates": [{"name": "g", "ok": False, "blockers": ["b" * 600] * 25}]}
    runner, _ = _runner(tmp_path, {("check",): (5, check), ("status",): status})
    res = asyncio.run(runner.call("n2f_sync", {}))
    body = json.loads(res.text)
    assert len(res.text) < SUMMARY_LIMIT
    # extreme input: lists are cut at ten, then further until the result fits; nothing is lost
    # without a count
    assert len(body["failing_checks"]) + body["more"]["failing_checks"] == 30
    assert len(body["blockers"]) + body["more"]["blockers"] == 25
    assert len(body["failing_checks"]) <= 10 and len(body["blockers"]) <= 10
    assert body["next"]["tool"] == "n2f_decide" and "ask the owner" in body["next"]["first"]
    assert body["next"]["arguments"]["check"] == "fastening://a/b"
    full = json.loads(asyncio.run(runner.call("n2f_sync", {"full": True})).text)
    assert full["steps"][3]["result"]["results"][0]["detail"]["blob"] == "y" * 900


def test_napkin_sync_lint_failure_stops_before_the_build(tmp_path: Path) -> None:
    lint = {"ok": False, "cards": 2, "problems": [f"card {i}: no title" for i in range(14)]}
    runner, fake = _runner(tmp_path, {("concept", "lint"): (1, lint)})
    body, err = _call(runner, "n2f_napkin_sync")
    assert err and fake.paths() == ["concept lint"]
    assert len(body["lint"]["problems"]) == 10 and body["lint"]["more"]["problems"] == 4


def test_lint_findings_come_as_objects_and_reasons_whole(tmp_path: Path) -> None:
    """The trial's two cuts (S-333): findings were Python reprs, a sag reason lost its end."""
    finding = {
        "severity": "error",
        "rule": "C8-number-kinds",
        "file": str(tmp_path.resolve() / "concepts" / "C-001.yaml"),
        "subject": "C-001",
        "message": "site.point_load is 150 kg, which is not a force",
        "hint": "give it as a force with its unit, like 1471.5 N",
    }
    runner, _ = _runner(tmp_path, {("concept", "lint"): (1, {"ok": False, "problems": [finding]})})
    body, err = _call(runner, "n2f_napkin_sync")
    assert err and body["lint"]["problems"] == [
        {
            "subject": "C-001",
            "message": finding["message"],
            "hint": finding["hint"],
            "severity": "error",
            "file": "concepts/C-001.yaml",
        }
    ]
    reason = "the top sags 4.22 mm, beyond the 2 mm limit " + "x" * 600 + " to pass: a deeper top"
    card = {
        "id": "C-001",
        "title": "Bench",
        "verdict": "red",
        "summary": "1600 mm",
        "screening": {
            "rules": [{"id": "structural-deflection", "status": "fail", "message": reason}]
        },
    }
    answers = {
        ("concept", "lint"): {"ok": True, "problems": []},
        ("concept", "build"): {"concepts": [card], "errors": []},
        ("concept", "board"): {"board": "build/concepts/board.html"},
    }
    runner, _ = _runner(tmp_path, answers)
    body, _ = _call(runner, "n2f_napkin_sync")
    assert body["cards"][0]["reasons"][0]["message"].endswith("to pass: a deeper top")


def test_napkin_sync_summarises_each_card(tmp_path: Path) -> None:
    card = {
        "id": "C-001",
        "title": "Legs",
        "verdict": "red",
        "summary": "1600 mm",
        "screening": {
            "rules": [{"id": f"r{i}", "status": "fail", "message": "too tall"} for i in range(5)]
        },
    }
    ok = {**card, "id": "C-002", "verdict": "green", "screening": {"rules": []}}
    answers = {
        ("concept", "lint"): {"ok": True, "problems": []},
        ("concept", "build"): {"concepts": [card, ok], "errors": []},
        ("concept", "board"): {"board": "build/concepts/board.html"},
    }
    runner, fake = _runner(tmp_path, answers)
    body, err = _call(runner, "n2f_napkin_sync", render=False)
    assert not err and fake.paths() == ["concept lint", "concept build", "concept board"]
    assert "--all" in fake.ran[1] and "--no-render" in fake.ran[1]
    first = body["cards"][0]
    assert first["screened"] == "fail" and len(first["reasons"]) == 3
    assert first["more_reasons"] == 2 and body["cards"][1]["screened"] == "pass"
    assert body["board"] == "build/concepts/board.html"
    assert body["next"]["arguments"] == {"action": "promote", "concept_id": "C-002"}
    _call(runner, "n2f_napkin_sync", concept="C-001")
    assert "C-001" in fake.ran[-2] and "--all" not in fake.ran[-2]


def test_promote_and_switch_name_sync_next(tmp_path: Path) -> None:
    runner, fake = _runner(tmp_path, {})
    body, _ = _call(runner, "n2f_promote_or_switch", action="switch", concept_id="C-003")
    assert fake.paths() == ["concept switch C-003"]
    assert body["next"] == {"tool": "n2f_sync", "arguments": {}}
    body, err = _call(runner, "n2f_promote_or_switch", action="fork")
    assert not err and fake.paths()[-1] == "concept fork-from-model"
    body, err = _call(runner, "n2f_promote_or_switch", action="new", title="Oak table", bogus=1)
    assert err and "unknown argument" in body["error"]["message"]
    body, err = _call(
        runner, "n2f_promote_or_switch", action="new", **{"title": "Oak", "from": "C-1"}
    )
    assert not err and "--from=C-1" in fake.ran[-1]


def test_ecr_wraps_a_changing_action_in_two_status_steps(tmp_path: Path) -> None:
    quick = {
        "id": "ECR-001",
        "mass": {"before": 47.1, "after": 47.3, "delta": 0.2, "unit": "kg"},
        "cost": {"before": 1000.0, "after": 1000.0, "delta": 0.0, "unit": "USD"},
    }
    runner, fake = _runner(tmp_path, {("ecr", "quick"): quick, ("status",): STATUS})
    body, err = _call(runner, "n2f_ecr", action="quick", set=["param://h=760 mm"], reason="r")
    assert not err and fake.paths() == ["status", "ecr quick", "status"]
    assert "--set=param://h=760 mm" in fake.ran[1]
    assert body["before"] == body["after"] == {"gates_open": ["verify"], "blockers": 1}
    assert body["delta"]["mass"]["delta"] == 0.2 and body["delta"]["blockers"] == 0
    assert body["next"] == {"tool": "n2f_sync", "arguments": {}}
    body, _ = _call(runner, "n2f_ecr", action="list")
    assert fake.paths()[3:] == ["ecr list"] and "before" not in body


def test_a_dropped_engine_stops_a_changing_tool_and_names_what_to_look_at(tmp_path: Path) -> None:
    dropped = {
        "error": "engine_stopped",
        "message": "the n2f engine stopped during `n2f undo`",
        "look_at": f"n2f checkpoints --dir={tmp_path}",
        "exit": 70,
    }
    runner, fake = _runner(tmp_path, {("undo",): (70, dropped), ("status",): STATUS})
    body, err = _call(runner, "n2f_ecr", action="undo")
    assert err and fake.paths() == ["status", "undo"]
    assert body["next"] == {"tool": "n2f_ecr", "arguments": {"action": "checkpoints"}}
    assert "repeat" in body["then"] and body["failed_step"] == 2


def test_decide_then_status_then_sync(tmp_path: Path) -> None:
    runner, fake = _runner(tmp_path, {("status",): STATUS, ("decide",): {"decision": "DEC-001"}})
    body, err = _call(runner, "n2f_decide", check="a://b", pick="1", by="Sam")
    assert not err and fake.paths() == ["decide a://b", "status"]
    assert body["decision"] == {"decision": "DEC-001"} and body["gates_open"] == ["verify"]
    assert body["next"]["tool"] == "n2f_sync"


def test_init_refuses_an_existing_product_and_asks_for_the_owner_facts(tmp_path: Path) -> None:
    runner, fake = _runner(tmp_path, {("init",): {"product": "p", "files": 26}})
    # Every missing argument at once, with its allowed values, and the owner has the answers
    body, err = _call(runner, "n2f_init_product", name="P")
    assert err and body["error"]["missing"] == ["units"] and fake.ran == []
    assert body["allowed"] == {
        "units": ["metric", "imperial"],
    }
    assert "one of metric, imperial" in body["error"]["message"]
    assert body["next"]["say"].startswith("Ask the owner for units")
    body, err = _call(runner, "n2f_init_product", name="P", region="XX", units="metric")
    assert (
        err
        and body["error"]["not_allowed"] == ["region"]
        and "got 'XX'" in body["error"]["message"]
    )
    body, err = _call(runner, "n2f_init_product", name="P", region="EU", units="metric")
    assert not err and body["read_first"] == ["AGENTS.md", "roles/pm.md"] and body["files"] == 26
    assert fake.ran[0][0] == "init" and fake.ran[0][-2:] == ["--", str(tmp_path.resolve())]
    (tmp_path / "n2f.yaml").write_text("x")
    body, err = _call(runner, "n2f_init_product", name="P", region="EU", units="metric")
    assert err and body["next"]["tool"] == "n2f_sync" and len(fake.ran) == 1


def test_context_sections(tmp_path: Path) -> None:
    long = (
        "# Guide\n\nintro\n\n## One\n"
        + "alpha " * 1000
        + "\n```\n# not a heading\n```\n## Two\nbeta\n"
    )
    short = "# Tiny\nhello"
    runner, _ = _runner(
        tmp_path,
        {("docs",): {"topic": "t", "text": long}, ("context",): {"module": "table"}},
    )
    body, _ = _call(runner, "n2f_context", topic="t")
    assert "text" not in body and len(json.dumps(body)) < 1000
    assert [s["heading"] for s in body["sections"]] == ["Guide", "One", "Two"]
    assert body["next"]["arguments"] == {"topic": "t", "section": 1}
    for want in ("2", "two", "One"):
        body, err = _call(runner, "n2f_context", topic="t", section=want)
        assert not err and body["section"]["heading"] in ("One", "Two")
    assert "beta" in _call(runner, "n2f_context", topic="t", section="Two")[0]["text"]
    assert "# not a heading" in _call(runner, "n2f_context", topic="t", section="One")[0]["text"]
    body, err = _call(runner, "n2f_context", topic="t", section="nope")
    assert err and "sections" in body
    runner2, _ = _runner(tmp_path, {("docs",): {"topic": "t", "text": short}})
    assert _call(runner2, "n2f_context", topic="t")[0]["text"] == short
    body, err = _call(runner, "n2f_context", uri="part://x")
    assert (
        err and body["kinds"] == ["asm://<assembly id>"] and body["next"]["tool"] == "n2f_context"
    )
    assert not _call(runner, "n2f_context", uri="asm://table")[1]
    body, err = _call(runner, "n2f_context", uri="asm://t", topic="t")
    assert err and "not both" in body["error"]["message"]
    body, err = _call(runner, "n2f_context", section="1")
    assert err


def test_the_real_guide_comes_as_sections(tmp_path: Path) -> None:
    (tmp_path / "n2f.yaml").write_text("x")  # not needed by docs; a plain folder
    runner = ToolRunner(tmp_path)
    res = asyncio.run(runner.call("n2f_context", {"topic": "agent-guide"}))
    body = json.loads(res.text)
    assert not res.is_error and len(res.text) < SUMMARY_LIMIT, res.text[:200]
    assert len(body["sections"]) > 8
    one = json.loads(
        asyncio.run(runner.call("n2f_context", {"topic": "agent-guide", "section": "3"})).text
    )
    assert one["ok"] and one["text"].startswith("#")


def test_context_materials(tmp_path: Path) -> None:
    (tmp_path / "n2f.yaml").write_text("x")
    runner = ToolRunner(tmp_path)

    # 1. Whole list in one call (under PAGE_LIMIT)
    res = asyncio.run(runner.call("n2f_context", {"topic": "materials"}))
    body = json.loads(res.text)
    assert not res.is_error and body["ok"]
    assert "sections" not in body
    assert "mild steel" in body["text"]
    assert len(body["text"]) <= PAGE_LIMIT

    # 2. One row whole by name
    res_one = asyncio.run(
        runner.call("n2f_context", {"topic": "materials", "section": "mild steel"})
    )
    body_one = json.loads(res_one.text)
    assert not res_one.is_error and body_one["ok"]
    assert body_one["material"]["name"] == "mild steel"
    assert "carbon steel" in body_one["material"]["source"]
    assert "density: 7850" in body_one["text"]

    # 3. Unknown name says which names exist
    res_err = asyncio.run(
        runner.call("n2f_context", {"topic": "materials", "section": "unobtainium"})
    )
    body_err = json.loads(res_err.text)
    assert not body_err["ok"]
    assert "no material 'unobtainium'" in body_err["error"]["message"]
    assert "mild steel" in body_err["error"]["message"]
    assert "mild steel" in body_err["materials"]


def test_a_real_failing_call_and_the_protocol_handler(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    server, runner = make_server(empty)
    assert server.instructions == INSTRUCTIONS

    async def go() -> tuple[Any, Any, Any]:
        listed = await server.request_handlers[types.ListToolsRequest](
            types.ListToolsRequest(method="tools/list")
        )
        call = server.request_handlers[types.CallToolRequest]

        def req(name: str, args: dict[str, Any]) -> types.CallToolRequest:
            return types.CallToolRequest(
                method="tools/call", params=types.CallToolRequestParams(name=name, arguments=args)
            )

        return listed, await call(req("n2f_sync", {})), await call(req("n2f_sync", {"dir": "/"}))

    listed, failing, bad = asyncio.run(go())
    assert [t.name for t in listed.root.tools] == SEVEN
    body = json.loads(failing.root.content[0].text)
    assert failing.root.isError and not body["ok"] and body["failed_step"] == 1
    assert body["steps"][0]["engine"] == "cold" and body["next"]
    assert bad.root.isError and "only inside" in bad.root.content[0].text


def test_a_verb_added_later_is_still_in_the_verb_table() -> None:
    clone = copy.copy(app)
    clone.registered_commands = list(app.registered_commands)
    clone.registered_groups = list(app.registered_groups)

    def frobnicate(
        part: str = typer.Argument(..., help="Which part."),
        size_mm: int = typer.Option(3, "--size-mm", help="How big."),
        dir: Path | None = typer.Option(None, "--dir", "-C"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Make a part more frobnicated."""

    clone.command("frobnicate")(frobnicate)
    tool = {t.name: t for t in build_tools(clone)}["n2f_frobnicate"]
    argv = build_argv(tool, {"part": "-x", "size_mm": 7}, Path("/tmp"))
    assert "--size-mm=7" in argv and argv[-2:] == ["--", "-x"]
    assert tools_mod.MAX_TEXT == combined.MAX_TEXT


def test_mcp_without_the_extra_says_how_to_install_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "mcp", None)  # `import mcp` now fails, as without the extra
    result = n2f("mcp", "--dir", str(tmp_path))
    assert result.returncode == 1
    assert 'pip install "napkin2factory[mcp]"' in result.stderr


def test_skill_file_and_verb(tmp_path: Path) -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    front = yaml.safe_load(text.split("---\n", 2)[1])
    assert front["name"] == "napkin2factory"
    assert 40 < len(front["description"]) <= 1024
    assert n2f("skill").stdout == text
    out = tmp_path / "skills"
    result = n2f("skill", "--write", str(out))
    assert result.returncode == 0
    assert (out / "napkin2factory" / "SKILL.md").read_text(encoding="utf-8") == text


def test_init_writes_neither_the_skill_nor_a_server_config(tmp_path: Path) -> None:
    product = tmp_path / "thing"
    assert n2f("init", str(product), "--name", "Thing").returncode == 0
    found = [p.name for p in product.rglob("*") if "mcp" in p.name.lower() or p.name == "SKILL.md"]
    assert not found


class Undoing(Fake):
    """Undo answers that walk back through a request's checkpoints, one per call."""

    def __init__(self, labels: list[tuple[str, str]]) -> None:
        super().__init__({("status",): STATUS})
        self.labels = labels  # (stepped over, now in effect)

    async def run(self, argv: list[str]) -> Step:
        if argv[0] != "undo":
            return await super().run(argv)
        self.ran.append(argv)
        if not self.labels:
            return Step(argv, 0, json.dumps({"undone": False}), "", "warm", 0.1)
        over, now = self.labels.pop(0)
        data = {
            "undone": True,
            "checkpoint": {"label": f"Undid: {over}"},
            "restored": {"label": now},
        }
        return Step(argv, 0, json.dumps(data), "", "warm", 0.1)


def test_undo_takes_back_a_whole_change_request_and_a_plain_undo_is_one_step(
    tmp_path: Path,
) -> None:
    fake = Undoing([("ECR-001", "ECR-001: set h"), ("ECR-001: set h", "Started ECR-001: h")])
    runner = ToolRunner(tmp_path, steps=fake)
    body, err = _call(runner, "n2f_ecr", action="undo")
    assert not err and fake.paths() == ["status", "undo", "undo", "status"]
    assert body["undid"] == ["ECR-001", "ECR-001: set h"] and "before" in body and "after" in body
    plain = Undoing([("Start edits", "Start")])
    body, _ = _call(ToolRunner(tmp_path, steps=plain), "n2f_ecr", action="undo")
    assert plain.paths() == ["status", "undo", "status"] and body["undid"] == ["Start edits"]
    nothing = Undoing([])
    body, err = _call(ToolRunner(tmp_path, steps=nothing), "n2f_ecr", action="undo")
    assert not err and "undid" not in body


def test_a_listing_keeps_its_rows(tmp_path: Path) -> None:
    """``ecr list`` showed "5 fields" for each request in the trial (S-333)."""
    row = {"id": "ECR-001", "title": "Widen", "status": "draft", "kind": "parametric", "by": "x"}
    runner, _ = _runner(tmp_path, {("ecr", "list"): {"ecrs": [row]}})
    body, err = _call(runner, "n2f_ecr", action="list")
    assert not err and body["result"]["ecrs"][0]["id"] == "ECR-001"


def test_promote_lists_what_it_seeded_and_names_the_build(tmp_path: Path) -> None:
    """Promotion seeds parts, a layout and structure checks; the agent sees them and builds next."""
    seeded = {
        "model": True,
        "skipped": None,
        "parts": [
            {"uri": "part://leg", "qty": 4, "kit": "block", "stretched_by": ["param://leg-height"]},
            {"uri": "part://shelf", "qty": 1, "kit": "block", "stretched_by": []},
        ],
        "overall_sizes": {"x": "param://top-width", "y": "param://top-depth", "z": "param://h"},
        "layout": ["model/geometry/bench.py"],
        "structure_checks": ["req://REQ-004"],
    }
    answers = {("concept", "promote"): {"id": "C-001", "summary": "done", "seeded": seeded}}
    runner, _ = _runner(tmp_path, answers)
    body, err = _call(runner, "n2f_promote_or_switch", action="promote", concept_id="C-001")
    assert not err and body["next"] == {"tool": "n2f_sync", "arguments": {}}
    view = body["result"]["seeded"]
    assert view["parts"] == [
        "part://leg x4 (block), follows param://leg-height",
        "part://shelf x1 (block)",
    ]
    assert view["layout"] == ["model/geometry/bench.py"] and view["structure_checks"] == [
        "req://REQ-004"
    ]
    assert "never rewrite them by hand" in view["note"] and "n2f_sync" in view["note"]
    # a product that already had parts: nothing seeded, and the result says so
    held = {**seeded, "model": False, "parts": [], "skipped": "the product already has parts"}
    runner, _ = _runner(tmp_path, {("concept", "promote"): {"id": "C-001", "seeded": held}})
    body, _ = _call(runner, "n2f_promote_or_switch", action="promote", concept_id="C-001")
    assert body["result"]["seeded"]["skipped"] == "the product already has parts"
    assert "note" not in body["result"]["seeded"]
