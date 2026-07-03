"""Tests for Amor event system."""

import pytest
from amor.events.types import Event, EventType
from amor.events.bus import EventBus


def test_event_type_enum():
    """标准事件类型"""
    assert EventType.NODE_START.value == "node_start"
    assert EventType.NODE_END.value == "node_end"
    assert EventType.EDGE_TRAVERSE.value == "edge_traverse"
    assert EventType.ERROR.value == "error"
    assert EventType.STREAM_TOKEN.value == "stream_token"


def test_event_model():
    """Event Pydantic 模型"""
    event = Event(type=EventType.NODE_START, node_id="think")
    assert event.node_id == "think"
    assert event.state is None
    assert event.error is None


def test_error_event():
    """ERROR 事件携带错误信息"""
    event = Event(
        type=EventType.ERROR,
        node_id="call_llm",
        error="Connection timeout",
    )
    assert event.error == "Connection timeout"


@pytest.mark.asyncio
async def test_subscribe_and_emit():
    """基本发布/订阅"""
    bus = EventBus()
    received: list[Event] = []

    async def handler(e: Event) -> None:
        received.append(e)

    bus.subscribe(EventType.NODE_START, handler)
    event = Event(type=EventType.NODE_START, node_id="step1")
    await bus.emit(event)

    assert len(received) == 1
    assert received[0].node_id == "step1"


@pytest.mark.asyncio
async def test_multiple_subscribers():
    """多个订阅者都收到事件"""
    bus = EventBus()
    count = 0

    async def h1(e: Event) -> None:
        nonlocal count
        count += 1

    async def h2(e: Event) -> None:
        nonlocal count
        count += 1

    bus.subscribe(EventType.NODE_END, h1)
    bus.subscribe(EventType.NODE_END, h2)
    await bus.emit(Event(type=EventType.NODE_END))

    assert count == 2


@pytest.mark.asyncio
async def test_wrong_type_not_notified():
    """事件类型不匹配的订阅者不被通知"""
    bus = EventBus()
    notified = False

    async def handler(e: Event) -> None:
        nonlocal notified
        notified = True

    bus.subscribe(EventType.NODE_START, handler)
    await bus.emit(Event(type=EventType.NODE_END))

    assert not notified