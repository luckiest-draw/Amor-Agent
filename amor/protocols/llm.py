"""LLM Protocol — 大语言模型组件接口."""

from __future__ import annotations
from abc import ABC,abstractmethod
from typing import Any, AsyncIterator,TypedDict
from pydantic import BaseModel,Field


class Message(TypedDict,total = False):
    """对话消息"""
    role: str           # "user" | "assistant" | "system" | "tool"
    content: str
    name: str           # 可选，工具名
    tool_call_id: str   # 可选，工具调用的 ID
    tool_calls: list    # 可选，assistant 消息携带的工具调用列表


class ToolCall(BaseModel):
    """LLM 发起的工作调用"""
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class TokenUsage(BaseModel):
    """Token 用量统计"""
    prompt: int = 0
    completion: int = 0

    @property
    def total(self) -> int:
        return self.prompt + self.completion


class Thought(BaseModel):
    """LLM 推理输出"""
    content: str = ""
    tool_calls: list[ToolCall] | None = None
    usage: TokenUsage | None = None


class LLMProtocol(ABC):
    """LLM 组件协议 — 任何 LLM 实现必须继承此类.

    必须实现:
        async def chat(self, messages: list[Message]) -> Thought
        async def stream(self, messages: list[Message]) -> AsyncIterator[str]
    """

    @abstractmethod
    async def chat(self, messages : list[Message]) -> Thought:
        """发送消息，返回完整 Thought（可能含 tool_calls）."""

    @abstractmethod
    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        """发送消息，流式返回 token 字符串."""