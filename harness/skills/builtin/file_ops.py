"""文件操作技能."""

from typing import Any
from pathlib import Path
from amor.protocols.tool import ToolProtocol, ToolSchema


class ReadFileTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(
            name="read_file",
            description="读取文件内容",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "文件路径"}},
                "required": ["path"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        path = Path(arguments["path"])
        if not path.exists():
            return f"文件不存在: {path}"
        return path.read_text(encoding="utf-8", errors="replace")


class WriteFileTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(
            name="write_file",
            description="写入内容到文件（覆盖写入）",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "要写入的内容"},
                },
                "required": ["path", "content"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        path = Path(arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(arguments["content"], encoding="utf-8")
        return f"文件已写入: {path} ({len(arguments['content'])} 字符)"


class ListFilesTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(
            name="list_files",
            description="列出目录内容",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "目录路径，默认当前目录"}},
                "required": [],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        path = Path(arguments.get("path", "."))
        if not path.exists():
            return f"目录不存在: {path}"
        items = list(path.iterdir())
        return "\n".join(
            f"{'[DIR]' if i.is_dir() else '[FILE]'} {i.name}" for i in items
        )