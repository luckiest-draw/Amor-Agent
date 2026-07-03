"""Tool Protocol — 外部工具组件接口."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Literal
from pydantic import BaseModel

# 工具风险等级
RiskLevel = Literal["none", "low", "medium", "high", "critical"]


class ToolSchema(BaseModel):
    """工具元信息 — 告知 LLM 怎么用 + 告知框架风险等级.

    Attributes:
        name: 工具名称
        description: 工具用途描述
        parameters: JSON Schema 格式的参数定义
        risk_level: 风险等级。critical=必须用户审批才能执行
        requires_approval: True = 执行前弹出确认框，等人点允许
    """
    name: str
    description: str
    parameters: dict[str, Any] = {}
    risk_level: RiskLevel = "none"
    requires_approval: bool = False


class ToolProtocol(ABC):
    """工具组件协议.

    必须实现:
        @property
        def schema(self) -> ToolSchema
        async def execute(self, arguments: dict[str, Any]) -> Any
    """

    @property
    @abstractmethod
    def schema(self) -> ToolSchema:
        """返回工具的 Schema 定义."""
        ...

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> Any:
        """执行工具，传入参数，返回执行结果."""
        ...
