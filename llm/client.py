"""LiteLLM 封装 — 统一接口，所有 LLM 调用走这里."""

import litellm
from amor.protocols.llm import LLMProtocol, Message, Thought, ToolCall, TokenUsage
from amor.logging import get_logger

logger = get_logger(__name__)


class LiteLLMClient(LLMProtocol):
    """LiteLLM 适配器，实现 LLMProtocol.

    Usage:
        client = LiteLLMClient(model="gpt-4o", api_key="sk-xxx")
        thought = await client.chat(messages)

    切换模型只需改 model 参数：
        client.model = "gemini/gemini-2.0-flash"
        client.model = "deepseek/deepseek-chat"
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def chat(
        self, messages: list[Message], tools: list[dict] | None = None
    ) -> Thought:
        """发送消息，返回完整 Thought."""
        formatted = []
        for m in messages:
            msg = {"role": m.get("role", "user"), "content": m.get("content", "")}
            if m.get("tool_call_id"):
                msg["tool_call_id"] = m["tool_call_id"]
            if m.get("tool_calls"):
                msg["tool_calls"] = m["tool_calls"]
            if m.get("name"):
                msg["name"] = m["name"]
            formatted.append(msg)

        kwargs: dict = dict(
            model=self.model,
            messages=formatted,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        if tools:
            kwargs["tools"] = tools

        logger.info("llm_call", extra={"model": self.model, "msg_count": len(messages)})

        response = await litellm.acompletion(**kwargs)

        choice = response.choices[0]   # 回复列表
        usage = response.usage         # token 用量（可能 None）

        return Thought(
            content=choice.message.content or "",       # LLM 说的文本
            tool_calls=self._parse_tool_calls(choice.message.tool_calls),     # 工具调用（可能 None）
            usage=TokenUsage(
                prompt=usage.prompt_tokens if usage else 0,           # 输入 token
                completion=usage.completion_tokens if usage else 0,   # 输出 token
            ),
        )

    async def stream(self, messages: list[Message]):
        """流式返回 token."""
        formatted = []
        for m in messages:
            msg = {"role": m.get("role", "user"), "content": m.get("content", "")}
            if m.get("tool_call_id"):
                msg["tool_call_id"] = m["tool_call_id"]
            if m.get("tool_calls"):
                msg["tool_calls"] = m["tool_calls"]
            if m.get("name"):
                msg["name"] = m["name"]
            formatted.append(msg)

        response = await litellm.acompletion(
            model=self.model,
            messages=formatted,
            api_key=self.api_key,
            stream=True,
        )

        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    def _parse_tool_calls(self, raw_tool_calls) -> list[ToolCall] | None:
        """把 LiteLLM 返回的 tool_calls 转成 Amor 的 ToolCall."""
        if not raw_tool_calls:
            return None

        result = []
        for tc in raw_tool_calls:
            import json
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            result.append(ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=args,
            ))
        return result or None