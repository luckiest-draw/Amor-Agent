"""上下文窗口管理 — 对话过长时自动裁剪."""

from amor.protocols.llm import Message


def estimate_tokens(messages: list[Message]) -> int:
    """粗略估算 token 数（4 字符 ≈ 1 token）."""
    total = 0
    for m in messages:
        total += len(m.get("content", "")) // 4
    return total


def trim_messages(
    messages: list[Message],
    max_tokens: int = 16000,
    keep_system: bool = True,
    keep_last_n: int = 20,
) -> list[Message]:
    """裁剪消息到 token 上限。

    策略:
    1. System Prompt 完整保留
    2. 最近 keep_last_n 条消息强制保护（Agent 决策链不能断）
    3. 只裁中间的老消息
    """
    # 分离 system 和非 system
    system_msgs = [m for m in messages if m.get("role") == "system"] if keep_system else []
    other_msgs = [m for m in messages if m.get("role") != "system"]

    if len(other_msgs) <= keep_last_n:
        # 消息量未超保护阈值，不做裁剪
        return system_msgs + other_msgs

    # 保护最近 N 条，只裁剪前面的老消息
    protected = other_msgs[-keep_last_n:]
    trimmable = other_msgs[:-keep_last_n]

    # 从最旧的开始删
    while estimate_tokens(system_msgs + trimmable + protected) > max_tokens and trimmable:
        trimmable.pop(0)

    return system_msgs + trimmable + protected