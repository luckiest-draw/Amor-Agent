"""工具注册表 — 统一管理所有 Tool."""

from amor.protocols.tool import ToolProtocol, ToolSchema


class ToolRegistry:
    """工具注册中心.

    所有 Tool（内置 Skill / 用户 Skill / MCP Tool）统一注册到这里。
    Agent 通过它获取可用工具列表、调用工具。
    """

    def __init__(self):
        self._tools: dict[str, ToolProtocol] = {}

    def register(self, tool: ToolProtocol) -> None:
        """注册一个工具."""
        name = tool.schema.name
        self._tools[name] = tool

    def get(self, name: str) -> ToolProtocol | None:
        """按名获取工具."""
        return self._tools.get(name)

    def get_all_schemas(self) -> list[ToolSchema]:
        """获取所有工具的 Schema，用于告诉 LLM 有哪些工具可用."""
        return [t.schema for t in self._tools.values()]

    def list_names(self) -> list[str]:
        """列出所有工具名."""
        return list(self._tools.keys())

    async def execute(self, name: str, arguments: dict) -> str:
        """执行工具并返回结果字符串."""
        tool = self._tools.get(name)
        if not tool:
            return f"[错误] 工具 '{name}' 未注册。可用工具: {self.list_names()}"
        try:
            result = await tool.execute(arguments)
            return str(result)
        except Exception as e:
            return f"[错误] 工具 '{name}' 执行失败: {e}"