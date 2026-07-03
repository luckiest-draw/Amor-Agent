"""图片生成技能."""

import os
from typing import Any
from amor.protocols.tool import ToolProtocol, ToolSchema


class GenerateImageTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(
            name="generate_image",
            description="用 AI 生成图片",
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "图片描述"},
                    "size": {"type": "string", "description": "尺寸，如 1024x1024"},
                },
                "required": ["prompt"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = await client.images.generate(
            model="dall-e-3",
            prompt=arguments["prompt"],
            size=arguments.get("size", "1024x1024"),
            n=1,
        )
        url = response.data[0].url
        return f"图片已生成: {url}"