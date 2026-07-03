"""MCP 客户端 — 连接外部 MCP Server，自动映射为本地 Tool.

连接生命周期:
  startup:  conn = await connect_mcp_server(...)
  runtime:  Agent 通过 ToolRegistry 调 MCP Tool
  shutdown: await conn.close()
"""

import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from amor.protocols.tool import ToolProtocol, ToolSchema
from harness.tool_registry import ToolRegistry


class MCPConnection:
    """一个长期存活的 MCP Server 连接."""

    def __init__(self, server_command: list[str]):
        self._command = server_command
        self._session: ClientSession | None = None
        self._read = None
        self._write = None

    async def connect(self) -> None:
        params = StdioServerParameters(
            command=self._command[0], args=self._command[1:],
        )
        self._read, self._write = await stdio_client(params).__aenter__()
        self._session = await ClientSession(self._read, self._write).__aenter__()
        await self._session.initialize()

    async def list_tools(self) -> list:
        return (await self._session.list_tools()).tools

    async def call_tool(self, name: str, arguments: dict) -> str:
        result = await self._session.call_tool(name, arguments)
        return json.dumps(result.content, ensure_ascii=False)

    async def close(self) -> None:
        if self._session:
            await self._session.__aexit__(None, None, None)
        if self._read:
            await self._read.__aexit__(None, None, None)


class _MCPToolWrapper(ToolProtocol):
    """把 MCP 远程 Tool 包装成 ToolProtocol."""

    def __init__(self, name: str, description: str, input_schema: dict, conn: MCPConnection):
        self._name = name
        self._description = description
        self._input_schema = input_schema
        self._conn = conn

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self._name, description=self._description,
            parameters=self._input_schema,
        )

    async def execute(self, arguments: dict) -> str:
        return await self._conn.call_tool(self._name, arguments)


async def connect_mcp_server(
    server_command: list[str],
    registry: ToolRegistry,
) -> MCPConnection:
    """连接 MCP Server，注册其所有 Tool.

    Returns MCPConnection，调用方在 shutdown 时 close()。
    """
    conn = MCPConnection(server_command)
    await conn.connect()

    for tool in await conn.list_tools():
        wrapper = _MCPToolWrapper(
            name=tool.name,
            description=tool.description or "",
            input_schema=tool.inputSchema or {},
            conn=conn,
        )
        registry.register(wrapper)

    return conn