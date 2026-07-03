"""Event types — 事件系统数据类型."""

from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel


class EventType(str, Enum):
    """框架标准事件类型"""
    NODE_START = "node_start"
    NODE_END = "node_end"
    EDGE_TRAVERSE = "edge_traverse"
    ERROR = "error"
    STREAM_TOKEN = "stream_token"
    INTERRUPT = "interrupt"            # 危险操作暂停，等人审批
    USER_RESPONSE = "user_response"    # 用户点了允许/拒绝


class Event(BaseModel):
    """
    图执行过程中产生的事件

    Attributes:
        type: 事件类型
        node_id: 相关节点名
        state: 当前状态快照(可选）
        error: 错误消息(ERROR 事件)
        tool_name: 工具名 (INTERRUPT 事件)
        tool_arguments: 工具参数 (INTERRUPT 事件)
        risk_level: 风险等级 (INTERRUPT 事件)
    """
    type: EventType
    node_id: str | None = None
    state: dict[str, Any] | None = None
    error: str | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    risk_level: str | None = None

