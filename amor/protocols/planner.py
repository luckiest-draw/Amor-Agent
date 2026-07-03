"""Planner Protocol — 任务规划组件接口."""

from __future__ import annotations
from abc import ABC,abstractmethod
from typing import Any
from pydantic import BaseModel


class PlanStep(BaseModel):
    """
    规划中的一个步骤

    Attributes:
        id: 步骤唯一标识
        description: 步骤描述
        tool: 需要调用的工具名(可选）
        depends_on: 依赖的前置步骤ID 列表
    """
    id: str
    description: str
    tool: str | None = None
    depends_on: list[str] = []

class Plan(BaseModel):
    """
    执行计划

    Attributes:
        task:原始任务描述
        steps:步骤列表(按依赖拓扑排序)
    """
    task: str
    steps: list[PlanStep]


class PlannerProtocol(ABC):
    """规划器协议 — 将复杂任务分解为可执行步骤.

    必须实现:
        async def plan(self, task: str, context: dict[str, Any]) -> Plan
        async def replan(self, original: Plan, feedback: str, progress: dict) -> Plan
    """
    @abstractmethod
    async def plan(self, take: str, context: dict[str, Any]) -> Plan:
        """根据任务和上下文生成执行计划"""

    @abstractmethod
    async def replan(
            self,
            original: Plan,
            feedback: str,
            progress: dict[str, Any]
    ) -> Plan:
        """根据反馈和进度调整计划"""