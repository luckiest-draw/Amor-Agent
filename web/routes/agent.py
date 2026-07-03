"""Agent 管理 API — 列出内置角色."""

from fastapi import APIRouter
from prompt.roles import ROLES

router = APIRouter()


@router.get("/agents")
async def list_agents():
    """列出所有可用 Agent 角色."""
    result = [
        {"id": role_id, "name": role_id.capitalize(), "prompt_preview": prompt[:200]}
        for role_id, prompt in ROLES.items()
    ]
    return {"agents": result}
