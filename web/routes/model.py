"""模型管理 API — 列出和切换 LLM 模型."""

from fastapi import APIRouter

router = APIRouter()

AVAILABLE_MODELS = [
    {"id": "deepseek/deepseek-chat", "name": "DeepSeek V4 Pro", "provider": "DeepSeek"},
    {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
    {"id": "gemini/gemini-2.0-flash", "name": "Gemini 2.0 Flash", "provider": "Google"},
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "provider": "Anthropic"},
]

_current_model = "deepseek/deepseek-chat"


@router.get("/models")
async def list_models():
    return {"models": AVAILABLE_MODELS, "current": _current_model}


@router.put("/models/active")
async def set_active_model(model_id: str):
    """切换当前使用的模型."""
    global _current_model
    _current_model = model_id
    return {"current": _current_model}
