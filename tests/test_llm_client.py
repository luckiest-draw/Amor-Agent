"""用 Mock 验证 LiteLLMClient 的 tool_calls 解析逻辑."""

import pytest
from llm.client import LiteLLMClient


def test_parse_tool_calls_empty():
    client = LiteLLMClient()
    assert client._parse_tool_calls(None) is None
    assert client._parse_tool_calls([]) is None


def test_lite_llm_client_init():
    client = LiteLLMClient(model="gpt-4o-mini")
    assert client.model == "gpt-4o-mini"
    assert client.temperature == 0.7