"""记忆存储 — 实现 MemoryProtocol，存 PostgreSQL."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from amor.protocols.memory import MemoryProtocol
from amor.logging import get_logger
from db.models.memory import Memory

logger = get_logger(__name__)


class PostgresMemory(MemoryProtocol):
    """基于 postgreSQL 的持久记忆存储"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, key: str, value: Any):
        """保留或更新一条记忆"""
        stmt = select(Memory).where(Memory.key == key)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.value = value
        else:
            memory = Memory(key = key, value = value)
            self.session.add(memory)

        await self.session.commit()
        logger.debug("memory_saved", extra={"key": key})

    async def query(self, key: str) -> Any | None:
        """查询记忆"""
        stmt = select(Memory).where(Memory.key == key)
        result = await self.session.execute(stmt)
        memory = result.scalar_one_or_none()
        return memory.value if memory else None

    async def delete(self, key: str) -> None:
        """删除所有记忆"""
        stmt = select(Memory).where(Memory.key == key)
        result = await self.session.execute(stmt)
        memory = result.scalar_one_or_none()
        if memory:
            await self.session.delete(memory)
            await self.session.commit()

    async def clear(self) -> None:
        """清空所有记忆"""
        from sqlalchemy import delete as sql_delete
        await self.session.execute(sql_delete(Memory))
        await self.session.commit()