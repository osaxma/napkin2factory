"""The MCP server over stdio (S-255, R14). Needs the optional ``napkin2factory[mcp]`` extra.

The protocol library's low-level server is used, not its decorator-based one: the tool list is
generated (``tools.build_tools``), so the input schemas are handed over as they are.
"""

from __future__ import annotations

from pathlib import Path

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from napkin2factory import __version__
from napkin2factory.mcp.tools import Tool, ToolRunner, build_tools

# The one place the server says it is experimental (R14); no tool description repeats it.
INSTRUCTIONS = (
    "napkin2factory turns an idea for a physical product into a design that can be made: "
    "a 3D model, drawings and a priced parts list. Each tool is one `n2f` command, run inside "
    "the product folder this server was opened on, and returns the command's JSON. "
    "These tools are experimental and change before 1.0. "
    "Start with the tool n2f_docs and the topic agent-guide."
)


def make_server(folder: Path, tools: list[Tool] | None = None) -> tuple[Server, ToolRunner]:
    """The protocol server for ``folder`` and the runner behind it."""
    runner = ToolRunner(folder, tools if tools is not None else build_tools())
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
    server, _ = make_server(folder)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())
