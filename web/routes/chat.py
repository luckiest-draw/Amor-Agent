"""对话 API — 发送消息、获取历史."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()

# 内存对话存储（生产环境换 PostgreSQL）
_CONVERSATIONS: dict[int, dict] = {}
_NEXT_ID = 1


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    message: str
    model: str = "gpt-4o"


def _get_history(conv_id: int | None) -> list[dict]:
    if conv_id and conv_id in _CONVERSATIONS:
        return _CONVERSATIONS[conv_id]["messages"]
    return []


def _save_turn(conv_id: int, user_msg: str, agent_msg: str) -> None:
    conv = _CONVERSATIONS[conv_id]
    conv["messages"].append({"role": "user", "content": user_msg})
    conv["messages"].append({"role": "assistant", "content": agent_msg})
    # 只保留最近 30 条
    if len(conv["messages"]) > 30:
        conv["messages"] = conv["messages"][-30:]


@router.post("/chat")
async def send_message(req: ChatRequest, request: Request):
    """用户发送消息，Agent 执行并返回结果."""
    from harness.orchestrator import Orchestrator
    from harness.tool_registry import ToolRegistry
    from llm.client import LiteLLMClient

    global _NEXT_ID

    # 没有对话则创建
    conv_id = req.conversation_id
    if conv_id is None or conv_id not in _CONVERSATIONS:
        conv_id = _NEXT_ID
        _NEXT_ID += 1
        _CONVERSATIONS[conv_id] = {"title": req.message[:30], "messages": []}

    history = _get_history(conv_id)

    llm = LiteLLMClient(model=req.model)
    registry: ToolRegistry = request.app.state.tool_registry

    orchestrator = Orchestrator(
        llm=llm, registry=registry,
        event_bus=getattr(request.app.state, "event_bus", None),
    )

    result = await orchestrator.execute(req.message, history=history)

    _save_turn(conv_id, req.message, result["summary"])

    return {
        "conversation_id": conv_id,
        "content": result["summary"],
        "mode": result.get("mode", "—"),
        "tokens": result.get("total_tokens", 0),
    }


@router.get("/conversations")
async def list_conversations():
    """列出所有对话."""
    return {
        "conversations": [
            {"id": cid, "title": c["title"]}
            for cid, c in _CONVERSATIONS.items()
        ]
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: int):
    """获取对话历史."""
    conv = _CONVERSATIONS.get(conversation_id)
    if not conv:
        return {"messages": []}
    return {"conversation_id": conversation_id, "messages": conv["messages"]}
