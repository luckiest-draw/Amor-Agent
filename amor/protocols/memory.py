"""Memory Protocol — 记忆存储组件接口."""

from __future__ import annotations
from abc import ABC, abstractmethod
import time
from typing import Any
from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """一条记忆记录."""
    key: str
    value: Any
    timestamp: float = Field(default_factory=time.time)


class MemoryProtocol(ABC):
    """记忆组件协议.

    必须实现:
        async def save(self, key: str, value: Any) -> None
        async def query(self, key: str) -> Any | None
        async def delete(self, key: str) -> None
        async def clear(self) -> None
    """

    @abstractmethod
    async def save(self, key: str, value: Any) -> None:
        """保存一条记忆."""
        ...

    @abstractmethod
    async def query(self, key: str) -> Any | None:
        """查询记忆，不存在返回 None."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """删除一条记忆."""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """清空所有记忆."""
        ...