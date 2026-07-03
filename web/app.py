"""Amor Agent Web 入口."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from web.routes import chat, agent, model, skill
from web.ws import websocket_endpoint

app = FastAPI(title="Amor Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(model.router, prefix="/api", tags=["model"])
app.include_router(skill.router, prefix="/api", tags=["skill"])

# WebSocket
app.websocket("/ws/{conversation_id}")(websocket_endpoint)

# 前端
app.mount("/", StaticFiles(directory="web/static", html=True), name="static")


@app.on_event("startup")
async def startup():
    """启动时: 1) 注册工具 2) 加载 Skill 3) 连接 MCP Server."""
    from harness.tool_registry import ToolRegistry
    from harness.skills.loader import discover_and_register
    from harness.mcp.client import connect_mcp_server

    # 工具
    registry = ToolRegistry()
    _register_builtin_tools(registry)
    _register_user_tools(registry)

    # MCP Server 连接（从环境变量读取配置）
    mcp_connections: list = []
    import os
    mcp_config = os.getenv("MCP_SERVERS", "")  # 格式: "npx:server1:/tmp,npx:server2"
    if mcp_config:
        for entry in mcp_config.split(","):
            parts = entry.strip().split(":")
            if len(parts) >= 1:
                conn = await connect_mcp_server(parts, registry)
                mcp_connections.append(conn)

    app.state.tool_registry = registry
    app.state.mcp_connections = mcp_connections

    # Skill（Prompt 注入，扫描 .md 文件）
    skills = discover_and_register()
    app.state.skills = skills


@app.on_event("shutdown")
async def shutdown():
    """关闭所有 MCP 连接."""
    for conn in getattr(app.state, "mcp_connections", []):
        await conn.close()


def _register_builtin_tools(registry):
    """注册内置工具."""
    from harness.skills.builtin.file_ops import ReadFileTool, WriteFileTool, ListFilesTool
    from harness.skills.builtin.shell import RunShellTool
    from harness.skills.builtin.search import WebSearchTool, RAGQueryTool
    from harness.skills.builtin.image_gen import GenerateImageTool
    from harness.skills.builtin.utils import GrepTool, EditFileTool, GetTimeTool, GlobTool, WebFetchTool

    for tool_cls in [ReadFileTool, WriteFileTool, ListFilesTool, RunShellTool,
                     WebSearchTool, RAGQueryTool, GenerateImageTool,
                     GrepTool, EditFileTool, GetTimeTool, GlobTool, WebFetchTool]:
        registry.register(tool_cls())


def _register_user_tools(registry):
    """扫描 skills/user/ 目录，注册用户自定义 Tool."""
    import importlib
    from pathlib import Path

    user_dir = Path("harness/skills/user")
    for py_file in user_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        module = importlib.import_module(f"harness.skills.user.{py_file.stem}")
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type)
                and hasattr(attr, "schema")
                and hasattr(attr, "execute")
                and attr.__name__ != "ToolProtocol"):
                registry.register(attr())