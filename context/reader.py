"""文件读取 — 按类型路由到最佳解析器.

路由规则:
  .pdf, .docx → LlamaParse Cloud API (云端 LLM 看图理解，不走传统解析)
  .xlsx/.csv   → pandas → HTML 表格 (结构化数据 100% 准确)
  .pptx        → MarkItDown (兜底)
  .html        → MarkItDown
  .png/.jpg    → GPT-4o / Gemini Vision (多模态直接看图描述)
  .md/.txt     → 直接读原文
  其他          → MarkItDown (兜底)

统一后处理: 所有 Markdown 表格 → HTML 表格 (LLM 对 HTML 结构理解力最强)
"""

import base64
from pathlib import Path
from markitdown import MarkItDown

_md = MarkItDown()

EXT_PARSER = {
    ".pdf": "llamaparse",
    ".docx": "llamaparse",
    ".xlsx": "pandas",
    ".xls": "pandas",
    ".csv": "pandas",
    ".pptx": "markitdown",
    ".html": "markitdown",
    ".md": "plain",
    ".txt": "plain",
    ".png": "vision",
    ".jpg": "vision",
    ".jpeg": "vision",
    ".webp": "vision",
    ".gif": "vision",
}


async def read_file(path: str | Path) -> str:
    """读任意文件，返回 Markdown 文本（含 HTML 表格）."""
    path = Path(path)
    if not path.exists():
        return f"[错误] 文件不存在: {path}"

    ext = path.suffix.lower()
    parser = EXT_PARSER.get(ext, "markitdown")

    try:
        text = await _dispatch(parser, path)
        # 统一后处理: Markdown 表格 → HTML 表格
        text = _convert_tables_to_html(text)
        return text
    except Exception as e:
        return f"[错误] 文件解析失败 ({parser}): {e}"


async def _dispatch(parser: str, path: Path) -> str:
    """路由到对应解析器."""
    match parser:
        case "llamaparse":
            from llama_parse import LlamaParse
            parser = LlamaParse(api_key=None, result_type="markdown", verbose=False)
            documents = await parser.aload_data(str(path))
            return "\n\n".join(d.text for d in documents)
        case "pandas":
            return _parse_pandas(path)
        case "markitdown":
            result = _md.convert(str(path))
            return result.text_content
        case "vision":
            return await _vision_describe(path)
        case "plain":
            return path.read_text(encoding="utf-8", errors="replace")
        case _:
            return _md.convert(str(path)).text_content


# ── 各解析器 ────────────────────────────────────

def _parse_pandas(path: Path) -> str:
    """Excel/CSV → 直接出 HTML 表格，不做中间 Markdown 转换."""
    import pandas as pd

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(str(path))
        return df.to_html(index=False) if not df.empty else "[空文件]"

    sheets = pd.read_excel(str(path), sheet_name=None)
    parts = []
    for sheet_name, df in sheets.items():
        if not df.empty:
            parts.append(f"## Sheet: {sheet_name}\n{df.to_html(index=False)}")
    return "\n\n".join(parts) if parts else "[空文件]"


async def _vision_describe(path: Path) -> str:
    """单独图片 → 多模态 LLM 直接看图描述.

    取到的是原始图片，不经任何压缩中间层。
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    image_b64 = base64.b64encode(path.read_bytes()).decode()

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "详细描述这张图片的内容。"
                        "如果是图表，列出所有具体数据。"
                        "如果是架构图/流程图，描述结构和关系。"
                        "如果是普通图片，描述画面内容。"
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/{path.suffix[1:]};base64,{image_b64}"},
                },
            ],
        }],
    )
    return response.choices[0].message.content or "[图片描述生成失败]"


# ── 表格后处理 ──────────────────────────────────

def _convert_tables_to_html(text: str) -> str:
    """Markdown 表格 → HTML 表格.

    LLM 对 HTML <table> 的结构推理能力
    远强于 Markdown |...| 表格语法。
    """
    import re

    def _md_to_html(md_table: str) -> str:
        lines = md_table.strip().split("\n")
        if len(lines) < 2:
            return md_table

        header = lines[0]
        data_lines = [l for l in lines[1:] if not re.match(r"^\|[\s\-:|]+\|$", l)]

        html = "<table>\n<thead>\n<tr>\n"
        for cell in header.split("|")[1:-1]:
            html += f"<th>{cell.strip()}</th>\n"
        html += "</tr>\n</thead>\n<tbody>\n"

        for line in data_lines:
            html += "<tr>\n"
            for cell in line.split("|")[1:-1]:
                html += f"<td>{cell.strip()}</td>\n"
            html += "</tr>\n"
        html += "</tbody>\n</table>"
        return html

    pattern = re.compile(
        r"(^\|.+\|$\n)+(^\|[\-\s:|]+\|$\n)?(^\|.+\|$\n)*", re.MULTILINE
    )
    return pattern.sub(lambda m: _md_to_html(m.group()), text)