"""Skill 管理 API — 列出/重载 Skill."""

from fastapi import APIRouter, Request
from harness.skills.loader import discover_and_register

router = APIRouter()


@router.get("/skills")
async def list_skills(request: Request):
    """列出当前加载的所有 Skill."""
    skills = getattr(request.app.state, "skills", [])
    return {
        "skills": [
            {"name": s.name, "description": s.description, "source": s.source_file}
            for s in skills
        ]
    }


@router.post("/skills/reload")
async def reload_skills(request: Request):
    """从磁盘重新加载所有 Skill (.md 文件)."""
    skills = discover_and_register()
    request.app.state.skills = skills
    return {"skills": [s.name for s in skills]}
