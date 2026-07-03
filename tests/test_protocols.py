"""Tests for Amor protocol definitions."""

from typing import AsyncIterator
import pytest
from amor.protocols.llm import LLMProtocol, Message, Thought,ToolCall, TokenUsage
from amor.protocols.tool import ToolProtocol, ToolSchema
from amor.protocols.memory import MemoryProtocol, MemoryEntry
from amor.protocols.planner import PlannerProtocol, Plan, PlanStep
from typing import Any


def test_message_create():
      msg = Message(role="user", content="Hello")
      assert msg["role"] == "user"
      assert msg["content"] == "Hello"


def test_thought_without_tool_calls():
    thought = Thought(content="I understand",
                usage=TokenUsage(prompt=10, completion=5))
    assert thought.content == "I understand"
    assert thought.tool_calls is None
    assert thought.usage.total == 15


def test_thought_with_tool_calls():
    tc = ToolCall(id="call_1", name="search", arguments={"query":"Python"})
    thought = Thought(content="", tool_calls=[tc])
    assert len(thought.tool_calls) == 1
    assert thought.tool_calls[0].name == "search"


def test_llm_protocol_cannot_instantiate():
    with pytest.raises(TypeError):
        LLMProtocol()  # type: ignore


def test_llm_protocol_subclass_works():
    class FakeLLM(LLMProtocol):
        async def chat(self, messages: list[Message]) -> Thought:
            return Thought(content="ok")

        async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
            yield "ok"

    llm = FakeLLM()
    assert isinstance(llm, LLMProtocol)

# ── Tool Protocol ───────────────────────────────

def test_tool_schema_model():
    schema = ToolSchema(
        name="get_weather",
        description="查询天气",
        parameters={"type": "object", "properties": {}},
    )
    assert schema.name == "get_weather"


def test_tool_protocol_cannot_instantiate():
    with pytest.raises(TypeError):
        ToolProtocol()  # type: ignore


def test_tool_protocol_subclass_works():
    class EchoTool(ToolProtocol):
        @property
        def schema(self) -> ToolSchema:
            return ToolSchema(name="echo", description="",
                              parameters={})

        async def execute(self, arguments: dict[str, Any]) -> str:
            return arguments.get("text", "")

    tool = EchoTool()
    assert isinstance(tool, ToolProtocol)
    assert tool.schema.name == "echo"

# ── Memory Protocol ───────────────────────────────

def test_memory_entry_model():
    """MemoryEntry 结构"""
    entry = MemoryEntry(key="conv:123", value={"role": "user", "text": "hi"})
    assert entry.key == "conv:123"
    assert entry.value["text"] == "hi"
    assert entry.timestamp > 0


def test_memory_protocol_is_abc():
    """MemoryProtocol 不能直接实例化"""
    with pytest.raises(TypeError):
        MemoryProtocol()  # type: ignore[abstract]


def test_memory_protocol_subclass():
    """正确实现的子类可以实例化"""

    class DictMemory(MemoryProtocol):
        async def save(self, key: str, value: Any) -> None:
            pass

        async def query(self, key: str) -> Any | None:
            return None

        async def delete(self, key: str) -> None:
            pass

        async def clear(self) -> None:
            pass

    mem = DictMemory()
    assert isinstance(mem, MemoryProtocol)


# ── Planner Protocol ───────────────────────────────

def test_plan_step_defaults():
    step = PlanStep(id="1", description="搜索资料")
    assert step.tool is None
    assert step.depends_on == []


def test_plan_contains_steps():
    plan = Plan(
        task="查询天气",
        steps=[
            PlanStep(id="1", description="调天气API",
                     tool="get_weather"),
            PlanStep(id="2", description="返回结果"),
        ],
    )
    assert len(plan.steps) == 2
    assert plan.steps[0].tool == "get_weather"


def test_planner_cannot_instantiate():
    with pytest.raises(TypeError):
        PlannerProtocol()


def test_planner_subclass_works():
    class SimplePlanner(PlannerProtocol):
        async def plan(
                self,
                task: str,
                context: dict[str, Any]
        ) -> Plan:
            return Plan(task=task, steps=[PlanStep(id="1",description=task)])

        async def replan(self, original, feedback, progress):
            return original

    planner = SimplePlanner()
    assert isinstance(planner, PlannerProtocol)