"""循环控制器 — 驱动任务持续执行直到完成."""

from sqlalchemy.ext.asyncio import AsyncSession
from harness.orchestrator import Orchestrator
from loop.state import LoopState
from amor.logging import get_logger

logger = get_logger(__name__)


async def run_task_loop(
    task_id: int,
    task: str,
    orchestrator: Orchestrator,
    session: AsyncSession,
    max_retries: int = 3,
) -> dict:
    """执行一个任务，失败自动重试，状态持久化."""

    state = await LoopState.load(task_id, session) or LoopState(task_id)

    retries = 0
    while state.status == "running" and retries < max_retries:
        logger.info("loop_step", extra={"task_id": task_id, "step": state.current_step})

        try:
            result = await orchestrator.execute(task)

            state.current_step += 1
            state.data["last_result"] = result
            state.status = "done"
            await state.save(session)

            logger.info("task_complete", extra={"task_id": task_id})
            return result

        except Exception as e:
            retries += 1
            logger.error("loop_error", extra={"task_id": task_id, "retry": retries, "error": str(e)})
            state.status = "running"
            state.data["last_error"] = str(e)
            await state.save(session)

            if retries >= max_retries:
                state.status = "failed"
                await state.save(session)
                return {"error": str(e), "retries": retries}