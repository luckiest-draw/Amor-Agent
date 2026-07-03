"""实用工具 — grep, 精准编辑, 时间."""

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from amor.protocols.tool import ToolProtocol, ToolSchema


class GrepTool(ToolProtocol):
    """搜索文件内容 — 返回匹配行及上下文."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="grep",
            description="在文件中搜索匹配的文本模式（支持正则），返回文件名、行号和匹配行",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "搜索的文本或正则表达式"},
                    "path": {"type": "string", "description": "搜索路径，目录或文件，默认当前目录"},
                    "glob": {"type": "string", "description": "文件名过滤，如 *.py"},
                },
                "required": ["pattern"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        pattern = arguments["pattern"]
        search_path = arguments.get("path", ".")
        glob_filter = arguments.get("glob", "*")

        try:
            result = subprocess.run(
                ["grep", "-rn", "-C", "1", "--include", glob_filter, pattern, search_path],
                capture_output=True, text=True, timeout=30,
            )
            output = result.stdout.strip()
            if not output:
                return f"未找到匹配 '{pattern}' 的内容"
            # 只取前 50 行
            lines = output.split("\n")
            if len(lines) > 50:
                return "\n".join(lines[:50]) + f"\n... (还有 {len(lines) - 50} 行)"
            return output
        except FileNotFoundError:
            # Windows 没有 grep，用 Python 实现
            return self._python_grep(pattern, search_path, glob_filter)
        except subprocess.TimeoutExpired:
            return f"搜索超时: {pattern}"

    def _python_grep(self, pattern: str, path: str, glob_filter: str) -> str:
        results = []
        base = Path(path)
        if base.is_file():
            files = [base]
        else:
            files = [p for p in base.rglob(glob_filter) if p.is_file()]
        try:
            regex = re.compile(pattern)
        except re.error:
            return f"无效的正则表达式: {pattern}"
        for f in files[:200]:  # 限制 200 个文件
            try:
                for i, line in enumerate(f.read_text(errors="replace").split("\n"), 1):
                    if regex.search(line):
                        results.append(f"{f}:{i}: {line.strip()[:200]}")
            except Exception:
                pass
        if not results:
            return f"未找到匹配 '{pattern}' 的内容"
        if len(results) > 50:
            return "\n".join(results[:50]) + f"\n... (还有 {len(results) - 50} 条)"
        return "\n".join(results)


class EditFileTool(ToolProtocol):
    """精准修改文件的特定行."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="edit_file",
            description="替换文件中的特定文本（精准编辑，不覆写整个文件）",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "old_text": {"type": "string", "description": "要替换的原文（必须精确匹配）"},
                    "new_text": {"type": "string", "description": "替换后的新文本"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        path = Path(arguments["path"])
        old_text = arguments["old_text"]
        new_text = arguments["new_text"]

        if not path.exists():
            return f"文件不存在: {path}"

        content = path.read_text(encoding="utf-8", errors="replace")

        if old_text not in content:
            return f"未找到要替换的文本。前 200 字符: {old_text[:200]}"

        if content.count(old_text) > 1:
            return f"匹配到 {content.count(old_text)} 处，请提供更精确的上下文。要替换的文本必须唯一。"

        new_content = content.replace(old_text, new_text, 1)
        path.write_text(new_content, encoding="utf-8")
        return f"文件已更新: {path}"


class GetTimeTool(ToolProtocol):
    """获取当前日期和时间."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="get_time",
            description="获取当前日期、时间、星期。用于需要实时时间信息的场景。",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        now = datetime.now()
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return (
            f"当前时间: {now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
            f"星期: {weekdays[now.weekday()]}\n"
            f"ISO: {now.isoformat()}"
        )


class GlobTool(ToolProtocol):
    """按文件名模式查找文件."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="glob",
            description="按文件名模式查找文件，如 **/*.py, src/*.ts。返回匹配的文件路径列表。",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "glob 模式，如 **/*.py"},
                    "path": {"type": "string", "description": "搜索根目录，默认当前目录"},
                },
                "required": ["pattern"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        pattern = arguments["pattern"]
        base = Path(arguments.get("path", "."))
        matches = sorted(base.glob(pattern))

        if not matches:
            return f"未找到匹配 '{pattern}' 的文件"

        result = []
        for p in matches[:100]:
            suffix = "/" if p.is_dir() else f" ({p.stat().st_size} B)"
            result.append(str(p) + suffix)

        if len(matches) > 100:
            result.append(f"... 还有 {len(matches) - 100} 个文件")

        return "\n".join(result)


class WebFetchTool(ToolProtocol):
    """抓取网页内容转 Markdown."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="webfetch",
            description="抓取指定 URL 的网页内容，转换为 Markdown 格式。用于阅读在线文档或文章。",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要抓取的网页 URL"},
                },
                "required": ["url"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        import httpx
        url = arguments["url"]

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers={"User-Agent": "Amor-Agent/1.0"})
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return f"请求失败: HTTP {e.response.status_code}"
        except httpx.TimeoutException:
            return f"请求超时: {url}"
        except Exception as e:
            return f"抓取失败: {e}"

        # HTML → 纯文本（简单版，不引入 BeautifulSoup）
        body = resp.text
        # 去掉 script/style 标签
        body = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.DOTALL | re.IGNORECASE)
        # 去掉 HTML 标签
        body = re.sub(r"<[^>]+>", " ", body)
        # 合并空白
        body = re.sub(r"\s+", " ", body).strip()

        # 限制长度
        if len(body) > 8000:
            body = body[:8000] + "\n...(内容已截断)"

        return body
