"""Agent Runner — 单 Agent 的 Think → Act → Observe → Judge 循环.

设计原则 (仿 Anthropic):
- 不写死 ReAct/PlanExecute 等策略，模型自己判断怎么做
- 工具标注风险等级，高危险操作 emit INTERRUPT 等人审批
- 简单任务直接回答，复杂任务模型自然产生多轮 think-act
"""

import asyncio
from amor.protocols.llm import LLMProtocol, Message
from amor.events.bus import EventBus
from amor.events.types import Event, EventType
from amor.logging import get_logger
from harness.tool_registry import ToolRegistry
from context.assembler import assemble_messages

logger = get_logger(__name__)


class AgentConfig:
    """单个 Agent 的配置."""

    def __init__(
        self,
        name: str = "agent",
        role: str = "",
        system_prompt: str = "",
        tools: list[str] | None = None,
        model: str = "gpt-4o",
        max_steps: int = 30,
    ):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.model = model
        self.max_steps = max_steps


class AgentResult:
    """Agent 执行结果."""

    def __init__(self):
        self.status: str = "running"  # running / success / failed / interrupted
        self.output: str = ""
        self.steps: list[dict] = []
        self.total_tokens: int = 0
        self.total_cost: float = 0.0


async def run_agent(
    config: AgentConfig,
    task: str,
    llm: LLMProtocol,
    registry: ToolRegistry,
    event_bus: EventBus | None = None,
    interrupt_handler: "InterruptHandler | None" = None,
    history: list | None = None,
) -> AgentResult:
    """执行 Think → Act → Observe → Judge 循环，直到任务完成或超步数."""
    result = AgentResult()
    active_schemas = [
        s for s in registry.get_all_schemas()
        if s.name in config.tools
    ] if config.tools else registry.get_all_schemas()

    messages = await assemble_messages(
        task=task,
        system_prompt=config.system_prompt,
        role_prompt=config.role,
        tool_schemas=active_schemas,
        history=history,
    )

    # 转成 OpenAI function calling 格式
    tool_defs = [
        {
            "type": "function",
            "function": {
                "name": s.name,
                "description": s.description,
                "parameters": s.parameters,
            },
        }
        for s in active_schemas
    ] if active_schemas else None

    for step in range(config.max_steps):
        await _emit(event_bus, Event(type=EventType.NODE_START, node_id=f"{config.name}_think_{step}"))

        # 1. Think — 传工具定义给 LLM，它才知道能搜
        try:
            thought = await llm.chat(messages, tools=tool_defs)
        except Exception as e:
            logger.error("llm_call_failed", extra={"error": str(e)})
            result.status = "failed"
            result.output = f"LLM 调用失败: {e}"
            break
        result.total_tokens += thought.usage.total if thought.usage else 0
        # DeepSeek 要求 assistant 消息带上 tool_calls
        assistant_msg: dict = {"role": "assistant", "content": thought.content}
        if thought.tool_calls:
            assistant_msg["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": str(tc.arguments)}}
                for tc in thought.tool_calls
            ]
        messages.append(Message(**assistant_msg))

        # 2. Judge: 没有 tool_call → 模型认为完成了
        if not thought.tool_calls:
            result.status = "success"
            result.output = thought.content
            await _emit(event_bus, Event(type=EventType.NODE_END, node_id=f"{config.name}_done"))
            break

        # 3. Act: 执行工具（先检查风险等级）
        for tc in thought.tool_calls:
            tool = registry.get(tc.name)
            tool_schema = tool.schema if tool else None

            # ═══════════════════════════════════════
            # 中断机制: 高危操作必须等人审批
            # ═══════════════════════════════════════
            if tool_schema and tool_schema.requires_approval:
                approved = await _interrupt(
                    event_bus, interrupt_handler,
                    tool_name=tc.name,
                    tool_args=tc.arguments,
                    risk_level=tool_schema.risk_level,
                    agent_name=config.name,
                )
                if not approved:
                    tool_result = (
                        f"[审批拒绝] 工具 '{tc.name}' 需要用户审批，"
                        f"但用户拒绝了该操作。请尝试其他方案。"
                    )
                    messages.append(Message(role="tool", content=tool_result, tool_call_id=tc.id))
                    result.steps.append({
                        "step": step, "thought": thought.content[:200],
                        "tool": tc.name, "result": tool_result,
                    })
                    continue  # 跳过这个 tool，继续下一个

            # 正常执行
            logger.info("tool_call", extra={"agent": config.name, "tool": tc.name})
            tool_result = await registry.execute(tc.name, tc.arguments)
            messages.append(Message(role="tool", content=str(tool_result), tool_call_id=tc.id))
            result.steps.append({
                "step": step,
                "thought": thought.content[:200],
                "tool": tc.name,
                "result": str(tool_result)[:500],
            })

        await _emit(event_bus, Event(type=EventType.NODE_END, node_id=f"{config.name}_step_{step}"))

        if step >= config.max_steps - 1:
            result.status = "failed"
            result.output = f"超过最大步数限制 ({config.max_steps})"

    return result


# ── 中断机制 ────────────────────────────────────

class InterruptEvent:
    """中断事件 — 高危操作等待用户决策."""
    def __init__(self):
        self.tool_name: str = ""
        self.tool_args: dict = {}
        self.risk_level: str = ""
        self.event = asyncio.Event()  # 用于等待用户响应
        self.approved: bool = False


class InterruptHandler:
    """管理所有待审批的中断."""
    def __init__(self):
        self._pending: dict[str, InterruptEvent] = {}

    def create(self, request_id: str, tool_name: str, tool_args: dict, risk_level: str) -> InterruptEvent:
        ie = InterruptEvent()
        ie.tool_name = tool_name
        ie.tool_args = tool_args
        ie.risk_level = risk_level
        self._pending[request_id] = ie
        return ie

    def approve(self, request_id: str):
        if request_id in self._pending:
            self._pending[request_id].approved = True
            self._pending[request_id].event.set()

    def reject(self, request_id: str):
        if request_id in self._pending:
            self._pending[request_id].approved = False
            self._pending[request_id].event.set()


async def _interrupt(
    event_bus: EventBus | None,
    handler: InterruptHandler | None,
    tool_name: str,
    tool_args: dict,
    risk_level: str,
    agent_name: str,
) -> bool:
    """中断执行，等人审批。返回 True=允许, False=拒绝."""
    import uuid
    request_id = str(uuid.uuid4())[:8]

    # 发射事件给前端
    if event_bus:
        await event_bus.emit(Event(
            type=EventType.INTERRUPT,
            node_id=agent_name,
            tool_name=tool_name,
            tool_arguments=tool_args,
            risk_level=risk_level,
        ))

    # 没有 handler → 自动拒绝
    if handler is None:
        logger.warning("no_interrupt_handler", extra={"tool": tool_name})
        return False

    # 等待用户决策（最多 5 分钟超时）
    ie = handler.create(request_id, tool_name, tool_args, risk_level)
    try:
        await asyncio.wait_for(ie.event.wait(), timeout=300.0)
    except asyncio.TimeoutError:
        logger.warning("interrupt_timeout", extra={"tool": tool_name})
        return False

    return ie.approved


async def _emit(bus: EventBus | None, event: Event) -> None:
    if bus:
        await bus.emit(event)