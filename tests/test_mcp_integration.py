"""Integration tests exercising the MCP server over stdio."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import anyio
import pytest
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.anyio("asyncio")
async def test_mcp_convert_complex_authors() -> None:
    """The MCP server converts the complex authors sample via stdio."""

    tex_path = REPO_ROOT / "tests/en/complex_authors.tex"
    assert tex_path.exists()

    server = StdioServerParameters(
        command=str(REPO_ROOT / ".venv/bin/python"),
        args=["-m", "tex2docx.mcp_server"],
        cwd=str(REPO_ROOT),
    )

    with anyio.fail_after(120):
        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                init_result = await session.initialize()
                assert (
                    init_result.protocolVersion in SUPPORTED_PROTOCOL_VERSIONS
                ), init_result.protocolVersion
                assert init_result.capabilities.tools is not None

                tools = await session.list_tools()
                tool_names = {tool.name for tool in tools.tools}
                assert "convert_latex_to_docx" in tool_names

                call = await session.call_tool(
                    "convert_latex_to_docx",
                    {
                        "tex_path": str(tex_path),
                    },
                )
                assert not call.isError

                converted_docx: Optional[Path] = None
                if call.content:
                    for item in call.content:
                        if isinstance(item, types.TextContent):
                            candidate = Path(item.text.strip())
                            if candidate.suffix.lower() == ".docx":
                                converted_docx = candidate
                                break

                if converted_docx is None and call.structuredContent:
                    path_text = call.structuredContent.get("result")
                    if isinstance(path_text, str):
                        converted_docx = Path(path_text)

                assert converted_docx is not None
                assert converted_docx.exists()

                # Clean up the produced file so repeated runs stay tidy.
                try:
                    converted_docx.unlink()
                except FileNotFoundError:
                    pass

    # Give the server a brief moment to shut down cleanly.
    await asyncio.sleep(0.1)
