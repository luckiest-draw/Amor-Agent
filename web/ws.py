"""WebSocket — 实时推送 Agent 执行进度."""

from fastapi import WebSocket, WebSocketDisconnect
from amor.events.bus import EventBus
from amor.events.types import Event, EventType
import json


async def websocket_endpoint(websocket: WebSocket, conversation_id: int):
    await websocket.accept()

    # 创建事件总线，订阅所有事件并推送到前端
    bus = EventBus()

    async def forward_to_client(event: Event):
        await websocket.send_text(json.dumps({
            "type": event.type.value,
            "node_id": event.node_id,
            "error": event.error,
        }, ensure_ascii=False))

    for event_type in EventType:
        bus.subscribe(event_type, forward_to_client)

    # 把 bus 存到 app.state 供 Agent 使用
    websocket.app.state.event_bus = bus

    try:
        while True:
            await websocket.receive_text()  # 保活
    except WebSocketDisconnect:
        pass