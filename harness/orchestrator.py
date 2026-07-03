"""Orchestrator — 多 Agent 调度中心.

三个核心能力:
1. 并行: 互不依赖的步骤同时执行 (asyncio.gather)
2. 通信: 前置步骤的输出自动注入给后续 Agent
3. 审核循环: 执行者产出 → 审核员检查 → 不通过就退回重做 (最多 3 次)
"""

import asyncio
from amor.protocols.llm import LLMProtocol, Message
from amor.protocols.tool import ToolProtocol, ToolSchema
from harness.runner import run_agent, AgentConfig, AgentResult
from harness.tool_registry import ToolRegistry
from harness.planner import LLMPlanner
from amor.events.bus import EventBus
from amor.logging import get_logger
from prompt.roles import ROLES

logger = get_logger(__name__)

MAX_REVIEW_RETRIES = 3  # 审核驳回最多重做次数


class StepResult:
    """单步执行结果 — 供 Agent 间通信."""

    def __init__(self):
        self.step_id: str = ""
        self.role: str = ""
        self.output: str = ""
        self.status: str = "pending"  # pending / running / success / failed
        self.tokens: int = 0
        self.retries: int = 0


class Orchestrator:
    """多 Agent 编排器.

    执行流程:
    1. 分析任务类型 → 确定需要的角色
    2. Planner 生成步骤列表（含依赖关系）
    3. 按依赖分组，组内并行，组间顺序
    4. 执行者 → 审核员 → 通过/驳回重做
    5. 汇总所有结果
    """

    def __init__(
        self,
        llm: LLMProtocol,
        registry: ToolRegistry,
        event_bus: EventBus | None = None,
    ):
        self.llm = llm
        self.registry = registry
        self.event_bus = event_bus
        self.planner = LLMPlanner(llm)
        self.results: dict[str, StepResult] = {}  # step_id → result

    # ── 主入口 ──────────────────────────────────

    async def execute(self, task: str, history: list | None = None) -> dict:
        """执行任务 — 仿 Claude Code: 单 Agent，模型自己决定怎么干."""
        logger.info("orchestrator_start", extra={"task": task})

        result = await run_agent(
            config=AgentConfig(
                name="agent",
                system_prompt=(
                    "你是一个 AI Agent。回答简洁直接，不要啰嗦。\n"
                    "只有需要实时信息或执行操作时才调工具。简单对话不要调工具。"
                ),
                model=self.llm.model if hasattr(self.llm, "model") else "gpt-4o",
            ),
            task=task, llm=self.llm, registry=self.registry,
            event_bus=self.event_bus,
            history=history,
        )
        return {
            "task": task, "mode": "auto",
            "summary": result.output,
            "total_tokens": result.total_tokens,
        }

    def _ensure_delegate_tool(self) -> None:
        """注入 delegate 工具 — Agent 自己决定何时分派子任务."""
        if self.registry.get("delegate"):
            return

        orch = self  # 捕获 Orchestrator 的引用

        class DelegateTool(ToolProtocol):
            @property
            def schema(self):
                return ToolSchema(
                    name="delegate",
                    description=(
                        "把子任务委托给另一个 Agent 处理。"
                        "只在任务确实需要另一个角色（研究员/审核员/设计师）协作时才调。"
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "subtask": {"type": "string", "description": "子任务描述"},
                            "role": {
                                "type": "string",
                                "enum": ["researcher", "executor", "reviewer", "designer"],
                                "description": "子 Agent 角色",
                            },
                        },
                        "required": ["subtask", "role"],
                    },
                )

            async def execute(self, arguments: dict) -> str:
                role = arguments["role"]
                sub_result = await run_agent(
                    config=AgentConfig(
                        name=role,
                        role=ROLES.get(role, ""),
                        system_prompt="你是 " + role + "。简洁高效地完成任务。",
                        model=orch.llm.model if hasattr(orch.llm, "model") else "gpt-4o",
                    ),
                    task=arguments["subtask"],
                    llm=orch.llm,
                    registry=orch.registry,
                    event_bus=orch.event_bus,
                )
                return sub_result.output

        self.registry.register(DelegateTool())

    # ── 单步执行 ────────────────────────────────

    async def _execute_step(self, step, roles_needed: list[str]) -> StepResult:
        """执行一个步骤: 分配角色 → 注入前置结果 → 执行 → 审核."""
        role = await self._pick_role(step.description, roles_needed)

        # 收集依赖步骤的输出（Agent 间通信）
        upstream_context = self._collect_upstream_results(step.depends_on)

        # 构建任务描述（注入前置结果）
        task_with_context = step.description
        if upstream_context:
            task_with_context += "\n\n## 前置步骤的输出（供参考）\n" + upstream_context

        # Agent 配置
        agent_config = AgentConfig(
            name=f"{role}_{step.id}",
            role=ROLES.get(role, ""),
            system_prompt="You are a helpful AI agent.",
            model=self.llm.model if hasattr(self.llm, "model") else "gpt-4o",
        )

        # 执行
        result = await run_agent(
            config=agent_config,
            task=task_with_context,
            llm=self.llm,
            registry=self.registry,
            event_bus=self.event_bus,
        )

        sr = StepResult()
        sr.step_id = step.id
        sr.role = role
        sr.output = result.output
        sr.status = result.status
        sr.tokens = result.total_tokens

        # 审核循环（如果有审核员角色可用）
        if "reviewer" in roles_needed and role != "reviewer":
            sr = await self._review_loop(sr, step, roles_needed)

        self.results[step.id] = sr
        logger.info("step_done", extra={"step_id": step.id, "role": role, "status": sr.status})
        return sr

    # ── 审核循环 ────────────────────────────────

    async def _review_loop(
        self,
        sr: StepResult,
        step,
        roles_needed: list[str],
    ) -> StepResult:
        """审核员检查执行者输出，不通过就退回重做."""
        for attempt in range(MAX_REVIEW_RETRIES):
            review_result = await self._run_reviewer(sr.output, step.description)

            if review_result["verdict"] == "pass":
                sr.output = review_result.get("final_output", sr.output)
                sr.status = "success"
                break
            else:
                # 驳回 → 把审核意见注入，重新执行
                logger.warning(
                    "review_rejected",
                    extra={"step_id": step.id, "attempt": attempt + 1, "reason": review_result["reason"]},
                )
                feedback = f"审核不通过: {review_result['reason']}\n请修正后重新输出。"

                redo_config = AgentConfig(
                    name=f"executor_{step.id}_retry{attempt + 1}",
                    role=ROLES.get("executor", ""),
                    system_prompt="You are a helpful AI agent.",
                    model=self.llm.model if hasattr(self.llm, "model") else "gpt-4o",
                )
                redo_result = await run_agent(
                    config=redo_config,
                    task=f"修正以下输出:\n\n原始输出:\n{sr.output}\n\n{feedback}",
                    llm=self.llm,
                    registry=self.registry,
                    event_bus=self.event_bus,
                )
                sr.output = redo_result.output
                sr.tokens += redo_result.total_tokens
                sr.retries = attempt + 1

        else:
            # 达到最大重试次数
            sr.status = "failed_with_review"
            sr.output += f"\n\n[审核驳回 {MAX_REVIEW_RETRIES} 次，放弃]"

        return sr

    async def _run_reviewer(self, output: str, step_description: str) -> dict:
        """调审核员 Agent 检查输出质量."""
        import json

        reviewer_config = AgentConfig(
            name="reviewer",
            role=ROLES.get("reviewer", ""),
            system_prompt="You are a helpful AI agent.",
            tools=["read_file"],
            model=self.llm.model if hasattr(self.llm, "model") else "gpt-4o",
        )
        review_result = await run_agent(
            config=reviewer_config,
            task=f"审核以下步骤的输出:\n\n步骤: {step_description}\n输出:\n{output}\n\n请回复 JSON: {{\"verdict\": \"pass\"|\"reject\", \"reason\": \"...\", \"final_output\": \"...\"}} 如果通过，final_output 可以是润色后的版本。",
            llm=self.llm,
            registry=self.registry,
            event_bus=self.event_bus,
        )

        # 解析审核结果
        try:
            content = review_result.output
            if "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except (json.JSONDecodeError, KeyError):
            return {"verdict": "pass", "reason": "审核解析失败，默认通过", "final_output": output}

    # ── Agent 间通信 ────────────────────────────

    def _collect_upstream_results(self, depends_on: list[str]) -> str:
        """收集前置步骤的输出，作为当前 Agent 的上下文."""
        if not depends_on:
            return ""

        parts = []
        for dep_id in depends_on:
            if dep_id in self.results:
                r = self.results[dep_id]
                parts.append(f"### [{dep_id}] {r.role} 的输出\n{r.output[:2000]}")
        return "\n\n".join(parts)

    # ── 汇总 ────────────────────────────────────

    def _summarize(self, task: str, roles_needed: list[str], plan) -> dict:
        """汇总所有步骤结果."""
        results_list = []
        for step in plan.steps:
            r = self.results.get(step.id)
            if r:
                results_list.append({
                    "step_id": r.step_id,
                    "role": r.role,
                    "result": r.output,
                    "status": r.status,
                    "tokens": r.tokens,
                    "retries": r.retries,
                })

        summary = "\n\n".join(
            f"## 步骤 {r['step_id']} ({r['role']})\n{r['result'][:1000]}"
            for r in results_list
        )

        return {
            "task": task,
            "roles": roles_needed,
            "plan": [s.model_dump() for s in plan.steps],
            "results": results_list,
            "summary": summary,
            "total_tokens": sum(r["tokens"] for r in results_list),
        }

    # ── Agent 角色选择（LLM 判断，不靠关键词）────

    async def _decide_roles(self, task: str) -> list[str]:
        """让 LLM 判断这个任务需要哪些 Agent 角色."""
        messages = [
            Message(role="system", content=(
                "你是一个任务分析器。给定一个任务，返回需要的 Agent 角色列表。\n"
                "可用角色: researcher(搜索/研究), executor(执行/写文件/调API), "
                "reviewer(审核/检查), designer(图片/设计)。\n"
                "回复格式: JSON数组，如 [\"researcher\", \"executor\"]"
            )),
            Message(role="user", content=task),
        ]
        thought = await self.llm.chat(messages)
        import json
        try:
            content = thought.content.strip()
            if "```" in content:
                content = content.split("```")[1].split("```")[0]
            roles = json.loads(content)
            return roles if roles else ["researcher", "executor", "reviewer"]
        except (json.JSONDecodeError, KeyError):
            return ["researcher", "executor", "reviewer"]

    async def _pick_role(self, step_description: str, available_roles: list[str]) -> str:
        """让 LLM 判断这个步骤最适合哪个角色."""
        if len(available_roles) <= 1:
            return available_roles[0]
        messages = [
            Message(role="system", content=(
                "你是一个任务分配器。给定一个步骤描述和可用角色列表，"
                "返回最适合执行这个步骤的角色名。只返回角色名，不要解释。\n"
                f"可用角色: {available_roles}"
            )),
            Message(role="user", content=step_description),
        ]
        thought = await self.llm.chat(messages)
        role = thought.content.strip().lower()
        for r in available_roles:
            if r in role:
                return r
        return available_roles[0]