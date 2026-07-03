import pytest
from amor.protocols.tool import ToolProtocol, ToolSchema
from harness.tool_registry import ToolRegistry


class FakeEchoTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(name="echo", description="echo back", parameters={})

    async def execute(self, arguments):
        return arguments.get("text", "")


@pytest.mark.asyncio
async def test_register_and_execute():
    registry = ToolRegistry()
    registry.register(FakeEchoTool())
    assert "echo" in registry.list_names()
    result = await registry.execute("echo", {"text": "hello"})
    assert result == "hello"


@pytest.mark.asyncio
async def test_execute_unknown_tool():
    registry = ToolRegistry()
    result = await registry.execute("nonexistent", {})
    assert "未注册" in result