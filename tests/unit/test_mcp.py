"""The thin MCP server and the skill (S-255, R14): tools generated from the CLI, scoped to
one folder, and the skill file."""

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
from napkin2factory.mcp import tools as tools_mod
from napkin2factory.mcp.server import INSTRUCTIONS, make_server
from napkin2factory.mcp.tools import SKIPPED, ToolError, ToolRunner, build_argv, build_tools
from tests.conftest import EXAMPLES, copy_product, n2f

SKILL = Path(__file__).resolve().parents[2] / "src" / "napkin2factory" / "skill" / "SKILL.md"


def _leaf_paths(command: Any, path: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    kids = getattr(command, "commands", None)
    if kids is None:
        return {path}
    out: set[tuple[str, ...]] = set()
    for name, child in kids.items():
        out |= _leaf_paths(child, (*path, name))
    return out


def _by_name() -> dict[str, tools_mod.Tool]:
    return {t.name: t for t in build_tools()}


def test_every_leaf_verb_is_a_tool() -> None:
    leaves = _leaf_paths(typer.main.get_command(app))
    assert SKIPPED <= leaves  # the skipped verbs exist (and are named in the module docstring)
    expected = {"n2f_" + "_".join(p).replace("-", "_") for p in leaves - SKIPPED}
    names = [t.name for t in build_tools()]
    assert len(names) == len(set(names))
    assert set(names) == expected
    assert {"n2f_build", "n2f_ecr_new", "n2f_concept_build", "n2f_undo", "n2f_docs"} <= expected
    for skipped in ("mcp", "serve", "skill"):
        assert f"n2f_{skipped}" not in names
        assert skipped in (tools_mod.__doc__ or "")


def test_schemas_of_two_known_verbs() -> None:
    tools = _by_name()
    build = tools["n2f_build"].schema
    props = build["properties"]
    assert props["clean"]["type"] == "boolean"
    assert props["jobs"]["type"] == "integer" and props["jobs"]["default"] == 1
    assert props["target"]["default"] == "all"
    assert "required" not in build and build["additionalProperties"] is False
    # the folder and the JSON switch are the server's, never the agent's
    for hidden in ("dir", "json", "json_out", "C"):
        assert hidden not in props
    ecr_new = tools["n2f_ecr_new"].schema
    assert ecr_new["required"] == ["title"]
    assert ecr_new["properties"]["set"] == {
        "type": "array",
        "items": {"type": "string"},
        "description": ecr_new["properties"]["set"]["description"],
    }
    assert tools["n2f_concept_build"].schema["properties"]["concept_id"]["type"] == "string"
    assert tools["n2f_ecr_new"].description  # the verb's own help text
    assert "experimental" not in " ".join(t.description for t in tools.values()).lower()


def test_a_verb_added_later_is_a_tool() -> None:
    clone = copy.copy(app)
    clone.registered_commands = list(app.registered_commands)
    clone.registered_groups = list(app.registered_groups)

    def frobnicate(
        part: str = typer.Argument(..., help="Which part."),
        size_mm: int = typer.Option(3, "--size-mm", help="How big."),
        loud: bool = typer.Option(False, "--loud"),
        dir: Path | None = typer.Option(None, "--dir", "-C"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Make a part more frobnicated."""

    sub = typer.Typer()
    sub.command("deep-dive")(frobnicate)
    clone.command("frobnicate")(frobnicate)
    clone.add_typer(sub, name="extra")
    tools = {t.name: t for t in build_tools(clone)}
    assert {"n2f_frobnicate", "n2f_extra_deep_dive"} <= set(tools)
    tool = tools["n2f_frobnicate"]
    assert tool.description == "Make a part more frobnicated."
    assert tool.schema["required"] == ["part"]
    assert tool.schema["properties"]["size_mm"]["type"] == "integer"
    argv = build_argv(tool, {"part": "-x", "size_mm": 7, "loud": True}, Path("/tmp"))
    assert argv[:1] == ["frobnicate"]
    assert "--size-mm=7" in argv and "--loud" in argv and "--json" in argv
    assert argv[-2:] == ["--", "-x"]  # a positional that looks like an option stays a value


def test_folder_is_fixed_and_cannot_be_overridden(tmp_path: Path) -> None:
    folder = tmp_path / "product"
    folder.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (folder / "link").symlink_to(elsewhere)
    tools = _by_name()
    argv = build_argv(tools["n2f_status"], {}, folder)
    assert argv == ["status", "--json", f"--dir={folder}"]
    with pytest.raises(ToolError, match="only inside"):
        build_argv(tools["n2f_status"], {"dir": str(elsewhere)}, folder)
    with pytest.raises(ToolError, match="only inside"):
        build_argv(tools["n2f_status"], {"C": "/"}, folder)
    for bad in ("../elsewhere/x", str(elsewhere / "x"), "link/x", "/etc/passwd"):
        with pytest.raises(ToolError, match="outside the product folder"):
            build_argv(tools["n2f_diff"], {"ref_a": "a", "ref_b": "b", "out": bad}, folder)
    with pytest.raises(ToolError, match="outside the product folder"):
        build_argv(tools["n2f_ecr_new"], {"title": "t", "patch": "../p.diff"}, folder)
    ok = build_argv(tools["n2f_diff"], {"ref_a": "a", "ref_b": "b", "out": "site/diff"}, folder)
    assert "--out=site/diff" in ok
    with pytest.raises(ToolError, match="required"):
        build_argv(tools["n2f_diff"], {"ref_a": "a"}, folder)
    with pytest.raises(ToolError, match="unknown argument"):
        build_argv(tools["n2f_status"], {"nope": 1}, folder)
    with pytest.raises(ToolError, match="whole number"):
        build_argv(tools["n2f_build"], {"jobs": "two"}, folder)
    # the verb that creates a product takes the folder as its positional, fixed the same way
    assert build_argv(tools["n2f_init"], {"name": "Thing"}, folder)[-2:] == ["--", str(folder)]
    runner = ToolRunner(folder)
    result = asyncio.run(runner.call("n2f_status", {"dir": "/"}))
    assert result.is_error and "only inside" in result.text
    assert asyncio.run(runner.call("n2f_nothing", {})).is_error


def test_a_real_call_through_the_handler(tmp_path: Path) -> None:
    product = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)
    server, _ = make_server(product)
    assert "experimental" in INSTRUCTIONS and INSTRUCTIONS.lower().count("experimental") == 1
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

        ok = await call(req("n2f_checkpoints", {}))
        bad = await call(req("n2f_checkpoints", {"dir": "/"}))
        return listed, ok, bad

    listed, ok, bad = asyncio.run(go())
    assert {t.name for t in listed.root.tools} == {t.name for t in build_tools()}
    assert not ok.root.isError, ok.root.content[0].text
    assert isinstance(json.loads(ok.root.content[0].text), dict | list)
    assert bad.root.isError and "only inside" in bad.root.content[0].text


def test_a_failing_verb_is_an_error_result_with_its_exit_code(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = asyncio.run(ToolRunner(empty).call("n2f_status", {}))
    assert result.is_error and result.exit_code not in (0, None)
    assert f"exit code {result.exit_code}" in result.text


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
