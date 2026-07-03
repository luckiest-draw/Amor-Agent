"""EventBus — 发布/订阅事件总线."""

from __future__ import annotations
from collections import defaultdict
from typing import Awaitable, Callable
from amor.events.types import Event,EventType
from amor.logging import get_logger

logger = get_logger(__name__)

EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """
    轻量事件总线 —— 发布/订阅模式

    图执行引擎通过 EventBus 向外发射生命周期事件，
    用户订阅关心的事件做日志、监控、流式输出等。

    Usage:
        bus = EventBus()
        bus.subscribe(EventType.NODE_START, on_node_start)
        await bus.emit(Event(type=EventType.NODE_START, node_id = "think"))
    """
    def __init__(self) -> None:
        self._subscribes: dict[EventType, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """订阅事件类型的回调"""
        self._subscribes[event_type].append(handler)
        logger.debug("event_subscribed", extra={"type": event_type.value})

    async def emit(self,event: Event) -> None:
        """发布事件，通知所有匹配的订阅者"""
        for handler in self._subscribes[event.type]:
            await handler(event)