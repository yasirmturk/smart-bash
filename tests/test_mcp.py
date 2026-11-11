import os
import sys
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


class MCPIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_connection_and_command(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "server.py")],
            env=dict(os.environ),
            cwd=str(ROOT),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                self.assertIn("execute_local_bash", [tool.name for tool in tools.tools])
                result = await session.call_tool(
                    "execute_local_bash",
                    {"command": "printf 'mcp-ready'", "return_raw": True},
                )
                self.assertFalse(result.is_error)
                self.assertIn("mcp-ready", result.content[0].text)
