"""The MCP server over stdio (S-255, R14). Needs the optional ``napkin2factory[mcp]`` extra.

The protocol library's low-level server is used, not its decorator-based one: the tool list is
the seven combined tools (``combined.py``), whose input schemas are handed over as they are.
"""

from __future__ import annotations

from pathlib import Path

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from napkin2factory import __version__
from napkin2factory.mcp.combined import ToolRunner

# The one place the server says it is experimental (R14); no tool description repeats it.
INSTRUCTIONS = (
    "napkin2factory designs a physical product with its owner: a 3D model, drawings, a priced "
    "parts list. Experimental: tools change before 1.0. You edit the product's files yourself; "
    "these tools check, build and record.\n"
    "Steps, in order:\n"
    "1. In an empty folder: ask the owner for the product name, region and units, then call "
    "n2f_init_product. Then read AGENTS.md and roles/pm.md in the folder.\n"
    "2. n2f_promote_or_switch action=new for each idea; fill in the card file; n2f_napkin_sync "
    "to screen it; show the owner concepts/ board; action=promote for the one they choose.\n"
    "3. Edit the files under model/, then n2f_sync. Fix what it lists, repeat.\n"
    "4. A choice waiting on the owner: ask them, then n2f_decide. Never pick for them.\n"
    '5. Changes to a finished design: n2f_ecr action=quick set=["uri=value"]. '
    "To take back the last change: n2f_ecr action=undo.\n"
    "Every result is JSON with ok and next: do what next says. For the rules on talking to "
    "the owner call n2f_context topic=agent-guide, then one section at a time. A first build "
    "can take a minute: allow calls 10 minutes."
)


def make_server(folder: Path, runner: ToolRunner | None = None) -> tuple[Server, ToolRunner]:
    """The protocol server for ``folder`` and the runner behind it."""
    runner = runner if runner is not None else ToolRunner(folder)
    server: Server = Server("napkin2factory", version=__version__, instructions=INSTRUCTIONS)

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def _list() -> list[types.Tool]:
        return [
            types.Tool(name=t.name, description=t.description, inputSchema=t.schema)
            for t in runner.tools
        ]

    @server.call_tool(validate_input=False)  # type: ignore[untyped-decorator]
    async def _call(name: str, arguments: dict[str, object]) -> types.CallToolResult:
        # The runner validates the arguments itself, in plain words.
        result = await runner.call(name, dict(arguments))
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=result.text)], isError=result.is_error
        )

    return server, runner


async def serve(folder: Path) -> None:
    """Serve over stdin and stdout until the client closes them."""
    server, runner = make_server(folder)
    await runner.start()  # the folder's warm engine, shared with the CLI (S-327)
    try:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    finally:
        await runner.close()  # an engine this server started stops with it (S-291)
