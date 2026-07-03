"""任务规划器 — 实现 PlannerProtocol，用 LLM 拆任务."""

from typing import Any
from amor.protocols.planner import PlannerProtocol, Plan, PlanStep
from amor.protocols.llm import LLMProtocol, Message
from amor.logging import get_logger

logger = get_logger(__name__)

PLANNING_PROMPT = """你是一个任务规划专家。给定一个任务，将它拆解为 3-7 个可执行步骤。

输出格式（JSON）：
```json
{
    "steps": [
        {"id": "1", "description": "步骤描述", "tool": "可能需要用到的工具名或null", "depends_on": []},
        ...
    ]
}
"""

class LLMPlanner(PlannerProtocol):
    """用 LLM 做任务规划."""
    def __init__(self, llm: LLMProtocol):
        self.llm = llm

    async def plan(self, task: str, context: dict[str, Any]) -> Plan:
        """生成执行计划."""
        messages: list[Message] = [
            Message(role="system", content=PLANNING_PROMPT),
            Message(
                role="user",
                content=f"任务: {task}\n可用工具: {context.get('tools', [])}",
            ),
        ]

        thought = await self.llm.chat(messages)

        # 解析 LLM 返回的 JSON
        import json
        try:
            # 提取 JSON 块
            content = thought.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            steps = [
                PlanStep(
                    id=s["id"],
                    description=s.get("description", ""),
                    tool=s.get("tool"),
                    depends_on=s.get("depends_on", []),
                )
                for s in data.get("steps", [])
            ]
        except (json.JSONDecodeError, KeyError, IndexError):
            # 解析失败 → 单步计划
            logger.warning("plan_parse_failed", extra={"content": thought.content[:200]})
            steps = [PlanStep(id="1", description=task)]

        return Plan(task=task, steps=steps)

    async def replan(
            self, original: Plan, feedback: str, progress: dict[str, Any]
    ) -> Plan:
        """根据反馈调整计划."""
        completed = progress.get("completed", [])
        remaining = [s for s in original.steps if s.id not in completed]

        # 简版：保留未完成的步骤，加一个修正步骤
        new_steps = remaining + [
            PlanStep(
                id="correction",
                description=f"根据反馈修正: {feedback}",
            )
        ]
        return Plan(task=original.task, steps=new_steps)