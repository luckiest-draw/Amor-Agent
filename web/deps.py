"""FastAPI 依赖注入."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.engine import get_db
from llm.client import LiteLLMClient


def get_llm(model: str = "gpt-4o") -> LiteLLMClient:
    """获取 LLM 客户端."""
    return LiteLLMClient(model=model)


def get_db_session() -> AsyncSession:
    """获取数据库 session."""
    return Depends(get_db)