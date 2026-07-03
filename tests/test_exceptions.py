"""Tests for Amor exception hierarchy."""

from amor.exceptions import AmorError, NodeExecutionError, MaxStepExceededError


def test_basic():
    # 1.能创建异常
    e = AmorError("测试")
    assert str(e) == "测试"

    # 2.NodeExecutionError 带上下文
    original = RuntimeError("原始错误")
    ne = NodeExecutionError(node_id="test_node",step=1,cause=original)
    assert ne.node_id == "test_node"
    assert ne.step == 1
    assert ne.__cause__ is original

    # 3.MaxStepExceededError
    from amor.exceptions import MaxStepExceededError
    me = MaxStepExceededError(max_steps=100,current_steps=101)
    assert me.max_steps == 100