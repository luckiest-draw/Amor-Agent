"""网页搜索 — Tavily Search API."""

import os
from tavily import TavilyClient

_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """搜索网页，返回结果列表."""
    try:
        response = _client.search(query, max_results=max_results)
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
            for r in response.get("results", [])
        ]
    except Exception as e:
        return [{"title": "搜索失败", "url": "", "content": str(e)}]