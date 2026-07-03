"""搜索技能 — 网页搜索 + RAG 查询."""

from typing import Any
from amor.protocols.tool import ToolProtocol, ToolSchema


class WebSearchTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(
            name="web_search",
            description="搜索互联网获取最新信息",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "max_results": {"type": "integer", "description": "最多返回几条"},
                },
                "required": ["query"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        from context.web_search import search_web
        results = await search_web(
            arguments["query"], arguments.get("max_results", 5)
        )
        return "\n\n".join(
            f"### {r['title']}\n{r['content']}\n{r['url']}" for r in results
        )


class RAGQueryTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(
            name="rag_query",
            description="从知识库中检索相关文档",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "查询内容"},
                    "top_k": {"type": "integer", "description": "返回几条"},
                },
                "required": ["query"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        from context.rag import query as rag_query
        results = await rag_query(arguments["query"], arguments.get("top_k", 5))
        return "\n\n".join(
            f"### [{r['source']}]\n{r['text']}" for r in results
        )