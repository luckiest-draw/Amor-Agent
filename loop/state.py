"""Loop 状态管理 — 保存/恢复执行检查点."""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.checkpoint import Checkpoint


class LoopState:
    """执行状态快照."""

    def __init__(self, task_id: int):
        self.task_id = task_id
        self.current_step: int = 0
        self.status: str = "running"
        self.data: dict = {}

    async def save(self, session: AsyncSession) -> None:
        """保存当前状态到数据库."""
        stmt = select(Checkpoint).where(Checkpoint.task_id == self.task_id)
        result = await session.execute(stmt)
        checkpoint = result.scalar_one_or_none()

        state_data = {
            "current_step": self.current_step,
            "status": self.status,
            "data": self.data,
        }

        if checkpoint:
            checkpoint.state = state_data
            checkpoint.created_at = datetime.utcnow()
        else:
            checkpoint = Checkpoint(task_id=self.task_id, state=state_data)
            session.add(checkpoint)

        await session.commit()

    @classmethod
    async def load(cls, task_id: int, session: AsyncSession) -> "LoopState | None":
        """从数据库恢复状态."""
        stmt = select(Checkpoint).where(Checkpoint.task_id == task_id)
        result = await session.execute(stmt)
        checkpoint = result.scalar_one_or_none()

        if not checkpoint:
            return None

        state = cls(task_id)
        state.current_step = checkpoint.state.get("current_step", 0)
        state.status = checkpoint.state.get("status", "running")
        state.data = checkpoint.state.get("data", {})
        return state